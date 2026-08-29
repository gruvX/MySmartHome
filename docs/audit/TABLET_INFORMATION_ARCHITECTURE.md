# Tablet Information Architecture — Truthful, Data-Backed Design

**Author:** tablet-information-agent · **Date:** 2026-07-15 · **Scope:** design-only.
READ-ONLY on HA. This document + a non-deployed local mock are the only artifacts.
No production tablet code (`tablet/tablet-panel.js`), no config, no automations were changed.

**Consumes (does not re-derive):** `ENERGY_INVENTORY.md` / `energy_inventory.json`,
`ENERGY_COST_MODEL.md`, `ENERGY_DATA_QUALITY.md`, `AUTOMATION_INVENTORY.md` /
`automation_inventory.json`, `AUTOMATION_CONFLICTS.md`, `AUTOMATION_RUNTIME.md`.

---

## 0. Runtime contract (how the tablet gets data)

The tablet runs as an HA-native `panel_custom` (`tablet/tablet-panel.js`), a `<tablet-panel>`
custom element that receives the injected **`hass`** session object. There is **no token** and
**no manual auth header** (verified in `tablet/tablet-panel.dev.html`, which asserts
`noAuthHeaderEverBuilt`). All data in this design comes from exactly three session-based
channels:

| Channel | Use in this design | Notes |
|---|---|---|
| `hass.states[entity_id]` | every live value; `.state`, `.attributes.*`, **`.last_updated` / `.last_changed`** | freshness comes from `last_updated`; no polling loop needed |
| `hass.callService(domain, service, data)` | control only — **not used on these three info screens** (info-only phase) | kept out of scope here |
| `hass.callApi('GET', path)` | calendar events (already used by the panel) | e.g. `calendarEvents/…` |
| `fetch('/local/today_prices.json')` | same-origin static price series for the 24 h chart (already fetched by the panel) | no auth; static file written by `📊 Elering цены дня` |
| `fetch(nameday api)` | cosmetic namedays only | external, allowed to fail silently |

**Consequence for design:** every tile below names an entity/attribute that must be resolvable
from `hass.states` (or `callApi`/the static json). Nothing requires a token, and no tile calls
a service. This matches the injected-`hass` model exactly.

---

## 1. Hard rules enforced by every tile

1. **Never render `0`/`—`/blank for missing data.** A tile in a missing state shows one of:
   `нет данных` (no source / meter doesn't exist), `не измеряется` (device has no
   power/energy sensor), `устарело` (state older than the freshness window),
   `недоступно` (entity `state === 'unavailable'` / `unknown`). The literal value `0` is shown
   **only** when the sensor is *available and genuinely reads zero* (the "available-but-idle"
   case from `ENERGY_COST_MODEL.md §3.2`).
2. **Per-block freshness stamp.** Every data block shows `обновлено HH:MM` derived from the
   **max `last_updated`** of the entities feeding it. If that age exceeds the block's freshness
   window (column "Freshness" below), the block flips to `устарело` and the stamp turns amber.
3. **Units are explicit and never mixed.** `W` (instantaneous power) ≠ `kW` ≠ `kWh` (energy) ≠
   `EUR` / `€` (cost) ≠ `EUR/kWh` (price). Power is `W`; energy `kWh`; price `EUR/kWh`;
   money `€`. A tile never labels a kWh figure as "power".
4. **No false success.** A value that is an estimate/projection/approximation is labelled
   (`≈`, `оценка`, `прогноз`, `спот-оценка без тарифа`). A control-safety verdict is never
   shown as "ok" unless its source entity actually confirms it.
5. **Critical actions are separated from information.** This phase is **info-only**: the three
   screens display state and never expose a control that could shut off water, arm/disarm,
   toggle the boiler, etc. (A future "actions" surface is out of scope and must be a distinct,
   confirm-gated panel.)
6. **Readable at 1280×800** — the real CSS resolution of the SM-T595 landscape (DPR 1.5). All
   three screens fit without vertical scroll at that size; wide content scrolls inside its own
   container, never the page body.

