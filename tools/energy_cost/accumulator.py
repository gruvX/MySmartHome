"""Interval-cost accumulator — LOCAL reference implementation of the ADR.

Implements ``docs/architecture/ADR_ENERGY_COST_STORAGE.md`` §4 (SQLite / WAL
schema) as an off-box, transactional ledger that prices every 15-min interval at
the Nord Pool price *in force during that interval*::

    interval_cost = accepted_delta_kWh * price_of_that_interval

and accumulates the result forward so long-term totals survive the recorder's
~10-day purge cliff.

**This module writes ONLY to a local SQLite file.** It never calls Home
Assistant, never touches a device, never mutates raw evidence, and never touches
the production ``cost_month_*`` helpers. It is the Phase-1 "local ledger build"
of the ADR rollout and nothing here is deployed.

Design highlights (each maps to an ADR §6 guarantee — see tests/test_accumulator.py):

* **Idempotent** upsert keyed on ``(device, interval_start_utc, schema_version)``
  (ADR §6.1). Re-running an interval is a PRIMARY-KEY conflict, never a
  duplicate; rollups are ``SUM()`` over the set so a rerun cannot double-count.
* **Atomic** — every run is one ``BEGIN IMMEDIATE … COMMIT`` on a WAL DB
  (ADR §6.2). A crash mid-run rolls back; no partial interval set is visible.
* **File lock** — ``fcntl.flock(LOCK_EX | LOCK_NB)`` advisory lock guards the
  single writer (ADR §6.3); a second concurrent run exits early.
* **Confirmed intervals are immutable** — a later run that merely sees a changed
  *current* price for a past confirmed slot skips it (ADR §6.4). Only
  ``incomplete`` rows may be upgraded (when source data has since arrived).
* **Missing is never zero** — a missing price or unavailable reading yields a
  ``NULL`` accepted delta / cost and an ``excluded_delta`` audit row, never 0
  (ADR §4.4, invariant from ``model.py``).
* **Per-device physical plausibility** — reconnect/catch-up spikes (e.g. the EV
  +15 kWh jump) and counter resets are refused per
  ``docs/audit/meter_delta_rules.json`` and recorded in the append-only audit
  trail, never silently dropped.
* **Fixed monthly charge is NEVER smeared** onto a device or interval row
  (ADR §5). It lives in its own ``fixed_charge`` table and is added only at the
  whole-home period level.
* **Spot-only while the tariff is null** — with the all-null template tariff
  (``docs/audit/tariff_schema.json``) only ``spot_cost_eur`` is populated;
  margin / distribution / VAT stay ``NULL`` (never invented, never 0).
* **Versioned schema** with numbered migrations (ADR §7).
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional, Sequence

# Reuse the already-tested pure model for tariff math + DST-aware calendar bounds.
from . import model
from .model import (
    LOCAL_TZ,
    UTC,
    Tariff,
    SPOT_ONLY,
    day_bounds,
    last_month_bounds,
    month_bounds,
    this_month_bounds,
    today_bounds,
    yesterday_bounds,
)

SCHEMA_VERSION = 1
GRID = timedelta(minutes=15)
GRID_SECONDS = 900
GRID_TOL_SECONDS = 60  # width within 900 ± 60 s counts as on-grid

# Reasons recorded in excluded_delta.reason (ADR §4.4 enum).
REASON_ENERGY_UNAVAILABLE = "energy_unavailable"
REASON_PRICE_MISSING = "price_missing"
REASON_COUNTER_RESET = "counter_reset"
REASON_IMPLAUSIBLE_SPIKE = "implausible_spike"
REASON_GAP = "gap_in_readings"

STATUS_CONFIRMED = "confirmed"
STATUS_INCOMPLETE = "incomplete"
STATUS_EXCLUDED = "excluded"


# --------------------------------------------------------------------------- #
# Tariff wrapper: model.Tariff (per-kWh add-ons + VAT) plus a monthly fixed
# charge, which model.Tariff does not carry. Fixed charge is kept SEPARATE and
# is NEVER apportioned to a device/interval (ADR §5).
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class LedgerTariff:
    model_tariff: Tariff = SPOT_ONLY
    fixed_monthly_eur: Optional[float] = None
    source_note: str = "spot-only (tariff template all-null)"

    @property
    def spot_only(self) -> bool:
        """True when NO retail add-on and NO fixed charge is configured."""
        return self.model_tariff.spot_only and self.fixed_monthly_eur is None


SPOT_ONLY_LEDGER = LedgerTariff()


def load_meter_rules(path: str) -> dict[str, float]:
    """Return ``{device: max_interval_kwh}`` from meter_delta_rules.json."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out: dict[str, float] = {}
    for dev, spec in data.items():
        if dev.startswith("_"):
            continue
        if isinstance(spec, dict) and "max_interval_kwh" in spec:
            out[dev] = float(spec["max_interval_kwh"])
    return out


