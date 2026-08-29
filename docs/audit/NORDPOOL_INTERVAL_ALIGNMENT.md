# Nord Pool ↔ Energy Interval Alignment Verdict

_Generated 2026-07-16 (Europe/Riga) by `nordpool-alignment-agent`. READ-ONLY analysis._
_Ledger analysed: `docs/audit/shadow_evidence/shadow_snapshots.frozen.jsonl`_
_sha256 `8191d6ea544092bc521d4f4f9e2e8d3a8dfe8dde9f27cd7ea4359383193e54d2` (matches CUSTODY.md — frozen, 96 records, 142041 bytes)._

---

## Verdict

**ALIGNMENT: PASS.** Every energy delta in the shadow pipeline is priced with the
Nord Pool price of the **same 15-minute interval**. Independent cross-check against
Elering NPS day-ahead history gives **96 / 96 exact price matches, 0 mismatches**.
Units, timezone, interval-start semantics, and 15-min granularity are all correct.
No forbidden practice (daily-avg pricing, silent interpolation, missing-as-zero,
hourly/15-min mixing) is present in the ledger or the cost model.

| Question | Finding |
|---|---|
| Source of truth | `sensor.nord_pool_lv_current_price` (HA Nord Pool LV integration), **EUR/kWh** |
| Independent verification | Elering NPS API (`dashboard.elering.ee/api/nps/price`, EUR/MWh) — 96/96 match after ÷1000 |
| Ledger mismatches vs Nord Pool history | **0** |
| Interval semantics | Price = slot that **contains/starts at** the snapshot `ts` (START-of-interval) |
| Product granularity | **15-minute** (both the sensor and Elering; :00/:15/:30/:45) |
| Unit / scale | EUR/kWh already; **no MWh→kWh scaling applied or needed** in the ledger |
| Negative prices | None in window (min 0.012); model does not clamp — correct |
| Missing prices | 0 unavailable in window; model yields `None`+flag, never 0 — correct |
| DST | 2026-07-16 is not a DST day; all offsets `+03:00` EEST; math in UTC — correct |

---

## 1. Source of truth

The ledger `price.current` mirrors **`sensor.nord_pool_lv_current_price`** — the HA
Nord Pool LV integration, expressed in **EUR/kWh** (the integration already divides
by 1000; observed range **0.012 – 0.2447**, unmistakably per-kWh, not per-MWh).

This was verified against a fully independent authority — the **Elering NPS
day-ahead API** for market area `lv` over the ledger window
(`2026-07-15T15:00Z … 2026-07-16T16:00Z`). Elering returns **EUR/MWh on a 15-minute
grid** (101 points, minutes {00,15,30,45}). After ÷1000 the two agree to 1e-6 on
every comparable slot (examples):

| Slot start (UTC) | Elering EUR/MWh | ÷1000 EUR/kWh | Ledger `current.v` |
|---|---|---|---|
| 15:45 | 150.70 | 0.15070 | 0.15070 ✓ |
| 16:00 | 125.15 | 0.12515 | 0.12515 ✓ |
| 16:15 | 143.83 | 0.14383 | 0.14383 ✓ |

**Rule for cross-checking Elering:** its `timestamp` is the **period START** in Unix
seconds **UTC**, price in **EUR/MWh** → divide by 1000 for EUR/kWh. Do not treat the
Elering timestamp as an end or as local time.

---

## 2. Interval semantics — START, not END

Snapshots are taken on the quarter-hour boundary (`ts` = :00/:15/:30/:45 local; the
only exception is the collector-start record `18:46:59`). For each snapshot:

- `ts_local → ts_utc` and the slot is `[floor15(ts_utc), floor15(ts_utc)+15min)`.
- `price.current.v` is the Nord Pool price for **that** slot (the slot that begins at,
  and contains, the snapshot instant). This is **START-of-interval** semantics.

The cost model / QA (`tools/energy_cost/shadow_qa.py`, `model.price_for_interval`)
prices the **forward** counter delta `[ts_i, ts_{i+1})` with `current.v` at `ts_i`.
Because `ts_i` is the slot start, this is exact interval-matched pricing:

```
spot_cost_interval = valid_energy_delta_kwh[ts_i → ts_{i+1}] × current.v[ts_i]
```

Cross-check (keyed on `ts→slot`, the correct method): **96/96 snaps** had
`current.v == Elering[slot_start]`. Verdict: energy consumed in a slot is priced at
the price actually in force during that slot.

---

## 3. `updated` field is `last_changed`, NOT slot start — do NOT key on it

Three snaps (`2026-07-16 12:00`, `13:30`, `14:30` local) carry a `price.current.updated`
timestamp exactly one 15-min slot behind their `ts`. This initially looks like a stale
/ skipped price tick, **but it is benign**: HA's `updated`/`last_changed` only advances
when the sensor **value changes**. In all three cases the previous slot and the current
slot had the **identical** price (0.014, 0.02, 0.02001), confirmed against Elering
(e.g. Elering `09:00Z = 0.014`, same as `08:45Z`). So the value was correct for the
slot; only the change-timestamp had not moved.

