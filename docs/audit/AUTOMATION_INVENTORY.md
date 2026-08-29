# Home Assistant — Complete Automation & Logic Inventory

**HA 2026.7.1** · generated 2026-07-15 · READ-ONLY audit (no HA changes made).
Secrets (tokens, boiler/basic-auth passwords) are REDACTED throughout.

## Counts
| Item | Count |
|---|---|
| automations in file | 46 |
| automation entities live | 47 |
| orphan automation storage | 1 |
| scripts | 5 |
| scenes tuya | 22 |
| scenes file | 0 |
| input boolean | 12 |
| input number | 14 |
| input datetime | 3 |
| input select | 0 |
| input text | 0 |
| timer | 0 |
| schedule | 0 |
| command line sensors | 2 |
| shell commands | 4 |
| rest commands | 7 |
| rest sensors | 21 |
| template entities | 1 |
| custom components | 6 |

> `automations_in_file`=46 (automations.yaml) but 47 automation entities are loaded — the extra one (`automation.ai_status_doma_kazhdye_2_chasa`) is an **orphan stored in `.storage`**, currently `unavailable`.

## ⚠️ Flagged: Ghost / Missing entity references (referenced but NOT in registry)

| Ghost entity_id | Problem |
|---|---|
| `sensor.boiler_temp_co` | TYPO — real entity is sensor.boiler_co_temperature; renders unknown in self-diagnostics text |
| `sensor.boiler_temp_cwu` | TYPO — real entity is sensor.boiler_cwu_temperature; renders unknown in self-diagnostics text |
| `sensor.ev_charger_ev_energiia_total` | Removed EV energy sensor (404); real one is sensor.ev_charger_energy. Renders 0 in morning briefing |
| `sensor.signalizatsiia_dvernogo_datchika_2_battery` | TYPO — real entity is sensor.signalizatsiia_dvernogo_datchika_battery_2; battery alert skips it |
| `sensor.sm_t595_battery_level` | Tablet deleted 2026-07-12; appears only in battery-alert EXCLUSION list (harmless stale ref) |

These are **real ghosts** (typos or removed devices). Two other look-alikes were verified as NOT ghosts and excluded: `input_boolean.moisture_bypass_` (dynamic string concatenation `~ area`; real helpers moisture_bypass_kukhnia/vannaia/garazh/water_sensor_4 all exist) and `scene.before_night_saver` (created at runtime by `scene.create` in the Night-saver automation).

## ⚠️ Flagged: Referenced entities currently UNAVAILABLE / UNKNOWN

| entity_id | state | Note |
|---|---|---|
| `sensor.occupancysensor_batareia` | unavailable | battery sensor unavailable |
| `sensor.signalizatsiia_dvernogo_datchika_battery` | unavailable | Сигн.1 — known 0%/dead battery (open issue) |
| `sensor.signalizatsiia_dvernogo_datchika_battery_2` | unavailable | Сигн.2 — known 0%/dead battery (open issue) |

## ⚠️ Flagged: Orphan / broken automations
- `automation.ai_status_doma_kazhdye_2_chasa` (id `1766840617096`) — state **unavailable**. Live entity from .storage, NOT in automations.yaml. Alias "🧠🏠 AI статус дома каждые 4 часа". State unavailable — orphaned/broken, not documented in CLAUDE.md

## Disabled automations (state = off)
- **🚗 EV зарядка по цене рынка** (`1774376407472`) — initial_state in YAML: `(unset)`
- **🔄 Бойлер sync после старта HA** (`1775106692658`) — initial_state in YAML: `(unset)`
- **🚨 Утечка воды - аварийное отключение v2** (`1775638334800`) — initial_state in YAML: `False`

## Master automation table

