"""Tests for the interval-cost accumulator (tools/energy_cost/accumulator.py).

Proves the ADR_ENERGY_COST_STORAGE.md integrity guarantees against the LOCAL
SQLite reference implementation. Every test is hermetic: it writes only to a
pytest ``tmp_path`` SQLite file, reads the frozen evidence read-only, and NEVER
touches Home Assistant, a device, or the production cost_month_* helpers. The
autouse network guard in conftest.py is active for all of them.

Coverage map (test -> ADR guarantee):
  * idempotent rerun ............... ADR §6.1
  * atomic / interrupted write ..... ADR §6.2 (fault_after -> rollback + WAL recovery)
  * concurrent writer / flock ...... ADR §6.3
  * confirmed price immutable ...... ADR §6.4 (duplicate interval, changed price)
  * missing never zero ............. ADR §4.4 (unavailable, missing price, gap)
  * per-device plausibility ........ meter_delta_rules.json (spike, reset)
  * excluded-delta audit ........... ADR §4.4 append-only trail
  * fixed charge not smeared ....... ADR §5
  * spot-only while tariff null .... ADR §5 / tariff_schema.json
  * schema migration ............... ADR §7
  * coverage / DST calendar ........ ADR §10 (bounds from model, not hardcoded)
"""
from __future__ import annotations

import multiprocessing
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.energy_cost import model  # noqa: E402
from tools.energy_cost.accumulator import (  # noqa: E402
    Accumulator,
    IntervalComputation,
    LedgerTariff,
    LockHeld,
    SPOT_ONLY_LEDGER,
    STATUS_CONFIRMED,
    STATUS_EXCLUDED,
    STATUS_INCOMPLETE,
    REASON_COUNTER_RESET,
    REASON_ENERGY_UNAVAILABLE,
    REASON_IMPLAUSIBLE_SPIKE,
    REASON_PRICE_MISSING,
    compute_interval,
    cost_label,
    format_coverage,
    format_eur,
    format_status_badge,
    load_meter_rules,
    load_shadow_snapshots,
    load_tariff_from_schema,
    snapshots_to_intervals,
    NO_DATA,
    SPOT_LABEL_RU,
)
from tools.energy_cost.model import LOCAL_TZ, UTC, Tariff  # noqa: E402

pytestmark = pytest.mark.unit

Q = timedelta(minutes=15)
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_JSON = os.path.join(REPO, "docs", "audit", "meter_delta_rules.json")
TARIFF_JSON = os.path.join(REPO, "docs", "audit", "tariff_schema.json")
FROZEN = os.path.join(REPO, "docs", "audit", "shadow_evidence",
                      "shadow_snapshots.frozen.jsonl")


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
@pytest.fixture
def rules() -> dict:
    return load_meter_rules(RULES_JSON)


@pytest.fixture
def acc(tmp_path, rules) -> Accumulator:
    return Accumulator(str(tmp_path / "cost_ledger.db"), rules=rules,
                       tariff=SPOT_ONLY_LEDGER)


def _cells(start: datetime, end: datetime):
    return model.build_grid(start, end, Q)


def synth(device, cells, delta, price, rules, tariff=SPOT_ONLY_LEDGER, base=0.0):
    """Confirmed-style intervals: constant per-cell ``delta`` from a rising counter."""
    ivs, r = [], base
    for (s, e) in cells:
        r0, r1 = r, r + delta
        r = r1
        ivs.append(compute_interval(device, s, e, r0, r1, price, rules=rules, tariff=tariff))
    return ivs


# --------------------------------------------------------------------------- #
# 1. Normal 96-interval day
# --------------------------------------------------------------------------- #
def test_normal_day_has_96_intervals(acc, rules):
    start, end = model.day_bounds(datetime(2026, 7, 15, 12, tzinfo=LOCAL_TZ))
    cells = _cells(start, end)
    assert len(cells) == 96
    acc.accrue(synth("boiler_ten", cells, 0.1, 0.10, rules))
    total = acc.period_cost(start, end)
    assert abs(total - 96 * 0.1 * 0.10) < 1e-9   # 0.96 EUR
    cov = acc.coverage(start, end, device="boiler_ten")
    assert cov == pytest.approx(cov)  # smoke
    assert cov["confirmed"] == 96 and cov["expected"] == 96
    assert cov["coverage_pct"] == 100.0


