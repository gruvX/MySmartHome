# House Capability Audit — 2026-08-16 (READ-ONLY)

HA 2026.8.2 · Home · TZ Europe/Riga · unit EUR
Totals: **817 live states**, **1019 registry entities** (205 disabled), **193 devices**, **39 config entries**, **14 areas**, 2 floors.

Source data (raw JSON, same folder): registries + states dumped via HA WS/REST at audit time.

---

## 1. Integrations (config entries)

| domain | title | state | devices | entities | disabled | unavail/unknown | verdict |
|---|---|---|---|---|---|---|---|
| analytics | Analytics | loaded | 0 | 0 | 0 | 0 | service-only |
| apple_tv | Главная спальня | loaded | 1 | 3 | 0 | 0 | healthy |
| backup | Backup | loaded | 1 | 5 | 0 | 0 | healthy |
| cloud | Home Assistant Cloud | loaded | 0 | 3 | 0 | 3 | **dead** (all entities unavailable) |
| co2signal | Electricity Maps | loaded | 1 | 2 | 0 | 0 | healthy |
| dlna_dmr | XBOX | loaded | 1 | 1 | 0 | 1 | **dead** (all entities unavailable) |
| dlna_dmr | SOLAS TV | loaded | 1 | 1 | 0 | 1 | **dead** (all entities unavailable) |
| go2rtc | go2rtc | loaded | 0 | 0 | 0 | 0 | service-only |
| google | owner@example.com | loaded | 0 | 6 | 1 | 0 | healthy |
| google_generative_ai_conversation | Google Generative AI | loaded | 4 | 4 | 0 | 2 | degraded (2/4 unavail) |
| google_translate | Google Translate text-to-speech | loaded | 1 | 1 | 0 | 1 | **dead** (all entities unavailable) |
| hacs |  | loaded | 17 | 34 | 17 | 0 | healthy |
| hassio | Supervisor | loaded | 10 | 56 | 47 | 0 | healthy |
| homekit | media_player.mitv_mssp2:21066 | loaded | 1 | 0 | 0 | 0 | healthy |
| homekit | remote.mitv_mssp2:21067 | loaded | 1 | 0 | 0 | 0 | healthy |
| homekit | HASS Bridge:21064 | loaded | 1 | 0 | 0 | 0 | healthy |
| local_ip | local_ip | loaded | 0 | 1 | 0 | 0 | healthy |
| matter | Matter | loaded | 5 | 19 | 4 | 15 | **dead** (all entities unavailable) |
| met | Home | loaded | 1 | 1 | 0 | 0 | healthy |
| mobile_app | phone | loaded | 1 | 22 | 0 | 2 | healthy |
| mobile_app | phone | loaded | 1 | 26 | 0 | 19 | degraded (19/26 unavail) |
| mobile_app | SM-T595 | loaded | 1 | 90 | 85 | 1 | healthy |
| nordpool | Nord Pool | loaded | 1 | 25 | 17 | 0 | healthy |
| oralb | IO Series 6/7 A913 | loaded | 1 | 9 | 2 | 0 | healthy |
| proxmoxve | 192.168.1.8 | loaded | 12 | 195 | 6 | 66 | healthy |
| radio_browser | Radio Browser | loaded | 0 | 0 | 0 | 0 | service-only |
| roborock | owner@example.com | loaded | 2 | 34 | 4 | 3 | healthy |
| samsungtv | 75&quot; QLED (QE75Q8FAAUXXH) | loaded | 1 | 2 | 0 | 0 | healthy |
| shopping_list | Shopping list | loaded | 0 | 1 | 0 | 0 | healthy |
| smartthings | Дом | loaded | 50 | 61 | 0 | 3 | healthy |
| sun | Sun | loaded | 1 | 9 | 3 | 0 | healthy |
| telegram_bot | МойУмныйДом | loaded | 2 | 2 | 0 | 0 | healthy |
| thread | Thread | loaded | 0 | 0 | 0 | 0 | service-only |
| tuya | ap-001165.7ee8ab2700ee4cdcb926e30b2192cc57.0 | loaded | 60 | 152 | 18 | 31 | healthy |
| version | Home Assistant Versions | loaded | 1 | 2 | 0 | 0 | healthy |
| xiaomi_home | <аккаунт Xiaomi> [中国大陆] | loaded | 10 | 87 | 0 | 58 | degraded (58/87 unavail) |
| androidtv_remote | MiTV-MSSP2 | setup_retry | 1 | 2 | 0 | 2 | **DEAD** — Couldn't connect to 192.168.1.63:6466 |
| homekit | Интеллектуальный дверной звонок:21065 | not_loaded | 1 | 0 | 0 | 0 | **DEAD** — user |
| ipp | HP LaserJet 200 color M251n (16DD3C) | setup_retry | 1 | 6 | 1 | 5 | **DEAD** — Invalid response from API: Error occurred while communicating with IPP server. |

---

## 2. Areas / rooms

Area registry is **largely unused and internally duplicated** — see verdict column.

| area_id | name | floor | devices | live entities | domains present |
|---|---|---|---|---|---|
| `server` | Server | 1этаж | 10 | 159 | sensor×89, button×53, binary_sensor×17 |
| `gostinaia` | Гостиная | — | 47 | 68 | switch×40, sensor×17, event×4, light×3, binary_sensor×2, media_player×1, number×1 |
| `<xiaomi-account-id>` | <xiaomi-account-id> | — | 1 | 57 | sensor×27, number×15, event×4, button×3, select×2, switch×2, binary_sensor×1, fan×1 |
| `kitchen` | Kitchen | 1этаж | 2 | 31 | sensor×15, binary_sensor×3, select×3, image×3, time×2, media_player×1, remote×1, number×1 |
| `spalnia` | Спальня | — | 2 | 6 | sensor×5, event×1 |
| `bedroom` | Bedroom | — | 2 | 5 | switch×2, media_player×1, select×1, sensor×1 |
| `koridor` | Коридор | — | 1 | 5 | sensor×4, event×1 |
| `akvarium` | Аквариум | 1этаж | 1 | 4 | switch×2, select×1, sensor×1 |
| `vannia` | Вання | 2 этаж | 1 | 4 | switch×2, binary_sensor×1, climate×1 |
| `glavnaia_spalnia` | Главная спальня | — | 1 | 3 | media_player×1, remote×1, binary_sensor×1 |
| `kukhnia` | Кухня | 1этаж | 1 | 3 | event×3 |
| `vannaia` | Ванная | — | 1 | 3 | event×3 |
| `living_room` | Living Room | 1этаж | 0 | 0 | — |
| `vkhodnaia_dver` | входная дверь | — | 0 | 0 | — |