| # | Alias | State | Mode | Crit | Last triggered | Traces | Ghosts | Unavail |
|---|---|---|---|---|---|---|---|---|
| 1 | 🔌 Уведомления о розетках (умные) v7 | on | parallel | HIGH-heating/EV | 2026-07-15 14:30 | 5 |  |  |
| 2 | 🔥 Бойлер по Nord Pool (<=0.04 ON, >0.04 OFF) | on | single | HIGH-heating/EV | 2026-07-15 14:30 | 5 |  |  |
| 3 | 🔥 Тёплый пол ванная по Nord Pool (<=0.04 manual 30C, >0.04 auto) | on | single | HIGH-heating/EV | 2026-07-15 14:32 | 1 |  |  |
| 4 | 🚗 EV зарядка по цене рынка | off | single | HIGH-heating/EV | 2026-04-08 09:00 | 0 |  |  |
| 5 | 🔄 Бойлер sync после старта HA | off | single | HIGH-heating/EV | 2026-04-08 08:05 | 0 |  |  |
| 6 | 🔥 Тёплый пол душевая 1эт по Nord Pool (<=0.04 manual 30C, >0.04 auto) | on | single | HIGH-heating/EV | 2026-07-15 14:30 | 5 |  |  |
| 7 | ☀️ Утренний брифинг | on | single | HIGH-heating/EV | 2026-07-15 04:00 | 0 |  |  |
| 8 | 🕛 Снимок энергии (полночь) | on | single | HIGH-heating/EV | 2026-07-14 21:01 | 0 |  |  |
| 9 | 📊 Ежедневный отчёт потребления | on | single | HIGH-heating/EV | 2026-07-14 20:00 | 0 |  |  |
| 10 | 🚗 EV зарядка — планировщик | on | single | HIGH-heating/EV | 2026-07-15 14:23 | 2 |  |  |
| 11 | 🚗 EV зарядка — автозарядка 2ч | on | single | HIGH-heating/EV | 2026-07-14 11:30 | 0 |  |  |
| 12 | Котёл — откл. ГВС при работе бойлера | on | single | HIGH-heating/EV | 2026-07-15 13:15 | 2 |  |  |
| 13 | 🔥 Котёл: уведомления о режиме и уставках | on | queued | HIGH-heating/EV | 2026-07-15 14:32 | 5 |  |  |
| 14 | 🏠 Присутствие: Владелец вернулся | on | single | HIGH-heating/EV | — | 0 | 2 |  |
| 15 | 🚗 EV: сброс ручного режима при окончании зарядки | on | single | HIGH-heating/EV | 2026-07-13 14:14 | 0 |  |  |
| 16 | ⚡🔥 EV + Бойлер: интерлок | on | restart | HIGH-heating/EV | 2026-07-15 13:15 | 2 |  |  |
| 17 | 🔥 Полотенцесушитель по Nord Pool (<=0.04 ON, >0.04 OFF) | on | single | HIGH-heating/EV | 2026-07-15 14:30 | 5 |  |  |
| 18 | 🌙 Ночная экономия: применить | on | single | HIGH-heating/EV | 2026-07-15 02:00 | 0 |  |  |
| 19 | 💶 Учёт стоимости (за день → месяц) | on | single | HIGH-heating/EV | 2026-07-14 20:58 | 0 |  |  |
| 20 | 💶 Месячный отчёт расходов | on | single | HIGH-heating/EV | 2026-07-05 10:06 | 0 |  |  |
| 21 | 🔄 Гард сброса счётчика энергии | on | queued | HIGH-heating/EV | 2026-07-15 14:39 | 5 |  |  |
| 22 | 🚨 Утечка воды - аварийное отключение v4 | on | parallel | HIGH-safety | 2026-07-15 06:42 | 0 |  |  |
| 23 | 🧠 Самодиагностика дома v3 | on | single | HIGH-safety | 2026-07-15 12:00 | 0 | 1 | 3 |
| 24 | 🤖 Telegram AI управление домом (Gemini) - FINAL | on | queued | HIGH-safety | 2026-07-12 19:12 | 0 |  |  |
| 25 | 🚨 Утечка воды - аварийное отключение v2 | off | parallel | HIGH-safety | 2026-07-09 18:27 | 0 |  |  |
| 26 | 🔋 Алерт низкого заряда батарей | on | single | HIGH-safety | 2026-07-15 06:00 | 0 | 2 | 1 |
| 27 | 📲 Telegram обработчик кнопок | on | queued | HIGH-safety | 2026-07-12 19:12 | 0 |  |  |
| 28 | 🔥 Задымление — сирена | on | single | HIGH-safety | — | 0 |  |  |
| 29 | 🛡 Охрана — тревога при срабатывании | on | single | HIGH-safety | 2026-06-21 17:37 | 5 |  |  |
| 30 | 🚨 Tuya: Gracе период при переподключении | on | restart | HIGH-safety | 2026-07-14 02:43 | 0 |  |  |
| 31 | ☁️ Tuya: авто-перезагрузка при обрыве датчика влаги | on | restart | HIGH-safety | 2026-07-14 02:43 | 0 |  |  |
| 32 | 🚨 Устройство недоступно | on | parallel | HIGH-safety | 2026-07-03 05:22 | 0 |  |  |
| 33 | 📊 Ежедневный прогноз цен электричества (Nord Pool) v4.2 | on | single | normal | 2026-07-15 11:10 | 0 |  |  |
| 34 | ⏰ Скоро будет дешёвое электричество | on | single | normal | 2026-07-15 14:17 | 1 |  |  |
| 35 | Ночной патруль (23:30) | on | single | normal | 2026-07-14 20:30 | 0 |  |  |
| 36 | 📲 Telegram меню с кнопками | on | single | normal | 2026-07-12 19:12 | 0 |  |  |
| 37 | ⚠️ Tailscale: ключ истекает | on | single | normal | — | 0 |  |  |
| 38 | 🚶 Присутствие: Владелец ушёл | on | single | normal | — | 0 |  |  |
| 39 | ⚡ Цены дня — Elering | on | single | normal | 2026-07-15 14:23 | 2 |  |  |
| 40 | 🔥 Турбо нагрев — активация | on | restart | normal | 2026-05-24 18:24 | 0 |  |  |
| 41 | 🔥 Турбо нагрев — деактивация | on | single | normal | 2026-05-24 18:53 | 0 |  |  |
| 42 | 🔄 HA: проверка обновлений | on | single | normal | 2026-07-15 07:00 | 0 |  |  |
| 43 | 🔄 HA: авто-установка дополнений (03:00) | on | single | normal | — | 0 |  |  |
| 44 | 🌙 Ночная экономия: расписание (22:00 ВКЛ, 05:00 ВЫКЛ) | on | single | normal | 2026-07-15 02:00 | 0 |  |  |
| 45 | 🌡 Микроклимат: алерты (жара/влажность/воздух) | on | queued | normal | — | 0 |  |  |
| 46 | ♨️ Рециркуляция ГВС по расписанию + присутствие | on | single | normal | 2026-07-15 14:40 | 5 |  |  |

## HIGH criticality — Safety (water leak / smoke / security)