# --------------------------------------------------------------------------- #
# 2. DST day = 92 or 100 intervals, computed from the LOCAL calendar
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("day,expected_hours,expected_slots", [
    (datetime(2026, 3, 29, 12, tzinfo=LOCAL_TZ), 23, 92),   # spring forward
    (datetime(2026, 10, 25, 12, tzinfo=LOCAL_TZ), 25, 100),  # fall back
])
def test_dst_day_slot_count_from_calendar(acc, rules, day, expected_hours, expected_slots):
    start, end = model.day_bounds(day)
    # Derived from the calendar, NOT hardcoded into the accumulator.
    slots = int(round((end - start).total_seconds() / Q.total_seconds()))
    assert (end - start) == timedelta(hours=expected_hours)
    assert slots == expected_slots
    assert slots != 96
    cells = _cells(start, end)
    acc.accrue(synth("towel", cells, 0.05, 0.08, rules))
    cov = acc.coverage(start, end, device="towel")
    assert cov["slots"] == expected_slots
    assert cov["confirmed"] == expected_slots
    assert cov["expected"] == expected_slots       # calendar-derived
    assert cov["coverage_pct"] == 100.0


# --------------------------------------------------------------------------- #
# 3. Duplicate interval — second write is a conflict, confirmed row immutable
#    even when the current price changed (ADR §6.4).
# --------------------------------------------------------------------------- #
def test_duplicate_interval_confirmed_is_immutable(acc, rules):
    s = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)
    iv1 = compute_interval("tv", s, s + Q, 0.0, 0.05, 0.10, rules=rules)
    r1 = acc.accrue([iv1])
    assert r1.n_confirmed == 1
    # Re-price the SAME interval at a different (later "current") price.
    iv2 = compute_interval("tv", s, s + Q, 0.0, 0.05, 0.99, rules=rules)
    r2 = acc.accrue([iv2])
    assert r2.n_skipped_locked == 1 and r2.n_confirmed == 0
    # Stored price stays the ORIGINAL, cost unchanged.
    conn = acc.connect()
    row = conn.execute("SELECT price_eur_kwh, total_variable_eur FROM interval_cost "
                       "WHERE device='tv'").fetchone()
    conn.close()
    assert row["price_eur_kwh"] == 0.10
    assert abs(row["total_variable_eur"] - 0.005) < 1e-9


# --------------------------------------------------------------------------- #
# 4. Missing interval — a gap in written slots shows in coverage, never as 0
# --------------------------------------------------------------------------- #
def test_missing_interval_reflected_in_coverage(acc, rules):
    start, end = model.day_bounds(datetime(2026, 7, 15, 12, tzinfo=LOCAL_TZ))
    cells = _cells(start, end)
    ivs = synth("aquarium", cells, 0.01, 0.10, rules)
    del ivs[50]                             # drop one slot entirely
    acc.accrue(ivs)
    cov = acc.coverage(start, end, device="aquarium")
    assert cov["recorded"] == 95
    assert cov["expected"] == 96            # calendar still expects 96
    assert cov["coverage_pct"] == 100.0     # of what was recorded
    assert cov["expected_coverage_pct"] < 100.0   # a slot is genuinely missing


# --------------------------------------------------------------------------- #
# 5 / 7. Counter reset & negative delta -> excluded, raw value preserved, audited
# --------------------------------------------------------------------------- #
def test_counter_reset_excluded_and_audited(acc, rules):
    s = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)
    iv = compute_interval("boiler_ten", s, s + Q, 500.0, 0.3, 0.10, rules=rules)
    assert iv.status == STATUS_EXCLUDED
    assert iv.quality == "C" and iv.reset_detected == 1
    assert iv.accepted_delta_kwh is None      # NEVER banked
    assert iv.raw_delta_kwh < 0               # raw preserved (negative)
    r = acc.accrue([iv])
    assert r.n_excluded == 1 and r.n_confirmed == 0
    audit = acc.excluded_audit(s, s + Q)
    assert len(audit) == 1
    assert audit[0]["reason"] == REASON_COUNTER_RESET
    assert audit[0]["raw_delta_kwh"] < 0      # observed value not discarded
    # nothing banked into totals
    assert acc.period_cost(s, s + Q) is None


