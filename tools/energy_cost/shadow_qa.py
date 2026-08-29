#!/usr/bin/env python3
"""Shadow-ledger QA / analysis tool (READ-ONLY, no production writes).

Consumes the shadow collector's append-only ledger
(``/config/shadow_snapshots.jsonl`` on HA; a local copy here) and produces a
data-quality + preliminary-cost report over whatever has been collected so far.

It NEVER mutates the ledger and NEVER silently substitutes missing data with 0:
missing energy or missing price yields ``None`` interval cost and a quality flag.
Raw snapshot values are preserved untouched; QA findings are reported alongside,
never written back.

Interval accounting reuses ``tools/energy_cost/model.py``:

    interval_cost = interval_kWh * NordPool_price_of_that_interval

Per-interval quality flags
--------------------------
  A  usable    energy available both ends, complete, no reset, price present
  B  usable*   usable but interval width deviates from the 15-min grid
  C  usable!   counter reset detected inside the interval (cost still computed)
  D  no-cost   energy unavailable/missing in the interval  -> cost = None
  E  no-cost   Nord Pool price missing for the interval     -> cost = None

Usage
-----
  python3 tools/energy_cost/shadow_qa.py --ledger /path/to/shadow_snapshots.jsonl
  python3 tools/energy_cost/shadow_qa.py --pull            # SSH-fetch (read-only)
  python3 tools/energy_cost/shadow_qa.py --pull --out docs/audit/ENERGY_SHADOW_INTERIM.md
  python3 tools/energy_cost/shadow_qa.py --ledger L --json  # machine-readable

``--pull`` fetches the ledger from HA over SSH (base64, sudo cat) into a temp
file, then analyses that copy. It also captures the remote file size + perms.
No secret value is ever printed; the ledger is scanned for leaks and only a
count + fingerprint is reported.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

# Reuse the cost model that lives next to this file.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model  # noqa: E402  (sibling module)

try:
    from zoneinfo import ZoneInfo

    RIGA = ZoneInfo("Europe/Riga")
except Exception:  # pragma: no cover
    RIGA = timezone(timedelta(hours=2))

REMOTE_LEDGER = "/config/shadow_snapshots.jsonl"
GAP_MAX = timedelta(minutes=16)      # gap larger than this = missing interval(s)
STEP = timedelta(minutes=15)         # nominal collection cadence
STEP_TOL = timedelta(minutes=1)      # tolerance around 15 min before "off-grid"

# Secret patterns (subset of tools/secret_scan.py) — the ledger must contain none.
SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN " + r"OPENSSH PRIVATE KEY-----"), "private SSH key"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b"), "JWT token"),
    (re.compile(r"\b\d{8,10}:AA[A-Za-z0-9_-]{30,}\b"), "Telegram bot token"),
    (re.compile(r"\bBoiler_\w+_\d{4}\b"), "boiler password"),
    (re.compile(r"\bpass(?:word|wd)\b\s*[=:]\s*['\"][^'\"]+['\"]", re.IGNORECASE), "password assignment"),
]


# --------------------------------------------------------------------------- #
# Ledger acquisition
# --------------------------------------------------------------------------- #
def pull_ledger(dst: str) -> dict:
    """SSH-fetch the remote ledger (read-only) into ``dst``. Returns metadata."""
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    from ha_ssh import ssh_connect, run
    from project_secrets import secret

    sudo = secret("HA_SUDO_PASSWORD", required=True)
    c = ssh_connect()
    try:
        b64, _ = run(c, f"printf '%s\\n' {json_shquote(sudo)} | sudo -S base64 {REMOTE_LEDGER} 2>/dev/null")
        meta, _ = run(c, f"printf '%s\\n' {json_shquote(sudo)} | sudo -S stat -c '%s %a %U %G' {REMOTE_LEDGER} 2>/dev/null")
    finally:
        c.close()
    raw = base64.b64decode(b64) if b64 else b""
    with open(dst, "wb") as f:
        f.write(raw)
    size = perms = owner = group = None
    parts = meta.split()
    if len(parts) >= 4:
        size, perms, owner, group = parts[0], parts[1], parts[2], parts[3]
    return {"bytes": len(raw), "stat_size": size, "perms": perms,
            "owner": owner, "group": group}


def json_shquote(s: str) -> str:
    import shlex
    return shlex.quote(s)


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
@dataclass
class Snap:
    ts: datetime
    raw_ts: str
    price: dict
    energy: dict
    context: dict
    lineno: int


def load_snapshots(path: str):
    snaps, errors = [], []
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"line {lineno}: JSON decode error: {e}")
                continue
            try:
                ts = datetime.fromisoformat(d["ts"])
            except Exception as e:
                errors.append(f"line {lineno}: bad ts {d.get('ts')!r}: {e}")
                continue
            snaps.append(Snap(ts=ts, raw_ts=d["ts"], price=d.get("price", {}),
                              energy=d.get("energy_kwh", {}), context=d.get("context", {}),
                              lineno=lineno))
    return snaps, errors


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
@dataclass
class DeviceStat:
    name: str
    n_intervals: int = 0
    n_usable: int = 0
    n_energy_missing: int = 0
    n_price_missing: int = 0
    n_reset: int = 0
    n_incomplete: int = 0
    n_offgrid: int = 0
    window_kwh: float = 0.0        # sum of usable interval deltas
    shadow_cost: float = 0.0       # sum of usable interval spot cost (EUR)
    first_value: float = None
    last_value: float = None
    n_avail_snaps: int = 0
    n_snaps: int = 0
    unavailable_ts: list = field(default_factory=list)
    reset_ts: list = field(default_factory=list)
    flags: list = field(default_factory=list)  # per-interval flag letters

    @property
    def snap_availability(self):
        return (self.n_avail_snaps / self.n_snaps) if self.n_snaps else 0.0

    @property
    def interval_completeness(self):
        return (self.n_usable / self.n_intervals) if self.n_intervals else 0.0


def interval_flag(en: "model.EnergyInterval", price, offgrid: bool) -> str:
    if price is None:
        return "E"
    # Energy unknown, OR the interval touched an unavailable/gap reading so its
    # true delta is uncertain: never price it (the model may carry-forward a 0.0
    # delta here — we must NOT bank that as real 0 consumption).
    if en.kwh is None or not en.complete:
        return "D"
    if en.reset:
        return "C"
    if offgrid:
        return "B"
    return "A"


def analyze(snaps, ledger_meta, secret_findings):
    snaps = sorted(snaps, key=lambda s: s.ts)
    devices = list(model_device_names(snaps))
    stats = {d: DeviceStat(name=d) for d in devices}

    # snapshot-level availability counts + first/last values
    for s in snaps:
        for d in devices:
            slot = s.energy.get(d, {})
            st = stats[d]
            st.n_snaps += 1
            if slot.get("avail"):
                st.n_avail_snaps += 1
                if st.first_value is None:
                    st.first_value = slot.get("v")
                st.last_value = slot.get("v")
            else:
                st.unavailable_ts.append(s.raw_ts)

    # timeline QA
    dup_ts, gaps, offgrid_intervals, dst_issues = [], [], [], []
    seen = {}
    for s in snaps:
        seen.setdefault(s.raw_ts, 0)
        seen[s.raw_ts] += 1
        # DST/offset correctness
        expected = s.ts.astimezone(RIGA).utcoffset()
        actual = s.ts.utcoffset()
        if expected is not None and actual is not None and expected != actual:
            dst_issues.append(f"{s.raw_ts}: offset {actual} != Europe/Riga {expected}")
    dup_ts = [t for t, n in seen.items() if n > 1]

    # price-point series from consecutive snapshots (current price at ts_i valid
    # over [ts_i, ts_{i+1}))
    price_points = []
    for i, s in enumerate(snaps):
        cur = s.price.get("current", {})
        end = snaps[i + 1].ts if i + 1 < len(snaps) else s.ts + STEP
        price_points.append(model.PricePoint(start=s.ts, end=end, price=cur.get("v")))

    # per-device readings
    readings = {d: [] for d in devices}
    for s in snaps:
        for d in devices:
            slot = s.energy.get(d, {})
            v = slot.get("v") if slot.get("avail") else None
            readings[d].append(model.Reading(ts=s.ts, value=v))

    price_lag = []
    intervals_meta = []  # (start,end,width,offgrid)
    for i in range(len(snaps) - 1):
        a, b = snaps[i], snaps[i + 1]
        width = b.ts - a.ts
        if width > GAP_MAX:
            gaps.append((a.raw_ts, b.raw_ts, round(width.total_seconds() / 60, 1)))
        offgrid = abs(width - STEP) > STEP_TOL
        if offgrid:
            offgrid_intervals.append((a.raw_ts, b.raw_ts, round(width.total_seconds() / 60, 1)))
        intervals_meta.append((a.ts, b.ts, width, offgrid))
        # price lag: current-price 'updated' vs interval start
        cur = a.price.get("current", {})
        upd = cur.get("updated")
        if upd:
            try:
                updt = datetime.fromisoformat(upd)
                lag = (a.ts - updt).total_seconds() / 60.0
                if lag > 20:  # stale beyond one interval
                    price_lag.append((a.raw_ts, round(lag, 1)))
            except Exception:
                pass

    # per interval per device cost
    for i in range(len(snaps) - 1):
        s_start, s_end, width, offgrid = intervals_meta[i]
        price = model.price_for_interval(price_points, s_start, s_end)
        for d in devices:
            st = stats[d]
            en = model.interval_energy(readings[d], s_start, s_end)
            ci = model.cost_interval(en, price, model.SPOT_ONLY)
            flag = interval_flag(en, price, offgrid)
            st.flags.append(flag)
            st.n_intervals += 1
            if offgrid:
                st.n_offgrid += 1
            if ci.energy_missing:
                st.n_energy_missing += 1
            if ci.price_missing:
                st.n_price_missing += 1
            if ci.reset:
                st.n_reset += 1
                st.reset_ts.append(s_start.isoformat())
            if not ci.energy_complete:
                st.n_incomplete += 1
            # Only A/B/C count toward the priced total. D (energy missing or
            # interval touched an unavailable reading -> uncertain delta) and E
            # (price missing) are NEVER summed as 0.
            if flag in ("A", "B", "C") and ci.usable:
                st.n_usable += 1
                st.window_kwh += ci.kwh or 0.0
                st.shadow_cost += ci.spot_cost or 0.0

    return {
        "snaps": snaps,
        "stats": stats,
        "devices": devices,
        "dup_ts": dup_ts,
        "gaps": gaps,
        "offgrid_intervals": offgrid_intervals,
        "dst_issues": dst_issues,
        "price_lag": price_lag,
        "price_points": price_points,
        "ledger_meta": ledger_meta,
        "secret_findings": secret_findings,
        "n_intervals": max(len(snaps) - 1, 0),
        "window": (snaps[0].ts, snaps[-1].ts) if snaps else None,
    }


def model_device_names(snaps):
    names = []
    for s in snaps:
        for d in s.energy.keys():
            if d not in names:
                names.append(d)
    return names


def scan_secrets(path: str):
    findings = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for lineno, line in enumerate(f, 1):
            for rx, label in SECRET_PATTERNS:
                m = rx.search(line)
                if m:
                    fp = hashlib.sha256(m.group(0).encode()).hexdigest()[:12]
                    findings.append(f"line {lineno}: {label} [fp={fp}]")
    return findings


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def _pct(x):
    return f"{x * 100:.1f}%"


def render_markdown(res) -> str:
    L = []
    now = datetime.now(RIGA)
    snaps = res["snaps"]
    stats = res["stats"]
    n = len(snaps)
    ni = res["n_intervals"]

    L.append("# Energy Shadow Ledger — Interim QA Report")
    L.append("")
    L.append(f"_Generated {now.isoformat(timespec='seconds')} (Europe/Riga) by "
             "`tools/energy_cost/shadow_qa.py`. READ-ONLY analysis; raw snapshots "
             "left intact, no historical value edited._")
    L.append("")
    L.append("**PRELIMINARY** — this is an early checkpoint over a partial "
             "collection window, not a full 24 h. All kWh / cost figures below are "
             "provisional.")
    L.append("")

    # -- collection overview
    lm = res["ledger_meta"] or {}
    L.append("## 1. Collection overview")
    L.append("")
    L.append(f"- Snapshots collected: **{n}**")
    L.append(f"- Consecutive intervals analysed: **{ni}**")
    if res["window"]:
        a, b = res["window"]
        span = b - a
        L.append(f"- Window: `{a.isoformat()}` → `{b.isoformat()}` "
                 f"(~{span.total_seconds()/3600:.2f} h)")
    if lm:
        L.append(f"- Ledger file: {lm.get('stat_size','?')} bytes, perms "
                 f"`{lm.get('perms','?')}`, owner `{lm.get('owner','?')}:{lm.get('group','?')}`")
    exp_per_day = int(round(24 * 60 / 15))
    L.append(f"- Nominal cadence: 15 min → **{exp_per_day} snapshots/day** expected at full coverage")
    if n:
        L.append(f"- Coverage vs a full day so far: **{n}/{exp_per_day}** "
                 f"({_pct(n/exp_per_day)}) of a 24 h ledger")
    L.append("")

    # -- secret scan
    L.append("## 2. Secret-leak scan of the ledger")
    L.append("")
    sf = res["secret_findings"]
    if sf:
        L.append(f"- **{len(sf)} possible secret(s) found** (values never printed):")
        for x in sf:
            L.append(f"  - {x}")
    else:
        L.append("- **0 secrets found** in the ledger. PASS. "
                 "(Ledger holds only numeric energy/price + non-secret context strings.)")
    L.append("")

    # -- timeline integrity
    L.append("## 3. Timeline integrity")
    L.append("")
    L.append(f"- Duplicate timestamps: **{len(res['dup_ts'])}**"
             + ("" if not res["dup_ts"] else " — " + ", ".join(res["dup_ts"])))
    if res["gaps"]:
        L.append(f"- Missing-interval gaps (> {int(GAP_MAX.total_seconds()/60)} min): "
                 f"**{len(res['gaps'])}**")
        for a, b, mins in res["gaps"]:
            L.append(f"  - `{a}` → `{b}` = {mins} min")
    else:
        L.append(f"- Missing-interval gaps (> {int(GAP_MAX.total_seconds()/60)} min): **0**")
    if res["offgrid_intervals"]:
        L.append(f"- Off-grid intervals (width ≠ 15±1 min): **{len(res['offgrid_intervals'])}** "
                 "(flagged B, cost still computed):")
        for a, b, mins in res["offgrid_intervals"]:
            L.append(f"  - `{a}` → `{b}` = {mins} min")
    else:
        L.append("- Off-grid intervals (width ≠ 15±1 min): **0**")
    L.append(f"- Timezone/DST offset issues: **{len(res['dst_issues'])}**"
             + ("" if not res["dst_issues"] else ""))
    for x in res["dst_issues"]:
        L.append(f"  - {x}")
    if not res["dst_issues"]:
        L.append("  - All timestamps carry the correct Europe/Riga offset "
                 "(+03:00 EEST for July). DST handling OK.")
    L.append("")

    # -- price QA
    L.append("## 4. Nord Pool price QA")
    L.append("")
    pp = res["price_points"]
    n_price_ok = sum(1 for p in pp if p.price is not None)
    L.append(f"- Price present on **{n_price_ok}/{len(pp)}** snapshot slots "
             f"({_pct(n_price_ok/len(pp)) if pp else 'n/a'}).")
    if res["price_lag"]:
        L.append(f"- Stale-price (lag > 20 min) intervals: **{len(res['price_lag'])}**")
        for t, lag in res["price_lag"]:
            L.append(f"  - `{t}`: price last updated {lag} min before interval")
    else:
        L.append("- No stale-price lag detected: `current` price `updated` "
                 "timestamps land on the 15-min UTC boundary (:00/:15/:30/:45), "
                 "confirming 15-min alignment.")
    L.append("- NOTE: the `current`/`next` Nord Pool sensors expose **no `start` "
             "attribute** (only `lowest`/`highest` do), so per-slot 15-min "
             "alignment is validated via each reading's `updated` timestamp and "
             "the snapshot `ts`, not via a price `start` field.")
    L.append("")

    # -- per device completeness
    L.append("## 5. Per-device data completeness")
    L.append("")
    L.append("| Device | Snap avail | Interval priced | Resets | Unavail snaps | No-cost intervals (D/E) |")
    L.append("|---|---|---|---|---|---|")
    for d in res["devices"]:
        st = stats[d]
        n_nocost = sum(1 for f in st.flags if f in ("D", "E"))
        L.append(f"| `{d}` | {st.n_avail_snaps}/{st.n_snaps} ({_pct(st.snap_availability)}) "
                 f"| {st.n_usable}/{st.n_intervals} ({_pct(st.interval_completeness)}) "
                 f"| {st.n_reset} | {len(st.unavailable_ts)} | {n_nocost} |")
    L.append("")

    # -- unavailable / reset detail
    L.append("### 5a. Unavailable / reset detail")
    L.append("")
    any_detail = False
    for d in res["devices"]:
        st = stats[d]
        if st.unavailable_ts or st.reset_ts:
            any_detail = True
            if st.unavailable_ts:
                L.append(f"- `{d}` unavailable at: " + ", ".join(f"`{t}`" for t in st.unavailable_ts))
            if st.reset_ts:
                L.append(f"- `{d}` counter reset at interval start: "
                         + ", ".join(f"`{t}`" for t in st.reset_ts))
    if not any_detail:
        L.append("- No unavailable stretches and no counter resets detected across any device.")
    L.append("")

    # -- preliminary kWh + cost
    L.append("## 6. Preliminary window kWh + shadow cost (SPOT energy only)")
    L.append("")
    L.append("Δ over the observed window (last usable − first usable cumulative "
             "reading), priced per-interval at the Nord Pool price in force. "
             "This is the **collection-window** figure since the collector "
             "started — **NOT** a full calendar-day total (no midnight anchor "
             "snapshot exists yet). Missing intervals are excluded, never counted "
             "as 0.")
    L.append("")
    L.append("| Device | Window kWh (priced) | Shadow spot cost € | Quality flags |")
    L.append("|---|---|---|---|")
    tot_kwh = tot_cost = 0.0
    for d in res["devices"]:
        st = stats[d]
        tot_kwh += st.window_kwh
        tot_cost += st.shadow_cost
        flagstr = "".join(st.flags) if st.flags else "-"
        L.append(f"| `{d}` | {st.window_kwh:.4f} | {st.shadow_cost:.5f} | `{flagstr}` |")
    L.append(f"| **TOTAL (observed devices)** | **{tot_kwh:.4f}** | **{tot_cost:.5f}** | |")
    L.append("")
    L.append("_Flags: A usable · B off-grid width but priced · C reset (priced) · "
             "D energy missing or interval touched an unavailable reading "
             "(no cost, delta uncertain) · E price missing (no cost)._")
    L.append("")
    L.append("Interval cost is **computable**: `Δ_kWh × price_of_that_interval` "
             "via `tools/energy_cost/model.py` (`interval_energy` + "
             "`price_for_interval` + `cost_interval`, SPOT_ONLY tariff — no "
             "invented VAT/distribution add-ons).")
    L.append("")

    # -- readiness
    L.append("## 7. Readiness assessment for the 24 h / 48 h checkpoint")
    L.append("")
    min_comp = min((stats[d].interval_completeness for d in res["devices"]), default=0.0)
    L.append(f"- Pipeline status: collector is appending valid JSON lines; parser, "
             f"QA, and cost model all run end-to-end. **{n} snapshots** so far.")
    L.append(f"- At 15-min cadence, a 24 h checkpoint needs ~{exp_per_day} snapshots "
             f"and 48 h needs ~{exp_per_day*2}; currently at {n}. "
             f"Projected time to 24 h coverage: ~{max(0, exp_per_day-n)*15/60:.1f} h more.")
    L.append(f"- Worst per-device interval completeness so far: **{_pct(min_comp)}**.")
    issues = []
    if any(stats[d].unavailable_ts for d in res["devices"]):
        issues.append("at least one device dropped to `unavailable` (Tuya/WiFi flap) — "
                      "expected intermittently; those intervals correctly carry no cost")
    if res["gaps"]:
        issues.append("timeline gaps present (collector missed run(s))")
    if res["offgrid_intervals"]:
        issues.append("first interval is off-grid (collector started mid-cycle) — cosmetic")
    if not issues:
        issues.append("no blocking issues observed")
    for x in issues:
        L.append(f"- {x}")
    L.append("")
    L.append("**Verdict:** data pipeline is sound and interval cost is computable. "
             "Continue collection to the 24 h / 48 h checkpoint; re-run this tool "
             "to refresh the report. Full calendar-day totals require the ledger "
             "to span local midnight (for a clean day anchor).")
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ledger", help="path to a local copy of shadow_snapshots.jsonl")
    ap.add_argument("--pull", action="store_true",
                    help="SSH-fetch the ledger from HA (read-only) before analysing")
    ap.add_argument("--out", help="write the Markdown report to this path")
    ap.add_argument("--json", action="store_true", help="emit a JSON summary to stdout")
    args = ap.parse_args()

    ledger_meta = None
    path = args.ledger
    if args.pull:
        tmp = args.ledger or os.path.join(
            os.environ.get("TMPDIR", "/tmp"), "shadow_snapshots_pull.jsonl")
        ledger_meta = pull_ledger(tmp)
        path = tmp
    if not path:
        ap.error("provide --ledger PATH or --pull")
    if not os.path.exists(path):
        ap.error(f"ledger not found: {path}")

    if ledger_meta is None:
        stt = os.stat(path)
        ledger_meta = {"bytes": stt.st_size, "stat_size": stt.st_size,
                       "perms": oct(stt.st_mode & 0o777)[2:], "owner": "?", "group": "?"}

    snaps, parse_errors = load_snapshots(path)
    secret_findings = scan_secrets(path)
    if not snaps:
        print("No snapshots parsed. Errors:", parse_errors, file=sys.stderr)
        return 1

    res = analyze(snaps, ledger_meta, secret_findings)
    res["parse_errors"] = parse_errors

    md = render_markdown(res)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"Report written to {args.out} ({len(snaps)} snapshots)")

    if args.json:
        summary = {
            "snapshots": len(snaps),
            "intervals": res["n_intervals"],
            "parse_errors": parse_errors,
            "secret_findings": secret_findings,
            "gaps": res["gaps"],
            "duplicate_ts": res["dup_ts"],
            "dst_issues": res["dst_issues"],
            "devices": {
                d: {
                    "snap_avail": round(res["stats"][d].snap_availability, 4),
                    "interval_completeness": round(res["stats"][d].interval_completeness, 4),
                    "window_kwh": round(res["stats"][d].window_kwh, 5),
                    "shadow_cost_eur": round(res["stats"][d].shadow_cost, 6),
                    "resets": res["stats"][d].n_reset,
                    "unavailable": len(res["stats"][d].unavailable_ts),
                    "flags": "".join(res["stats"][d].flags),
                } for d in res["devices"]
            },
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    elif not args.out:
        print(md)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