### 🚨 Утечка воды - аварийное отключение v4
- **id**: `1748000001001` · **entity**: `automation.ha_startup_grace_period`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: parallel · max=10
- **triggers**: state:['binary_sensor.vannaia_moisture', 'binary_sensor.garazh_moisture', 'binary_sensor.kukhnia_moisture', 'binary_sensor.water_sensor_4_moisture']->on for 00:03:00, state:['binary_sensor.vannaia_moisture', 'binary_sensor.garazh_moisture', 'binary_sensor.kukhnia_moisture']->off for 00:00:15
- **conditions**: 7 · **actions**: notify.send_message, switch.turn_off, select.select_option, number.set_value, siren.turn_on
- **last_triggered**: 2026-07-15T06:42:25.918681+00:00 · **traces stored**: 0 · **trace errors**: False
- template-constructed refs (ok): input_boolean.moisture_bypass_
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🧠 Самодиагностика дома v3
- **id**: `1765960140022` · **entity**: `automation.polnaia_samodiagnostika_doma_ai`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: time:11:00:00, time:15:00:00, time:19:00:00
- **conditions**: 0 · **actions**: notify.send_message
- **last_triggered**: 2026-07-15T12:00:00.328433+00:00 · **traces stored**: 0 · **trace errors**: False
- **⚠️ GHOST refs**: `sensor.ev_charger_ev_energiia_total`
- **⚠️ unavailable refs**: `sensor.occupancysensor_batareia`(unavailable), `sensor.signalizatsiia_dvernogo_datchika_battery`(unavailable), `sensor.signalizatsiia_dvernogo_datchika_battery_2`(unavailable)
- **documented in CLAUDE.md**: NO
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🤖 Telegram AI управление домом (Gemini) - FINAL
- **id**: `1766844364781` · **entity**: `automation.telegram_ai_upravlenie_domom_gemini`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: queued · max=10
- **triggers**: event:telegram_text
- **conditions**: 2 · **actions**: ai_task.generate_data, telegram_bot.send_message, scene.turn_on, switch.turn_on, switch.turn_off, switch.toggle, light.turn_on, light.turn_off, light.toggle
- **last_triggered**: 2026-07-12T19:12:46.477445+00:00 · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: NO
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🚨 Утечка воды - аварийное отключение v2
- **id**: `1775638334800` · **entity**: `automation.utechka_vody_avariinoe_otkliuchenie`
- **state**: off · **initial_state (yaml)**: `False` · **mode**: parallel · max=10
- **triggers**: state:['binary_sensor.vannaia_moisture', 'binary_sensor.garazh_moisture', 'binary_sensor.kukhnia_moisture', 'binary_sensor.water_sensor_4_moisture']->on for 00:03:00, state:['binary_sensor.vannaia_moisture', 'binary_sensor.garazh_moisture', 'binary_sensor.kukhnia_moisture']->off for 00:00:15
- **conditions**: 6 · **actions**: notify.send_message, switch.turn_off, select.select_option, number.set_value, siren.turn_on
- **last_triggered**: 2026-07-09T18:27:58.528225+00:00 · **traces stored**: 0 · **trace errors**: False
- template-constructed refs (ok): input_boolean.moisture_bypass_
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🔋 Алерт низкого заряда батарей
- **id**: `1775638921592` · **entity**: `automation.alert_nizkogo_zariada_batarei_3`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: time:09:00:00
- **conditions**: 0 · **actions**: notify.send_message
- **last_triggered**: 2026-07-15T06:00:00.118228+00:00 · **traces stored**: 0 · **trace errors**: False
- **⚠️ GHOST refs**: `sensor.signalizatsiia_dvernogo_datchika_2_battery`, `sensor.sm_t595_battery_level`
- **⚠️ unavailable refs**: `sensor.signalizatsiia_dvernogo_datchika_battery`(unavailable)
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 📲 Telegram обработчик кнопок
- **id**: `1778700001005` · **entity**: `automation.telegram_obrabotchik_knopok`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: queued · max=10
- **triggers**: event:telegram_callback
- **conditions**: 1 · **actions**: telegram_bot.send_message, input_boolean.turn_on, telegram_bot.answer_callback_query, notify.send_message, input_boolean.turn_off, siren.turn_off, switch.turn_off, select.select_option, number.set_value, siren.turn_on, switch.turn_on, homeassistant.turn_off
- **last_triggered**: 2026-07-12T19:12:55.510485+00:00 · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🔥 Задымление — сирена
- **id**: `1779200002001` · **entity**: `automation.zadymlenie_sirena`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: state:binary_sensor.wifi_th_smoke_sensor_smoke->on for 00:00:10, state:binary_sensor.wifi_th_smoke_sensor_smoke->off
- **conditions**: 2 · **actions**: select.select_option, number.set_value, siren.turn_on, notify.send_message, siren.turn_off
- **last_triggered**: — · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🛡 Охрана — тревога при срабатывании
- **id**: `1779200003001` · **entity**: `automation.okhrana_trevoga_pri_srabatyvanii`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single · max_exceeded=silent
- **triggers**: state:binary_sensor.door_sensor_door->on for 00:00:05, state:binary_sensor.motion_sensor_motion->on for 00:00:05
- **conditions**: 2 · **actions**: select.select_option, number.set_value, siren.turn_on, notify.send_message
- **last_triggered**: 2026-06-21T17:37:33.301307+00:00 · **traces stored**: 5 · **trace errors**: False
- **documented in CLAUDE.md**: NO
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🚨 Tuya: Gracе период при переподключении
- **id**: `1748000001004` · **entity**: `automation.tuya_grace_period_pri_perepodkliuchenii`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: restart
- **triggers**: state:['binary_sensor.vannaia_moisture', 'binary_sensor.garazh_moisture', 'binary_sensor.kukhnia_moisture', 'binary_sensor.water_sensor_4_moisture']->unavailable
- **conditions**: 0 · **actions**: input_boolean.turn_on, input_boolean.turn_off
- **last_triggered**: 2026-07-14T02:43:06.372597+00:00 · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: NO
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### ☁️ Tuya: авто-перезагрузка при обрыве датчика влаги
- **id**: `1748000001005` · **entity**: `automation.tuya_avto_perezagruzka_pri_obryve_datchika_vlagi`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: restart
- **triggers**: state:['binary_sensor.vannaia_moisture', 'binary_sensor.garazh_moisture', 'binary_sensor.kukhnia_moisture', 'binary_sensor.water_sensor_4_moisture']->unavailable, state:['binary_sensor.vannaia_moisture', 'binary_sensor.garazh_moisture', 'binary_sensor.kukhnia_moisture', 'binary_sensor.water_sensor_4_moisture']->on
- **conditions**: 0 · **actions**: homeassistant.reload_config_entry
- **last_triggered**: 2026-07-14T02:43:06.373392+00:00 · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: NO
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🚨 Устройство недоступно
- **id**: `1778900002001` · **entity**: `automation.ustroistvo_nedostupno`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: parallel · max=10
- **triggers**: state:['switch.smart_plug_2_socket_1', 'switch.kalarifer_socket_1', 'switch.ev_charger_switch', 'switch.retserkuliatsiia_goriachai_vody_socket_1', 'switch.akvarium_svet_socket_1', 'sensor.nord_pool_lv_current_price', 'sensor.ev_charger_status', 'binary_sensor.vannaia_moisture', 'binary_sensor.garazh_moisture', 'binary_sensor.kukhnia_moisture', 'binary_sensor.water_sensor_4_moisture']->unavailable for {'minutes': 5}
- **conditions**: 1 · **actions**: telegram_bot.send_message
- **last_triggered**: 2026-07-03T05:22:19.486325+00:00 · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: NO
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