def test_negative_delta_not_banked(acc, rules):
    s = datetime(2026, 7, 15, 11, 0, tzinfo=UTC)
    iv = compute_interval("recirc", s, s + Q, 10.0, 9.0, 0.10, rules=rules)
    assert iv.raw_delta_kwh == pytest.approx(-1.0)
    assert iv.accepted_delta_kwh is None
    assert iv.status == STATUS_EXCLUDED


# --------------------------------------------------------------------------- #
# 6 / 16. Reconnect jump & per-device physical threshold (from rules json)
# --------------------------------------------------------------------------- #
def test_reconnect_jump_excluded_ev(acc, rules):
    s = datetime(2026, 7, 16, 3, 0, tzinfo=UTC)
    iv = compute_interval("ev", s, s + Q, 882.8, 882.8 + 15.19, 0.155, rules=rules)
    assert iv.status == STATUS_EXCLUDED
    assert iv.exclude_reason == REASON_IMPLAUSIBLE_SPIKE
    assert iv.accepted_delta_kwh is None
    assert iv.raw_delta_kwh == pytest.approx(15.19)


def test_per_device_threshold_boundary(rules):
    # EV max_interval_kwh = 5.5 (22 kW * 0.25h). At the boundary is accepted;
    # just over is a spike. Threshold value comes from meter_delta_rules.json.
    assert rules["ev"] == 5.5
    s = datetime(2026, 7, 16, 3, 0, tzinfo=UTC)
    at = compute_interval("ev", s, s + Q, 0.0, 5.5, 0.10, rules=rules)
    over = compute_interval("ev", s, s + Q, 0.0, 5.5001, 0.10, rules=rules)
    assert at.status == STATUS_CONFIRMED
    assert over.status == STATUS_EXCLUDED and over.exclude_reason == REASON_IMPLAUSIBLE_SPIKE


def test_threshold_is_per_device(rules):
    # A 0.2 kWh delta is fine for the boiler (max 0.875) but a spike for the
    # aquarium (max 0.0375) — proving the gate is per-device, from the json.
    s = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)
    b = compute_interval("boiler_ten", s, s + Q, 0.0, 0.2, 0.10, rules=rules)
    a = compute_interval("aquarium", s, s + Q, 0.0, 0.2, 0.10, rules=rules)
    assert b.status == STATUS_CONFIRMED
    assert a.status == STATUS_EXCLUDED


# --------------------------------------------------------------------------- #
# 8. Unavailable reading -> incomplete, energy_unavailable, never zero
# --------------------------------------------------------------------------- #
def test_unavailable_is_incomplete_not_zero(acc, rules):
    s = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)
    iv = compute_interval("hydrophore", s, s + Q, None, 5.0, 0.10, rules=rules)
    assert iv.status == STATUS_INCOMPLETE
    assert iv.quality == "D"
    assert iv.accepted_delta_kwh is None
    r = acc.accrue([iv])
    assert r.n_incomplete == 1
    audit = acc.excluded_audit(s, s + Q)
    assert audit[0]["reason"] == REASON_ENERGY_UNAVAILABLE
    # incomplete cost is NOT part of the confirmed total
    assert acc.period_cost(s, s + Q, status=STATUS_CONFIRMED) is None
    assert acc.period_cost(s, s + Q, status=STATUS_INCOMPLETE) is None  # cost NULL


# --------------------------------------------------------------------------- #
# 9. Stale reading: a repeated (unchanged) counter is genuine 0 kWh, NOT missing
# --------------------------------------------------------------------------- #
def test_stale_repeated_value_is_zero_not_missing(acc, rules):
    s = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)
    iv = compute_interval("tv", s, s + Q, 0.0, 0.0, 0.10, rules=rules)  # no change
    assert iv.status == STATUS_CONFIRMED
    assert iv.accepted_delta_kwh == 0.0        # real zero, priced
    assert iv.spot_cost_eur == 0.0