### Quality classes (from `ENERGY_INVENTORY.md`, reused verbatim)
`A` exact interval · `B` cumulative kWh · `C` power only · `D` estimate (nameplate×time) ·
`E` no data. The house has **8× B, 3× D, 3× E, zero A/C**.

### Entity-verification legend (used in every source column)
- **V1** — confirmed present in `energy_inventory.json`.
- **V2** — confirmed present in `automation_inventory.json` (`referenced_entities`).
- **V3** — named in `CLAUDE.md` / the panel only; **NOT present in either audit inventory** →
  existence unverified by this audit, flagged, and given a mandatory fallback.
- **GHOST** — confirmed *non-existent* (typo / removed) by the audits; must NOT be used.

---

## 2. SCREEN 1 — MAIN (главный экран)

Purpose: at-a-glance house status + anything demanding attention. Layout: a top **critical
banner** (only appears when something is wrong), then a 3-column tile grid.

### 2.1 Critical banner (shown only when non-empty)
Aggregates the highest-priority conditions in priority order water → smoke → security →
device/plug offline. Each row is a fact, not an action.

| Condition | Source entity → state | Shows | Fallback if source missing |
|---|---|---|---|
| Water leak active | `binary_sensor.vannaia_moisture` / `garazh_moisture` / `kukhnia_moisture` / `water_sensor_4_moisture` = `on` (V2) | `⚠ Протечка: <room>` | if any is `unavailable` → `Датчик протечки недоступно` (do not imply "dry") |
| Smoke | `binary_sensor.wifi_th_smoke_sensor_smoke` = `on` (V2) | `⚠ Задымление` | `unavailable` → `Датчик дыма недоступно` |
| Siren engaged | `siren.alarm` = `on` (V2) | `🔊 Сирена включена` | — |
| Security armed + breach | `input_boolean.security_armed` = `on` (V2) + `binary_sensor.door_sensor_door` = `on` (V2) | `🛡 Охрана: дверь открыта` | door `unavailable` → `Дверь: недоступно` |

Banner is empty (hidden) when all clear — **no green "all ok" fakery**; the absence of the
banner is the signal.

### 2.2 Tile grid