## HIGH criticality — Heating / EV / Boiler

### 🔌 Уведомления о розетках (умные) v7
- **id**: `1765801568958` · **entity**: `automation.uvedomleniia_o_rozetkakh`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: parallel · max=10
- **triggers**: state:['switch.akvarium_svet_socket_1', 'switch.retserkuliatsiia_goriachai_vody_socket_1', 'switch.zigbee_plug_socket_1', 'switch.zigbee_plug_2_socket_1', 'switch.ev_charger_switch']->['on', 'off'] for 00:00:20, state:['switch.akvarium_svet_socket_1', 'switch.retserkuliatsiia_goriachai_vody_socket_1', 'switch.zigbee_plug_socket_1', 'switch.ev_charger_switch']->unavailable for 00:02:00, state:switch.zigbee_plug_2_socket_1->unavailable for 00:30:00
- **conditions**: 1 · **actions**: notify.send_message
- **last_triggered**: 2026-07-15T14:30:21.176149+00:00 · **traces stored**: 5 · **trace errors**: False
- **documented in CLAUDE.md**: NO
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🔥 Бойлер по Nord Pool (<=0.04 ON, >0.04 OFF)
- **id**: `1766138420302` · **entity**: `automation.boiler_kalorifer_po_tsene_porog_0_04`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: ha:start, state:sensor.nord_pool_lv_current_price for 00:00:30
- **conditions**: 1 · **actions**: switch.turn_on, notify.send_message, switch.turn_off
- **last_triggered**: 2026-07-15T14:30:30.004165+00:00 · **traces stored**: 5 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🔥 Тёплый пол ванная по Nord Pool (<=0.04 manual 30C, >0.04 auto)
- **id**: `1767188164410` · **entity**: `automation.teplyi_pol_po_nord_pool_0_04_heat_30c_0_04_auto`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: numeric_state:sensor.nord_pool_lv_current_price<0.04001 for {'minutes': 2}, numeric_state:sensor.nord_pool_lv_current_price>0.04 for {'minutes': 2}
- **conditions**: 1 · **actions**: climate.set_hvac_mode, climate.set_preset_mode, climate.set_temperature
- **last_triggered**: 2026-07-15T14:32:00.003688+00:00 · **traces stored**: 1 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🚗 EV зарядка по цене рынка
- **id**: `1774376407472` · **entity**: `automation.ev_zariadka_po_tsene_0_04`
- **state**: off · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: numeric_state:sensor.nord_pool_lv_current_price<0.04, numeric_state:sensor.nord_pool_lv_current_price>0.05, time_pattern:{'minutes': '/30'}
- **conditions**: 1 · **actions**: switch.turn_on, notify.send_message, switch.turn_off
- **last_triggered**: 2026-04-08T09:00:00.268070+00:00 · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🔄 Бойлер sync после старта HA
- **id**: `1775106692658` · **entity**: `automation.boiler_sync_posle_starta_ha`
- **state**: off · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: ha:start
- **conditions**: 1 · **actions**: switch.turn_on, notify.send_message, switch.turn_off
- **last_triggered**: 2026-04-08T08:05:25.962275+00:00 · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🔥 Тёплый пол душевая 1эт по Nord Pool (<=0.04 manual 30C, >0.04 auto)
- **id**: `1776085158491` · **entity**: `automation.teplyi_pol_dushevaia_1et_po_nord_pool_0_04_heat_30c_0_04_auto`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: ha:start, state:sensor.nord_pool_lv_current_price for 00:00:30
- **conditions**: 1 · **actions**: climate.set_hvac_mode, climate.set_preset_mode, climate.set_temperature
- **last_triggered**: 2026-07-15T14:30:30.005142+00:00 · **traces stored**: 5 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### ☀️ Утренний брифинг
- **id**: `1778700001001` · **entity**: `automation.utrennii_brifing`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: time:07:00:00
- **conditions**: 0 · **actions**: notify.send_message
- **last_triggered**: 2026-07-15T04:00:00.138418+00:00 · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🕛 Снимок энергии (полночь)
- **id**: `1778700001002` · **entity**: `automation.snimok_energii_polnoch`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: time:00:01:00
- **conditions**: 0 · **actions**: input_number.set_value
- **last_triggered**: 2026-07-14T21:01:00.458635+00:00 · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 📊 Ежедневный отчёт потребления
- **id**: `1778700001003` · **entity**: `automation.ezhednevnyi_otchet_potrebleniia`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: time:23:00:00
- **conditions**: 0 · **actions**: notify.send_message
- **last_triggered**: 2026-07-14T20:00:00.175994+00:00 · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: NO
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🚗 EV зарядка — планировщик
- **id**: `1778800001001` · **entity**: `automation.ev_zariadka_planirovshchik`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: state:sensor.nord_pool_lv_lowest_price, ha:start, time:14:05:00
- **conditions**: 1 · **actions**: shell_command.ev_find_best2h
- **last_triggered**: 2026-07-15T14:23:10.327098+00:00 · **traces stored**: 2 · **trace errors**: False
- **documented in CLAUDE.md**: NO
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🚗 EV зарядка — автозарядка 2ч
- **id**: `1778800001002` · **entity**: `automation.ev_zariadka_avtozariadka_2ch`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: time:input_datetime.ev_charge_start
- **conditions**: 2 · **actions**: switch.turn_on, switch.turn_off, telegram_bot.send_message, notify.send_message
- **last_triggered**: 2026-07-14T11:30:00.003064+00:00 · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### Котёл — откл. ГВС при работе бойлера
- **id**: `1778900001001` · **entity**: `automation.kotel_otkl_gvs_pri_rabote_boilera`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: state:switch.smart_plug_2_socket_1->on, state:switch.smart_plug_2_socket_1->off
- **conditions**: 2 · **actions**: rest_command.disable_boiler_cwu, notify.send_message, input_datetime.set_datetime, rest_command.enable_boiler_cwu
- **last_triggered**: 2026-07-15T13:15:15.180377+00:00 · **traces stored**: 2 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🔥 Котёл: уведомления о режиме и уставках
- **id**: `1779000001002` · **entity**: `automation.kotel_uvedomleniia_o_rezhime_i_ustavkakh`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: queued · max=5
- **triggers**: state:sensor.boiler_mode for 00:00:05, state:sensor.boiler_cwu_setpoint for 00:00:10, state:sensor.boiler_co_setpoint for 00:00:10
- **conditions**: 2 · **actions**: notify.send_message
- **last_triggered**: 2026-07-15T14:32:03.233116+00:00 · **traces stored**: 5 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🏠 Присутствие: Владелец вернулся
- **id**: `1779200001003` · **entity**: `automation.prisutstvie_owner_vernulsia`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: state:binary_sensor.prisutstvie_owner->on
- **conditions**: 1 · **actions**: notify.send_message
- **last_triggered**: — · **traces stored**: 0 · **trace errors**: False
- **⚠️ GHOST refs**: `sensor.boiler_temp_co`, `sensor.boiler_temp_cwu`
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🚗 EV: сброс ручного режима при окончании зарядки
- **id**: `1748000001006` · **entity**: `automation.ev_sbros_ruchnogo_rezhima_pri_okonchanii_zariadki`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: state:sensor.ev_charger_status->charger_end, state:sensor.ev_charger_status->charger_free, state:input_boolean.ev_manual_mode->on for 03:00:00
- **conditions**: 1 · **actions**: input_boolean.turn_off, notify.send_message
- **last_triggered**: 2026-07-13T14:14:56.921985+00:00 · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: NO
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### ⚡🔥 EV + Бойлер: интерлок
- **id**: `1779000001001` · **entity**: `automation.ev_boiler_interlok`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: restart
- **triggers**: state:switch.ev_charger_switch->on, state:sensor.ev_charger_status->charger_charging, state:switch.ev_charger_switch->off, state:sensor.ev_charger_status->['charger_free', 'charger_end', 'charger_pause']
- **conditions**: 0 · **actions**: switch.turn_off, switch.turn_on
- **last_triggered**: 2026-07-15T13:15:14.485286+00:00 · **traces stored**: 2 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🔥 Полотенцесушитель по Nord Pool (<=0.04 ON, >0.04 OFF)
- **id**: `1783000001001` · **entity**: `automation.polotentsesushitel_po_nord_pool_0_04_on_0_04_off`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: ha:start, state:sensor.nord_pool_lv_current_price for 00:00:30
- **conditions**: 1 · **actions**: switch.turn_on, notify.send_message, switch.turn_off
- **last_triggered**: 2026-07-15T14:30:30.005937+00:00 · **traces stored**: 5 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🌙 Ночная экономия: применить
- **id**: `1784000001002` · **entity**: `automation.nochnaia_ekonomiia_primenit`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: state:input_boolean.night_saver
- **conditions**: 0 · **actions**: scene.create, switch.turn_off, climate.set_preset_mode, notify.send_message, scene.turn_on, switch.turn_on, climate.set_hvac_mode, climate.set_temperature
- **last_triggered**: 2026-07-15T02:00:00.408628+00:00 · **traces stored**: 0 · **trace errors**: False
- runtime-created refs (ok): scene.before_night_saver
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 💶 Учёт стоимости (за день → месяц)
- **id**: `1785000001001` · **entity**: `automation.uchet_stoimosti_za_den_mesiats`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: time:23:58:00
- **conditions**: 0 · **actions**: input_number.set_value
- **last_triggered**: 2026-07-14T20:58:00.075764+00:00 · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 💶 Месячный отчёт расходов
- **id**: `1785000001002` · **entity**: `automation.mesiachnyi_otchet_raskhodov`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: time:00:05:00
- **conditions**: 1 · **actions**: notify.send_message, input_number.set_value
- **last_triggered**: 2026-07-05T10:06:59.696164+00:00 · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🔄 Гард сброса счётчика энергии
- **id**: `1786000001001` · **entity**: `automation.gard_sbrosa_schetchika_energii`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: queued · max=10
- **triggers**: state:['sensor.boiler_total_energy', 'sensor.terarium_total_energy', 'sensor.akvarium_svet_total_energy', 'sensor.cherepakha_total_energy', 'sensor.zigbee_plug_2_total_energy', 'sensor.ev_charger_energy']
- **conditions**: 1 · **actions**: input_number.set_value, notify.send_message
- **last_triggered**: 2026-07-15T14:39:26.541252+00:00 · **traces stored**: 5 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