def test_stale_then_catchup_jump_excluded(acc, rules):
    # A long-stale aquarium counter that finally steps by more than one slot's
    # plausible delta is a reconnect/catch-up jump -> excluded (mis-attributed).
    s = datetime(2026, 7, 16, 6, 0, tzinfo=UTC)
    iv = compute_interval("aquarium", s, s + Q, 0.024, 0.024 + 0.5, 0.10, rules=rules)
    assert iv.status == STATUS_EXCLUDED
    assert iv.exclude_reason == REASON_IMPLAUSIBLE_SPIKE


# --------------------------------------------------------------------------- #
# 10. Missing price -> incomplete, price_missing, raw delta preserved, not 0
# --------------------------------------------------------------------------- #
def test_missing_price_incomplete(acc, rules):
    s = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)
    iv = compute_interval("boiler_ten", s, s + Q, 0.0, 0.2, None, rules=rules)
    assert iv.status == STATUS_INCOMPLETE
    assert iv.quality == "E"
    assert iv.raw_delta_kwh == pytest.approx(0.2)   # observed delta kept
    assert iv.accepted_delta_kwh is None            # but not priced
    acc.accrue([iv])
    audit = acc.excluded_audit(s, s + Q)
    assert audit[0]["reason"] == REASON_PRICE_MISSING


# --------------------------------------------------------------------------- #
# 11. Negative price is NOT clamped
# --------------------------------------------------------------------------- #
def test_negative_price_not_clamped(acc, rules):
    s = datetime(2026, 7, 15, 3, 0, tzinfo=UTC)
    iv = compute_interval("boiler_ten", s, s + Q, 0.0, 0.5, -0.05, rules=rules)
    assert iv.status == STATUS_CONFIRMED
    assert iv.spot_cost_eur == pytest.approx(-0.025)
    acc.accrue([iv])
    assert acc.period_cost(s, s + Q) == pytest.approx(-0.025)  # you are paid


# --------------------------------------------------------------------------- #
# 12. Idempotent rerun — double-run yields identical totals (ADR §6.1)
# --------------------------------------------------------------------------- #
def test_idempotent_rerun_same_totals(acc, rules):
    start, end = model.day_bounds(datetime(2026, 7, 15, 12, tzinfo=LOCAL_TZ))
    ivs = synth("ev", _cells(start, end), 1.0, 0.10, rules)  # 1 kWh/slot < 5.5 max
    r1 = acc.accrue(ivs)
    t1 = acc.period_cost(start, end)
    r2 = acc.accrue(ivs)             # exact rerun
    t2 = acc.period_cost(start, end)
    assert r1.n_confirmed == 96
    assert r2.n_confirmed == 0 and r2.n_skipped_locked == 96
    assert t1 == t2
    # exactly one row per interval, no duplication
    conn = acc.connect()
    n = conn.execute("SELECT COUNT(*) c FROM interval_cost WHERE device='ev'").fetchone()["c"]
    conn.close()
    assert n == 96


# --------------------------------------------------------------------------- #
# 13. Concurrent writer — advisory flock is exclusive (ADR §6.3)
# --------------------------------------------------------------------------- #
def test_concurrent_writer_lock_in_process(acc, rules):
    s = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)
    iv = compute_interval("tv", s, s + Q, 0.0, 0.01, 0.10, rules=rules)
    with acc._writer_lock():
        # A second accumulator on the SAME lock file cannot write concurrently.
        other = Accumulator(acc.db_path, rules=rules, lock_path=acc.lock_path)
        with pytest.raises(LockHeld):
            other.accrue([iv])


def _child_try_write(db_path, lock_path, ready_evt, release_evt, result_q):
    """Child process: signal ready, then attempt a locked write while the parent
    holds the lock; report whether LockHeld was raised."""
    from datetime import datetime, timedelta, timezone
    from tools.energy_cost.accumulator import (
        Accumulator, LockHeld, compute_interval, load_meter_rules)
    r = load_meter_rules(RULES_JSON)
    a = Accumulator(db_path, rules=r, lock_path=lock_path)
    s = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    iv = compute_interval("tv", s, s + timedelta(minutes=15), 0.0, 0.01, 0.10, rules=r)
    ready_evt.set()
    release_evt.wait(5)
    try:
        a.accrue([iv])
        result_q.put("wrote")
    except LockHeld:
        result_q.put("lockheld")
    except Exception as e:  # pragma: no cover
        result_q.put(f"error:{e!r}")


