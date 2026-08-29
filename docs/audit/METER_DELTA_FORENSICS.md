# Meter-Delta Forensics — Frozen Shadow Ledger

_Generated 2026-07-16T15:45:38+00:00 by `tools/energy_cost` meter-delta-agent. READ-ONLY over the FROZEN ledger; no ledger/production/device was modified._

## Source

- Ledger: `docs/audit/shadow_evidence/shadow_snapshots.frozen.jsonl` (immutable, read-only)
- Records: **96** → **95** consecutive intervals
- Window: `2026-07-15T18:46:59+03:00` → `2026-07-16T18:30:00+03:00` (~23.72 h, +03:00 EEST)
- Interval width: 0.25 h nominal (15 min)
- Devices: `ev`, `boiler_ten`, `towel`, `aquarium`, `recirc`, `hydrophore`, `bed_backlight`, `tv`

## Threshold methodology

Per-device rule (NOT one universal threshold):

> `max_interval_kwh = plausible_power_kW × 0.25 h`

An interval delta **>** the device's `max_interval_kwh` is flagged as a **reconnect / catch-up jump** (cumulative counter reported a stale value then caught up in one slot). A delta **< 0** is a **reset** (counter dropped/rebased). **No nameplate power is exposed in Home Assistant** (verified read-only: the only power sensor is `sensor.75_qled_power`, unrelated). Every threshold below is therefore **heuristic** — a device-class typical with headroom above that device's own observed max delta. Flagged intervals are **excluded from accepted totals but never deleted** from the ledger; they are surfaced for review, not silently dropped. Missing / unavailable readings are never counted as 0.

## Per-device summary

| Device | Raw Δ kWh | Accepted Δ kWh | Excluded Δ kWh | Valid/Total iv | Coverage | Unavail | Resets | Jumps | Total | Confidence |
|---|--:|--:|--:|:--:|--:|--:|--:|--:|:--:|:--:|
| `ev` | 15.1900 | 0.0000 | 15.1900 | 94/95 | 98.9% | 0 | 0 | 1 | EXCLUDED | SUSPECT |
| `boiler_ten` | 10.5760 | 10.5760 | 0.0000 | 95/95 | 100.0% | 0 | 0 | 0 | INCLUDED | OK |
| `towel` | 0.0000 | 0.0000 | 0.0000 | 95/95 | 100.0% | 0 | 0 | 0 | INCLUDED | LOW |
| `aquarium` | 0.5170 | 0.5170 | 0.0000 | 95/95 | 100.0% | 0 | 0 | 0 | INCLUDED | OK |
| `recirc` | 0.0370 | 0.0370 | 0.0000 | 95/95 | 100.0% | 0 | 0 | 0 | INCLUDED | OK |
| `hydrophore` | 2.4800 | 1.9800 | 0.0000 | 93/95 | 97.9% | 1 | 0 | 0 | INCLUDED | MEDIUM |
| `bed_backlight` | 0.0000 | 0.0000 | 0.0000 | 95/95 | 100.0% | 0 | 0 | 0 | INCLUDED | LOW |
| `tv` | 0.0000 | 0.0000 | 0.0000 | 95/95 | 100.0% | 0 | 0 | 0 | INCLUDED | LOW |
| **TOTAL (included)** | | **13.1100** | | | | | | | | |

_Coverage = valid priced intervals / total intervals. `Accepted Δ` excludes flagged (jump/reset) and gap-spanning deltas. `Excluded Δ` is energy in flagged jump/reset intervals — real cumulative energy but unattributable to the 15-min slot/price it landed in._

## Delta distribution & thresholds per device

| Device | Max Δ | Median Δ | p95 Δ | Nonzero iv | Plausible kW | Max iv kWh | Src |
|---|--:|--:|--:|--:|--:|--:|:--:|
| `ev` | 15.1900 | 0.0000 | 0.0000 | 1 | 22.0 | 5.5 | heuristic |
| `boiler_ten` | 0.7580 | 0.0000 | 0.7508 | 25 | 3.5 | 0.875 | heuristic |
| `towel` | 0.0000 | 0.0000 | 0.0000 | 0 | 0.7 | 0.175 | heuristic |
| `aquarium` | 0.0240 | 0.0000 | 0.0230 | 24 | 0.15 | 0.0375 | heuristic |
| `recirc` | 0.0040 | 0.0000 | 0.0030 | 14 | 0.1 | 0.025 | heuristic |
| `hydrophore` | 0.2700 | 0.0000 | 0.1840 | 17 | 1.5 | 0.375 | heuristic |
| `bed_backlight` | 0.0000 | 0.0000 | 0.0000 | 0 | 0.1 | 0.025 | heuristic |
| `tv` | 0.0000 | 0.0000 | 0.0000 | 0 | 0.4 | 0.1 | heuristic |