## Normal criticality

### 📊 Ежедневный прогноз цен электричества (Nord Pool) v4.2
- **id**: `1765800603456` · **entity**: `automation.ezhednevnyi_prognoz_tsen_elektrichestva`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: state:sensor.nord_pool_lv_current_price, time:14:10:00, time:19:10:00
- **conditions**: 1 · **actions**: notify.send_message
- **last_triggered**: 2026-07-15T11:10:00.486225+00:00 · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: NO
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### ⏰ Скоро будет дешёвое электричество
- **id**: `1765800619701` · **entity**: `automation.skoro_budet_deshevoe_elektrichestvo`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: numeric_state:sensor.nord_pool_lv_next_price<0.04 for {'minutes': 2}
- **conditions**: 2 · **actions**: telegram_bot.send_message
- **last_triggered**: 2026-07-15T14:17:00.003834+00:00 · **traces stored**: 1 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### Ночной патруль (23:30)
- **id**: `1768228398352` · **entity**: `automation.nochnoi_patrul_podsvetki_proverka_v_23_30`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: time:23:30:00
- **conditions**: 0 · **actions**: telegram_bot.send_message
- **last_triggered**: 2026-07-14T20:30:00.201707+00:00 · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 📲 Telegram меню с кнопками
- **id**: `1778700001004` · **entity**: `automation.telegram_meniu_s_knopkami`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: event:telegram_text
- **conditions**: 1 · **actions**: telegram_bot.send_message
- **last_triggered**: 2026-07-12T19:12:46.484583+00:00 · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### ⚠️ Tailscale: ключ истекает
- **id**: `1779200001001` · **entity**: `automation.tailscale_kliuch_istekaet`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: time:09:00:00
- **conditions**: 1 · **actions**: notify.send_message
- **last_triggered**: — · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🚶 Присутствие: Владелец ушёл
- **id**: `1779200001002` · **entity**: `automation.prisutstvie_owner_ushel`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: state:binary_sensor.prisutstvie_owner->off
- **conditions**: 1 · **actions**: homeassistant.turn_off, notify.send_message
- **last_triggered**: — · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### ⚡ Цены дня — Elering
- **id**: `1748100001001` · **entity**: `automation.tseny_dnia_elering_hourly`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: time:00:10:00, time:13:10:00, ha:start
- **conditions**: 0 · **actions**: shell_command.update_today_prices
- **last_triggered**: 2026-07-15T14:23:10.330535+00:00 · **traces stored**: 2 · **trace errors**: False
- **documented in CLAUDE.md**: NO
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🔥 Турбо нагрев — активация
- **id**: `1748000001002` · **entity**: `automation.turbo_nagrev_aktivatsiia`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: restart
- **triggers**: state:input_boolean.turbo_hot_water->on
- **conditions**: 0 · **actions**: switch.turn_on, rest_command.turbo_boiler_cwu, notify.send_message, input_boolean.turn_off
- **last_triggered**: 2026-05-24T18:24:51.481404+00:00 · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: NO
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🔥 Турбо нагрев — деактивация
- **id**: `1748000001003` · **entity**: `automation.turbo_nagrev_deaktivatsiia`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: state:input_boolean.turbo_hot_water->off
- **conditions**: 0 · **actions**: rest_command.enable_boiler_cwu, rest_command.disable_boiler_cwu, notify.send_message
- **last_triggered**: 2026-05-24T18:53:19.359393+00:00 · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: NO
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🔄 HA: проверка обновлений
- **id**: `1782000001001` · **entity**: `automation.ha_proverka_obnovlenii`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: time:10:00:00
- **conditions**: 1 · **actions**: notify.send_message
- **last_triggered**: 2026-07-15T07:00:00.393526+00:00 · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🔄 HA: авто-установка дополнений (03:00)
- **id**: `1782000001002` · **entity**: `automation.ha_avto_ustanovka_dopolnenii_03_00`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: time:03:00:00
- **conditions**: 1 · **actions**: update.install, notify.send_message
- **last_triggered**: — · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🌙 Ночная экономия: расписание (22:00 ВКЛ, 05:00 ВЫКЛ)
- **id**: `1784000001001` · **entity**: `automation.nochnaia_ekonomiia_raspisanie_22_00_vkl_05_00_vykl`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: time:22:00:00, time:05:00:00
- **conditions**: 0 · **actions**: input_boolean.turn_off, input_boolean.turn_on
- **last_triggered**: 2026-07-15T02:00:00.407919+00:00 · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### 🌡 Микроклимат: алерты (жара/влажность/воздух)
- **id**: `1786000001002` · **entity**: `automation.mikroklimat_alerty_zhara_vlazhnost_vozdukh`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: queued · max=10
- **triggers**: numeric_state:['sensor.kukhnia_temperature', 'sensor.miaomiaoc_cn_blt_3_living_t1_temperature_p_2_1', 'sensor.lumi_cn_lumi_bedroom_th_v1_temperature_p_2_1']>28 for {'minutes': 15}, numeric_state:['sensor.kukhnia_humidity', 'sensor.miaomiaoc_cn_blt_3_living_t1_relative_humidity_p_2_2', 'sensor.lumi_cn_lumi_bedroom_th_v1_relative_humidity_p_2_2']>70 for {'minutes': 15}, numeric_state:sensor.zhimi_cn_purifier_mb3_pm2_5_density_p_3_6>35 for {'minutes': 10}
- **conditions**: 1 · **actions**: notify.send_message
- **last_triggered**: — · **traces stored**: 0 · **trace errors**: False
- **documented in CLAUDE.md**: yes
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