def test_concurrent_writer_two_processes(acc, rules):
    ctx = multiprocessing.get_context("spawn")
    ready, release, q = ctx.Event(), ctx.Event(), ctx.Queue()
    p = ctx.Process(target=_child_try_write,
                    args=(acc.db_path, acc.lock_path, ready, release, q))
    with acc._writer_lock():          # parent holds the exclusive lock
        p.start()
        assert ready.wait(5)
        release.set()                 # tell child to attempt its write now
        outcome = q.get(timeout=10)
    p.join(10)
    assert outcome == "lockheld"


# --------------------------------------------------------------------------- #
# 14. Interrupted atomic write -> full rollback + WAL recovery (ADR §6.2)
# --------------------------------------------------------------------------- #
def test_interrupted_write_rolls_back(acc, rules):
    start, end = model.day_bounds(datetime(2026, 7, 15, 12, tzinfo=LOCAL_TZ))
    ivs = synth("boiler_ten", _cells(start, end), 0.1, 0.10, rules)
    with pytest.raises(RuntimeError, match="injected fault"):
        acc.accrue(ivs, fault_after=40)      # crash mid-transaction
    # NOTHING committed: the whole run rolled back.
    conn = acc.connect()
    n = conn.execute("SELECT COUNT(*) c FROM interval_cost").fetchone()["c"]
    conn.close()
    assert n == 0
    # DB reopens cleanly (WAL auto-recovery) and a clean run then succeeds.
    r = acc.accrue(ivs)
    assert r.n_confirmed == 96
    assert acc.period_cost(start, end) == pytest.approx(96 * 0.1 * 0.10)


def test_interrupted_write_integrity_check_ok(acc, rules):
    s = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)
    ivs = [compute_interval("tv", s + i * Q, s + (i + 1) * Q, float(i), float(i) + 0.01,
                            0.10, rules=rules) for i in range(10)]
    with pytest.raises(RuntimeError):
        acc.accrue(ivs, fault_after=3)
    conn = acc.connect()
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    conn.close()


# --------------------------------------------------------------------------- #
# 15. Schema migration vN -> vN+1 (ADR §7)
# --------------------------------------------------------------------------- #
def test_schema_migration_applies_and_records(tmp_path, rules):
    db = str(tmp_path / "cost_ledger.db")
    a1 = Accumulator(db, rules=rules)
    assert a1.schema_versions() == [1]
    # Reopen with an additive v2 migration (new nullable column).
    a2 = Accumulator(db, rules=rules, extra_migrations=[
        (2, "add ui_note column", "ALTER TABLE interval_cost ADD COLUMN ui_note TEXT;")])
    assert a2.schema_versions() == [1, 2]
    conn = a2.connect()
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(interval_cost)")}
    conn.close()
    assert "ui_note" in cols


def test_migration_is_idempotent(tmp_path, rules):
    db = str(tmp_path / "cost_ledger.db")
    mig = [(2, "add ui_note", "ALTER TABLE interval_cost ADD COLUMN ui_note TEXT;")]
    Accumulator(db, rules=rules, extra_migrations=mig)
    # Reopening again must NOT try to re-add the column (would raise).
    a = Accumulator(db, rules=rules, extra_migrations=mig)
    assert a.schema_versions() == [1, 2]


