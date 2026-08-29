# Energy / Statistics Data-Quality Audit

**Scope:** Historical energy sensors + recorder long-term statistics on HA `192.168.1.45:8123`.
**Method:** READ-ONLY. Long-term statistics pulled via WebSocket `recorder/statistics_during_period`
(period `day` covering 2026-06-15..2026-07-14, period `hour` covering 2026-07-08..2026-07-15) and
`recorder/list_statistic_ids`; raw history via REST `/api/history/period` (recent window — recorder
retains ~10 days). Current live values via `/api/states`. **No edits, no reloads, no service calls,
no recorder/statistics changes.**
**Date of audit:** 2026-07-15.

---

## TL;DR — trust matrix (for cost accounting)

| Sensor | Device | Long-term `sum` trustworthy for cost? | Notes |
|---|---|---|---|
| `sensor.zigbee_plug_2_total_energy` | "Гидрофон" (gidro) — **79% of monthly €** | **YES** (with caveat) | Monotonic total; frequent unavailable flapping loses granularity, not totals |
| `sensor.boiler_total_energy` | Boiler ТЭН | **YES** (with caveat) | Daily-resetting counter; HA reset-detection keeps `sum` monotonic. **1 lost day (2026-07-04, plug offline)** |
| `sensor.akvarium_svet_total_energy` | Aquarium light | **YES** | Daily-reset counter, `sum` clean ~0.53 kWh/day |
| `sensor.cherepakha_total_energy` | Turtle/recirc | **YES** | Daily-reset counter, `sum` clean |
| `sensor.terarium_total_energy` | Полотенцесушитель (towel, `kalarifer_socket_1`) | **MOSTLY** | Daily-reset counter; name/device mismatch; low usage |
| `sensor.ev_charger_energy` | EV charger | **PARTIAL** | Lifetime total OK; **daily/period attribution unreliable** (stale command_line → 110 kWh dumped on one day) |
| `sensor.zigbee_plug_total_energy` | (plug #1) | **NO — DEAD** | Flat `sum=1.32` all month, `state=0` always. Not used for cost |
| `sensor.75_qled_energy` | TV | **NO — DEAD** | Always 0 |
| `sensor.75_qled_energy_saved` | TV | **NO — DEAD** | Always 0 |
| `sensor.75_qled_power_energy` | TV | **NO — misconfigured** | `state_class=total` on a kWh energy sensor; always 0 |
| `sensor.75_qled_energy_difference` | TV | **NO — misconfigured** | `state_class=total`, oscillates, produces **negative `sum` (-0.001)** |

**No whole-home / grid total energy sensor exists** → sum-of-devices cannot be cross-validated against a house total.

---

## Cross-reference: boiler "resetting to 0" known issue

**Confirmed behaviour (statistics are NOT corrupted by the resets):**
`sensor.boiler_total_energy` is a **daily-resetting** Tuya counter (resets to 0 at ~local midnight,
21:00 UTC). It is declared `state_class: total_increasing`, so HA's reset detection converts each
reset into a delta and the long-term `sum` stays **monotonic**: it climbed **723.914 → 972.610 kWh**
across 2026-06-15..2026-07-14 with per-day deltas of ~5–18 kWh (plausible for a boiler ТЭН).

The **"Гард сброса счётчика энергии"** automation (`id 1786000001001`) protects a *different*
mechanism — the `input_number.midnight_*` daily-cost snapshots — not the recorder. The two
reset-handling paths are independent; both are currently working:
- Recorder `sum`: monotonic (verified above).
- Daily-cost snapshots: `input_number.midnight_boiler_energy=10.099` vs current `state=0` — the boiler
  reset after the snapshot; the guard rebases so today's-cost math doesn't go negative.

**Residual boiler problem — data LOSS on plug-offline days (not resets):**
- **2026-07-04 is entirely MISSING from daily statistics** (30 day-points vs 31 for peers) — the boiler
  smart plug (`switch.smart_plug_2_socket_1`) was offline that day (known open issue). That day's boiler
  consumption is permanently absent from statistics → month total under-counts by ~1 day.
- **2026-06-23** `state` frozen at 21.762 (dSum=0.0, identical to 2026-06-22) — likely a same-day
  freeze/offline before the 06-24 reset; some consumption probably lost.

---

## Per-sensor findings

### 1. `sensor.zigbee_plug_2_total_energy` — "Гидрофон" (cost_month_gidro = 41.85 € = 79% of month)  ⚠ MEDIUM
- Unit `kWh`, `state_class: total_increasing`, `unit_class: energy` — **correct**.
- Long-term `sum` monotonic 182.52 → 252.20 over the month, steady ~2 kWh/day. **Good for cost totals.**
- **Frequent connectivity flapping:** hourly stats show **9 gaps in 2026-07-08..07-10** (largest 10 h).
  Raw history for a single day (2026-07-13) shows **27 unavailable episodes**.
- Impact: `total_increasing` preserves the delta across each unavailable→available transition, so the
  **cumulative total (and monthly €) is intact**, but hourly/attribution granularity is degraded, and
  brief consumption during an outage window may be smeared into the next reading.
- Note: statistics `sum` (182.52) ≠ device lifetime `state` (205.97). This ~23.45 kWh offset is the
  normal statistics baseline (sum is relative to statistics start), **not** a bug.
- **Severity: MEDIUM** (this is the dominant cost driver, so its flapping matters most).
- **Recommended fix (do NOT apply):** improve Zigbee/Tuya signal or reserve/repeat for this plug;
  consider a Zigbee router node near it. Also verify the "Гидрофон" label is correct — a steady
  2–3 kWh/day steady draw reads more like a pump/appliance than a hydrophone.

### 2. `sensor.boiler_total_energy` — Boiler ТЭН (cost_month_boiler = 5.84 €)  ⚠ MEDIUM
- Unit `kWh`, `state_class: total_increasing` — correct. Daily-resetting counter (see cross-reference).
- `sum` monotonic and reset-safe. **Trustworthy for cost**, EXCEPT:
  - **2026-07-04 missing entirely** (plug offline) — 1 lost day.
  - **2026-06-23 frozen** — possible partial loss.
- **Severity: MEDIUM** (occasional whole-day holes from the plug's weak-WiFi zone).
- **Recommended fix (do NOT apply):** resolve `switch.smart_plug_2_socket_1` offline drops
  (reserve IP / improve WiFi in the boiler area — same weak zone as ecoNET, per known issues).

### 3. `sensor.ev_charger_energy` — EV charger (cost_month_ev = 4.46 €)  ⚠ MEDIUM
- Unit `kWh`, `state_class: total_increasing`, lifetime cumulative (command_line via Tuya Cloud, 10 s).
- Lifetime `sum`/`state` monotonic 713.53 → 882.80, **no resets** — lifetime total is fine.
- **Stale-then-jump pattern:** flat at **713.53 for 16 days** (2026-06-14..06-29), then a single-day
  jump of **+110.01 kWh on 2026-06-30**. This is characteristic of the command_line sensor returning a
  cached/stale value (known `ev_query.py` cache issue) and then catching up — the 110 kWh almost
  certainly accrued over multiple days but is **attributed to one day**.
- Impact: **daily / per-day EV cost attribution is unreliable**; monthly aggregate is roughly OK because
  the catch-up lands within the same accounting window (but a month-boundary catch-up would misattribute).
- **Severity: MEDIUM.**
- **Recommended fix (do NOT apply):** ensure `ev_query.py` always emits a fresh value (the known cache
  in `/config/.ev_cache/`); consider marking the sensor `unavailable` when the fetch is stale rather than
  repeating the last value, so statistics record a gap instead of a false flat line + spike.

### 4. `sensor.akvarium_svet_total_energy` — Aquarium light (cost_month_akv = 0.29 €)  ✔ OK
- Correct unit/state_class. Daily-reset counter; `sum` clean & monotonic (~0.52–0.55 kWh/day).
- Many intra-series `state`→0 resets are expected (timer) and handled correctly. **Trustworthy.**

### 5. `sensor.cherepakha_total_energy` — Turtle/recirc (cost_month_chep = 0.30 €)  ✔ OK
- Correct unit/state_class. Daily-reset counter; `sum` monotonic.
- Minor pattern change (~0.08 kWh/day 06-18..06-23 → ~0.6 kWh/day after) reflects real usage change, not
  a data fault. **Trustworthy.**

### 6. `sensor.terarium_total_energy` — Полотенцесушитель / towel warmer (cost_month_kalarifer = 0.33 €)  ⚠ LOW
- Correct unit/state_class. Daily-reset counter; mostly idle in June, light July usage; `sum` monotonic
  111.38 → 119.39. **Cost figure OK.**
- **Naming/traceability confusion (LOW):** device = "полотенцесушитель", energy sensor id = `terarium`
  (terrarium), switch = `kalarifer_socket_1`, accumulator = `cost_month_kalarifer`. Three legacy names
  for one device — easy to mis-map in future edits.
- 2026-07-03 shows a day `sum` delta of +2.476 with end-`state`=0 — a within-day spike then reset; not
  clearly wrong but worth noting given the sensor is otherwise near-idle.
- **Recommended fix (do NOT apply):** document the name mapping (already partly in CLAUDE.md); no data fix needed.

### 7. `sensor.zigbee_plug_total_energy` — plug #1  ⚠ LOW (ghost/dead)
- `state=0` for the entire month; `sum` frozen at **1.32** since before 2026-06-15. Device unused/offline.
- Not referenced by any `cost_month_*` accumulator, so it does not affect cost.
- **Severity: LOW.** **Recommended fix (do NOT apply):** confirm the plug is decommissioned; if so,
  hide/remove the orphaned entity to reduce noise.

### 8–11. `sensor.75_qled_*` (TV) — 4 sensors, misconfigured / dead  ⚠ LOW
- `75_qled_energy` (`total_increasing`): always 0 — dead.
- `75_qled_energy_saved` (`total_increasing`): always 0 — dead.
- `75_qled_power_energy`: unit `kWh` but **`state_class: total`** (should be `total_increasing` for a
  cumulative energy meter) — always 0.
- `75_qled_energy_difference`: **`state_class: total`**, oscillates around ~0.001, occasional resets and a
  **negative long-term `sum` (down to -0.001)**. A "difference" quantity with `state_class: total` produces
  meaningless / negative statistics.
- Impact: these pollute the statistics list; `midnight_tv_energy` (=0.0) tracks one of these zero sensors,
  so any TV cost tracking is effectively always 0. No `cost_month_*` uses the TV, so monthly € is unaffected.
- **Severity: LOW.** **Recommended fix (do NOT apply):** exclude the 3 non-cumulative QLED sensors from
  recorder statistics (or correct `state_class`), and drop `midnight_tv_energy` if TV cost isn't tracked.

---

## Consistency checks

- **Monthly € accumulator internal consistency — OK.** Sum of device accumulators
  `boiler 5.84 + kalarifer 0.33 + akv 0.29 + chep 0.30 + gidro 41.85 + ev 4.46 = 53.07` ≈
  `cost_month_total = 53.08` (0.01 rounding). Arithmetic is consistent.
- **Cost concentration:** `gidro` (zigbee_plug_2) = **41.85 / 53.08 = 79%** of the month — its data quality
  (flapping) is the single most important factor for total cost accuracy.
- **Midnight snapshots vs live states — consistent** (taken at last local midnight):
  `midnight_gidro 275.34` vs live 275.69 (+0.35 today); `midnight_ev 882.8` vs 882.8 (0);
  `midnight_akv/chep/kalarifer` match live; `midnight_boiler 10.099` vs live 0 (boiler reset after snapshot —
  handled by the reset guard).
- **No whole-home total sensor** was found → cannot validate Σdevices against a house/grid meter.
- **No duplicate energy sensors for one device** found (the QLED cluster is 4 different metrics of one TV, all
  unusable; zigbee_plug vs zigbee_plug_2 are two distinct plugs).

---

## Severity summary

| Severity | Items |
|---|---|
| MEDIUM | zigbee_plug_2 flapping (dominant cost); boiler plug-offline day loss (2026-07-04); EV stale-then-jump attribution |
| LOW | zigbee_plug (dead); 4× 75_qled_* (dead/misconfigured, incl. negative sum); terarium naming confusion |
| OK | akvarium, cherepakha (clean); terarium cost figure |

**Nothing here warrants a recorder/statistics repair action in this task** (per scope: no such changes).
All recommendations above are advisory and were **not applied**.