def load_tariff_from_schema(path: str) -> LedgerTariff:
    """Build a LedgerTariff from tariff_schema.json. All-null template => spot-only.

    Never invents a rate: any unset value stays ``None`` and the result is
    ``spot_only`` (ADR §5 / tariff_schema rules).
    """
    with open(path, "r", encoding="utf-8") as f:
        s = json.load(f)
    layers = s.get("layers", {})
    addons = layers.get("2_variable_addons", {})
    dn = addons.get("day_night", {})

    def _v(node: dict, key: str) -> Optional[float]:
        node = node.get(key) or {}
        v = node.get("value")
        return float(v) if v is not None else None

    vat_pct = _v(layers.get("3_vat", {}), "vat_percent")
    fixed = _v(layers.get("4_fixed_charges", {}), "fixed_monthly_eur")
    dn_enabled = dn.get("enabled")
    t = Tariff(
        supplier_margin_eur_per_kwh=_v(addons, "supplier_markup_eur_per_kwh"),
        distribution_eur_per_kwh=_v(addons, "distribution_eur_per_kwh"),
        transmission_eur_per_kwh=_v(addons, "transmission_eur_per_kwh"),
        excise_eur_per_kwh=_v(addons, "electricity_tax_eur_per_kwh"),
        distribution_day_eur_per_kwh=(_v(dn, "distribution_day_eur_per_kwh") if dn_enabled else None),
        distribution_night_eur_per_kwh=(_v(dn, "distribution_night_eur_per_kwh") if dn_enabled else None),
        night_start_hour=int(_v(dn, "night_start_hour") or 23),
        night_end_hour=int(_v(dn, "night_end_hour") or 7),
        vat_rate=(vat_pct / 100.0 if vat_pct is not None else None),
    )
    return LedgerTariff(model_tariff=t, fixed_monthly_eur=fixed,
                        source_note=f"tariff_schema.json (spot_only={s.get('spot_only')})")


# --------------------------------------------------------------------------- #
# Per-interval computation (pure; no DB)
# --------------------------------------------------------------------------- #
@dataclass
class IntervalComputation:
    device: str
    interval_start_utc: str          # ISO-8601 UTC
    interval_end_utc: str
    grid_seconds: int
    raw_delta_kwh: Optional[float]
    accepted_delta_kwh: Optional[float]
    reading_start_kwh: Optional[float]
    reading_end_kwh: Optional[float]
    price_eur_kwh: Optional[float]
    price_source: Optional[str]
    spot_cost_eur: Optional[float]
    supplier_margin_eur: Optional[float]
    distribution_var_eur: Optional[float]
    vat_eur: Optional[float]
    total_variable_eur: Optional[float]
    quality: str
    status: str
    reset_detected: int
    energy_complete: int
    exclude_reason: Optional[str] = None
    exclude_detail: Optional[str] = None
    source_hash: Optional[str] = None


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


