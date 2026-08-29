# Cost-Model Dry-Run — Three Models on the Frozen Shadow Window

_Generated 2026-07-16 (Europe/Riga) by `cost-dryrun-agent`. **LOCAL, READ-ONLY.** No HA
call, no device write, no production change. The interval accumulator wrote ONLY to a
throwaway temp SQLite file (deleted after the run); the frozen ledger was never mutated._

## Source & scope

- Ledger: `docs/audit/shadow_evidence/shadow_snapshots.frozen.jsonl`
  (immutable, `chmod 444`, **96 records → 95 consecutive intervals**, ~23.7 h)
- Window: `2026-07-15T18:46:59+03:00` → `2026-07-16T18:30:00+03:00` (+03:00 EEST, no DST change)
- sha256: `8191d6ea544092bc521d4f4f9e2e8d3a8dfe8dde9f27cd7ea4359383193e54d2` (matches CUSTODY.md; **unchanged after this run**)
- Rules: `docs/audit/meter_delta_rules.json` · Tariff: `docs/audit/tariff_schema.json` (**all-null template → spot-only**)
- Devices: `ev`, `boiler_ten`, `hydrophore`, `aquarium`, `recirc`, `towel`, `bed_backlight`, `tv`

> **PRELIMINARY — spot-only. NOT a bill.** The tariff template is all-null, so only the
> Nord Pool **spot** cost is computed. Supplier margin, distribution, transmission, excise
> and VAT are all `NULL` (never invented, never 0). Every € figure below is spot-only and
> understates the real invoice; it must NOT be shown to anyone as «Итоговый счёт».

## The three models

| # | Model | kWh basis | Price basis |
|---|-------|-----------|-------------|
| **NEW** | Interval accumulator (trustworthy) | `accepted_delta` — per-15-min delta, spikes/resets/gaps **excluded** | Nord Pool price **of that same 15-min slot** |
| **CUR** | Current production proxy (`total−midnight`) | **raw** delta = last − first reading (no exclusions) | one blended **avg spot** = 0.121593 €/kWh |
| **OLD** | Deprecated `cost_month` | **raw** delta (daily kWh) | **(min+max)/2 midpoint** = 0.128350 €/kWh |

Price basis over the window: 95 priced intervals · avg spot **0.121593** · min **0.01200** ·
max **0.24470** · midpoint **0.128350** €/kWh. (Interval-matched pricing verified PASS,
96/96 vs Elering — see `NORDPOOL_INTERVAL_ALIGNMENT.md`.)

---

## Section D — Model divergence (TOTAL and per device)

All € are **spot-only**. Divergence is measured **against the NEW interval model** (the trustworthy one).

### Headline (whole home)

| Model | Spot € | Δ vs NEW | % vs NEW |
|-------|-------:|---------:|---------:|
| **OLD** (min+max)/2 × raw kWh | **3.6965** | +3.0583 | **+479.2 %** |
| **CUR** total−midnight × avg spot | **3.5019** | +2.8637 | **+448.7 %** |
| **NEW** interval-matched (accepted) | **0.6382** | 0.0000 | 0.0 % |

**The crude models overstate the window's spot cost by roughly 4.5×–4.8× (≈ +€2.9–3.1).**

### Per device