### ♨️ Рециркуляция ГВС по расписанию + присутствие
- **id**: `1789000001001` · **entity**: `automation.retsirkuliatsiia_gvs_po_raspisaniiu_prisutstvie`
- **state**: on · **initial_state (yaml)**: `(unset)` · **mode**: single
- **triggers**: time_pattern:{'minutes': '/10'}, state:binary_sensor.prisutstvie_owner, state:input_boolean.night_saver
- **conditions**: 0 · **actions**: switch.turn_on, switch.turn_off
- **last_triggered**: 2026-07-15T14:40:00.310140+00:00 · **traces stored**: 5 · **trace errors**: False
- **documented in CLAUDE.md**: NO
- **disable manually**: REST POST /api/services/automation/turn_off {entity_id} OR set initial_state:false in automations.yaml

## Scripts (scripts.yaml)

| entity_id | alias | state | actions | ghosts |
|---|---|---|---|---|
| `script.scene_away` | 🚪 Ушёл из дома | off | light.turn_off, switch.turn_off, input_boolean.turn_on, notify.send_message |  |
| `script.scene_cinema` | 🎬 Кино | off | light.turn_off, switch.turn_off, switch.turn_on, notify.send_message |  |
| `script.scene_guests` | 🎉 Гости | off | light.turn_on, notify.send_message |  |
| `script.rezhim_zhara_on` | 🔥 Жара — выключить весь нагрев (кроме бойлера) | off | input_boolean.turn_on, switch.turn_off, climate.turn_off, notify.send_message |  |
| `script.rezhim_zhara_off` | ❄️ Жара — выключить режим, вернуть нагрев | off | input_boolean.turn_off, climate.set_hvac_mode, climate.set_preset_mode, notify.send_message |  |