# --------------------------------------------------------------------------- #
# 17. Excluded-delta audit is append-only and complete
# --------------------------------------------------------------------------- #
def test_excluded_audit_append_only(acc, rules):
    s = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)
    spike = compute_interval("ev", s, s + Q, 0.0, 9.0, 0.10, rules=rules)
    reset = compute_interval("tv", s, s + Q, 5.0, 0.0, 0.10, rules=rules)
    gap = compute_interval("towel", s, s + Q, None, 1.0, 0.10, rules=rules)
    acc.accrue([spike, reset, gap])
    audit = acc.excluded_audit(s, s + Q)
    reasons = {a["device"]: a["reason"] for a in audit}
    assert reasons["ev"] == REASON_IMPLAUSIBLE_SPIKE
    assert reasons["tv"] == REASON_COUNTER_RESET
    assert reasons["towel"] == REASON_ENERGY_UNAVAILABLE
    assert len(audit) == 3


# --------------------------------------------------------------------------- #
# 18. Coverage calculation over a known mix
# --------------------------------------------------------------------------- #
def test_coverage_over_known_mix(acc, rules):
    s = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)
    ivs = []
    # 6 confirmed, 2 incomplete (missing price), 2 excluded (spike)
    for i in range(6):
        ivs.append(compute_interval("tv", s + i * Q, s + (i + 1) * Q,
                                    float(i) * 0.01, float(i) * 0.01 + 0.01, 0.10, rules=rules))
    for i in range(6, 8):
        ivs.append(compute_interval("tv", s + i * Q, s + (i + 1) * Q,
                                    0.0, 0.01, None, rules=rules))
    for i in range(8, 10):
        ivs.append(compute_interval("tv", s + i * Q, s + (i + 1) * Q,
                                    0.0, 9.0, 0.10, rules=rules))
    acc.accrue(ivs)
    cov = acc.coverage(s, s + 10 * Q, device="tv")
    assert cov["recorded"] == 10
    assert cov["confirmed"] == 6
    assert cov["incomplete"] == 2
    assert cov["excluded"] == 2
    assert cov["coverage_pct"] == 60.0


# --------------------------------------------------------------------------- #
# 19. Tariff null -> spot-only; full bill / add-on columns NULL, not 0
# --------------------------------------------------------------------------- #
def test_tariff_null_is_spot_only(acc, rules):
    assert SPOT_ONLY_LEDGER.spot_only is True
    s = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)
    # ev delta 1.0 kWh (< 5.5 max) at 0.10 EUR/kWh -> spot 0.10.
    acc.accrue([compute_interval("ev", s, s + Q, 0.0, 1.0, 0.10, rules=rules)])
    comp = acc.components(s, s + Q)
    assert comp["spot"] == pytest.approx(0.10)
    assert comp["margin"] is None            # not configured -> NULL, never 0
    assert comp["distribution"] is None
    assert comp["vat"] is None
    assert comp["total_variable"] == pytest.approx(0.10)


def test_tariff_schema_json_loads_spot_only():
    t = load_tariff_from_schema(TARIFF_JSON)
    assert t.spot_only is True
    assert t.fixed_monthly_eur is None
    assert t.model_tariff.vat_rate is None


def test_month_full_null_when_spot_only(acc, rules):
    now = datetime(2026, 7, 15, 12, tzinfo=UTC)
    start, _ = model.this_month_bounds(now)
    acc.accrue([compute_interval("boiler_ten", start, start + Q, 0.0, 1.0, 0.10, rules=rules)])
    mf = acc.month_full(now)
    assert mf["spot_only"] is True
    assert mf["fixed"] is None               # no fixed charge invented
    assert mf["full"] == pytest.approx(mf["variable"])   # == variable only
    assert cost_label(mf["spot_only"]) == SPOT_LABEL_RU  # «Стоимость Nord Pool»


# --------------------------------------------------------------------------- #
# 20. VAT applied correctly when set, with component separation
# --------------------------------------------------------------------------- #
def test_vat_and_components(tmp_path, rules):
    t = LedgerTariff(model_tariff=Tariff(
        supplier_margin_eur_per_kwh=0.01,
        distribution_eur_per_kwh=0.05,
        vat_rate=0.21,
    ), source_note="test full tariff")
    a = Accumulator(str(tmp_path / "db.db"), rules=rules, tariff=t)
    s = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)
    iv = compute_interval("ev", s, s + Q, 0.0, 1.0, 0.10, rules=rules, tariff=t)
    # 1 kWh: spot .10, margin .01, dist .05, subtotal .16, vat .0336, total .1936
    assert iv.spot_cost_eur == pytest.approx(0.10)
    assert iv.supplier_margin_eur == pytest.approx(0.01)
    assert iv.distribution_var_eur == pytest.approx(0.05)
    assert iv.vat_eur == pytest.approx(0.0336)
    assert iv.total_variable_eur == pytest.approx(0.1936)
    a.accrue([iv])
    comp = a.components(s, s + Q)
    assert comp["vat"] == pytest.approx(0.0336)
    assert comp["total_variable"] == pytest.approx(0.1936)