| Tile | Source entity · attr (verif) | Unit | Freshness window | Missing-data fallback |
|---|---|---|---|---|
| **Мощность сейчас (весь дом)** | **none exists** — no whole-home meter (`whole_home_meter=false`, V1) | — | — | **`нет данных — общего счётчика нет`**. Optionally a secondary line "измеряемая сумма недоступна: приборы дают только kWh, не W" — never a fabricated W figure. See §4. |
| **Цена сейчас** | `sensor.nord_pool_lv_current_price` (V1/V2) | `EUR/kWh` | 30 min | `недоступно` if state `unavailable`; `устарело` if age>30 min |
| **Следующий интервал** | `sensor.nord_pool_lv_next_price` (V2) | `EUR/kWh` | 30 min | `нет данных` |
| **Дешёвое окно** | `sensor.nord_pool_lv_lowest_price` state + `.attributes.start`/`end` (V2) | `EUR/kWh` @ `HH:MM–HH:MM` | 60 min | `нет данных` (no list attrs on current-price; §note) |
| **Пик** (context) | `sensor.nord_pool_lv_highest_price` + `.start` (V2) | `EUR/kWh` @ `HH:MM` | 60 min | `нет данных` |
| **Энергия сегодня (сумма измеренных)** | Σ over 8 class-B plugs of `state(total_energy) − input_number.midnight_*` (V1); reset-safe via guard `1786000001001` | `kWh` | per-plug 15 min | show `kWh (только измеряемые приборы, дом не покрыт)`; per-plug `недоступно` when its sensor is `unavailable`, never 0 |
| **Стоимость за месяц** | `input_number.cost_month_total` (V2) | `€` | 24 h (accrues 23:58) | `нет данных`. **Caveat badge:** method is min/max-midpoint (flawed per `ENERGY_COST_MODEL §0`) → label `€ (оценка, midpoint)` |
| **Топ-3 потребителя (месяц)** | rank `input_number.cost_month_{gidro,boiler,ev,kalarifer,akv,chep}` desc (V2) | `€` | 24 h | if all zero/reset → `нет данных`. gidro ≈79% (data-quality caveat, see Energy screen) |
| **Вода (клапан)** | `switch.voda_kran_switch_1` (V1/V2) | on/off | state | `недоступно` |
| **Дым** | `binary_sensor.wifi_th_smoke_sensor_smoke` (V2) | ok/alarm | state | `недоступно` |
| **Охрана** | `input_boolean.security_armed` (V2) + `binary_sensor.door_sensor_door` (V2) | armed/disarmed · door | state | door `недоступно` shown separately |
| **Котёл (режим)** | `sensor.boiler_mode` (V2) | text | 5 min | `недоступно` (REST flaps) |
| **Котёл ГВС / t°** | **`sensor.boiler_cwu_temperature` (V3 — NOT in inventories)**; setpoint `sensor.boiler_cwu_setpoint` (V2) | `°C` | 5 min | temp is V3 → verify entity id before shipping; if unresolved show `нет данных`. **Do NOT use `sensor.boiler_temp_cwu` (GHOST typo).** |
| **Отопление пол — ванная** | `climate.floor_heating` state + `.attributes.current_temperature`, `.preset_mode` (V1/V2) | `°C` + preset | state | `недоступно` |
| **Отопление пол — душевая** | `climate.floor_heating_2` (V1/V2) | `°C` + preset | state | `недоступно` |
| **Температура (улица)** | `sensor.smart_weather_station_temperature` (V2) | `°C` | 30 min | `нет данных` |
| **EV — статус** | `sensor.ev_charger_status` (V2) | text (charger_*) | 15 min | `недоступно`. Note: status can read `charging` while `switch.ev_charger_switch=off` (cloud-sourced) — show both, don't reconcile silently |
| **EV — расписание** | `input_datetime.ev_charge_start` (V2) | time | state | `нет данных` |
| **EV — заряжено (всего)** | `sensor.ev_charger_energy` (V1/V2) | `kWh` lifetime | 15 min | `недоступно`. Daily attribution unreliable (stale-then-jump, DQ §3) — this tile shows **lifetime total only**, never a "today EV kWh" |
| **Недоступные устройства** | derived: entities with `state==='unavailable'` from a watch-list; seeds from `unavailable_entities` (occupancy battery, 2× door-sensor battery) (V2) | count + list | live | list is empty → `нет недоступных` (a real true-zero) |
| **Низкий заряд батарей** | battery sensors `< 30%`; **kukhnia_battery (V2)** confirmed; other battery sensors are **V3** | `%` | 24 h | V3 sensors unverified → the tile lists only resolvable battery entities and labels the rest `нет данных`; skips GHOST `signalizatsiia_dvernogo_datchika_2_battery` |
| **Погода** | `weather.forecast_home` state + `.attributes.temperature` (V2) | °C / condition | 30 min | `нет данных` |
| **Ближайшие события** | `hass.callApi('GET','calendars/…')` — **calendar entity V3 (none in inventories)** | list | on load | `нет данных` if callApi empty/fails (panel already tolerates this) |

**Note (Nord Pool list attrs):** `sensor.nord_pool_lv_current_price` exposes **no**
`today`/`raw_today`/`tomorrow` list (`ENERGY_COST_MODEL §1.1`). The cheap-window tile therefore
uses the dedicated `_lowest_price`/`_highest_price` sensors (which carry `start`/`end`), and the
24 h chart uses `/local/today_prices.json`. Any tile that would need the intraday price array
falls back to `нет данных` rather than reading a non-existent attribute.

---

## 3. SCREEN 2 — ENERGY (энергия)

Purpose: per-device measured energy, cost, ranking, and an **honest data-quality panel**.

### 3.1 Power-now per device
Every class-B plug meters **kWh only, not W**. The **only** device exposing instantaneous power
is the TV (`sensor.75_qled_power`), and that sensor is **DEAD (always 0)** per DQ §8.