## Threshold reasoning & findings (per device)

### `ev` — EV charger (Tuya cloud cumulative kWh)

- **Confidence: SUSPECT · Total: EXCLUDED**
- First reading: 882.8 kWh · Last: 897.99 kWh · Raw Δ: 15.19 kWh
- Accepted Δ (sum of valid 15-min deltas): **0.0 kWh** over 94 valid intervals
- Threshold: plausible **22.0 kW** → **5.5 kWh/15min** (source: heuristic). Home AC charger max ~22 kW (3-phase 32A); the box's charger is likely single-phase 7.4 kW. Cap set at 22 kW (5.5 kWh/15min) so ANY plausible real charge passes; nothing observed here comes close to legitimate charging anyway.
- **Flagged intervals (1)** (excluded, retained in ledger):
  - `2026-07-16T05:45:00+03:00` → `2026-07-16T06:00:00+03:00`: Δ **15.19 kWh**, implied **60.76 kW** over 15.0 min — reconnect/catch-up jump > plausible 5.5 kWh

### `boiler_ten` — Boiler electric heating element (TEN / DHW)

- **Confidence: OK · Total: INCLUDED**
- First reading: 1.033 kWh · Last: 11.609 kWh · Raw Δ: 10.576 kWh
- Accepted Δ (sum of valid 15-min deltas): **10.576 kWh** over 95 valid intervals
- Threshold: plausible **3.5 kW** → **0.875 kWh/15min** (source: heuristic). Electric DHW heating element, class 2-3 kW. Observed max delta 0.758 kWh/15min = 3.03 kW. Threshold 3.5 kW (0.875 kWh) sits just above the observed physical max.

### `towel` — Towel warmer (kalarifer, 1F bath)

- **Confidence: LOW · Total: INCLUDED**
- First reading: 0.0 kWh · Last: 0.0 kWh · Raw Δ: 0.0 kWh
- Accepted Δ (sum of valid 15-min deltas): **0.0 kWh** over 95 valid intervals
- Threshold: plausible **0.7 kW** → **0.175 kWh/15min** (source: heuristic). Towel warmer ~0.5-0.6 kW. Threshold 0.7 kW (0.175 kWh). No movement observed.
- **Stale source**: the `updated` timestamp NEVER advanced across the 24h window (distinct_updated=1). Flat 0.0 is therefore NOT a verified measured zero — the sensor may be off OR not reporting. Not trustworthy as real consumption evidence.

### `aquarium` — Aquarium light

- **Confidence: OK · Total: INCLUDED**
- First reading: 0.024 kWh · Last: 0.541 kWh · Raw Δ: 0.517 kWh
- Accepted Δ (sum of valid 15-min deltas): **0.517 kWh** over 95 valid intervals
- Threshold: plausible **0.15 kW** → **0.0375 kWh/15min** (source: heuristic). Aquarium light ~0.1 kW. Observed max 0.024 kWh/15min = 0.096 kW. Threshold 0.15 kW (0.0375 kWh).

### `recirc` — Hot-water recirculation / turtle pump

- **Confidence: OK · Total: INCLUDED**
- First reading: 0.002 kWh · Last: 0.039 kWh · Raw Δ: 0.037 kWh
- Accepted Δ (sum of valid 15-min deltas): **0.037 kWh** over 95 valid intervals
- Threshold: plausible **0.1 kW** → **0.025 kWh/15min** (source: heuristic). Small recirculation pump. Observed max 0.004 kWh/15min = 0.016 kW. Threshold 0.1 kW (0.025 kWh).

### `hydrophore` — Water booster pump (gidrofor)