def _hash_inputs(device: str, start_iso: str, r0, r1, price) -> str:
    payload = json.dumps([device, start_iso, r0, r1, price], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _distribution_and_margin(tariff: Tariff, interval_start_utc: datetime):
    """Split configured per-kWh add-ons into (margin_per_kwh, distribution_per_kwh).

    margin       = supplier_margin only.
    distribution = distribution (day/night aware) + transmission + excise + OIK.
    Returns (margin_or_None, distribution_or_None): None when NOTHING in that
    bucket is configured (so the column stays NULL, never 0).
    """
    margin = tariff.supplier_margin_eur_per_kwh

    dist_parts = []
    if tariff.distribution_day_eur_per_kwh is not None or tariff.distribution_night_eur_per_kwh is not None:
        local = interval_start_utc.astimezone(LOCAL_TZ)
        night = tariff._is_night(local)
        v = tariff.distribution_night_eur_per_kwh if night else tariff.distribution_day_eur_per_kwh
        if v is not None:
            dist_parts.append(v)
    elif tariff.distribution_eur_per_kwh is not None:
        dist_parts.append(tariff.distribution_eur_per_kwh)
    for f in ("transmission_eur_per_kwh", "excise_eur_per_kwh", "renewables_oik_eur_per_kwh"):
        v = getattr(tariff, f)
        if v is not None:
            dist_parts.append(v)
    distribution = sum(dist_parts) if dist_parts else None
    return margin, distribution


def compute_interval(
    device: str,
    start_utc: datetime,
    end_utc: datetime,
    reading_start: Optional[float],
    reading_end: Optional[float],
    price: Optional[float],
    *,
    rules: dict[str, float],
    tariff: LedgerTariff = SPOT_ONLY_LEDGER,
    price_source: str = "shadow_ledger",
) -> IntervalComputation:
    """Classify + price one (device, interval). Pure function.

    Precedence of exclusion:
      1. reading unavailable at either end  -> D / incomplete / energy_unavailable
      2. price missing                      -> E / incomplete / price_missing
      3. raw delta < 0 (counter reset)      -> C / excluded / counter_reset
      4. raw delta > per-device threshold   -> excluded / implausible_spike
      else -> confirmed (A, or B if off-grid width); costs computed.
    """
    start_iso, end_iso = _iso(start_utc), _iso(end_utc)
    width = int(round((end_utc - start_utc).total_seconds()))
    off_grid = abs(width - GRID_SECONDS) > GRID_TOL_SECONDS
    src_hash = _hash_inputs(device, start_iso, reading_start, reading_end, price)

    def _incomplete(quality, reason, detail, raw=None):
        return IntervalComputation(
            device=device, interval_start_utc=start_iso, interval_end_utc=end_iso,
            grid_seconds=width, raw_delta_kwh=raw, accepted_delta_kwh=None,
            reading_start_kwh=reading_start, reading_end_kwh=reading_end,
            price_eur_kwh=price, price_source=price_source,
            spot_cost_eur=None, supplier_margin_eur=None, distribution_var_eur=None,
            vat_eur=None, total_variable_eur=None,
            quality=quality, status=STATUS_INCOMPLETE, reset_detected=0,
            energy_complete=0, exclude_reason=reason, exclude_detail=detail,
            source_hash=src_hash,
        )

    def _excluded(quality, reason, detail, raw, reset=0):
        return IntervalComputation(
            device=device, interval_start_utc=start_iso, interval_end_utc=end_iso,
            grid_seconds=width, raw_delta_kwh=raw, accepted_delta_kwh=None,
            reading_start_kwh=reading_start, reading_end_kwh=reading_end,
            price_eur_kwh=price, price_source=price_source,
            spot_cost_eur=None, supplier_margin_eur=None, distribution_var_eur=None,
            vat_eur=None, total_variable_eur=None,
            quality=quality, status=STATUS_EXCLUDED, reset_detected=reset,
            energy_complete=1, exclude_reason=reason, exclude_detail=detail,
            source_hash=src_hash,
        )

    # 1. availability gate (never bank a gap as 0)
    if reading_start is None or reading_end is None:
        return _incomplete("D", REASON_ENERGY_UNAVAILABLE,
                           "reading unavailable at interval start/end")

    raw = float(reading_end) - float(reading_start)

    # 2. price gate
    if price is None:
        return _incomplete("E", REASON_PRICE_MISSING,
                           "Nord Pool price missing for interval", raw=raw)

    # 3. counter reset (negative delta): pre-reset consumption is unknown; refuse.
    if raw < 0:
        return _excluded("C", REASON_COUNTER_RESET,
                         f"counter dropped {raw:.4f} kWh (reset); pre-reset "
                         "consumption unknown, not banked", raw, reset=1)

    # 4. per-device physical plausibility (reconnect / catch-up jump)
    max_kwh = rules.get(device)
    if max_kwh is not None and raw > max_kwh:
        return _excluded("A", REASON_IMPLAUSIBLE_SPIKE,
                         f"delta {raw:.4f} kWh > device max {max_kwh:.4f} kWh "
                         "(reconnect/catch-up jump); mis-attributable to one "
                         "interval's price, not banked", raw)

    # ---- confirmed: bank it, price per component ----------------------------
    accepted = raw
    mt = tariff.model_tariff
    spot = accepted * float(price)  # may be negative on negative prices
    margin_pk, dist_pk = _distribution_and_margin(mt, start_utc)
    margin_eur = accepted * margin_pk if margin_pk is not None else None
    dist_eur = accepted * dist_pk if dist_pk is not None else None
    subtotal = spot + (margin_eur or 0.0) + (dist_eur or 0.0)
    vat_eur = subtotal * mt.vat_rate if mt.vat_rate is not None else None
    total_variable = subtotal + (vat_eur or 0.0)
    quality = "B" if off_grid else "A"
    return IntervalComputation(
        device=device, interval_start_utc=start_iso, interval_end_utc=end_iso,
        grid_seconds=width, raw_delta_kwh=raw, accepted_delta_kwh=accepted,
        reading_start_kwh=reading_start, reading_end_kwh=reading_end,
        price_eur_kwh=price, price_source=price_source,
        spot_cost_eur=spot, supplier_margin_eur=margin_eur,
        distribution_var_eur=dist_eur, vat_eur=vat_eur,
        total_variable_eur=total_variable,
        quality=quality, status=STATUS_CONFIRMED, reset_detected=0,
        energy_complete=1, exclude_reason=None, exclude_detail=None,
        source_hash=src_hash,
    )


# --------------------------------------------------------------------------- #
# Shadow-ledger parsing (frozen JSONL evidence -> per-interval computations)
# --------------------------------------------------------------------------- #
@dataclass
class Snapshot:
    ts: datetime
    price: Optional[float]
    energy: dict[str, Optional[float]]  # device -> kWh (None when unavailable)


def load_shadow_snapshots(path: str) -> list[Snapshot]:
    """Parse the shadow collector JSONL (READ-ONLY). Never mutates the file."""
    snaps: list[Snapshot] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            ts = datetime.fromisoformat(d["ts"]).astimezone(UTC)
            cur = (d.get("price") or {}).get("current") or {}
            price = cur.get("v") if cur.get("avail") else None
            energy: dict[str, Optional[float]] = {}
            for dev, slot in (d.get("energy_kwh") or {}).items():
                energy[dev] = slot.get("v") if slot.get("avail") else None
            snaps.append(Snapshot(ts=ts, price=price, energy=energy))
    snaps.sort(key=lambda s: s.ts)
    return snaps


def snapshots_to_intervals(
    snaps: Sequence[Snapshot],
    rules: dict[str, float],
    tariff: LedgerTariff = SPOT_ONLY_LEDGER,
    devices: Optional[Sequence[str]] = None,
) -> list[IntervalComputation]:
    """Consecutive snapshots -> one IntervalComputation per (device, interval).

    Each interval is [snap[i].ts, snap[i+1].ts); the price in force is the
    ``current`` price at snap[i]. Off-grid widths are tolerated (quality B).
    """
    if devices is None:
        seen: list[str] = []
        for s in snaps:
            for d in s.energy:
                if d not in seen:
                    seen.append(d)
        devices = seen
    out: list[IntervalComputation] = []
    for i in range(len(snaps) - 1):
        a, b = snaps[i], snaps[i + 1]
        for dev in devices:
            out.append(
                compute_interval(
                    dev, a.ts, b.ts,
                    a.energy.get(dev), b.energy.get(dev), a.price,
                    rules=rules, tariff=tariff, price_source="shadow_ledger",
                )
            )
    return out


# --------------------------------------------------------------------------- #
# Schema / migrations
# --------------------------------------------------------------------------- #
_DDL_V1 = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL, description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tariff (
    tariff_id INTEGER PRIMARY KEY AUTOINCREMENT,
    valid_from_utc TEXT NOT NULL, valid_to_utc TEXT,
    supplier_margin_eur_kwh REAL, distribution_day_eur_kwh REAL,
    distribution_night_eur_kwh REAL, night_start_hour INTEGER DEFAULT 23,
    night_end_hour INTEGER DEFAULT 7, excise_eur_kwh REAL, renewables_oik_eur_kwh REAL,
    vat_rate REAL, fixed_monthly_eur REAL, source_note TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS interval_cost (
    schema_version INTEGER NOT NULL DEFAULT 1,
    device TEXT NOT NULL,
    interval_start_utc TEXT NOT NULL, interval_end_utc TEXT NOT NULL,
    grid_seconds INTEGER NOT NULL,
    raw_delta_kwh REAL, accepted_delta_kwh REAL,
    reading_start_kwh REAL, reading_end_kwh REAL,
    price_eur_kwh REAL, price_source TEXT, price_locked_at TEXT,
    spot_cost_eur REAL, supplier_margin_eur REAL, distribution_var_eur REAL,
    vat_eur REAL, total_variable_eur REAL,
    tariff_id INTEGER REFERENCES tariff(tariff_id),
    quality TEXT NOT NULL, status TEXT NOT NULL,
    reset_detected INTEGER NOT NULL DEFAULT 0, energy_complete INTEGER NOT NULL DEFAULT 1,
    computed_at TEXT NOT NULL, computed_run_id TEXT NOT NULL, source_hash TEXT,
    PRIMARY KEY (device, interval_start_utc, schema_version)
);
CREATE INDEX IF NOT EXISTS ix_ic_start  ON interval_cost(interval_start_utc);
CREATE INDEX IF NOT EXISTS ix_ic_dev_st ON interval_cost(device, interval_start_utc);
CREATE INDEX IF NOT EXISTS ix_ic_status ON interval_cost(status);
CREATE TABLE IF NOT EXISTS excluded_delta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device TEXT NOT NULL, interval_start_utc TEXT NOT NULL,
    raw_delta_kwh REAL, reason TEXT NOT NULL, detail TEXT, quality TEXT,
    computed_at TEXT NOT NULL, computed_run_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_excl_start ON excluded_delta(interval_start_utc);
CREATE TABLE IF NOT EXISTS fixed_charge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_kind TEXT NOT NULL, period_key TEXT NOT NULL, amount_eur REAL NOT NULL,
    tariff_id INTEGER REFERENCES tariff(tariff_id), note TEXT, computed_at TEXT NOT NULL,
    UNIQUE(period_kind, period_key)
);
CREATE TABLE IF NOT EXISTS accumulator_run (
    run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
    window_start_utc TEXT NOT NULL, window_end_utc TEXT NOT NULL,
    n_confirmed INTEGER DEFAULT 0, n_incomplete INTEGER DEFAULT 0,
    n_excluded INTEGER DEFAULT 0, n_skipped_locked INTEGER DEFAULT 0,
    source_low_water TEXT, status TEXT NOT NULL, note TEXT
);
"""

# (version, description, ddl). Version 1 is the base schema. Additional
# migrations may be supplied at construction time for testing / evolution.
BASE_MIGRATIONS: list[tuple[int, str, str]] = [
    (1, "initial schema (ADR §4)", _DDL_V1),
]


class LockHeld(RuntimeError):
    """Raised when the advisory writer lock is already held by another run."""


@dataclass
class RunResult:
    run_id: str
    n_confirmed: int = 0
    n_incomplete: int = 0
    n_excluded: int = 0
    n_skipped_locked: int = 0
    status: str = "ok"


# --------------------------------------------------------------------------- #
# The accumulator
# --------------------------------------------------------------------------- #
class Accumulator:
    def __init__(
        self,
        db_path: str,
        *,
        schema_version: int = SCHEMA_VERSION,
        rules: Optional[dict[str, float]] = None,
        tariff: LedgerTariff = SPOT_ONLY_LEDGER,
        lock_path: Optional[str] = None,
        extra_migrations: Optional[Sequence[tuple[int, str, str]]] = None,
    ) -> None:
        self.db_path = db_path
        self.schema_version = schema_version
        self.rules = rules or {}
        self.tariff = tariff
        self.lock_path = lock_path or (db_path + ".lock")
        self.migrations = list(BASE_MIGRATIONS)
        if extra_migrations:
            self.migrations.extend(extra_migrations)
        self.migrations.sort(key=lambda m: m[0])
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._tariff_id: Optional[int] = None
        self.migrate()

    # -- connection ------------------------------------------------------- #
    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    # -- advisory single-writer lock (ADR §6.3) --------------------------- #
    @contextmanager
    def _writer_lock(self):
        fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o640)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as e:
                raise LockHeld("another accumulator run holds the writer lock") from e
            yield
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    # -- migrations (ADR §7) ---------------------------------------------- #
    def _applied_versions(self, conn: sqlite3.Connection) -> set[int]:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version "
            "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL, description TEXT NOT NULL);"
        )
        return {r["version"] for r in conn.execute("SELECT version FROM schema_version")}

    def migrate(self, target: Optional[int] = None) -> None:
        conn = self.connect()
        try:
            applied = self._applied_versions(conn)
            for ver, desc, ddl in self.migrations:
                if target is not None and ver > target:
                    break
                if ver in applied:
                    continue
                # executescript() issues its own implicit COMMIT, so it cannot be
                # nested inside a manual BEGIN/COMMIT. The DDL is all
                # ``IF NOT EXISTS`` / additive, so re-applying is harmless; the
                # schema_version row is the idempotency guard.
                conn.executescript(ddl)
                conn.execute(
                    "INSERT OR IGNORE INTO schema_version(version, applied_at, description) "
                    "VALUES (?,?,?)",
                    (ver, datetime.now(UTC).isoformat(), desc),
                )
        finally:
            conn.close()

    def schema_versions(self) -> list[int]:
        conn = self.connect()
        try:
            return [r["version"] for r in
                    conn.execute("SELECT version FROM schema_version ORDER BY version")]
        finally:
            conn.close()

    # -- tariff row (by reference; ADR §4.2) ------------------------------ #
    def _ensure_tariff(self, conn: sqlite3.Connection) -> int:
        mt = self.tariff.model_tariff
        row = conn.execute(
            "SELECT tariff_id FROM tariff WHERE source_note=? ORDER BY tariff_id DESC LIMIT 1",
            (self.tariff.source_note,),
        ).fetchone()
        if row:
            return row["tariff_id"]
        cur = conn.execute(
            "INSERT INTO tariff(valid_from_utc, valid_to_utc, supplier_margin_eur_kwh, "
            "distribution_day_eur_kwh, distribution_night_eur_kwh, night_start_hour, "
            "night_end_hour, excise_eur_kwh, renewables_oik_eur_kwh, vat_rate, "
            "fixed_monthly_eur, source_note, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                datetime.now(UTC).isoformat(), None,
                mt.supplier_margin_eur_per_kwh, mt.distribution_day_eur_per_kwh,
                mt.distribution_night_eur_per_kwh, mt.night_start_hour, mt.night_end_hour,
                mt.excise_eur_per_kwh, mt.renewables_oik_eur_per_kwh, mt.vat_rate,
                self.tariff.fixed_monthly_eur, self.tariff.source_note,
                datetime.now(UTC).isoformat(),
            ),
        )
        return cur.lastrowid

    # -- main write path -------------------------------------------------- #
    def accrue(
        self,
        intervals: Sequence[IntervalComputation],
        *,
        run_id: Optional[str] = None,
        fault_after: Optional[int] = None,
    ) -> RunResult:
        """Idempotently upsert a batch of interval computations in ONE atomic
        transaction under the advisory lock.

        ``fault_after``: test-only hook — raise mid-transaction after N rows to
        prove the whole run rolls back (ADR §6.2). Never used in production.
        """
        run_id = run_id or str(uuid.uuid4())
        res = RunResult(run_id=run_id)
        starts = [i.interval_start_utc for i in intervals]
        w_start = min(starts) if starts else datetime.now(UTC).isoformat()
        w_end = max(i.interval_end_utc for i in intervals) if intervals else w_start
        now = datetime.now(UTC).isoformat()

        with self._writer_lock():
            conn = self.connect()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                tariff_id = self._ensure_tariff(conn)
                conn.execute(
                    "INSERT OR REPLACE INTO accumulator_run"
                    "(run_id, started_at, window_start_utc, window_end_utc, status) "
                    "VALUES (?,?,?,?,?)",
                    (run_id, now, w_start, w_end, "running"),
                )
                months_touched: set[str] = set()
                for n, iv in enumerate(intervals):
                    if fault_after is not None and n >= fault_after:
                        raise RuntimeError("injected fault (test): mid-transaction crash")
                    self._upsert_interval(conn, iv, tariff_id, run_id, now, res)
                    if iv.status == STATUS_CONFIRMED:
                        local = datetime.fromisoformat(iv.interval_start_utc).astimezone(LOCAL_TZ)
                        months_touched.add(f"{local.year:04d}-{local.month:02d}")
                # Fixed monthly charge: one row per touched month (ADR §5) —
                # NEVER written into an interval_cost row.
                if self.tariff.fixed_monthly_eur is not None:
                    for mkey in sorted(months_touched):
                        conn.execute(
                            "INSERT OR IGNORE INTO fixed_charge"
                            "(period_kind, period_key, amount_eur, tariff_id, note, computed_at) "
                            "VALUES ('month',?,?,?,?,?)",
                            (mkey, self.tariff.fixed_monthly_eur, tariff_id,
                             "standing charge (not smeared onto devices)", now),
                        )
                conn.execute(
                    "UPDATE accumulator_run SET finished_at=?, n_confirmed=?, n_incomplete=?, "
                    "n_excluded=?, n_skipped_locked=?, status=? WHERE run_id=?",
                    (datetime.now(UTC).isoformat(), res.n_confirmed, res.n_incomplete,
                     res.n_excluded, res.n_skipped_locked, "ok", run_id),
                )
                conn.execute("COMMIT;")
            except Exception:
                conn.execute("ROLLBACK;")
                raise
            finally:
                # Bound the WAL file after a successful/attempted run.
                try:
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                except Exception:
                    pass
                conn.close()
        return res

    def _upsert_interval(self, conn, iv: IntervalComputation, tariff_id, run_id, now, res):
        existing = conn.execute(
            "SELECT status FROM interval_cost WHERE device=? AND interval_start_utc=? "
            "AND schema_version=?",
            (iv.device, iv.interval_start_utc, self.schema_version),
        ).fetchone()

        if existing is not None:
            st = existing["status"]
            # Confirmed + excluded rows are IMMUTABLE: never recompute a settled
            # past interval, even if the current price changed (ADR §6.4 / §6.1).
            if st in (STATUS_CONFIRMED, STATUS_EXCLUDED):
                res.n_skipped_locked += 1
                return
            # Existing incomplete: may be upgraded now that data arrived.
            if st == STATUS_INCOMPLETE:
                if iv.status == STATUS_INCOMPLETE:
                    res.n_incomplete += 1  # still incomplete; leave row as-is
                    return
                conn.execute(
                    "DELETE FROM interval_cost WHERE device=? AND interval_start_utc=? "
                    "AND schema_version=?",
                    (iv.device, iv.interval_start_utc, self.schema_version),
                )
                # append a resolving audit row (original exclusion never deleted)
                conn.execute(
                    "INSERT INTO excluded_delta(device, interval_start_utc, raw_delta_kwh, "
                    "reason, detail, quality, computed_at, computed_run_id) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (iv.device, iv.interval_start_utc, iv.raw_delta_kwh, "resolved",
                     f"incomplete upgraded to {iv.status}", iv.quality, now, run_id),
                )

        self._insert_interval(conn, iv, tariff_id, run_id, now)
        if iv.status == STATUS_CONFIRMED:
            res.n_confirmed += 1
        elif iv.status == STATUS_INCOMPLETE:
            res.n_incomplete += 1
            self._insert_excluded(conn, iv, run_id, now)
        elif iv.status == STATUS_EXCLUDED:
            res.n_excluded += 1
            self._insert_excluded(conn, iv, run_id, now)

    def _insert_interval(self, conn, iv, tariff_id, run_id, now):
        price_locked = now if iv.price_eur_kwh is not None else None
        conn.execute(
            "INSERT INTO interval_cost("
            "schema_version, device, interval_start_utc, interval_end_utc, grid_seconds, "
            "raw_delta_kwh, accepted_delta_kwh, reading_start_kwh, reading_end_kwh, "
            "price_eur_kwh, price_source, price_locked_at, "
            "spot_cost_eur, supplier_margin_eur, distribution_var_eur, vat_eur, total_variable_eur, "
            "tariff_id, quality, status, reset_detected, energy_complete, "
            "computed_at, computed_run_id, source_hash) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                self.schema_version, iv.device, iv.interval_start_utc, iv.interval_end_utc,
                iv.grid_seconds, iv.raw_delta_kwh, iv.accepted_delta_kwh,
                iv.reading_start_kwh, iv.reading_end_kwh, iv.price_eur_kwh, iv.price_source,
                price_locked, iv.spot_cost_eur, iv.supplier_margin_eur, iv.distribution_var_eur,
                iv.vat_eur, iv.total_variable_eur, tariff_id, iv.quality, iv.status,
                iv.reset_detected, iv.energy_complete, now, run_id, iv.source_hash,
            ),
        )

    def _insert_excluded(self, conn, iv, run_id, now):
        conn.execute(
            "INSERT INTO excluded_delta(device, interval_start_utc, raw_delta_kwh, reason, "
            "detail, quality, computed_at, computed_run_id) VALUES (?,?,?,?,?,?,?,?)",
            (iv.device, iv.interval_start_utc, iv.raw_delta_kwh, iv.exclude_reason,
             iv.exclude_detail, iv.quality, now, run_id),
        )

    # convenience: parse frozen ledger and accrue in one call
    def accrue_shadow_ledger(self, path: str, **kw) -> RunResult:
        snaps = load_shadow_snapshots(path)
        ivs = snapshots_to_intervals(snaps, self.rules, self.tariff)
        return self.accrue(ivs, **kw)

    # ------------------------------------------------------------------ #
    # Queries (ADR §10) — all bounds are UTC ISO strings
    # ------------------------------------------------------------------ #
    def _period_variable(self, conn, start_iso, end_iso, status=STATUS_CONFIRMED,
                         device=None) -> Optional[float]:
        sql = ("SELECT SUM(total_variable_eur) AS s FROM interval_cost "
               "WHERE status=? AND interval_start_utc>=? AND interval_start_utc<? "
               "AND schema_version=?")
        args = [status, start_iso, end_iso, self.schema_version]
        if device is not None:
            sql += " AND device=?"
            args.append(device)
        r = conn.execute(sql, args).fetchone()
        return r["s"]

    def period_cost(self, start: datetime, end: datetime, *, status=STATUS_CONFIRMED,
                    device: Optional[str] = None) -> Optional[float]:
        """Summed variable € over [start,end) for a status (confirmed by default).

        Returns ``None`` when NO usable row exists (never fabricates 0).
        """
        conn = self.connect()
        try:
            return self._period_variable(conn, _iso(start), _iso(end), status, device)
        finally:
            conn.close()

    def per_device(self, start: datetime, end: datetime, *,
                   status=STATUS_CONFIRMED) -> dict[str, float]:
        conn = self.connect()
        try:
            rows = conn.execute(
                "SELECT device, ROUND(SUM(total_variable_eur),6) AS eur FROM interval_cost "
                "WHERE status=? AND interval_start_utc>=? AND interval_start_utc<? "
                "AND schema_version=? GROUP BY device",
                (status, _iso(start), _iso(end), self.schema_version),
            ).fetchall()
            return {r["device"]: r["eur"] for r in rows if r["eur"] is not None}
        finally:
            conn.close()

    def today(self, now=None, **kw): return self.period_cost(*today_bounds(now), **kw)
    def yesterday(self, now=None, **kw): return self.period_cost(*yesterday_bounds(now), **kw)
    def this_month(self, now=None, **kw): return self.period_cost(*this_month_bounds(now), **kw)
    def last_month(self, now=None, **kw): return self.period_cost(*last_month_bounds(now), **kw)

    def components(self, start: datetime, end: datetime) -> dict[str, Optional[float]]:
        """Confirmed per-component breakdown for a period (each None if all-null)."""
        conn = self.connect()
        try:
            r = conn.execute(
                "SELECT SUM(spot_cost_eur) spot, SUM(supplier_margin_eur) margin, "
                "SUM(distribution_var_eur) dist, SUM(vat_eur) vat, "
                "SUM(total_variable_eur) total, SUM(accepted_delta_kwh) kwh "
                "FROM interval_cost WHERE status='confirmed' AND interval_start_utc>=? "
                "AND interval_start_utc<? AND schema_version=?",
                (_iso(start), _iso(end), self.schema_version),
            ).fetchone()
            return {"spot": r["spot"], "margin": r["margin"], "distribution": r["dist"],
                    "vat": r["vat"], "total_variable": r["total"], "kwh": r["kwh"]}
        finally:
            conn.close()

    def fixed_charge(self, period_key: str, period_kind: str = "month") -> Optional[float]:
        conn = self.connect()
        try:
            r = conn.execute(
                "SELECT amount_eur FROM fixed_charge WHERE period_kind=? AND period_key=?",
                (period_kind, period_key),
            ).fetchone()
            return r["amount_eur"] if r else None
        finally:
            conn.close()

    def month_full(self, now=None) -> dict:
        """Whole-home month cost = confirmed variable + fixed (fixed added ONCE)."""
        start, end = this_month_bounds(now)
        local = start.astimezone(LOCAL_TZ)
        mkey = f"{local.year:04d}-{local.month:02d}"
        variable = self.period_cost(start, end)  # None if nothing usable
        fixed = self.fixed_charge(mkey)
        full = None
        if variable is not None or fixed is not None:
            full = (variable or 0.0) + (fixed or 0.0)
        return {"variable": variable, "fixed": fixed, "full": full, "period_key": mkey,
                "spot_only": self.tariff.spot_only}

    def coverage(self, start: datetime, end: datetime, *,
                 device: Optional[str] = None,
                 expected: Optional[int] = None) -> dict:
        """Coverage over [start,end): confirmed vs recorded, plus calendar-expected.

        ``coverage_pct`` is the ADR §10 recipe: confirmed ÷ recorded rows.
        ``expected`` is the DST-aware count of 15-min slots the LOCAL calendar
        period spans (``(end-start)/15min``), times the number of devices when no
        single ``device`` is given — computed, never hardcoded.
        """
        conn = self.connect()
        try:
            slots = int(round((end - start).total_seconds() / GRID.total_seconds()))
            base_where = ("interval_start_utc>=? AND interval_start_utc<? AND schema_version=?")
            args: list = [_iso(start), _iso(end), self.schema_version]
            if device is not None:
                base_where += " AND device=?"
                args.append(device)
                n_devices = 1
            else:
                dr = conn.execute(
                    "SELECT COUNT(DISTINCT device) d FROM interval_cost WHERE "
                    + base_where, args).fetchone()
                n_devices = dr["d"] or 1
            if expected is None:
                expected = slots * n_devices
            r = conn.execute(
                "SELECT COUNT(*) n, SUM(status='confirmed') n_conf, "
                "SUM(status='incomplete') n_inc, SUM(status='excluded') n_exc "
                "FROM interval_cost WHERE " + base_where, args).fetchone()
            n = r["n"] or 0
            n_conf = r["n_conf"] or 0
            recorded_pct = (100.0 * n_conf / n) if n else 0.0
            expected_pct = (100.0 * n_conf / expected) if expected else 0.0
            return {"recorded": n, "confirmed": n_conf, "incomplete": r["n_inc"] or 0,
                    "excluded": r["n_exc"] or 0, "expected": expected, "slots": slots,
                    "n_devices": n_devices,
                    "coverage_pct": round(recorded_pct, 4),
                    "expected_coverage_pct": round(expected_pct, 4)}
        finally:
            conn.close()

    def excluded_audit(self, start: datetime, end: datetime) -> list[dict]:
        conn = self.connect()
        try:
            rows = conn.execute(
                "SELECT device, interval_start_utc, raw_delta_kwh, reason, detail, quality "
                "FROM excluded_delta WHERE interval_start_utc>=? AND interval_start_utc<? "
                "ORDER BY interval_start_utc",
                (_iso(start), _iso(end)),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def high_water_mark(self, device: Optional[str] = None) -> Optional[str]:
        """Newest CONFIRMED ``interval_start_utc`` — the restart-recovery anchor
        (ADR §6.5). A next run recomputes forward from here; earlier confirmed
        intervals are skipped as immutable. ``None`` when nothing is confirmed."""
        conn = self.connect()
        try:
            sql = ("SELECT MAX(interval_start_utc) m FROM interval_cost "
                   "WHERE status='confirmed' AND schema_version=?")
            args: list = [self.schema_version]
            if device is not None:
                sql += " AND device=?"
                args.append(device)
            r = conn.execute(sql, args).fetchone()
            return r["m"]
        finally:
            conn.close()

    def run_log(self) -> list[dict]:
        conn = self.connect()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM accumulator_run ORDER BY started_at")]
        finally:
            conn.close()


# --------------------------------------------------------------------------- #
# UI-facing formatting (null / stale / excluded / spot-only)
# --------------------------------------------------------------------------- #
NO_DATA = "—"                      # em dash: value genuinely unknown (never "0.00")
SPOT_LABEL_RU = "Стоимость Nord Pool"   # spot-only label (never «Итоговый счёт»)
FULL_LABEL_RU = "Итоговый счёт"


def format_eur(value: Optional[float], *, dp: int = 2) -> str:
    """Format a EUR figure for the UI. ``None`` -> em dash, NEVER 0."""
    if value is None:
        return NO_DATA
    return f"{value:.{dp}f} €"


def format_status_badge(status: str) -> str:
    return {
        STATUS_CONFIRMED: "✓ подтверждено",
        STATUS_INCOMPLETE: "⚠ неполные данные",
        STATUS_EXCLUDED: "⛔ исключено",
    }.get(status, status)


def cost_label(spot_only: bool) -> str:
    """UI label for a headline cost figure."""
    return SPOT_LABEL_RU if spot_only else FULL_LABEL_RU


def format_coverage(cov: dict) -> str:
    return f"{cov['confirmed']}/{cov['expected']} ({cov['coverage_pct']:.1f}%)"


__all__ = [
    "SCHEMA_VERSION", "Accumulator", "LedgerTariff", "SPOT_ONLY_LEDGER",
    "IntervalComputation", "Snapshot", "RunResult", "LockHeld",
    "compute_interval", "load_shadow_snapshots", "snapshots_to_intervals",
    "load_meter_rules", "load_tariff_from_schema",
    "STATUS_CONFIRMED", "STATUS_INCOMPLETE", "STATUS_EXCLUDED",
    "REASON_ENERGY_UNAVAILABLE", "REASON_PRICE_MISSING", "REASON_COUNTER_RESET",
    "REASON_IMPLAUSIBLE_SPIKE", "REASON_GAP",
    "format_eur", "format_status_badge", "cost_label", "format_coverage",
    "NO_DATA", "SPOT_LABEL_RU", "FULL_LABEL_RU",
]