| Device | Power source | Design |
|---|---|---|
| EV, Boiler, Towel, Aquarium, Recirc, Hydrophore, Bed backlight | none (V1: `power_sensor: null`) | **`не измеряется`** (explicit — do not synthesize W from kWh) |
| TV 75" | `sensor.75_qled_power` (V1) but dead | show `не измеряется` (sensor reads 0 always; treat as no data, not "0 W idle") |

→ The whole "power now" column on this screen is honestly `не измеряется` across the board. This
is a real finding, surfaced rather than hidden.

### 3.2 kWh + € today & month per device

| Device (plug) | Energy sensor (V1) | Today kWh | Month € | Quality |
|---|---|---|---|---|
| Гидрофон/насос | `sensor.zigbee_plug_2_total_energy` | `state − input_number.midnight_gidro_energy` | `input_number.cost_month_gidro` | **B, MEDIUM** — flapping unavailable; totals intact, granularity degraded (DQ §1). Badge `≈79% месяца` |
| Бойлер ТЭН | `sensor.boiler_total_energy` | `state − midnight_boiler_energy` (reset-guarded) | `cost_month_boiler` | **B, MEDIUM** — 2026-07-04 day lost (plug offline); reads 0 now (idle/reset) |
| EV | `sensor.ev_charger_energy` | **not shown per-day** (attribution unreliable, DQ §3) → `нет надёжных данных за день` | `cost_month_ev` | **B, PARTIAL** — lifetime OK, daily unreliable |
| Полотенцесушитель | `sensor.terarium_total_energy` | `state − midnight_kalarifer_energy` | `cost_month_kalarifer` | **B, LOW** — name mismatch documented |
| Аквариум | `sensor.akvarium_svet_total_energy` | `state − midnight_akv_energy` | `cost_month_akv` | **B, OK** |
| Рециркуляция | `sensor.cherepakha_total_energy` | `state − midnight_chep_energy` | `cost_month_chep` | **B, OK** |
| Подсветка кровати | `sensor.zigbee_plug_total_energy` | — | **нет данных** (not in `cost_month_*`; DEAD, DQ §7) | **B but DEAD** — flat sum, `state=0`. Show `не отслеживается` |
| ТВ 75" | `sensor.75_qled_energy` | — | **нет данных** (dead, DQ §8) | **DEAD** — show `не отслеживается` |
| Тёплый пол ×2, свет, ecoNET электр., клапан, прочие розетки | — (V1: D/E) | — | — | **`не измеряется`** (class D/E — no meter) |

**Today-€ per device:** there is **no per-device "cost today" entity**. Deriving it would need
`today_kWh × price`, and the audit forbids `kWh × daily-avg`. Design choice: show **today kWh**
(where the plug is available) and, if a €-today figure is shown at all, label it
`≈ спот-оценка (без тарифа)` using `sensor.nord_pool_lv_current_price` — explicitly an estimate,
never presented as billed cost. Default: omit €-today, show kWh-today + month-€.

### 3.3 Price + consumption chart
- **Price series (24 h):** `/local/today_prices.json` (same-origin static, already used by the
  panel). Freshness = file mtime / last point time; if stale → `устарело`.
- **Consumption overlay:** only the class-B plugs have recorded kWh. Because per-device power is
  not measured, the overlay is **stepwise kWh-per-interval** (from the running `total_energy`
  deltas), not a W curve, and is labelled `kWh/интервал`. Devices that flap (gidro) render gaps,
  **never zero-filled** (DQ §1).

### 3.4 Consumer ranking (month)
Bar chart of `cost_month_{gidro,boiler,ev,kalarifer,akv,chep}` (V2), descending, each with its
quality badge. `gidro` visually dominant (≈79%); its MEDIUM badge is attached so the number is
never read as high-confidence.

### 3.5 Unaccounted energy
`main_kWh − Σ device_kWh` → **requires a whole-home meter, which does not exist** (V1).
Tile shows **`недоступно — нет общего счётчика`** and a one-line explanation. **Not** computed,
**not** shown as 0. (Per `ENERGY_COST_MODEL §3.6`, `unaccounted_* = None` by design.)

### 3.6 Data-quality indicator
A compact panel that turns the audit into live status:

| Indicator | Live source | Rule |
|---|---|---|
| Гидрофон связь | `sensor.zigbee_plug_2_total_energy` `.state==='unavailable'` right now? | amber "флапает" (known); red if currently unavailable |
| Бойлер счётчик | `sensor.boiler_total_energy` availability + last_updated | amber if `unavailable`/stale |
| EV свежесть | `sensor.ev_charger_energy` last_updated age | amber if >30 min (stale-then-jump risk) |
| Мёртвые сенсоры | static list from DQ (bed backlight, 4× QLED) | grey "не отслеживается" |
| Общий счётчик | constant `false` (V1) | grey "нет — дом не покрыт" |
| Метод стоимости | constant | amber "midpoint (неточный)" |

### 3.7 Month forecast
`month_forecast = cost_month_total / elapsed_days × days_in_month` (client-side, from
`cost_month_total` V2 + calendar date). Labelled **`прогноз (линейный run-rate)`**, `None`/hidden
until `cost_month_total > 0` and `elapsed_days ≥ 1`. Never presented as a guaranteed bill.

### 3.8 vs previous period
**Not backable.** `cost_month_*` are reset to 0 on the 1st (automation `1785000001002`), and no
`last-month` accumulator or long-window exact recorder data exists (purge 10 days,
`ENERGY_COST_MODEL §2`). Tile shows **`нет данных — прошлый месяц не сохраняется`** with a note
that this needs a persistent per-device cost statistic (design recommendation, not implemented).

---

## 4. Whole-home power / cost — why the MAIN tile is "нет данных"

Requested tile: "current WHOLE-HOME power". Ground truth (V1): **no whole-home meter**, and the
per-device plugs expose **kWh, not W** — so even a "sum of measured power" is impossible (there is
no power to sum). Two honest options, both non-fabricating:

- **Default (chosen):** `нет данных — общего счётчика нет`.
- **Optional secondary:** a *measured-energy* rate proxy could be derived as ΔkWh/Δt over the
  last interval for the class-B plugs and shown as `≈ … kW (только измеряемые розетки, не весь дом)`
  — but this covers only 8 plugs (excludes all lighting, kitchen, HVAC not on those plugs) and
  each plug's flapping makes Δt noisy. If shown at all it must carry the "только измеряемые
  розетки" caveat and the amber estimate flag. **Recommended: keep the default "нет данных"** and
  push the owner toward a CT-clamp/grid meter (Energy Inventory rec #2).

---

## 5. SCREEN 3 — AUTOMATIONS (info-only)

Purpose: surface automation health and the audited conflicts. **No enable/disable controls** in
this phase — pure information. Live automation data comes from iterating `hass.states` for
`automation.*` entities: `.state` (`on`/`off`/`unavailable`), `.attributes.last_triggered`,
`.attributes.friendly_name`, `.attributes.id`. Match specific automations by `.attributes.id`
(stable) rather than slug.

### 5.1 Critical automations (health)
Grid of the safety-critical automations with live on/off + last-run age:

| Automation | id | Live source | Freshness rule |
|---|---|---|---|
| 🚨 Утечка воды v4 | `1748000001001` | `automation.*` where `attributes.id==id` → state + last_triggered | flag if `off` (should be on) |
| 🔥 Задымление — сирена | `1779200002001` | same | `off` = red; last_triggered may be never (expected) |
| 🛡 Охрана — тревога | `1779200003001` | same | `off` = info (disarmed is normal) |
| 🚨 Устройство недоступно | `1778900002001` | same | shown; unconfirmed coverage (RUNTIME) |
| 🔥 Бойлер по Nord Pool | `1766138420302` | same | on, ~every 15 min |
| ⚡🔥 EV+Бойлер интерлок | `1779000001001` | same | on |

### 5.2 Active modes
Live booleans, real entities (V2): `input_boolean.night_saver`, `rezhim_zhara`,
`security_armed`, `ev_manual_mode`, `ha_startup_grace`, `tuya_reconnect_grace`. Each shows
on/off + `last_changed` stamp. `недоступно` fallback if any is missing.

### 5.3 Conflicts (surface the audit — static, curated cards)
These are the four findings from `AUTOMATION_CONFLICTS.md`, shown as info cards. Each pairs a
**static description** (from the audit) with a **live check** where one exists:

| Card | Finding | Live corroboration available? |
|---|---|---|
| **C1 (Critical)** — Tuya auto-reload can defeat leak shut-off + dead entry_id | `1748000001005` reloads on genuine leak → moisture/valve `unavailable` → grace blocks shut-off; also reloads removed entry `01OLDENTRY…` | live: show `automation[1748000001005].state`; live check that `input_boolean.tuya_reconnect_grace` is currently on/off |
| **H1 (High)** — life-safety Telegram buttons use unsupported `notify.send_message`+`inline_keyboard` | leak v4 / smoke / security / callbacks | static only (needs a live send test; RUNTIME "verify first") — card labelled `требует проверки` |
| **H2 (High)** — floor-heating auto-branch ignores `rezhim_zhara` → re-enables heat | `1767188164410`, `1776085158491` | **live proof possible:** show `input_boolean.rezhim_zhara` vs `climate.floor_heating_2.state` — if zhara on but climate `heat_cool`, flag red |
| **H3 (High)** — leak v2 duplicate of v4 | `1775638334800` | live: show `automation[1775638334800].state` (should be `off`); red if `on` |

### 5.4 Last error / known-broken
Per-automation live "last error" is **not exposed in `hass.states`** (would need the trace or
`system_log` API). So this section is two **curated known-issue cards** from `AUTOMATION_RUNTIME`,
each with a live state check:

| Card | Source | Live check |
|---|---|---|
| Котёл — откл. ГВС: template TypeError (18×/3d), notifications silently dead | `1778900001001`, RUNTIME §not-working 1 | show `automation[1778900001001].state` (on) + note "уведомления не отправляются" |
| Tuya авто-перезагрузка: errors on removed entry every run | `1748000001005`, RUNTIME §not-working 2 | linked to C1 card |

### 5.5 Long-not-run
List automations where `now − attributes.last_triggered` exceeds a threshold, computed live.
Contextualize with RUNTIME so seasonal/gated ones aren't alarming:
- Турбо нагрев ×2 (`1748000001002/003`) — ~52 d idle (seasonal, expected).
- Присутствие ушёл/вернулся (`1779200001002/003`) — never fired in window (owner home).
- Задымление (`1779200002001`) — never (no smoke; expected).
Each row tags `ожидаемо` vs `проверить` per RUNTIME verdict.

### 5.6 Disabled automations
Live filter `automation.*` with `state==='off'` — expect leak v2 (`1775638334800`), EV-old
(`1774376407472`), boiler-sync (`1775106692658`). Plus orphan
`automation.ai_status_doma_kazhdye_2_chasa` (`1766840617096`, state `unavailable`, V2 orphan) —
tagged `осиротевшая, к удалению`.

### 5.7 EV / boiler / water / security state (info footer)
Live: `sensor.ev_charger_status`, `switch.ev_charger_switch`, `switch.smart_plug_2_socket_1`
(boiler plug), `sensor.boiler_mode`, `switch.voda_kran_switch_1`, `input_boolean.security_armed`,
`siren.alarm` — all V1/V2. Standard `недоступно` fallbacks.

---

## 6. Requested tiles NOT backable by real data

| Requested tile | Why not | Design resolution |
|---|---|---|
| **Whole-home power now** | no main meter; plugs give kWh not W (V1) | `нет данных — общего счётчика нет` (§4) |
| **Unaccounted energy** | needs main meter (V1) | `недоступно — нет общего счётчика` (§3.5) |
| **Per-device €/kWh today** (reliable) | no cost-today entity; audit forbids kWh×avg | show kWh-today + optional `≈ спот-оценка (без тарифа)`; default omit € |
| **EV energy today** | stale-then-jump attribution (DQ §3) | lifetime kWh only; `нет надёжных данных за день` |
| **vs previous month** | `cost_month_*` reset on 1st; no last-month store (10-day purge) | `нет данных — прошлый месяц не сохраняется` (§3.8) |
| **Per-automation live "last error"** | not in `hass.states` (needs trace/system_log) | curated known-issue cards (§5.4) |
| **Power-now per device** | only TV has a W sensor and it's DEAD (DQ §8) | `не измеряется` everywhere (§3.1) |
| **"All OK" success states** | forbidden by rule #4 | absence-of-warning is the signal (empty banner) |
| **Bed backlight / TV cost** | dead sensors, not in `cost_month_*` | `не отслеживается` |

### Entities referenced that are NOT verified by the two inventories (flagged V3)
Must be re-confirmed against live `hass.states` before shipping; each already has a `нет данных`
fallback in the tables above:
- `sensor.boiler_cwu_temperature` (real GVS temp; inventories carry only the **setpoint**
  `sensor.boiler_cwu_setpoint` (V2) and the **GHOST typo** `sensor.boiler_temp_cwu`).
- `sensor.boiler_co_temperature` (same situation; GHOST typo `sensor.boiler_temp_co`).
- Per-room climate sensors other than kitchen (`sensor.kukhnia_*` is V2; living-room/bedroom
  Mijia/Lumi ids from CLAUDE.md are V3).
- Weather-station humidity, air-quality (PM2.5) and illuminance sensors (V3).
- Battery sensors other than `sensor.kukhnia_battery` (V2); the unavailable door-sensor
  batteries are V2 (`unavailable_entities`).
- `calendar.*` — no calendar entity appears in either inventory (calendar reached via
  `hass.callApi`); treat as V3.

### GHOST entities that MUST NOT be used (audit-confirmed non-existent)
`sensor.boiler_temp_co`, `sensor.boiler_temp_cwu`, `sensor.ev_charger_ev_energiia_total`,
`sensor.signalizatsiia_dvernogo_datchika_2_battery`, `sensor.sm_t595_battery_level`.

---

## 7. Layout for 1280×800 (DPR 1.5)

- Fixed top bar: 3 tabs (Главная / Энергия / Автоматизации) + global freshness clock. ~56 px.
- Content area ~744 px tall, no page scroll. Each screen is a CSS grid:
  - **Главная:** critical banner (0 px when empty) + `grid-template-columns: repeat(3, 1fr)`,
    tiles `min-height` tuned so ~7–8 tiles per column fit; wide items span 2–3 cols.
  - **Энергия:** left = ranking + per-device kWh/€ table (own `overflow-y`), right = price/kWh
    chart + data-quality panel + forecast.
  - **Автоматизации:** left = critical health + active modes, right = conflicts + known-issues +
    long-not-run + disabled (each list scrolls inside its card).
- Every data block header carries its `обновлено HH:MM` stamp; amber when stale.
- Theme-aware (light/dark); tables/charts scroll inside `overflow-x:auto` wrappers.

---

## 8. Appendix — tile → entity → unit → fallback (flat source map)

```
MAIN
  price.now         sensor.nord_pool_lv_current_price          EUR/kWh   недоступно/устарело   V1/V2
  price.next        sensor.nord_pool_lv_next_price             EUR/kWh   нет данных            V2
  price.low         sensor.nord_pool_lv_lowest_price(.start)   EUR/kWh   нет данных            V2
  price.high        sensor.nord_pool_lv_highest_price(.start)  EUR/kWh   нет данных            V2
  power.wholehome   (none)                                     —         нет данных            V1(false)
  energy.today.sum  Σ(*_total_energy − midnight_*)             kWh       недоступно (per-plug) V1
  cost.month        input_number.cost_month_total              €         нет данных (midpoint) V2
  top3              cost_month_{gidro,boiler,ev,...}           €         нет данных            V2
  water.valve       switch.voda_kran_switch_1                  on/off    недоступно            V1/V2
  smoke             binary_sensor.wifi_th_smoke_sensor_smoke   ok/alarm  недоступно            V2
  security          input_boolean.security_armed + door_sensor_door       недоступно           V2
  boiler.mode       sensor.boiler_mode                         text      недоступно            V2
  boiler.cwu.temp   sensor.boiler_cwu_temperature              °C        нет данных            V3(!)
  boiler.cwu.set    sensor.boiler_cwu_setpoint                 °C        нет данных            V2
  floor.bath        climate.floor_heating(.current_temperature,.preset_mode) °C  недоступно    V1/V2
  floor.shower      climate.floor_heating_2                    °C        недоступно            V1/V2
  temp.outside      sensor.smart_weather_station_temperature   °C        нет данных            V2
  ev.status         sensor.ev_charger_status                   text      недоступно            V2
  ev.schedule       input_datetime.ev_charge_start             time      нет данных            V2
  ev.energy.total   sensor.ev_charger_energy                   kWh       недоступно            V1/V2
  devices.unavail   derived (state==unavailable watch-list)    count     нет недоступных       V2
  batteries.low     sensor.kukhnia_battery + V3 battery sensors %        нет данных            V2/V3
  weather           weather.forecast_home(.temperature)        °C/cond   нет данных            V2
  calendar          hass.callApi calendars                     list      нет данных            V3

ENERGY
  power.now.*       (no power sensors; TV power dead)           —         не измеряется         V1
  gidro.kwh/eur     sensor.zigbee_plug_2_total_energy / cost_month_gidro  kWh/€ недоступно      V1/V2
  boiler.kwh/eur    sensor.boiler_total_energy / cost_month_boiler        kWh/€ недоступно      V1/V2
  ev.kwh/eur        sensor.ev_charger_energy(lifetime) / cost_month_ev    kWh/€ нет надёжных за день V1/V2
  towel.kwh/eur     sensor.terarium_total_energy / cost_month_kalarifer   kWh/€ недоступно      V1/V2
  aqua.kwh/eur      sensor.akvarium_svet_total_energy / cost_month_akv    kWh/€ недоступно      V1/V2
  recirc.kwh/eur    sensor.cherepakha_total_energy / cost_month_chep      kWh/€ недоступно      V1/V2
  bed.kwh           sensor.zigbee_plug_total_energy (DEAD)                 —     не отслеживается V1
  tv.kwh            sensor.75_qled_energy (DEAD)                           —     не отслеживается V1
  price.chart       /local/today_prices.json                   EUR/kWh   устарело              static
  unaccounted       (needs main meter)                         —         недоступно            V1(false)
  forecast.month    cost_month_total / elapsed × days_in_month €         прогноз/скрыто        V2 derived
  vs.prev.month     (not stored)                               —         нет данных            n/a

AUTOMATIONS  (iterate automation.* by attributes.id)
  crit.leakv4       id 1748000001001  state+last_triggered               off=red               V2
  crit.smoke        id 1779200002001                                                            V2
  crit.security     id 1779200003001                                                            V2
  modes             input_boolean.{night_saver,rezhim_zhara,security_armed,ev_manual_mode,ha_startup_grace,tuya_reconnect_grace} V2
  conflict.C1       id 1748000001005 + input_boolean.tuya_reconnect_grace  static+live          V2
  conflict.H2       input_boolean.rezhim_zhara vs climate.floor_heating_2  live red-check       V1/V2
  conflict.H3       id 1775638334800 (expect off)                          on=red               V2
  known.boilerGVS   id 1778900001001 (template TypeError, notif dead)      static+state         V2
  disabled          automation.* state==off + orphan 1766840617096         list                 V2
  ev/boiler/water/sec footer  ev_charger_status, ev_charger_switch, smart_plug_2_socket_1, boiler_mode, voda_kran_switch_1, security_armed, siren.alarm  V1/V2
```

---

## 9. Files created by this task
- `docs/audit/TABLET_INFORMATION_ARCHITECTURE.md` (this document).
- `docs/audit/tablet_mock/index.html` — standalone, non-deployed wireframe with **DE-IDENTIFIED
  ДЕМО** data illustrating the three screens and every "missing data" fallback state.
- `docs/audit/tablet_mock/screenshot.png` — rendered at 1280×800 (if chromium available).

No secrets appear in any created file. Nothing was deployed.
```