# --------------------------------------------------------------------------- #
# 21. Fixed monthly charge accounted SEPARATELY (never smeared) — ADR §5
# --------------------------------------------------------------------------- #
def test_fixed_charge_never_smeared(tmp_path, rules):
    t = LedgerTariff(model_tariff=Tariff(), fixed_monthly_eur=12.0,
                     source_note="fixed-only tariff")
    a = Accumulator(str(tmp_path / "db.db"), rules=rules, tariff=t)
    now = datetime(2026, 7, 15, 12, tzinfo=UTC)
    start, end = model.this_month_bounds(now)
    # delta 0.1 kWh (within every device threshold) at price 1.0 -> spot 0.10 each.
    ivs = [compute_interval(d, start, start + Q, 0.0, 0.1, 1.0, rules=rules, tariff=t)
           for d in ("boiler_ten", "ev", "tv")]
    a.accrue(ivs)
    # No interval row carries the fixed charge.
    conn = a.connect()
    rows = conn.execute("SELECT total_variable_eur FROM interval_cost").fetchall()
    conn.close()
    for r in rows:
        assert r["total_variable_eur"] == pytest.approx(0.10)   # spot only, no +12
    # Fixed charge lives in its own table, once for the month.
    mkey = f"{start.astimezone(LOCAL_TZ).year:04d}-{start.astimezone(LOCAL_TZ).month:02d}"
    assert a.fixed_charge(mkey) == pytest.approx(12.0)
    # Whole-home month = variable(all devices) + fixed, added ONCE.
    mf = a.month_full(now)
    assert mf["variable"] == pytest.approx(0.30)     # 3 devices * 0.10
    assert mf["fixed"] == pytest.approx(12.0)
    assert mf["full"] == pytest.approx(12.30)
    # per-device sums are variable-only (no fixed apportionment).
    pd = a.per_device(start, end)
    assert sum(pd.values()) == pytest.approx(0.30)


def test_fixed_charge_not_double_counted_on_rerun(tmp_path, rules):
    t = LedgerTariff(model_tariff=Tariff(), fixed_monthly_eur=12.0,
                     source_note="fixed rerun tariff")
    a = Accumulator(str(tmp_path / "db.db"), rules=rules, tariff=t)
    now = datetime(2026, 7, 15, 12, tzinfo=UTC)
    start, _ = model.this_month_bounds(now)
    iv = compute_interval("ev", start, start + Q, 0.0, 1.0, 0.10, rules=rules, tariff=t)
    a.accrue([iv])
    a.accrue([iv])                                  # rerun
    mkey = f"{start.astimezone(LOCAL_TZ).year:04d}-{start.astimezone(LOCAL_TZ).month:02d}"
    assert a.fixed_charge(mkey) == pytest.approx(12.0)   # UNIQUE(period) held


# --------------------------------------------------------------------------- #
# 22. UI-facing null / stale / excluded formatting
# --------------------------------------------------------------------------- #
def test_ui_formatting():
    assert format_eur(None) == NO_DATA          # null -> em dash, never "0.00 €"
    assert format_eur(0.0) == "0.00 €"          # a real zero IS shown
    assert format_eur(1.2345) == "1.23 €"
    assert format_eur(1.2345, dp=4) == "1.2345 €"
    assert "подтверждено" in format_status_badge(STATUS_CONFIRMED)
    assert "неполные" in format_status_badge(STATUS_INCOMPLETE)
    assert "исключено" in format_status_badge(STATUS_EXCLUDED)
    assert cost_label(True) == SPOT_LABEL_RU
    assert cost_label(False) == "Итоговый счёт"
    cov = {"confirmed": 90, "expected": 96, "coverage_pct": 93.75}
    assert format_coverage(cov) == "90/96 (93.8%)"