**Duplicate / junk areas:** `spalnia`(Спальня) vs `bedroom`(Bedroom) vs `glavnaia_spalnia`; `kukhnia`(Кухня) vs `kitchen`(Kitchen); `vannia`(Вання) vs `vannaia`(Ванная); `gostinaia`(Гостиная) vs `living_room`(Living Room, empty); `<xiaomi-account-id>` is a raw **Xiaomi cloud account id**, not a room (57 entities dumped there); `server` holds 159 entities (Proxmox) and is not a living space; `living_room` and `vkhodnaia_dver` are **completely empty**.

### 2.1 Entities with NO area — **466** enabled entities are invisible to any room-based UI

| domain | count |
|---|---|
| sensor | 134 |
| automation | 69 |
| switch | 31 |
| binary_sensor | 29 |
| update | 27 |
| scene | 22 |
| event | 19 |
| select | 17 |
| script | 17 |
| input_datetime | 16 |
| input_boolean | 14 |
| input_number | 14 |
| button | 13 |
| light | 11 |
| number | 5 |
| calendar | 5 |
| notify | 4 |
| tts | 3 |
| device_tracker | 3 |
| media_player | 2 |
| stt | 2 |
| person | 1 |
| todo | 1 |
| weather | 1 |
| ai_task | 1 |
| conversation | 1 |
| remote | 1 |
| humidifier | 1 |
| siren | 1 |
| climate | 1 |

Critically, the **controllable** ones with no area:

- **light** (11): `light.1_dimmer_switch`, `light.2dimmerswitch`, `light.2dimmerswitch_2`, `light.pro4_humidifier`, `light.svet_pervyi_etazh_1_light`, `light.svet_pervyi_etazh_1_light_2`, `light.vtoroi_etazh_light`, `light.dream_color_rgb`, `light.veranda_light`, `light.prikhozhaia_i_fanar_light`, `light.prikhozhaia_i_fanar_light_2`
- **switch** (31): `switch.gerlianda_i_prozhektor`, `switch.boiler`, `switch.outlet1_4`, `switch.outlet51_2`, `switch.4kh_konalnyi_kontroler`, `switch.retserkuliatsiia_goriachai_vody_child_lock`, `switch.retserkuliatsiia_goriachai_vody_socket_1`, `switch.wifi_th_smoke_sensor_mute`, `switch.kukhnia_poloski_switch_1`, `switch.kukhnia_poloski_switch_2`, `switch.gostinnaia_zanaveska_zona_switch_1`, `switch.gostinnaia_zanaveska_zona_switch_2`, `switch.svet_tv_zona_switch_1`, `switch.svet_tv_zona_switch_2`, `switch.smart_plug_2_child_lock`, `switch.smart_plug_2_socket_1`, `switch.smart_switch_2ch_switch_1`, `switch.smart_switch_2ch_switch_2`, `switch.220v_wifi_smart_dry_contact_switch_switch_1`, `switch.220v_wifi_smart_dry_contact_switch_switch_2`, `switch.220v_wifi_smart_dry_contact_switch_switch_3`, `switch.220v_wifi_smart_dry_contact_switch_switch_4`, `switch.zigbee_plug_child_lock`, `switch.zigbee_plug_socket_1`, `switch.zigbee_plug_2_child_lock`, `switch.zigbee_plug_2_socket_1`, `switch.ev_charger_switch`, `switch.voda_kran_switch_1`, `switch.perekryt_vodu`, `switch.floor_heating_child_lock_2`, `switch.floor_heating_frost_protection_2`
- **climate** (1): `climate.floor_heating_2`
- **siren** (1): `siren.alarm`
- **media_player** (2): `media_player.solas_tv`, `media_player.75_qled_qe75q8faauxxh`
- **humidifier** (1): `humidifier.pro4_humidifier`
- **remote** (1): `remote.75_qled_qe75q8faauxxh`
- **number** (5): `number.occupancysensor_hold_time`, `number.1_dimmer_switch_na_urovne`, `number.2dimmerswitch_na_urovne`, `number.2dimmerswitch_na_urovne_2`, `number.alarm_time`
- **select** (17): `select.retserkuliatsiia_goriachai_vody_power_on_behavior`, `select.retserkuliatsiia_goriachai_vody_indicator_light_mode`, `select.svet_pervyi_etazh_1_power_on_behavior`, `select.vtoroi_etazh_power_on_behavior`, `select.kukhnia_poloski_power_on_behavior`, `select.gostinnaia_zanaveska_zona_power_on_behavior`, `select.svet_tv_zona_power_on_behavior`, `select.veranda_power_on_behavior`, `select.prikhozhaia_i_fanar_power_on_behavior`, `select.smart_plug_2_power_on_behavior`, `select.smart_plug_2_indicator_light_mode`, `select.smart_switch_2ch_power_on_behavior`, `select.220v_wifi_smart_dry_contact_switch_power_on_behavior`, `select.zigbee_plug_power_on_behavior`, `select.zigbee_plug_2_power_on_behavior`, `select.alarm_volume`, `select.voda_kran_power_on_behavior`

> Implication for the new UI: a room-first navigation model cannot be built from the HA area registry as it stands. Either the registry gets fixed first, or the new UI must carry its own room map (a static entity→room table in the front-end), which is what the current tablet/Mini App do.

---

## 3. Per-device capabilities — CONTROL vs OBSERVE

`a=` references in automations.yaml/scripts.yaml/configuration.yaml, `u=` references in the deployed UI files (`tablet-panel.js`, `smarthouse.html`, `livemap.html`, `boiler.html`). `a=0 u=0` means nothing in the house uses it today.

### 3.1 Climate — electric floor heating (2 zones, Tuya)