- **Confidence: MEDIUM · Total: INCLUDED**
- First reading: 276.63 kWh · Last: 279.11 kWh · Raw Δ: 2.48 kWh
- Accepted Δ (sum of valid 15-min deltas): **1.98 kWh** over 93 valid intervals
- Unpriced across unavailable gap: **0.5 kWh** (2 incomplete interval(s), 1 unavailable snapshot(s)) — real energy, dropped from priced total (never zeroed)
- Threshold: plausible **1.5 kW** → **0.375 kWh/15min** (source: heuristic). Water booster pump ~1.1 kW. Observed max 0.27 kWh/15min = 1.08 kW. Threshold 1.5 kW (0.375 kWh).

### `bed_backlight` — Bed LED backlight

- **Confidence: LOW · Total: INCLUDED**
- First reading: 0.0 kWh · Last: 0.0 kWh · Raw Δ: 0.0 kWh
- Accepted Δ (sum of valid 15-min deltas): **0.0 kWh** over 95 valid intervals
- Threshold: plausible **0.1 kW** → **0.025 kWh/15min** (source: heuristic). LED strip. Threshold 0.1 kW (0.025 kWh). No movement observed.
- **Stale source**: the `updated` timestamp NEVER advanced across the 24h window (distinct_updated=1). Flat 0.0 is therefore NOT a verified measured zero — the sensor may be off OR not reporting. Not trustworthy as real consumption evidence.

### `tv` — TV zone

- **Confidence: LOW · Total: INCLUDED**
- First reading: 0.0 kWh · Last: 0.0 kWh · Raw Δ: 0.0 kWh
- Accepted Δ (sum of valid 15-min deltas): **0.0 kWh** over 95 valid intervals
- Threshold: plausible **0.4 kW** → **0.1 kWh/15min** (source: heuristic). TV + zone ~0.2 kW. Threshold 0.4 kW (0.1 kWh). No movement observed.
- **Stale source**: the `updated` timestamp NEVER advanced across the 24h window (distinct_updated=1). Flat 0.0 is therefore NOT a verified measured zero — the sensor may be off OR not reporting. Not trustworthy as real consumption evidence.

## Key findings

1. **EV — SUSPECT, total EXCLUDED.** The entire window's movement (882.80 → 897.99, raw Δ 15.19 kWh) occurred in a **single 15-min interval** (05:45→06:00) while `ev_status = charger_pause` at BOTH ends — implied **60.76 kW**, ~11× a 5.5 kWh cap. This is a Tuya cloud cumulative-counter catch-up, not real 15-min consumption. The 15.19 kWh is real cumulative energy but cannot be priced at that slot's Nord Pool price. Accepted plausible consumption in-window = **0 kWh**. Flag & review; do NOT bank at the 06:00 price.
2. **hydrophore — MEDIUM.** One `unavailable` snapshot (2026-07-15 20:15) breaks 2 intervals; ~0.50 kWh consumed across that gap is real but unpriceable → excluded from the priced total (1.98 of 2.48 kWh accepted). Coverage 97.9%.
3. **towel / bed_backlight / tv — LOW.** Their source `updated` timestamp never advanced across the full 24h (distinct_updated=1, frozen at ~15:11-15:12 UTC before collection began). Flat 0.0 kWh is ambiguous (off vs. dead sensor) and must not be treated as a verified measured zero.
4. **boiler_ten / aquarium / recirc — OK.** Clean monotonic ramps, all deltas within plausible power caps, no resets or jumps. boiler_ten max 0.758 kWh/15min (3.03 kW) is consistent with a ~3 kW electric element.
5. **No counter resets (delta<0)** on any device across the window.

## Caveats

- All thresholds are **heuristic** (no HA nameplate power). Before any production rule auto-drops data, an owner/reviewer should confirm the EV charger's real max power and the boiler element rating.
- Flagged intervals are **flagged, not deleted**. The frozen ledger is untouched.
- `stale_snapshots` in the machine rules counts source-`updated` lag; for idle total_increasing counters an old `updated` is normal (HA writes state on change only). The reliable stale signal is `distinct_updated_timestamps == 1`.

## Outputs

- `docs/audit/METER_DELTA_FORENSICS.md` (this file)
- `docs/audit/meter_delta_rules.json` (machine-readable per-device quality rules)