## Scenes
- **scenes.yaml**: EMPTY (0 file-defined scenes)
- **Runtime-created**: scene.before_night_saver (scene.create in Night-saver automation)
- **Integration scenes (22)** — all 22 from Tuya cloud integration:
  - `scene.otkrylas_dver`
  - `scene.turn_off_all_sockets`
  - `scene.turn_on_all_sockets`
  - `scene.vkliuchit_koridor_vtoroi_etazh`
  - `scene.vkliuchit_svet_kukhnia`
  - `scene.vkliuchit_svet_nad_akvariumom`
  - `scene.vkliuchit_svet_nad_stolom`
  - `scene.vkliuchit_svet_ostrov`
  - `scene.vkliuchit_svet_stena`
  - `scene.vkliuchit_svet_tv_zona`
  - `scene.vkliuchit_svet_u_lestnitsy`
  - `scene.vkliuchit_svet_zanaveski`
  - `scene.vykliuchit_ostrov_svet`
  - `scene.vykliuchit_svet_kukhnia`
  - `scene.vykliuchit_svet_nad_akvariumom`
  - `scene.vykliuchit_svet_nad_stolom`
  - `scene.vykliuchit_svet_pervyi_etazh`
  - `scene.vykliuchit_svet_stena`
  - `scene.vykliuchit_svet_tv_zona`
  - `scene.vykliuchit_svet_u_lestnitsi`
  - `scene.vykliuchit_svet_zanaveski`
  - `scene.vykliuchit_vtoroi_etazh_koridor`

## input_boolean helpers
| entity_id | name | state |
|---|---|---|
| `input_boolean.ev_manual_mode` | EV Manual Mode | on |
| `input_boolean.ha_startup_grace` | HA Startup Grace | on |
| `input_boolean.input_boolean_boiler_price_active` | input_boolean.boiler_price_active | off |
| `input_boolean.moisture_bypass_garazh` | Bypass влага гараж | off |
| `input_boolean.moisture_bypass_kukhnia` | Bypass влага кухня | off |
| `input_boolean.moisture_bypass_vannaia` | Bypass влага ванная | off |
| `input_boolean.moisture_bypass_water_sensor_4` | Bypass влага душевая 1эт Period | off |
| `input_boolean.night_saver` | Ночная экономия | off |
| `input_boolean.rezhim_zhara` | Режим Жара (лето, нагрев выкл) | on |
| `input_boolean.security_armed` | Охрана | off |
| `input_boolean.turbo_hot_water` | Турбо нагрев воды | off |
| `input_boolean.tuya_reconnect_grace` | Tuya Reconnect Grace Period | off |

