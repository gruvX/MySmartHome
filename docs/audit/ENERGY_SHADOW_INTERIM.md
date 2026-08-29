# Energy Shadow Ledger — Interim QA Report

_Generated 2026-07-15 (Europe/Riga) by `tools/energy_cost/shadow_qa.py` over an SSH-pulled read-only copy of `/config/shadow_snapshots.jsonl`. READ-ONLY analysis; raw snapshots left intact, no historical value edited. This does NOT replace production monthly cost accounting (`cost_month_*`)._

**PRELIMINARY / тестовый** — this is an early checkpoint over a partial collection window, not a full 24 h. All kWh / cost figures below are provisional and must NOT be used for billing or to replace the production monthly totals.

## 1. Collection overview

- Snapshots collected: **13**
- Consecutive intervals analysed: **12**
- Window: `2026-07-15T18:46:59+03:00` → `2026-07-15T21:45:00+03:00` (**~2.97 h elapsed**)
- Ledger file: **19209 bytes**, perms `644`, owner `root:root`
- Nominal cadence: 15 min → **96 snapshots/day** expected at full coverage
- Coverage vs a full day so far: **13/96** (13.5%) of a 24 h ledger

## 2. Secret-leak scan of the ledger

- **0 secrets found** in the ledger. PASS. (Ledger holds only numeric energy/price + non-secret context strings.)

## 3. Timeline integrity / cadence health

- Duplicate timestamps: **0**
- Missing-interval gaps (> 25 min): **0** — cadence is healthy (min/median/max inter-snapshot = 13.0 / 15.0 / 15.0 min)
- Off-grid intervals (width ≠ 15±1 min): **1** (flagged B, cost still computed):
  - `2026-07-15T18:46:59+03:00` → `2026-07-15T19:00:00+03:00` = 13.0 min (collector started mid-cycle — cosmetic)
- Timezone/DST offset issues: **0**
  - All timestamps carry the correct Europe/Riga offset (+03:00 EEST for July). DST handling OK.

## 4. Nord Pool price QA

- Price present on **13/13** snapshot slots (100.0%).
- No stale-price lag detected: `current` price `updated` timestamps land on the 15-min UTC boundary (:00/:15/:30/:45), confirming 15-min alignment.
- NOTE: the `current`/`next` Nord Pool sensors expose **no `start` attribute** (only `lowest`/`highest` do; snapshot carries `start: null`), so per-slot 15-min alignment is validated via each reading's `updated` timestamp and the snapshot `ts`, not via a price `start` field.

## 5. Per-device data completeness

| Device | Snap avail | Interval priced | Resets | Unavail/null snaps | No-cost intervals (D/E) |
|---|---|---|---|---|---|
| `ev` | 13/13 (100.0%) | 12/12 (100.0%) | 0 | 0 | 0 |
| `boiler_ten` | 13/13 (100.0%) | 12/12 (100.0%) | 0 | 0 | 0 |
| `towel` | 13/13 (100.0%) | 12/12 (100.0%) | 0 | 0 | 0 |
| `aquarium` | 13/13 (100.0%) | 12/12 (100.0%) | 0 | 0 | 0 |
| `recirc` | 13/13 (100.0%) | 12/12 (100.0%) | 0 | 0 | 0 |
| `hydrophore` | 12/13 (92.3%) | 10/12 (83.3%) | 0 | **1** | **2** |
| `bed_backlight` | 13/13 (100.0%) | 12/12 (100.0%) | 0 | 0 | 0 |
| `tv` | 13/13 (100.0%) | 12/12 (100.0%) | 0 | 0 | 0 |

### 5a. Unavailable / reset detail

- `hydrophore` unavailable (`raw: "unavailable"`, `v: null`) at exactly one slot: `2026-07-15T20:15:00+03:00`. Counted as **missing**, never as 0. The two intervals touching that slot (20:00→20:15 and 20:15→20:30) carry **no cost** (D flag); the ~0.50 kWh that flowed across the dropout is therefore excluded from the priced total, not fabricated.
- **No counter resets** detected on any device (all cumulative series monotonic non-decreasing).

### 5b. Hydrophone anomaly