| | |
|---|---|
| entities | `climate.floor_heating` (Ванная, a=55 u=30), `climate.floor_heating_2` (Душевая 1эт, a=25 u=15) |
| hvac_modes | `off`, `heat_cool` — **`off` IS available** (both zones read `off` right now; the project notes claiming "only heat_cool" are out of date) |
| preset_modes | `auto` (follow the thermostat's own weekly program), `manual` (hold `temperature`) |
| supported_features | 401 = TARGET_TEMPERATURE + PRESET_MODE + TURN_ON + TURN_OFF |
| target range in HA | min 5.0 °C, **max 300.0 °C**, step 0.5 |
| readable | `current_temperature`, plus `binary_sensor.floor_heating_valve(_2)` (relay open/closed — the true "is it heating right now" signal, a=0 **u=6/3**) |
| extra Tuya-native switches in HA | `switch.floor_heating_child_lock(_2)`, `switch.floor_heating_frost_protection(_2)` (both entity_category=config, so hidden from the default dashboard) |

**The 300 °C ceiling is real in the vendor spec, not an HA bug.** Tuya declares `temp_set: min 50, max 3000, scale 1` → HA renders 5.0…300.0 °C faithfully. The device's own sane bound is a *separate* datapoint: **`upper_temp` = 500 → 50.0 °C** and **`lower_temp` = 50 → 5.0 °C**, both live-read from the cloud. A new UI should clamp its slider to `lower_temp`…`upper_temp`, not to `max_temp`.

**Cloud datapoints HA does NOT surface at all** (verified live via `/v1.0/devices/{id}/specifications` + `/status`):

| DP | type | range | live value | meaning |
|---|---|---|---|---|
| `upper_temp` | Integer W/R | 50–3000 ÷10 | **500 → 50.0 °C** | user-settable max target — the real ceiling |
| `lower_temp` | Integer W/R | 50–3000 ÷10 | **50 → 5.0 °C** | user-settable min target |
| `work_days` | Enum W/R | `5_2` / `6_1` / `7` | **`5_2`** | weekly-program shape (5+2 / 6+1 / 7-day) driving `preset auto` |
| `temp_unit_convert` | Enum W/R | `c` / `f` | `c` | display unit |
| `fault` | Bitmap R | e1 / e2 / e3 | `0` | sensor/relay fault flags — **no fault entity exists in HA** |

> Opportunity: `preset auto` is opaque today because the weekly schedule (`work_days` + the thermostat's internal program) is invisible. Showing `valve_state` + `work_days` + `upper/lower_temp` would make the auto/manual choice legible for the first time.

### 3.2 Sockets / metered loads (Tuya plugs)

| load | switch entity | energy sensor | a/u | live W available? |
|---|---|---|---|---|
| Бойлер (water-heater ТЭН) | `switch.smart_plug_2_socket_1` | `sensor.boiler_total_energy` (12.874 kWh) | a=45/u=18 | **yes, disabled** |
| Полотенцесушитель (towel warmer) | `switch.kalarifer_socket_1` | `sensor.terarium_total_energy` (0 kWh) | a=30/u=6 | **yes, disabled** |
| Аквариум свет | `switch.akvarium_svet_socket_1` | `sensor.akvarium_svet_total_energy` (0.323 kWh) | a=20/u=7 | **yes, disabled** |
| Черепаха / рециркуляция ГВС | `switch.retserkuliatsiia_goriachai_vody_socket_1` | `sensor.cherepakha_total_energy` (0.008 kWh) | a=20/u=8 | **yes, disabled** |
| Гидрофор (well pump) | `switch.zigbee_plug_2_socket_1` | `sensor.zigbee_plug_2_total_energy` (329.04 kWh) | a=16/u=8 | **yes, disabled** |
| Подсветка кровати | `switch.zigbee_plug_socket_1` | `sensor.zigbee_plug_total_energy` (0.0 kWh) | a=2/u=1 | **yes, disabled** |

**Every one of these six plugs reports `cur_power` (W), `cur_current` (mA) and `cur_voltage` (V) to the Tuya cloud, and HA has already created the matching entities — but all 18 are `disabled_by: integration`.** `sensor.smart_plug_2_power`, `sensor.kalarifer_power`, `sensor.akvarium_svet_power`, `sensor.retserkuliatsiia_goriachai_vody_power`, `sensor.zigbee_plug_power`, `sensor.zigbee_plug_2_power` (+ `_current`, `_voltage`). Enabling them costs one registry toggle each and no restart of anything physical. Today the UI can only show cumulative kWh; with these it could show **live wattage per load and a real "what is drawing power right now" view**.

Other unexposed plug datapoints: `countdown_1` (0–86400 s auto-off timer, W/R), `relay_status` (power-on behaviour), `cycle_time` / `random_time` / `switch_inching` (device-side schedules), `overcharge_switch`, `fault` bitmap (`ov_cr`/`ov_vol`/`ov_pwr`/`ls_vol` — over-current / over-voltage / over-power / low-voltage).

> Opportunity: `countdown_1` is a **device-side** timer that keeps running even if HA is down. "Towel warmer on for 45 min" is a one-call feature the current UIs do not have.

### 3.3 Lighting

Lighting is split across **three overlapping control paths for the same physical circuits**, which is the single
biggest source of confusion in this house.

**Path A — Tuya native entities (the real, reliable ones).** 7 dimmable channels + 6 relay channels:

| entity | room / load | capability | a/u |
|---|---|---|---|
| `light.svet_pervyi_etazh_1_light` | Кухня: остров | on/off + **brightness** | a=10 u=7 |
| `light.svet_pervyi_etazh_1_light_2` | Кухня: стол | on/off + **brightness** | a=5 u=4 |
| `light.prikhozhaia_i_fanar_light` | Прихожая | on/off + **brightness** | a=8 u=6 |
| `light.prikhozhaia_i_fanar_light_2` | Фонарь у входа | on/off + **brightness** | a=4 u=3 |
| `light.veranda_light` | Веранда | on/off + **brightness** | a=4 u=4 |
| `light.vtoroi_etazh_light` | Коридор 2 эт | on/off + **brightness** | a=4 u=3 |
| `light.dream_color_rgb` | Подсветка бани (Tuya) | on/off + **hs colour** + `white` mode | a=11 u=5 |
| `light.dream_color_rgb_2` | same lamp via SmartThings | on/off + **hs colour** | a=3 u=2 |
| `switch.svet_tv_zona_switch_1` / `_2` | «Звездная стена ТВ» / «LED квадрат зона 1» | on/off only | a=7 u=5 / a=7 u=4 |
| `switch.kukhnia_poloski_switch_1` / `_2` | «LED лента лестница» / «LED лента кухня» | on/off only | a=7 u=3 each |
| `switch.gostinnaia_zanaveska_zona_switch_1` / `_2` | «Подсветка занавески» / «LED квадрат зона 2» | on/off only | a=5 u=1 / a=5 **u=0** |
| `switch.smart_switch_2ch_switch_1` / `_2` | «Гирлянда» / «Прожектор» | on/off only | a=9 u=3 each |
| `switch.220v_wifi_smart_dry_contact_switch_switch_1..4` | 4-канальный сухой контакт | on/off ×4 | **a=0 u=0 — purpose unknown; channel 4 is currently `on`** |

> **The canonical human names for all of these already exist in one place**: the Telegram-AI automation
> (`automation.telegram_ai_upravlenie_domom_gemini`, `automations.yaml` ≈ line 828) carries a complete
> `target → entity_id → friendly` map for 23 controllable targets — `boiler`, `kalarifer`, `aquarium`, `turtle`,
> `island`, `table`, `second_floor`, `veranda`, `hall1`, `hall2`, `rgb_bath`, `led_stairs`, `led_kitchen`,
> `curtain_lights`, `living_square1/2`, `tv_wall`, `garland`, `floodlight`, `water_valve`, `all_sockets_on/off`,
> `home`. It also carries an `ai_denied` safety list (`switch.voda_kran_switch_1`, `siren.*`, `script.*`,
> `scene.turn_on/off_all_sockets`). **This is the closest thing the house has to a canonical device catalogue and
> the new UI should be built from it** rather than from the HA area registry (§2).

**Every dimmable channel supports `brightness` (`supported_color_modes: ['brightness']`), and the Tuya cloud also
exposes `brightness_min_N` / `brightness_max_N` (currently 200…1000, i.e. the dimmers are calibrated to a 20 % floor)
and a per-channel `countdown_N` auto-off timer.** The existing UIs treat all of these as plain on/off toggles.
`light.dream_color_rgb` additionally has cloud `work_mode: white | colour | scene | music` and `music_data` —
i.e. a music-reactive mode — of which HA exposes only `hs`/`white`.

**Path B — SmartThings mirrors of the same devices.** `switch.svet_tv_zona`, `switch.kukhnia_poloski`,
`switch.gostinnaia_zanaveska_zona`, `switch.veranda`, `switch.vtoroi_etazh`, `switch.prikhozhaia_i_fanar`,
`switch.svet_pervyi_etazh_1_ostrov_i_stol`, `switch.gerlianda_i_prozhektor`, `switch.4kh_konalnyi_kontroler`,
`switch.akvarium_svet`, `switch.boiler`, `switch.cherepakha`, `switch.terarium`, `switch.perekryt_vodu`,
`light.dream_color_rgb_2`, `switch.outlet1{,_2,_3,_4}`, `switch.outlet39{,_2}`, `switch.outlet51{,_2}`.
These are the **same physical relays reached through a second cloud**. Confusingly, the automations and UI use a
mix of both paths for the same device (e.g. `switch.akvarium_svet` a=20 *and* `switch.akvarium_svet_socket_1` a=20).
They are, however, a genuine **redundant control path** when the Tuya cloud throws `sign invalid` — worth keeping,
but the new UI must pick one canonical entity per load and treat the other as fallback, not as a separate device.

**Path C — 22 Tuya "Scene" pseudo-devices**, each surfaced *twice*: as `switch.vkliuchit_svet_*` /
`switch.vykliuchit_svet_*` (SmartThings, model `Scene`) **and** as `scene.vkliuchit_svet_*` (tuya platform).
Their `on`/`off` state is meaningless — several read `on` while the light they name is off. 15 of the `switch.*`
copies are referenced exactly once each (in one automation); **all 20 `scene.*` copies have zero references**.

### 3.4 EV charger (Tuya, proto 3.5 → cloud-only)

| | |
|---|---|
| HA control | `switch.ev_charger_switch` (on/off only) |
| HA observe | `sensor.ev_charger_status` (a=40 u=19), `sensor.ev_charger_energy` (kWh total, a=19 u=9) + json attrs `status`, `mode`, `switch`, `session_kwh`, `src`, `stale_age` |
| polling | `command_line` → `python3 /config/ev_query.py`, 300 s, 290 s result cache, up to 24 h stale-serving with an explicit `src`/`stale_age` label |

**Cloud exposes a whole charging-mode dimension HA never surfaces:**
`work_mode` is **writable** with `charge_now | charge_pct | charge_energy | charge_schedule`.
Today the only lever is the on/off switch plus a HA-side scheduler (`ev_best2h.py`) that toggles it. The charger can
natively be told "charge to N %", "charge N kWh", or "run this schedule" — that would move the smart-charging logic
into the device, surviving HA downtime.

`work_state` has **8** values in the cloud spec — `charger_free`, `charger_insert`, `charger_free_fault`,
`charger_wait`, `charger_charging`, `charger_pause`, `charger_end`, `charger_fault`. The project's documented list has
only 6: **`charger_free_fault` and `charger_wait` are unhandled**, and `charger_fault` is documented as `cloud_error`
(which is actually `ev_query.py`'s own failure sentinel, not a device state). A new UI must not conflate
"the charger reports a fault" with "we could not reach Tuya".
`charge_energy_once` (kWh this session, ÷100) is read and passed through as `session_kwh`.

### 3.5 Water, leak protection and security

| capability | entity | notes |
|---|---|---|
| Main water valve | `switch.voda_kran_switch_1` (Tuya) / `switch.perekryt_vodu` (SmartThings mirror) | on = open. Cloud also has `countdown_1` (0–43200 s) — a device-side auto-reopen/close timer, unused |
| Well pump (гидрофор) | `switch.zigbee_plug_2_socket_1` | metered; cut during a leak |
| Siren | `siren.alarm`, `supported_features: 3` = TURN_ON + TURN_OFF only | duration and volume are **separate** entities: `number.alarm_time` (1–380 s, currently **1 s**) and `select.alarm_volume` (`low/middle/high/mute`, currently `high`) — both a=0 u=0, i.e. no UI ever set them. A 1-second siren is very likely not what the owner wants |
| Second siren (undiscovered) | Tuya `Matter Wired Gateway` | cloud DPs `alarm_active` (String, W), `master_state` (`normal`/`alarm`, W), `switch_alarm_sound` (Boolean, W). **HA exposes only `binary_sensor.matter_wired_gateway_problem`** — the alarm/siren function of this gateway is invisible to HA |
| Leak truth | `sensor.leak_protection_status` (a=10 u=11) — single source of truth (`ok`/…); `sensor.tuya_leak_cloud` (a=13 u=0), independent 30 s cloud cross-check | plus 4 `binary_sensor.*_moisture` (Ванная / Гараж / Кухня / Душевая 1эт) |
| Extra leak sensors nobody uses | Xiaomi `event.lumi_..._aq1_submersion_detected_e_2_1` ×2 (Aqara水浸传感器 + Датчик утечек воды) | **two additional water sensors exist on the Xiaomi cloud and are wired into nothing** |
| Door | `binary_sensor.door_sensor_door` (a=7 u=18) | + `binary_sensor.signalizatsiia_dvernogo_datchika_door(_2)` — both `unavailable`, duplicated |
| Smoke | `binary_sensor.wifi_th_smoke_sensor_smoke` (a=12 u=19), `switch.wifi_th_smoke_sensor_mute` | + Xiaomi 烟雾报警器 smoke alarm (`event.lumi_...high_concentration_of_smoke_detected`) — **unavailable and unused** |
| Motion / occupancy | `binary_sensor.motion_sensor_motion` (a=1), `binary_sensor.pir_motion_sensor_motion` (a=0 u=0), `binary_sensor.occupancysensor_zaniatost` (unavailable), `binary_sensor.lumi_..._motion_state` (unavailable) | 4 motion sources, **essentially none drives anything** |
| Arming | `input_boolean.security_armed` — a=5 **u=32**, the most-referenced helper in the UI | |
| Gateway alarm | `switch.lumi_cn_gateway_v3_alarm_p_3_1`, `switch.lumi_cn_gateway_v3_guard_mode_p_2_1`, `number.lumi_..._volume_p_3_2` (0–100 %) | Xiaomi gateway has its own armed-mode + siren + volume. a=0 u=0 |

### 3.6 Boiler (ecoNET300, REST — not a HA integration)

Read via a `rest:` block (13 numeric sensors + 7 binary), written via 7 `rest_command`s.

**Control surface (all of it):** `boiler_turn_on` / `boiler_turn_off` (param 75), `set_boiler_cwu_temp{temp}` and
`set_boiler_co_temp{temp}` (params 1281 / 1280), plus three fixed-value shortcuts `disable_boiler_cwu` (ГВС 40 °C),
`enable_boiler_cwu` (55 °C), `turbo_boiler_cwu` (65 °C). So **ГВС and CO setpoints are freely settable** —
the UIs only ever use the three canned values.

**Observe:** `sensor.boiler_mode` (a=12 **u=23** — the most-shown boiler value), `boiler_co_temperature` /
`_setpoint`, `boiler_cwu_temperature` / `_setpoint`, `boiler_outside_temperature`, `boiler_return_temperature`,
`boiler_flue_gas_temperature`, `boiler_feeder_temperature` (a=0 u=0), `boiler_mixer_temperature` / `_setpoint`,
`boiler_power` %, `boiler_fan_power` %, `boiler_fuel_level` (**always 0 — sensor physically disconnected, do not
display**), `binary_sensor.boiler_alarm` (currently **`on`**), `_circulation_pump`, `_co_pump`, `_cwu_pump`, `_fan`,
`_feeder`, `_thermostat`.

Note the address is hard-coded as `http://ecoNET300.local/` in `rest_command` while the `rest:` sensors and the
project notes track a drifting IP (.10 → .11 → .12). Mixed addressing is a live fragility, not a capability.

### 3.7 Everything else that can be controlled

| device | entity | what HA can actually do | used? |
|---|---|---|---|
| Robot vacuum (Roborock "Киборг") | `vacuum.kiborg` | start/pause/stop/return/locate/clean-spot/send_command, `fan_speed` ∈ `quiet, balanced, turbo, max, gentle`; `select.kiborg_selected_map` (multi-floor maps, currently "2 этаж"), `select.kiborg_mop_mode`, `select.kiborg_mop_intensity`, `number.kiborg_volume`, `time.kiborg_do_not_disturb_begin/_end`, `switch.kiborg_do_not_disturb` | partly: the tablet has a vacuum tile (`vacuumSvc()`, u=3) exposing start/stop/return + battery + fan_speed **readout**. Nothing uses the maps, mop modes, DND window, volume, or `sensor.kiborg_current_room` ("Детская Миша") — room-targeted cleaning is possible and unbuilt |
| Air purifier (Mijia 3) | `fan.zhimi_..._air_purifier` | on/off, `percentage` (3 steps), `preset_mode` ∈ `Авто, Ночной, Ручной, режима`; `switch.*_alarm`, `light.*_indicator_light` (3 effects), `switch.*_physical_controls_locked`, `number.*_favorite_fan_level` (0–14) | **fan entity a=0 u=0** — only its PM2.5/temp/humidity readings are shown |
| Humidifier (Tesla Pro4) | `humidifier.pro4_humidifier` + `light.pro4_humidifier` | on/off (no target-humidity support: `supported_features: 0`, min 0 / max 100 are nominal) | a=0 u=0 |
| Apple TV (Главная спальня) | `media_player.glavnaia_spalnia` (`supported_features: 450487`), `remote.glavnaia_spalnia` | full transport, volume, source, browse/play media, turn on/off, remote key sending | a=0 u=0 |
| Samsung 75" QLED | `media_player.75_qled` (SmartThings, sf 23997) **and** `media_player.75_qled_qe75q8faauxxh` (samsungtv, sf 24509) + `remote.75_qled_qe75q8faauxxh` | duplicate control paths for one TV; volume/source/power/remote | a=0 u=0 |
| TTS | `tts.google_ai_tts`, `tts.google_translate_en_com`, `tts.home_assistant_cloud` | spoken announcements through any media_player | a=0 u=0 — three TTS engines exist and are wired to nothing; the only reachable speaker today is the Apple TV (`idle`), the Samsung TV is `off` |
| Calendars | `calendar.semia`, `calendar.birthdays`, `calendar.prazdniki_latvii`, `calendar.owner_mail`, `calendar.holidays` | read + `calendar.create_event` | the UIs read them through the generic `GET /api/calendars` endpoint, not by entity_id, so the per-entity counts read 0. **Write access (`calendar.create_event`) is unused** |
| Shopping list | `todo.shopping_list` | add/complete items | a=0 u=0 |
| Wireless scene remotes | `event.stsenarnyi_pult_button_1..4`, `event.ostrov_vykliuchatel_button_1..4`, `event.perenosnoi_pult_button_1..4`, `event.vykuliuchatel_2_etazh_button_1`, `event.4_scene_switch_knopka_1..4`, `event.lumi_..._click/double_click/long_press` | each button fires `click` / `double_click` / `press` (Tuya) or click/double/long (Xiaomi) | **all a=0 u=0 — ~30 physical buttons bound to nothing on the HA side** (they may be bound cloud-side in the Tuya app; that could not be verified read-only) |
| Proxmox (12 devices, 195 entities) | `button.<vm>_start/_stop/_restart/_shut_down/_reset/_suspend/_create_snapshot` for 8 VMs + `button.mylab_start_all/_stop_all/_suspend_all` | full VM lifecycle control from HA | **every one of these buttons is a=0 u=0**; only the `binary_sensor.*_status` values feed the alert automations |

> **Caveat on the `a=`/`u=` counts.** They are literal substring matches. Several helpers are addressed by *computed*
> entity_id in Jinja (`'input_datetime.tuya_selfheal_r' ~ i`, `'input_boolean.moisture_bypass_' ~ sensor`), and the
> calendars are read through `GET /api/calendars`. Those therefore show 0 while being very much alive. Every "unused"
> claim below was re-checked against that pattern.

---

## 4. Sensors worth showing

### 4.1 Climate per room

| room | temperature | humidity | notes |
|---|---|---|---|
| Кухня | `sensor.kukhnia_temperature` (24.4) | `sensor.kukhnia_humidity` (54) | Tuya. A **second, duplicate** Tuya→SmartThings pair exists: `..._temperature_2` / `..._humidity_2` / `..._battery_2` — same physical sensor, a=0 u=0 |
| Гостиная | `sensor.miaomiaoc_cn_blt_3_living_t1_temperature_p_2_1` (22.2) | `..._relative_humidity_p_2_2` (56) | Mijia Pro. Battery **23 %** |
| Спальня | `sensor.lumi_cn_lumi_bedroom_th_v1_temperature_p_2_1` | `..._relative_humidity_p_2_2` | **currently `unavailable`** |
| Спальня доп. | `sensor.miaomiaoc_cn_blt_3_bedroom2_t1_temperature_p_2_1` (23.0) | `..._relative_humidity_p_2_2` (53) | deliberately hidden from the UIs; still reports, battery 38 % |
| Улица | `sensor.smart_weather_station_temperature` (25.2) | `sensor.smart_weather_station_humidity` (48) | + `sensor.boiler_outside_temperature` (23.9) as a second outdoor reading |
| Воздух (гостиная) | `sensor.zhimi_..._temperature_p_3_8` (25.7) | `sensor.zhimi_..._relative_humidity_p_3_7` (52) | air purifier's own sensors, currently unused |

Air quality: `sensor.zhimi_..._pm2_5_density_p_3_6` (**1 μg/m³**, a=1 u=4).
Illuminance: `sensor.lumi_cn_gateway_v3_illumination_p_5_1` (1293 lx, gateway/гостиная, a=0 u=2) and
`sensor.light_sensor_75_qled_illuminance` (4 lx, a=0 u=0).
`sensor.pressure` (barometric, from the iPhone) is `unavailable`.

**Rooms with no climate sensor at all:** Ванная, Душевая 1эт (only the floor thermostats' `current_temperature`
— 26.8 °C / 27.0 °C — which is a *floor* temperature, not air), Коридор, Гараж, Веранда, Прихожая, Детская.

### 4.2 Energy — what is and is not metered

**Metered (7 loads + TV):** boiler ТЭН, towel warmer, aquarium, recirculation pump, hydrophore, bed light,
EV charger, Samsung TV. Each has a `*_total_energy` (cumulative kWh) plus a `input_number.midnight_*_energy`
snapshot for the daily delta, and a `input_number.cost_month_*` € accumulator (7 of them + `cost_month_total`).

**NOT metered — and this is the important half:**
- **Both electric floor-heating zones.** They are Nord-Pool-switched electric loads with *no* energy sensor at all,
  so they never appear in the daily kWh report or the monthly € total. There is no `cost_month_*` for them.
- **Every lighting circuit** — 7 dimmer channels + 6 relay channels, all unmetered.
- The 4-channel dry-contact controller, the water valve, the vacuum, air purifier, humidifier.
- **There is no whole-house / main-meter reading anywhere.** Every "consumption" figure in the house is the sum of
  8 individually-metered plugs. Whatever else the house draws (heating, lighting, kitchen, everything on
  unmetered circuits) is invisible. Any new "energy" screen must say so, or it will overstate accuracy.

**Available but disabled:** live W / A / V for all six metered plugs (18 entities, §3.2).

### 4.3 Prices

`sensor.nord_pool_lv_current_price` (a=48 u=23 — the single most-referenced entity in the house), `_next_price`,
`_previous_price`, `_lowest_price`, `_highest_price` (both carry a `start` attribute), `_currency`, `_last_updated`,
`binary_sensor.nord_pool_lv_tomorrow_price_available`. Tomorrow's curve lives in
`state_attr('sensor.nord_pool_lv_current_price','tomorrow')`, plus a file-based day curve at
`/local/today_prices.json` written by `shell_command.update_today_prices`, and `price_forecast.py`.

**17 Nord Pool entities are disabled by the integration** and would be free wins for a price UI:
`_daily_average`, `_peak_average` / `_peak_lowest_price` / `_peak_highest_price` / `_peak_time_from` / `_peak_time_until`,
and the same six for `off_peak_1` and `off_peak_2`, plus `_exchange_rate`.
Also live: `sensor.electricity_maps_co2_intensity` (48 gCO2eq/kWh) and
`sensor.electricity_maps_grid_fossil_fuel_percentage` (2.85 %) — **both a=0 u=0**, a ready-made "how clean is the
grid right now" tile.

### 4.4 Proxmox (192.168.1.8)

12 devices / 195 entities: 9 guests (`homeassistant`, `mylab`, `jarvis`, `ssh-tool`, `atlas-dev`, `homelab-dev`,
`homelab-staging`, `homelab-ci-runner`, `homelab-clean-ubuntu-2404`) × ~20 entities each, plus 3 storages
(`local`, `local-btrfs`, `nas`). **66 of them are unavailable/unknown right now.** Per guest: status
binary_sensor, uptime, CPU/memory/disk (several disabled), and the 7-button lifecycle set. Six alert automations
consume the status/backup/storage signals; the buttons are untouched.

### 4.5 Presence

`binary_sensor.prisutstvie_owner` (device_class presence, `on`, a=4 **u=0** — the UIs do not show it) =
`person.owner home OR device_tracker.myiphone home OR sensor.ssid == 'HOME_WIFI'`, delay_on 10 s / delay_off 10 min.
Raw inputs: `person.owner` (home), `device_tracker.myiphone` (home), `sensor.ssid` (`HOME_WIFI`), `sensor.bssid`,
`sensor.connection_type`, `sensor.distance` (1516 m), `sensor.geocoded_location` (Unknown).
`device_tracker.sm_t595_2` still reports `home` and `device_tracker.unknown` is a leftover.
Only **one person** is tracked — there is no second household member in the registry.

### 4.6 Batteries

25 battery sensors. Low right now: **`sensor.perenosnoi_pult_battery` 20 %**,
**`sensor.miaomiaoc_..._living_battery_level` 23 % (Гостиная Mijia Pro)**,
`sensor.kukhnia_battery` 43 %, `sensor.miaomiaoc_..._bedroom2_battery_level` 38 %, `sensor.garazh_battery` 55 %.
Dead/unavailable: `sensor.signalizatsiia_dvernogo_datchika_battery` and `_battery_2`,
`sensor.occupancysensor_batareia`, `sensor.lumi_cn_lumi_zigbee_ieee_v1_battery_level` (Xiaomi smoke alarm).
The documented "Сигн.1 / Сигн.2 at 0 %" devices now read `unavailable`, not 0 — they appear to be fully offline.

---

## 5. Scripts, scenes, helpers

### 5.1 Scripts (17, all in `scripts.yaml`)

| script | purpose | referenced by | ever run? |
|---|---|---|---|
| `scene_away` / `scene_cinema` / `scene_guests` | 🚪 Ушёл / 🎬 Кино / 🎉 Гости | a=1 u=1 each | **never triggered** |
| `rezhim_zhara_on` / `_off` | summer mode: kill all heating except ГВС | a=1 u=2 each | yes (16 Aug / 14 Aug) |
| `alarm_smoke_siren` / `_off` / `alarm_security_siren` | fire-and-forget siren drivers | a=2/1/1 | **never triggered** |
| `leak_shutoff_and_siren` | hydrophore off + valve off + siren | a=2 | **never triggered** |
| `leak_valve_verify` | confirm the valve actually closed | a=1 | never |
| `ev_verify_start` / `ev_verify_stop` | confirm the EV command landed | a=3 each | `_stop` ran today |
| `turbo_hot_water_start` / `_restore` | ГВС 65 °C then back | a=2 each | never |
| `night_saver_restore_snapshot` | restore devices after night saving | a=1 | never |
| `tuya_grace_release` | drop the Tuya grace flag after 5 min | a=3 | never |
| `house_change_digest` | coalescing window for "изменения в доме" | a=2 | yes, today |

None are dead code — all are referenced. Several have never fired because they are alarm paths.

### 5.2 Scenes (22)

All 22 `scene.*` entities come from the **tuya** platform: they are the Tuya app's cloud scenes, mirrored into HA.
`scenes.yaml` is included by `configuration.yaml` but does not exist on disk (no local scenes).
**20 of the 22 are referenced nowhere at all** — including every light scene and `scene.otkrylas_dver`
("Открылась дверь"). The only two in use are `scene.turn_on_all_sockets` / `scene.turn_off_all_sockets`, reachable
solely through the Telegram-AI target map (and blocked there by its `ai_denied` list).
Where an automation does need a light scene, it calls the SmartThings `switch.vkliuchit_svet_*` copy instead.
The house's actual "scenes" are the three `script.scene_*` above.

### 5.3 Helpers

- **14 `input_boolean`.** Live and central: `security_armed` (u=32), `night_saver` (a=16 u=14),
  `ev_manual_mode` (a=14 u=11), `ha_startup_grace` (a=19), `tuya_reconnect_grace` (a=15), `turbo_hot_water` (a=13),
  `rezhim_zhara` (a=9 u=9), `boiler_manual_mode` (a=8), `tuya_stale_alert` (a=5).
  The four `moisture_bypass_*` look dead by grep but are addressed dynamically by the leak automations — **keep**.
  **`input_boolean.input_boolean_boiler_price_active` is genuinely dead** — the name is doubled
  (`input_boolean.input_boolean_…`), its friendly_name is literally `input_boolean.boiler_price_active`, and the
  string `boiler_price_active` appears nowhere in any config. A creation bug, never referenced.
- **14 `input_number`.** 7 `midnight_*_energy` snapshots + 7 `cost_month_*` (+ `cost_month_total`). All referenced.
  Note `cost_month_kalarifer` and `cost_month_ev` are 0.00 and `midnight_*` for boiler/akv/chep/kalarifer/tv are 0.0 —
  consistent with a recent counter reset, guarded by the "Гард сброса счётчика энергии" automation.
- **16 `input_datetime`.** `ev_charge_start` is the only user-facing one; the other 15 are
  notification-debounce timestamps (`tuya_cmd_fail_*`, `gvs_last_notify_*`, `proxmox_metric_last_alert`,
  `tuya_selfheal_msg`/`_giveup_msg`, `ev_overrun_notify`) and the six `tuya_selfheal_r1..r6` rotation marks
  (dynamically referenced — alive). **A new UI should show `ev_charge_start` and hide the rest.**

---

## 6. Unused capability — the design opportunities

Ranked by how much a new UI would gain:

1. **Live wattage per load.** 18 already-created Tuya `power`/`current`/`voltage` sensors sit `disabled_by:
   integration`. Enabling six of them turns the energy screen from "kWh since some reset" into a live
   "what is drawing power right now" view. Zero new code, zero device risk.
2. **Dimming.** 7 light channels support `brightness` and are driven as on/off toggles everywhere. The dimmers even
   report their calibrated floor/ceiling (`brightness_min/max` = 200/1000).
3. **Device-side countdown timers.** Every Tuya plug/relay/dimmer channel and the water valve expose a writable
   `countdown_N` (0–86400 s; valve 0–43200 s). "Towel warmer for 45 min", "veranda light off in 10 min",
   "valve closed for 2 h" — all survive an HA restart because the timer lives in the device.
4. **The real floor-heating limits.** `upper_temp` (50 °C) / `lower_temp` (5 °C) / `work_days` / `fault` are live on
   the cloud and absent from HA. Clamping the target slider to these is both a UX and a safety fix versus the
   nonsense 300 °C ceiling.
5. **EV `work_mode`.** `charge_pct` / `charge_energy` / `charge_schedule` are writable on the charger and unused.
6. **The siren is configured to sound for 1 second.** `number.alarm_time` = 1 (range 1–380 s) and
   `select.alarm_volume` = high, neither ever set by any UI. Worth surfacing prominently.
7. **A second alarm device nobody knows about:** the Tuya `Matter Wired Gateway` has writable
   `master_state: normal|alarm`, `alarm_active`, `switch_alarm_sound` — HA shows only a `problem` binary_sensor.
   The Xiaomi gateway likewise has `switch.lumi_..._alarm`, `switch.lumi_..._guard_mode` and a volume `number`.
8. **~30 physical buttons doing nothing in HA.** Four 4-button Tuya remotes + a Xiaomi wireless switch, each
   emitting `click` / `double_click` / `press` events, referenced by no automation.
9. **Vacuum beyond start/stop.** Multi-floor maps (`select.kiborg_selected_map`), mop mode/intensity, DND window,
   `sensor.kiborg_current_room` — room-level cleaning is available.
10. **Media + TTS.** Apple TV (`supported_features: 450487`) and the Samsung TV are fully controllable and used by
    nothing; three TTS engines are installed and the house has never spoken a word. Announce-on-leak is one call away.
11. **Grid carbon intensity** (`electricity_maps_*`) and the **17 disabled Nord Pool peak/off-peak/daily-average
    sensors** — a proper price screen for free.
12. **Proxmox VM lifecycle buttons** (63 of them) — currently observe-only.
13. **Air purifier `fan` entity** — preset modes Авто/Ночной/Ручной, 3 speed steps, unused; only its sensors are shown.
14. **Unbound extra safety sensors:** two Xiaomi water sensors, a Xiaomi smoke alarm, and four motion/occupancy
    sensors, none of which drive anything (several are `unavailable` and need attention first).

---

## 7. Duplicates and ghosts

### 7.1 Slugs that no longer match their names

| entity_id | actual alias | note |
|---|---|---|
| `automation.ha_startup_grace_period` | **🚨 Утечка воды - аварийное отключение v4** | the leak-shutoff automation is named after the grace-period one. The *real* grace automation is `automation.ha_startup_grace_restored`. Anyone reading logs or the entity list will mis-identify the most safety-critical automation in the house |
| `automation.boiler_kalorifer_po_tsene_porog_0_04` | 🔥 Бойлер по Nord Pool (**<=0.10** ON) | slug says 0.04 and "kalorifer"; it is the boiler at 0.10 |
| `automation.teplyi_pol_po_nord_pool_0_04_heat_30c_0_04_auto` and `..._dushevaia_...` | floor heating | slugs encode a threshold that may drift |
| `sensor.terarium_total_energy` | **Полотенцесушитель энергия** | energy meter of the towel warmer, named after a terrarium |
| `switch.kalarifer_socket_1` (device "Коларифер") | **Полотенцесушитель** | ditto — device name, child-lock and `select.kalarifer_power_on_behavior` all still say калорифер |
| `switch.retserkuliatsiia_goriachai_vody_*` (device "Черепаха") | recirculation pump / "turtle" | two different metaphors for one plug; `sensor.cherepakha_total_energy` vs `switch.retserkuliatsiia_...` |
| `input_boolean.input_boolean_boiler_price_active` | `input_boolean.boiler_price_active` | doubled domain in the object_id |
| `switch.zigbee_plug_2_socket_1` | **Гидрофор** | generic slug for a load-bearing device |

### 7.2 Duplicated devices (same hardware, two integrations)

Sixteen physical Tuya devices appear **twice**, once through the Tuya cloud entry and once through SmartThings:
`Бойлер`, `Черепаха`, `Аквариум свет`, `Терариум/Коларифер`, `Веранда`, `Второй этаж`, `Прихожая и фанарь`,
`Свет первый этаж 1`, `Свет тв зона`, `Гостинная занавеска зона`, `Кухня полоски`, `Герлянда и прожектор`,
`4х кональный контролер`, `Перекрыть воду` (= `Вода кран`), `Dream Color RGB`, `Кухня T&H sensor`.
The automations and the current UIs use **both copies inconsistently** for the same load.
Also duplicated: the Samsung TV (`media_player.75_qled` via SmartThings + `media_player.75_qled_qe75q8faauxxh`
via samsungtv), and the door alarm (`binary_sensor.signalizatsiia_dvernogo_datchika_door` and `_door_2`).

### 7.3 Duplicated scene surface

22 Tuya cloud scenes are each exposed twice — as `switch.*` (SmartThings, model `Scene`) **and** as `scene.*` (tuya).
44 entities for 22 scenes. The `switch.*` copies have a meaningless on/off state (`switch.vykliuchit_svet_stena`
reads `on` while the wall light is off). The `scene.*` copies are entirely unreferenced.

### 7.4 Anonymous / orphaned entities

- `switch.outlet1`, `switch.outlet1_2`, `switch.outlet1_3`, `switch.outlet1_4`, `switch.outlet39`,
  `switch.outlet39_2`, `switch.outlet51`, `switch.outlet51_2` — eight switches named after nothing, from two
  different SmartThings models (`smartplug` and a metering one). Two of them are **on right now** and nobody knows
  what they power. a=0 u=0.
- `light.1_dimmer_switch`, `light.2dimmerswitch`, `light.2dimmerswitch_2`, `number.*_na_urovne` ×3,
  `number.occupancysensor_hold_time`, `binary_sensor.occupancysensor_zaniatost` — all `restored: True`, i.e.
  the integration that created them is gone. Pure registry ghosts.
- `light.lg_tv` (Magic Home via SmartThings) — `unavailable`.
- `media_player.solas_tv`, `media_player.xbox` (two dead `dlna_dmr` entries), `media_player.mitv_mssp2` +
  `remote.mitv_mssp2` (androidtv_remote in `setup_retry`, can't reach 192.168.1.63:6466),
  `sensor.hp_laserjet_*` ×5 (ipp in `setup_retry`).
- `notify.unknown`, `notify.unknown_2`, `device_tracker.unknown`, `sensor.*_2` mobile_app twins — leftovers of the
  deleted SM-T595 companion entries; `device_tracker.sm_t595_2` still reports `home` and could skew presence if
  anyone wires it up.
- `binary_sensor.remote_ui` + 2 more `cloud` entities — HA Cloud is configured but all its entities are unavailable.
- `switch.turn_on_all_sockets` / `switch.turn_off_all_sockets` (SmartThings copies) — a=0 u=0. The **`scene.*`
  copies** of the same two Tuya scenes *are* referenced (a=2 each): they are the only two `scene.*` entities in use,
  reachable through the Telegram-AI targets `all_sockets_on` / `all_sockets_off` — and both are on that automation's
  `ai_denied` list, so the AI may name them but not fire them. Worth confirming what "all sockets" actually
  switches before any new UI surfaces them.

---

## 8. What this audit could NOT determine

- **What the eight `outlet1/39/51` SmartThings switches actually power.** They have no name, no area, no
  references, and two are energised. Determining this needs a physical walk-through, not a query.
- **What the 4-channel dry-contact controller (`switch.220v_wifi_smart_dry_contact_switch_switch_1..4`) drives.**
  Channel 4 is `on`. No config or UI references it. Same problem.
- **Whether the ~30 wireless-remote buttons are bound to anything cloud-side.** The Tuya app can bind a button
  directly to a scene without HA ever seeing it. Read-only cloud APIs expose the button's DPs but not the
  automations the app has attached to them, so "unused" here means "unused *by HA*".
- **Whether the SmartThings mirrors still work as a fallback.** Verifying that would require actually sending a
  command, which this audit is forbidden to do.
- **Which of the two `dlna_dmr` entries (XBOX / SOLAS TV) is salvageable** — both are simply unavailable.
- **Real per-load consumption history.** The recorder DB was not queried (275 MB, and long-range statistics were
  out of scope). Only current states and the `input_number` accumulators were read.
- **`scenes.yaml` content** — it is `!include`d by `configuration.yaml` but does not exist on disk. HA tolerates
  this; it means there are zero locally-defined scenes, but it is worth confirming that is intentional.
- **The physical ceiling of the floor thermostats.** `upper_temp` = 50.0 °C is the device's *configured* maximum;
  the manufacturer's hard limit was not verified against a datasheet.

## 9. Method

Read-only throughout. HA REST `GET /api/states`, `/api/services`, `/api/config`, `/api/config/config_entries/entry`;
HA WebSocket `config/{entity,device,area,floor,label}_registry/list`, `config_entries/get`, `manifest/list`,
`entity/source`. Config text read with `sudo cat` over SSH (`automations.yaml`, `configuration.yaml`, `scripts.yaml`,
`www/*`). Tuya cloud read with `GET /v1.0/devices/{id}/specifications` and `/status` against
`https://apigw.tuyaeu.com` (HMAC-SHA256, sorted query params), executed **on the HA host** so the credentials never
left `/config/local_secrets.json`; 38 of 38 physical Tuya devices answered. No service was called, no entity was
commanded, no file on the HA host was modified, and nothing was restarted. Raw dumps live beside this file in
`01_capabilities.json`.
