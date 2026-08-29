# Hydrophore Energy Sensor — Forensic Investigation & Verdict

**Entity:** `sensor.zigbee_plug_2_total_energy` (friendly name **«Гидрофор Всего энергия»**)
**Switch:** `switch.zigbee_plug_2_socket_1` · **Tuya device:** `7c1647265a8607cc1c85515941c8e8cb`
(unique_id `tuya.bfa9b0af64bf09b034xvx6add_ele`, `ap-` cloud account)
**Date:** 2026-07-16 (Europe/Riga) · **Method:** READ-ONLY (HA REST `/api/history`, `/api/states`;
WebSocket `recorder/statistics_during_period`, `config/entity_registry/list`; frozen ledger).
**No devices touched, no production modified, no Tuya reload.**

---

## TL;DR / VERDICT

The **meter itself is REAL CONSUMPTION** — trustworthy, monotonic, correctly-scaled, no reset,
no reconnect catch-up. The **false ~€42 cost is NOT a sensor defect**; it is an **accounting-automation
bug**: the midnight-snapshot automation coerces an `unavailable` reading to **0** (`| float(0)`), and on
a day the flapping sensor is `unavailable` at 00:01 the daily-accrual automation then bills the device's
**entire ~276 kWh lifetime total as one day's consumption** (~276 kWh × ~0.15 €/kWh ≈ **€41**).

| Question | Answer |
|---|---|
| Classification of the **sensor** behavior | **REAL CONSUMPTION** (clean, ~2.4 kWh/day) |
| Restored-cumulative jump on reconnect? | **NO** — 43 reconnects in 10 days, **0 jumps > 1 kWh** |
| Counter reset? | **NO** — lifetime cumulative, monotonic (does *not* daily-reset like boiler/aquarium) |
| Scale error (Wh↔kWh)? | **NO** — `kWh`, `total_increasing`, recorder `sum` monotonic |
| Source of the false €42 | **Accounting bug** — `unavailable → float(0)` midnight snapshot |
| Is the device name right? | **«Гидрофор» = hydrophore (water pressure pump)**, NOT "hydrophone". ~2.4 kWh/day fits a pressure/well pump. CLAUDE.md label is a mistranslation. |

---

## 1. Entity source, semantics, units — CONFIRMED

- `platform: tuya` (single `ap-` cloud account). Live state `279.11`, attributes:
  `state_class: total_increasing`, `unit_of_measurement: kWh`, `device_class: energy`.
- `add_ele` datapoint = **cumulative lifetime** kWh counter (does **not** reset at midnight; unlike
  `boiler`/`akvarium`/`cherepakha` which are daily-resetting Tuya counters).
- **No scale factor, no Wh↔kWh switch.** Recorder statistic `sensor.zigbee_plug_2_total_energy`:
  `has_sum=true`, `statistics_unit_of_measurement=kWh`, `unit_class=energy`.
- `last_changed == last_updated` on every observed row (state and attributes move together — normal for a
  cumulative meter; no attribute-only churn).