| Device | OLD € | CUR € | NEW € | Δ CUR−NEW | Δ OLD−NEW | % (OLD vs NEW) | One-line explanation |
|--------|------:|------:|------:|----------:|----------:|---------------:|----------------------|
| **ev** | 1.9496 | 1.8470 | **0.0000** | +1.8470 | +1.9496 | n/a (NEW=0) | EV +15.19 kWh **single-slot** catch-up jump (implied 60.8 kW) inflates old/current by ~€1.85–1.95; NEW **excludes** it (unpriceable at one slot's price). |
| **boiler_ten** | 1.3574 | 1.2860 | **0.2978** | +0.9882 | +1.0596 | +355.8 % | Boiler ran at **cheap** Nord Pool slots (effective 0.028 €/kWh); blended avg/midpoint price it ~4.5× too high. Load-shifting is invisible to crude pricing. |
| **hydrophore** | 0.3183 | 0.3016 | **0.2964** | +0.0052 | +0.0219 | +7.4 % | Real ~2.0 kWh pump load, **included**; small gap over 1 unavailable snapshot drops 0.5 kWh raw→accepted (2.48→1.98), so NEW is slightly lower — the only device where crude≈new. |
| **aquarium** | 0.0664 | 0.0629 | **0.0376** | +0.0253 | +0.0288 | +76.6 % | Light ran mostly at cheap night slots; crude blended price overstates. |
| **recirc** | 0.0047 | 0.0045 | **0.0064** | −0.0019 | −0.0017 | −26.6 % | Tiny 0.037 kWh; ran during **pricier** slots than the blended avg, so NEW is marginally *higher* here (negligible € either way). |
| **towel** | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | — | Flat 0.0 kWh, **stale source** (never reported) — no cost in any model; not a verified zero. |
| **bed_backlight** | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | — | Flat 0.0 kWh, stale source — no cost in any model; not a verified zero. |
| **tv** | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | — | Flat 0.0 kWh, stale source — no cost in any model; not a verified zero. |
| **TOTAL** | **3.6965** | **3.5019** | **0.6382** | **+2.8637** | **+3.0583** | **+479.2 %** | See headline below. |

**Two independent drivers of the divergence:**
1. **EV catch-up jump (~64 % of the gap):** the entire window's EV counter movement
   (882.80 → 897.99 = 15.19 kWh) landed in **one 15-min slot** (06:00) while
   `ev_status=charger_pause` at both ends — physically impossible (60.8 kW). Crude models
   bank all 15.19 kWh; NEW excludes it (€0). Alone this is +€1.85 (CUR) / +€1.95 (OLD).
2. **Load-shifting blindness (~36 % of the gap):** even with EV removed, OLD/CUR still
   overstate by **≈ +€1.02–1.11 (+159 %–174 %)**, dominated by `boiler_ten`. The Nord Pool
   automation deliberately heats at the **cheapest** slots (boiler's effective NEW price
   0.028 €/kWh vs the 0.122 €/kWh blended avg), so pricing daily kWh at a blended/midpoint
   price systematically over-charges every price-following load.

---

## Section B — Delta reconciliation (per device)

Reconciled against `meter_delta_rules.json` and `METER_DELTA_FORENSICS.md`.
`conf/inc/exc` = confirmed / incomplete / excluded 15-min interval rows. Spot € is the NEW
interval-matched total. All numbers reproduce the forensics doc exactly.

| Device | Raw Δ kWh | Accepted Δ kWh | Excluded Δ kWh | conf/inc/exc | Coverage | Spot € (NEW) | Quality | Reason |
|--------|----------:|---------------:|---------------:|:------------:|---------:|-------------:|:-------:|--------|
| `ev` | 15.1900 | **0.0000** | 15.1900 | 94/0/1 | 98.9 % | 0.0000 | **SUSPECT** | 1 reconnect/catch-up jump (15.19 kWh > 5.5 cap) EXCLUDED; unpriceable at one slot's price. |
| `boiler_ten` | 10.5760 | **10.5760** | 0.0000 | 95/0/0 | 100.0 % | 0.2978 | OK | Clean monotonic ramp, all deltas ≤ 0.875 cap; ~10.6 kWh all included. |
| `hydrophore` | 2.4800 | **1.9800** | 0.0000 | 93/2/0 | 97.9 % | 0.2964 | MEDIUM | Real ~2 kWh pump load included; 0.5 kWh over 1 unavailable snapshot → 2 incomplete intervals, dropped from priced total (never zeroed). |
| `aquarium` | 0.5170 | **0.5170** | 0.0000 | 95/0/0 | 100.0 % | 0.0376 | OK | Clean ramp, all deltas ≤ 0.0375 cap; fully included. |
| `recirc` | 0.0370 | **0.0370** | 0.0000 | 95/0/0 | 100.0 % | 0.0064 | OK | Clean ramp, ≤ 0.025 cap; fully included. |
| `towel` | 0.0000 | **0.0000** | 0.0000 | 95/0/0 | 100.0 % | 0.0000 | **LOW** | Flat 0.0; source `updated` never advanced (distinct_updated=1) — ambiguous off vs dead, not a verified zero. |
| `bed_backlight` | 0.0000 | **0.0000** | 0.0000 | 95/0/0 | 100.0 % | 0.0000 | **LOW** | Flat 0.0; stale source (distinct_updated=1) — not a verified zero. |
| `tv` | 0.0000 | **0.0000** | 0.0000 | 95/0/0 | 100.0 % | 0.0000 | **LOW** | Flat 0.0; stale source (distinct_updated=1) — not a verified zero. |
| **TOTAL (included)** | **28.8000** | **13.1100** | 15.1900 | 757/2/1 | 99.6 % | **0.6382** | | Accepted 13.11 kWh = boiler 10.576 + hydrophore 1.98 + aquarium 0.517 + recirc 0.037. |

_Coverage = confirmed ÷ recorded interval rows. 8 devices × 95 intervals = 760 rows =
757 confirmed + 2 incomplete (hydrophore gap) + 1 excluded (EV jump)._

---

## Section C — Anomalies (from `energy_shadow_quality.json`)

7 anomalies flagged by the QA staleness heuristic. **Implied power = Δ ÷ 0.25 h.**
Decision = what the interval accumulator (`meter_delta_rules.json` plausibility caps) does.

| ts (local) | Device | before → after (kWh) | Δ kWh | Implied kW | Cause | Decision |
|------------|--------|----------------------|------:|-----------:|-------|----------|
| 2026-07-15 20:15 | hydrophore | 277.79 → *unavailable* | — | — | Source `unavailable` snapshot | **INCOMPLETE** — 2 intervals; 0.5 kWh real but unpriceable, dropped (never zeroed) |
| 2026-07-16 06:00 | ev | 882.80 → 897.99 | 15.190 | **60.76** | Tuya cloud counter frozen ~8 h then catch-up (paused both ends) | **EXCLUDED** — 15.19 > 5.5 cap; implausible spike, not banked |
| 2026-07-16 06:30 | hydrophore | 278.63 → 278.78 | 0.150 | 0.60 | `updated` frozen ~6.7 h then caught up | **INCLUDED** — 0.15 ≤ 0.375 cap; plausible magnitude |
| 2026-07-16 06:45 | recirc | 0.023 → 0.024 | 0.001 | 0.004 | Coarse ~30-min reporting cadence | **INCLUDED** — 0.001 ≤ 0.025 cap |
| 2026-07-16 09:00 | aquarium | 0.101 → 0.102 | 0.001 | 0.004 | Coarse ~30-min reporting cadence | **INCLUDED** — 0.001 ≤ 0.0375 cap |
| 2026-07-16 10:00 | boiler_ten | 1.033 → 1.409 | 0.376 | 1.50 | `updated` frozen then caught up | **INCLUDED** — 0.376 ≤ 0.875 cap; plausible |
| 2026-07-16 17:45 | recirc | 0.038 → 0.039 | 0.001 | 0.004 | Coarse ~30-min reporting cadence | **INCLUDED** — 0.001 ≤ 0.025 cap |

**Key reconciliation:** the QA staleness flags (7) are **not** the same as accumulator
exclusions. Only **1** anomaly is actually excluded from cost (EV, magnitude implausible) and
**1** is incomplete (hydrophore unavailable). The other **5** are staleness/cadence artefacts
whose magnitude is physically plausible, so the accumulator **keeps** them — correctly. No
counter resets (Δ < 0) occurred on any device.

---

## Headline divergence

> Over this frozen ~24 h window the **spot-only** cost is **€0.64** by the trustworthy
> **interval model**. The **current production proxy** (`total−midnight`) reports **€3.50**
> and the **old** `(min+max)/2 × daily-kWh` model **€3.70** — i.e. the crude models
> **overstate spot cost by +449 % and +479 %** (≈ 4.5×–4.8×).
>
> **Why:** (1) the EV Tuya counter dumped a full **15.19 kWh** into one 15-min slot
> (implied 60.8 kW while paused) — crude models bank it, the interval model excludes it as
> unpriceable (~64 % of the gap); (2) price-following loads (chiefly the boiler) run at the
> **cheapest** slots, so pricing daily kWh at a blended/midpoint price over-charges them
> (~36 % of the gap; ≈ +€1.0–1.1 even with EV removed). The interval model is the only one
> that both drops the impossible spike and prices each kWh at the slot it was actually used.

**This is a spot-only PRELIMINARY comparison.** Tariff add-ons and VAT are all `NULL` and
were not applied. These figures are for model validation only and **must not be presented as
a bill or as `cost_month` truth**. Do not switch production cost to the interval model until
the tariff is filled and the shadow window is signed off (see `TARIFF_INPUT_REQUIRED.md`).

---

## Reproduce

```
python3 <scratchpad>/dryrun_cost.py          # LOCAL, read-only; temp SQLite, auto-deleted
# loads: docs/audit/shadow_evidence/shadow_snapshots.frozen.jsonl
#        docs/audit/meter_delta_rules.json  (via tools/energy_cost/accumulator.py)
```

The accumulator (`tools/energy_cost/accumulator.py`) parses the frozen JSONL read-only,
prices each interval at its own Nord Pool slot price, excludes spikes/resets/gaps per
`meter_delta_rules.json`, and never zero-fills a missing reading.

### Integrity — frozen ledger unchanged after run

| Metric | Before | After |
|--------|--------|-------|
| mtime | 1784216316.816 | 1784216316.816 (unchanged) |
| sha256 | `8191d6ea…3e54d2` | `8191d6ea…3e54d2` (unchanged) |
| bytes | 142041 | 142041 |

No secrets read, printed, or written. Temp SQLite DB removed after the run.