## input_number helpers
| entity_id | name | state |
|---|---|---|
| `input_number.cost_month_akv` | Cost month akv | 0.29 |
| `input_number.cost_month_boiler` | Cost month boiler | 5.84 |
| `input_number.cost_month_chep` | Cost month chep | 0.3 |
| `input_number.cost_month_ev` | Cost month ev | 4.46 |
| `input_number.cost_month_gidro` | Cost month gidro | 41.85 |
| `input_number.cost_month_kalarifer` | Cost month kalarifer | 0.33 |
| `input_number.cost_month_total` | Cost month total | 53.08 |
| `input_number.midnight_akv_energy` | Snapshot aquarium midnight | 0.023 |
| `input_number.midnight_boiler_energy` | Snapshot boiler midnight | 10.099 |
| `input_number.midnight_chep_energy` | Snapshot turtle midnight | 0.001 |
| `input_number.midnight_ev_energy` | Snapshot EV midnight | 882.8 |
| `input_number.midnight_gidro_energy` | Snapshot hydrophore midnight | 275.34 |
| `input_number.midnight_kalarifer_energy` | Snapshot kalarifer midnight | 0.0 |
| `input_number.midnight_tv_energy` | Snapshot TV midnight | 0.0 |

## input_datetime helpers
| entity_id | name | state |
|---|---|---|
| `input_datetime.ev_charge_start` | EV Charge Start Time | 2026-07-16 10:30:00 |
| `input_datetime.gvs_last_notify_off` | ГВС — последнее уведомление plug_off | 1970-01-01 00:00:00 |
| `input_datetime.gvs_last_notify_on` | ГВС — последнее уведомление plug_on | 1970-01-01 00:00:00 |

## Empty helper domains
- **input_select**: none defined
- **input_text**: none defined
- **timer**: none defined
- **schedule**: none defined
- **utility_meter**: none defined
- **integration_riemann_sensors**: none defined (no riemann/integration/derivative helpers)

## command_line sensors
- `sensor.ev_charger_energy` — cmd `python3 /config/ev_query.py` (scan 300s) — state: 882.8
- `sensor.ev_charger_status` — cmd `python3 /config/ev_query.py` (scan 300s) — state: charger_charging

## shell_command
- `update_today_prices` → `python3 /config/update_today_prices.py`
- `ev_find_best2h` → `python3 /config/ev_best2h.py`
- `ev_night2h` → `python3 /config/ev_night2h.py`
- `ev_day2h` → `python3 /config/ev_day2h.py`

## rest_command (ecoNET boiler)
_All target ecoNET boiler 192.168.1.10 (HTTP basic auth; credentials REDACTED). set_boiler_* take {{ temp }}_
- `boiler_turn_on`
- `boiler_turn_off`
- `set_boiler_cwu_temp`
- `set_boiler_co_temp`
- `disable_boiler_cwu`
- `enable_boiler_cwu`
- `turbo_boiler_cwu`

## REST sensors (ecoNET boiler)
_21 sensors/binary_sensors from single REST resource ecoNET boiler regParams (scan 30s; creds REDACTED). Each has per-field availability guard (fixed 2026-07-12)_

- `sensor.boiler_co_temperature`
- `binary_sensor.boiler_co_pump`
- `sensor.boiler_co_setpoint`
- `binary_sensor.boiler_cwu_pump`
- `binary_sensor.boiler_fan`
- `binary_sensor.boiler_feeder`
- `sensor.boiler_cwu_temperature`
- `sensor.boiler_cwu_setpoint`
- `sensor.boiler_return_temperature`
- `sensor.boiler_flue_gas_temperature`
- `sensor.boiler_outside_temperature`
- `sensor.boiler_feeder_temperature`
- `sensor.boiler_fan_power`
- `sensor.boiler_power`
- `sensor.boiler_mode`
- `sensor.boiler_fuel_level`
- `sensor.boiler_mixer_temperature`
- `sensor.boiler_mixer_setpoint`
- `binary_sensor.boiler_alarm`
- `binary_sensor.boiler_circulation_pump`
- `binary_sensor.boiler_thermostat`

## Template entities
- `binary_sensor.prisutstvie_owner` (Присутствие Владелец) — state: on — logic: person.owner=home OR device_tracker.myiphone=home OR sensor.ssid=HOME_WIFI; delay_on 10s / delay_off 10min

## Custom components
_localtuya & plum_ecomax present on disk but NOT active integrations per CLAUDE.md (Tuya via cloud, boiler via REST). miniapp_auth serves /api/miniapp-* (Mini App + tablet actions). xiaomi_home=92 entities, tapo_control=Tapo cams._
- `hacs`
- `localtuya`
- `miniapp_auth`
- `plum_ecomax`
- `tapo_control`
- `xiaomi_home`

## panel_custom
- tablet-panel (/local/tablet-panel.js) — sidebar "Умный дом"

---
_Machine-readable equivalent: `docs/audit/automation_inventory.json`. Trace counts reflect only traces retained by HA (most automations have 0 stored since last restart); `last_triggered` is authoritative for run recency._