### Duplicate / ghost entities — NONE
Registry search for `zigbee_plug_2` returns exactly one energy entity (`..._total_energy`) plus its
sibling controls (`switch.*_socket_1`, `*_child_lock`, `select.*_power_on_behavior`) and three
**disabled-by-integration** electrical sensors: `sensor.zigbee_plug_2_power`, `_current`, `_voltage`.
`sensor.zigbee_plug_total_energy` (plug **#1**) is a *different, dead* device — not a duplicate.

---

## 2. Long-term statistics (recorder) — CLEAN, REAL

`recorder/statistics_during_period`, period `day`, 2026-06-14 → 2026-07-15:

| Metric | Value |
|---|---|
| `sum` trajectory | 182.52 → **255.66** kWh (monotonic, no drops) |
| `state` (device lifetime) | 205.97 → **279.11** kWh |
| Per-day delta range | **0.48 – 6.16 kWh/day**, median ≈ 2.3 kWh/day |
| Resets detected | **0** |
| Day-jumps > 10 kWh | **0** |

~2.3 kWh/day for a **hydrophore / pressure-boost pump** is entirely realistic (short, frequent
pump cycles). **The meter's cumulative total and monthly kWh are trustworthy.** Statistics `sum`
(255.66) ≠ device `state` (279.11): the ~23.4 kWh offset is the normal statistics baseline, not a bug.

---

## 3. Unavailable flapping & reconnect behavior — RULES OUT "restored-cumulative jump"

10-day states history (`/api/history/period`): **210 rows, 43 `unavailable` rows, 43 reconnects.**

- The plug flaps `available → unavailable → available` constantly (Tuya-cloud connectivity in a weak
  zone — matches the boiler-plug / ecoNET weak-WiFi area).
- **On every one of the 43 reconnects the value resumed at (essentially) the last-good value — 0 jumps
  above 1 kWh.** In the frozen ledger the single in-window gap (20:15 unavailable) resumed at 278.29 vs
  277.79 before it = **+0.50 kWh**, consistent with ~30 min of real pumping, not a stale-value catch-up.
- **Therefore the sensor does NOT restore an old cumulative and does NOT produce a catch-up jump on
  reconnect.** (Contrast: `sensor.ev_charger_energy` *does* do stale-then-jump; hydrophore does not.)

Impact of flapping: it degrades hourly/attribution *granularity* only; because `total_increasing`
preserves the delta across each gap, the cumulative total and monthly kWh survive intact.

---

## 4. Frozen-ledger cross-check (24 h, 2026-07-15 18:46 → 2026-07-16 18:30)

`docs/audit/shadow_evidence/shadow_snapshots.frozen.jsonl` (sha256 verified in CUSTODY.md), 96 records:

- hydrophore `v`: **276.63 → 279.11 kWh**, net **+2.48 kWh** in ~24 h — monotonic, matches §2.
- 1 `unavailable` sample (20:15), resumed +0.50 (see §3). No jump, no reset, no scale change.

---

## 5. ROOT CAUSE of the false cost — accounting automation, not the sensor

The «сегодня»/month cost pipeline is two automations plus a guard:

**(a) Snapshot — `1778700001002` «🕛 Снимок энергии (полночь)», at 00:01** (scratch_automations.yaml:2766-2770):
```jinja
value: "{{ states('sensor.zigbee_plug_2_total_energy') | float(0) }}"
```
No `unavailable`/`unknown` guard. When the sensor is `unavailable` at 00:01, `states()` returns the string
`"unavailable"` and **`| float(0)` coerces it to `0`** → `input_number.midnight_gidro_energy = 0`.
Given 43 unavailable episodes / 10 days, being `unavailable` exactly at 00:01 is a routine event.

**(b) Daily accrual — `1785000001001` «💶 Учёт стоимости», at 23:58** (scratch_automations.yaml:3865, 3897):
```jinja
d_gidro = [ total_now - midnight_gidro , 0] | max          # 276 - 0 = 276 kWh
avg     = (nord_pool_lowest + nord_pool_highest) / 2        # ≈ 0.13-0.15 €/kWh
cost_month_gidro += d_gidro * avg                           # 276 × 0.15 ≈ €41 in ONE day
```
With `midnight_gidro = 0` and `total_now ≈ 276`, `d_gidro` becomes the **whole lifetime meter reading**,
priced at the day's min/max **midpoint**, and dumped into the monthly accumulator in a single day.

**(c) Reset-guard — `1786000001001` «🔄 Гард сброса счётчика энергии»** protects the WRONG direction
(scratch_automations.yaml:3993):
```jinja
{{ cur >= 0 and cur < states(midnight_snapshot) | float(0) }}   # fires only when total < snapshot
```
It rebases only on a counter **drop** (total < snapshot). In this failure mode snapshot=0 and total=276,
so total **>** snapshot → **the guard never fires.** It also `float(-1)`s `unavailable` (so it correctly
ignores unavailable transitions) — but it does nothing about the snapshot being set to 0.

### The numbers confirm it
- Live `input_number.cost_month_gidro` = **42.29 €**; `cost_month_total` = **53.67 €** → gidro = **78.8 %**
  (and up to ~93 % if EV+boiler are viewed separately). Matches the "79–93 %" premise.
- **Real** July-MTD consumption: `state` 251.84 (07-01) → 279.11 (now) = **27.3 kWh** → at ~0.13-0.15 €/kWh
  ≈ **€3.5–4 real**.
- Phantom = 42.29 − ~4 ≈ **€38**, i.e. ≈ **253 kWh** priced once — ≈ the lifetime baseline. Consistent with
  exactly **one** bad-snapshot day this month.
- `42.29 / 0.15 ≈ 282 kWh ≈` the lifetime total. The arithmetic closes only under the snapshot=0 hypothesis;
  it cannot be explained by ~2.4 kWh/day real use.

### Why hydrophore specifically dominates
It combines (1) the **highest lifetime cumulative** among the non-EV plugs (~276 kWh; boiler/aquarium
reset daily to small numbers, so their snapshot=0 case bills almost nothing) with (2) the **highest
unavailable rate** (43/10 days → high chance of being down at 00:01). EV has a big total but a stable
midnight snapshot. That intersection is unique to gidro → it produces ~79–93 % of the (false) cost.

---

## 6. VERDICT

- **Observed sensor/meter behavior: REAL CONSUMPTION.** Monotonic, correctly-scaled `kWh`
  `total_increasing`, ~2.4 kWh/day (plausible pressure pump), recorder `sum` clean. **NOT** a
  restored-cumulative reconnect jump, **NOT** a counter reset, **NOT** a scale error.
- **Observed cost behavior: FALSE — an accounting artifact,** produced by the
  `unavailable → | float(0)` midnight snapshot (never-zero-for-missing violation) feeding a
  `total − snapshot` daily-delta model. Closest of the required buckets by magnitude is a "scale"
  blow-up, but the precise cause is an **accounting/automation bug, not a sensor phenomenon.**

**Confidence: HIGH.** Recorder statistics, 10-day states history, the frozen ledger, and the live
accumulator arithmetic all agree, and the exact automation code path is identified.

---

## 7. RECOMMENDATION

**Immediate (display / trust):** Until the automation is fixed, **exclude hydrophore from the aggregated
«сегодня» total and from cost**, or show it separately labelled **SUSPECT** with its real figure
(~2.4 kWh/day, ~€10/month at spot). Do **not** show the €42 accumulator as truth. The **kWh** from
recorder statistics is trustworthy and may be shown as-is.

**Fix the accounting (not the hardware) — the meter is fine:**
1. **Guard the snapshot** (`1778700001002`): skip the write / carry forward the previous snapshot when the
   reading is not a finite number — e.g. `{% if states(sensor) not in ['unavailable','unknown'] %}` write,
   else leave the old value. Never write `0` for missing. Apply to all 7 `midnight_*` writes.
2. **Harden the accrual** (`1785000001001`): treat `unavailable` energy as *unknown* (skip that device for
   the day), never as a delta from 0. Add a sanity cap (a single-day per-device delta far above the
   30-day max, e.g. > 20 kWh for gidro, is almost certainly a snapshot artifact → do not accrue, notify).
3. **Correct the current month:** `cost_month_gidro` (42.29) and `cost_month_total` (53.67) are inflated by
   ~€38 from one bad day. After owner approval (R2 write), rebase `cost_month_gidro` to the real MTD figure
   computed from recorder statistics (~€3.5–4) and reduce `cost_month_total` accordingly.
4. **Strongly preferred — replace the midpoint model** with the already-prototyped interval model
   (`tools/energy_cost/`, `docs/audit/ENERGY_COST_MODEL.md`): it reads the **recorder statistics** (which
   are clean for gidro) and prices exact 15-min `kWh × price`, sidestepping the snapshot mechanism entirely.

**Trustworthy future measurement (options):**
- The meter data is already trustworthy for **totals/kWh** — **no new hardware is required** to fix cost.
- To reduce the *flapping* (granularity, not totals): enable the three disabled Tuya electrical sensors
  (`sensor.zigbee_plug_2_power/_current/_voltage`) for a live W reading, but note they ride the **same
  Tuya cloud** and will flap identically.
- For a genuinely **local, flap-free** measurement: this is a **Zigbee** plug currently bridged via Tuya
  **cloud** — re-pair it to a **local Zigbee coordinator** (ZHA / deCONZ / Zigbee2MQTT) to get local
  power+energy without cloud dropouts, or swap in a dedicated local energy-metering plug. This is an
  **optional data-quality upgrade**, not needed to fix the false cost.

---

## Evidence appendix (key figures)

| Item | Value | Source |
|---|---|---|
| Live state | 279.11 kWh | `/api/states` |
| Attrs | kWh · total_increasing · energy | `/api/states` |
| 30-day daily `sum` | 182.52 → 255.66 (monotonic, 0 resets, 0 big jumps) | WS statistics `day` |
| 30-day daily delta | 0.48–6.16 kWh/day (median ~2.3) | WS statistics `day` |
| 10-day history | 210 rows, 43 unavailable, 43 reconnects, 0 jumps>1 kWh | REST history |
| Frozen 24 h net | +2.48 kWh (276.63→279.11), 1 gap, no jump | frozen ledger |
| `cost_month_gidro` | 42.29 € (78.8 % of 53.67 total) | `/api/states` |
| Real July-MTD | 27.3 kWh (state 251.84→279.11) ≈ €3.5–4 | WS statistics + states |
| `midnight_gidro_energy` (now) | 278.63 (currently correct) | `/api/states` |
| Snapshot bug | `{{ states(...) | float(0) }}` no unavailable guard | scratch_automations.yaml:2770 |
| Accrual formula | `[total-snapshot,0]\|max × (low+high)/2` | scratch_automations.yaml:3865,3897 |
| Guard limitation | fires only `total < snapshot` (wrong direction) | scratch_automations.yaml:3993 |