# --------------------------------------------------------------------------- #
# 23. Frozen evidence ledger as a fixture (immutable input)
# --------------------------------------------------------------------------- #
def test_frozen_ledger_end_to_end(tmp_path, rules):
    tar = load_tariff_from_schema(TARIFF_JSON)
    a = Accumulator(str(tmp_path / "db.db"), rules=rules, tariff=tar)
    before = os.stat(FROZEN).st_mtime          # prove we never write the evidence
    res = a.accrue_shadow_ledger(FROZEN)
    assert os.stat(FROZEN).st_mtime == before
    # 95 intervals * 8 devices = 760 device-intervals.
    assert res.n_confirmed + res.n_incomplete + res.n_excluded == 760
    snaps = load_shadow_snapshots(FROZEN)
    s, e = snaps[0].ts, snaps[-1].ts + Q
    # The EV +15.19 kWh catch-up jump must be excluded as a spike.
    ev_excl = [x for x in a.excluded_audit(s, e)
               if x["device"] == "ev" and x["reason"] == REASON_IMPLAUSIBLE_SPIKE]
    assert ev_excl and ev_excl[0]["raw_delta_kwh"] == pytest.approx(15.19)
    # Confirmed spot cost is a positive, finite EUR figure; spot-only.
    comp = a.components(s, e)
    assert comp["spot"] is not None and comp["spot"] > 0
    assert comp["margin"] is None              # spot-only tariff
    cov = a.coverage(s, e)
    assert cov["confirmed"] == res.n_confirmed


def test_frozen_ledger_rerun_is_stable(tmp_path, rules):
    a = Accumulator(str(tmp_path / "db.db"), rules=rules,
                    tariff=load_tariff_from_schema(TARIFF_JSON))
    r1 = a.accrue_shadow_ledger(FROZEN)
    snaps = load_shadow_snapshots(FROZEN)
    s, e = snaps[0].ts, snaps[-1].ts + Q
    total1 = a.components(s, e)["spot"]
    r2 = a.accrue_shadow_ledger(FROZEN)         # rerun: all locked
    total2 = a.components(s, e)["spot"]
    assert total1 == total2
    assert r2.n_confirmed == 0
    assert r2.n_skipped_locked == r1.n_confirmed + r1.n_excluded


# --------------------------------------------------------------------------- #
# Restart-recovery anchor (ADR §6.5): high-water-mark of confirmed intervals
# --------------------------------------------------------------------------- #
def test_high_water_mark(acc, rules):
    assert acc.high_water_mark() is None      # empty ledger
    start, end = model.day_bounds(datetime(2026, 7, 15, 12, tzinfo=LOCAL_TZ))
    cells = _cells(start, end)
    acc.accrue(synth("ev", cells, 1.0, 0.10, rules))
    hwm = acc.high_water_mark("ev")
    # last confirmed interval start = last cell's start
    assert hwm == cells[-1][0].astimezone(UTC).isoformat()


# --------------------------------------------------------------------------- #
# Incomplete -> confirmed upgrade (ADR §6.1) when data later arrives
# --------------------------------------------------------------------------- #
def test_incomplete_upgraded_to_confirmed(acc, rules):
    s = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)
    # First run: price missing -> incomplete.
    acc.accrue([compute_interval("boiler_ten", s, s + Q, 0.0, 0.2, None, rules=rules)])
    assert acc.period_cost(s, s + Q, status=STATUS_CONFIRMED) is None
    # Second run: price now available -> upgrade to confirmed.
    acc.accrue([compute_interval("boiler_ten", s, s + Q, 0.0, 0.2, 0.10, rules=rules)])
    assert acc.period_cost(s, s + Q, status=STATUS_CONFIRMED) == pytest.approx(0.02)
    conn = acc.connect()
    st = conn.execute("SELECT status FROM interval_cost WHERE device='boiler_ten'").fetchone()["status"]
    conn.close()
    assert st == STATUS_CONFIRMED