- `hydrophore` (`sensor.zigbee_plug_2_total_energy`, Zigbee plug 2) is by far the dominant consumer in this window: raw total climbed `276.63 → 278.49 kWh` (~1.86 kWh raw over ~3 h ≈ **~620 W near-continuous draw**), of which **1.36 kWh** is priced (rest excluded across the dropout). It accounts for **~93%** of all observed consumption in the window.
- It is also the **only** device that flapped to `unavailable` (single Zigbee/WiFi dropout at 20:15). This pairing — a steady heavy load plus an intermittent radio — is the flagged hydrophone anomaly: worth watching whether the dropout correlates with the load, and whether ~620 W continuous is expected for this device or a stuck/miscounting plug.

## 6. Preliminary window kWh + shadow cost (SPOT energy only) — тестовый

Δ over the observed window (last usable − first usable cumulative reading), priced per-interval at the Nord Pool price in force. This is the **collection-window** figure since the collector started — **NOT** a full calendar-day total (no midnight anchor snapshot exists yet). Missing intervals are excluded, never counted as 0. **Does not replace production `cost_month_*` accounting.**

| Device | Window kWh (priced) | Shadow spot cost € | Quality flags |
|---|---|---|---|
| `ev` | 0.0000 | 0.00000 | `BAAAAAAAAAAA` |
| `boiler_ten` | 0.0000 | 0.00000 | `BAAAAAAAAAAA` |
| `towel` | 0.0000 | 0.00000 | `BAAAAAAAAAAA` |
| `aquarium` | 0.0770 | 0.01239 | `BAAAAAAAAAAA` |
| `recirc` | 0.0190 | 0.00341 | `BAAAAAAAAAAA` |
| `hydrophore` | 1.3600 | 0.21844 | `BAAAADDAAAAA` |
| `bed_backlight` | 0.0000 | 0.00000 | `BAAAAAAAAAAA` |
| `tv` | 0.0000 | 0.00000 | `BAAAAAAAAAAA` |
| **TOTAL (observed devices)** | **1.4560** | **≈ 0.234 (PRELIMINARY)** | |

_Idle in this window (0 Δ): ev (flat 882.8 kWh — no charging), boiler_ten (flat 1.033), towel (flat 0.0), bed_backlight, tv._

_Flags: A usable · B off-grid width but priced · C reset (priced) · D energy missing or interval touched an unavailable reading (no cost, delta uncertain) · E price missing (no cost)._

Interval cost is **computable**: `Δ_kWh × price_of_that_interval` via `tools/energy_cost/model.py` (`interval_energy` + `price_for_interval` + `cost_interval`, SPOT_ONLY tariff — no invented VAT/distribution add-ons).

## 7. Data-quality findings summary

1. **hydrophore** — 1 unavailable/null snapshot (20:15), 2 no-cost intervals, ~0.50 kWh un-priced across the dropout; also the anomalous dominant load (see 5b). Only device with a coverage gap.
2. **No resets, no missing prices, no duplicate timestamps, no DST issues.**
3. **First interval off-grid** (13 min) — collector start artefact only.
4. All idle devices report legitimately flat cumulative totals (not missing) — their 0 Δ is real, not a substituted zero.

## 8. Readiness assessment for the 24 h / 48 h checkpoint

- Pipeline status: collector is appending valid JSON lines (0 parse errors); parser, QA, and cost model all run end-to-end. **13 snapshots** so far.
- Cadence health: **healthy** — 0 gaps > 25 min, all inner intervals 15.0 min.
- At 15-min cadence, a 24 h checkpoint needs ~96 snapshots and 48 h needs ~192; currently at 13. Projected time to a full 24 h span: **~21 h more** (~45 h more for 48 h).
- Worst per-device interval completeness so far: **83.3%** (`hydrophore`, due to the single dropout).
- Still needed before proposing the production interval-cost model switch:
  1. Ledger must span **local midnight** to give a clean per-calendar-day anchor (none yet).
  2. A full **24–48 h clean window** with the hydrophore dropout behaviour characterised (transient vs recurring).
  3. Confirm no counter resets survive a full day, and that idle/flat devices stay classified as available-flat (not missing).

**Verdict:** pipeline sound, cadence healthy, interval cost computable — but only ~3 h of a partial window collected. **~21 more hours** of continued collection are needed to reach the first clean 24 h checkpoint (spanning midnight); re-run `tools/energy_cost/shadow_qa.py --pull` to refresh. Do NOT switch production cost accounting yet.