**Consequence / guidance:**
- Key interval→price matching on the snapshot **`ts`** (as the model does), **not** on
  `price.current.updated`. Using `updated` as a slot-start proxy produces 3 false
  "stale" flags in this window.
- `shadow_qa.py`'s staleness heuristic (`lag > 20 min`) does not fire here (lag is
  exactly 15 min) — harmless, because the values are in fact correct. If a *true* late
  update ever occurs (value wrong for the slot), the >20-min lag rule may still miss a
  single-slot lag; the authoritative detector is the Elering cross-check in this report,
  not the lag heuristic.

---

## 4. 15-minute product confirmed (no hourly/15-min mixing)

Both the HA sensor and Elering deliver **15-minute** prices for LV. Evidence:
- `price.current.updated` timestamps land only on :00/:15/:30/:45 UTC (96/96).
- `next[i]` chains to `current[i+1]` across every clean 15-min boundary (0 breaks).
- Consecutive quarters within an hour carry **distinct** prices
  (e.g. 16:00Z 0.12515 / 16:15Z 0.14383 / 16:30Z 0.15902 / 16:45Z 0.18066).
- `lowest`/`highest` `start` attributes appear at :30 and :45 — sub-hourly.
- `model.PRICE_STEP` / grid step = 15 min (`tools/energy_cost/`).

There is **no** hourly product in the ledger, so no hourly-vs-15-min aggregation risk
inside the analysed data. (Long-term HA statistics are hourly-mean and are explicitly
documented as approximation-only in `ha_source.py` — do not feed those into the
per-interval spot total.)

---

## 5. Timeline / DST / gaps

- Interval widths: **94 × 15.0 min + 1 × 13.0 min** (the first, collector-start
  interval `18:46:59 → 19:00`). The short first interval is priced with its own slot
  price (0.1507, matches Elering) — correct, just narrower.
- **No gaps** > 16 min; **no duplicate** timestamps.
- All `ts` offsets are `+03:00` (EEST). **2026-07-16 is not a DST transition day**, so
  no repeated/short-hour handling was exercised. The model performs interval math in
  **UTC** and calendar bucketing in **Europe/Riga** (DST-length days handled by
  `day_bounds`/`month_bounds`), which is the correct design.

---

## 6. Missing / negative price handling (rules verified in code)

- **Missing price** → `cost_interval` returns `total=None`, flag `E`, excluded from
  sums. **Never zero, never interpolated.** (0 missing prices in this window.)
- **Missing energy / gap-touched interval** → `total=None`, flag `D`, excluded. Never
  zero-filled; carry-forward 0.0 deltas across an `unavailable` reading are explicitly
  discarded (`shadow_qa.interval_flag`).
- **Negative prices** are not clamped (`spot = kwh*price` may be negative) — correct
  Nord Pool behaviour. None occurred in this window (min 0.012), so untested live but
  the rule is right.
- **Tomorrow publication (~13:00):** `price.next` is populated throughout; not required
  for historical alignment, but confirms the day-ahead feed was healthy.

---

## 7. Forbidden-practice audit

| Forbidden practice | Present? |
|---|---|
| daily energy × average price | **No** — model sums per-interval products only |
| `(lowest+highest)/2` style averaging | **No** (that is the *old HA automation*; the shadow model does not do it) |
| interpolating a missing price without a quality flag | **No** — missing ⇒ `None` + flag `E` |
| treating missing price as zero | **No** |
| mixing hourly and 15-min prices without explicit aggregation | **No** — ledger is pure 15-min |

---

## 8. Interval-matched pricing rule (authoritative)

```
For each device, for each 15-min slot [t, t+15min):
    delta_kwh   = counter(t+15) − counter(t)          # reset-detected; None if any endpoint unavailable
    price       = nord_pool_lv_current_price for the slot starting at t   # EUR/kWh, START-of-interval
    if delta_kwh is None or price is None:
        interval_cost = None            # excluded from totals; flagged D/E — NEVER 0
    else:
        interval_cost = delta_kwh × price   # negative prices allowed; not clamped
day/month_cost = Σ usable interval_cost   # UTC math, Europe/Riga calendar bucketing
```

Match the price to the slot by the snapshot **`ts`** (converted to UTC, floored to the
15-min grid), **not** by `price.current.updated`.

---

## Summary for caller

- **Alignment verdict:** PASS — each energy delta is priced with the same-interval
  15-min Nord Pool price.
- **Source of truth:** `sensor.nord_pool_lv_current_price` (EUR/kWh), independently
  confirmed against Elering NPS (EUR/MWh ÷ 1000).
- **Mismatch count:** 0 (96/96 slots match Elering history).
- **Pricing rule:** `spot_cost = interval_kWh × price_EUR_per_kWh`, price = slot that
  starts at the snapshot `ts`; missing/negative handled per §6; never zero-for-missing.
- **One caveat:** key price↔interval matching on `ts`, not on `current.updated`
  (`updated` = `last_changed`, lags one slot when consecutive slots share a price).
