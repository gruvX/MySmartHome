# Ghost / Unavailable Entity Audit — 2026-07-16

Read-only inventory of every entity currently in `unavailable`/`unknown` state, plus the
integration-disabled (no-state) registry entries. Data pulled live from HA REST `/api/states`
(589 states) and WS `config/entity_registry/list` (700 registry entries) on 2026-07-16.

Usage columns: **Auto** = grep of live `/config/automations.yaml` + `scripts.yaml` + `configuration.yaml`.
**UI** = grep of live `/config/www/*` dashboards (tablet-panel.js, smarthouse.html, livemap.html, boiler.html, graph.html, hapanel.html) + repo `tablet/`, `miniapp/`.

No registry entry was deleted. The only registry mutation performed this session is documented in the
**Action taken** section at the bottom (reversible disable of `switch.podsvetka_ostrov`).

## A. Live `unavailable` / `unknown` entities (129)

### xiaomi_home (55)

| entity_id | state | reason | went unavail./last change | Auto? | UI? | recommended action |
|---|---|---|---|---|---|---|
| `binary_sensor.lumi_cn_lumi_158d000431e0e2_v2_contact_state_p_2_1` | unavailable | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 15:11 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `button.zhimi_cn_purifier_mb3_reset_filter_life_a_4_1` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `button.zhimi_cn_purifier_mb3_toggle_a_8_1` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `button.zhimi_cn_purifier_mb3_toggle_mode_a_8_2` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `event.lumi_cn_lumi_zigbee_ieee_v1_high_concentration_of_smoke_detected_e_2_1` | unknown | by-design (event entity: unknown until fired) | 2026-07-15 17:13 | no | no | leave (by-design) |
| `event.lumi_cn_lumi_bedroom_th_v1_low_battery_e_3_1` | unknown | by-design (event entity: unknown until fired) | 2026-07-15 17:13 | no | no | leave (by-design) |
| `event.lumi_cn_lumi_158d0004216edb_aq1_low_battery_e_3_1` | unknown | by-design (event entity: unknown until fired) | 2026-07-15 17:13 | no | no | leave (by-design) |
| `event.lumi_cn_lumi_158d0004216edb_aq1_no_submersion_e_2_2` | unknown | by-design (event entity: unknown until fired) | 2026-07-15 17:13 | no | no | leave (by-design) |
| `event.lumi_cn_lumi_158d0004216edb_aq1_submersion_detected_e_2_1` | unknown | by-design (event entity: unknown until fired) | 2026-07-15 17:13 | no | no | leave (by-design) |
| `event.lumi_cn_lumi_158d00042d8e09_aq1_low_battery_e_3_1` | unknown | by-design (event entity: unknown until fired) | 2026-07-15 17:13 | no | no | leave (by-design) |
| `event.lumi_cn_lumi_158d00042d8e09_aq1_no_submersion_e_2_2` | unknown | by-design (event entity: unknown until fired) | 2026-07-15 17:13 | no | no | leave (by-design) |
| `event.lumi_cn_lumi_158d00042d8e09_aq1_submersion_detected_e_2_1` | unknown | by-design (event entity: unknown until fired) | 2026-07-15 17:13 | no | no | leave (by-design) |
| `event.lumi_cn_lumi_158d000431e0e2_v2_close_e_2_1` | unavailable | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 15:11 | no | no | leave (by-design) |
| `event.lumi_cn_lumi_158d000431e0e2_v2_door_not_closed_e_2_3` | unavailable | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 15:11 | no | no | leave (by-design) |
| `event.lumi_cn_lumi_158d000431e0e2_v2_low_battery_e_3_1` | unavailable | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 15:11 | no | no | leave (by-design) |
| `event.lumi_cn_lumi_158d000431e0e2_v2_open_e_2_2` | unavailable | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 15:11 | no | no | leave (by-design) |
| `event.zhimi_cn_purifier_mb3_cild_lock_trigger_e_8_1` | unknown | by-design (event entity: unknown until fired) | 2026-07-15 17:13 | no | no | leave (by-design) |
| `event.zhimi_cn_purifier_mb3_filter_door_opened_e_9_2` | unknown | by-design (event entity: unknown until fired) | 2026-07-15 17:13 | no | no | leave (by-design) |
| `light.zhimi_cn_purifier_mb3_s_6_indicator_light` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `number.zhimi_cn_purifier_mb3_app_extra_p_15_1` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `number.zhimi_cn_purifier_mb3_aqi_goodh_p_13_6` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `number.zhimi_cn_purifier_mb3_aqi_updata_heartbeat_p_13_9` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `number.zhimi_cn_purifier_mb3_filter_hour_debug_p_9_2` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `number.zhimi_cn_purifier_mb3_filter_max_time_p_9_1` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `number.zhimi_cn_purifier_mb3_main_channel_p_15_2` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `number.zhimi_cn_purifier_mb3_motor_favorite_p_10_7` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `number.zhimi_cn_purifier_mb3_motor_high_p_10_2` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `number.zhimi_cn_purifier_mb3_motor_low_p_10_5` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `number.zhimi_cn_purifier_mb3_motor_med_l_p_10_4` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `number.zhimi_cn_purifier_mb3_motor_med_p_10_3` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `number.zhimi_cn_purifier_mb3_motor_silent_p_10_6` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `number.zhimi_cn_purifier_mb3_motor_strong_p_10_1` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `number.zhimi_cn_purifier_mb3_slave_channel_p_15_3` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `select.zhimi_cn_purifier_mb3_country_code_p_15_11` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `select.zhimi_cn_purifier_mb3_temperature_unit_p_15_12` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `sensor.lumi_cn_lumi_zigbee_ieee_v1_battery_level_p_3_1` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `sensor.lumi_cn_lumi_zigbee_ieee_v1_status_p_2_2` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `sensor.lumi_cn_lumi_zigbee_ieee_v1_voltage_p_3_2` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `sensor.zhimi_cn_purifier_mb3_aqi_runstate_p_13_7` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `sensor.zhimi_cn_purifier_mb3_aqi_state_p_13_8` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `sensor.zhimi_cn_purifier_mb3_aqi_zone_p_13_4` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `sensor.zhimi_cn_purifier_mb3_average_aqi_cnt_p_13_3` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `sensor.zhimi_cn_purifier_mb3_average_aqi_p_13_2` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `sensor.zhimi_cn_purifier_mb3_device_serial_number_p_15_13` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `sensor.zhimi_cn_purifier_mb3_fault_p_2_1` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `sensor.zhimi_cn_purifier_mb3_hw_version_p_15_8` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `sensor.zhimi_cn_purifier_mb3_motor_set_speed_p_10_9` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `sensor.zhimi_cn_purifier_mb3_motor_speed_p_10_8` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `sensor.zhimi_cn_purifier_mb3_reboot_cause_p_15_6` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `sensor.zhimi_cn_purifier_mb3_rfid_factory_id_p_14_2` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `sensor.zhimi_cn_purifier_mb3_rfid_product_id_p_14_3` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `sensor.zhimi_cn_purifier_mb3_rfid_serial_num_p_14_5` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `sensor.zhimi_cn_purifier_mb3_rfid_time_p_14_4` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `sensor.zhimi_cn_purifier_mb3_sensor_state_p_13_5` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `text.zhimi_cn_purifier_mb3_cola_p_15_4` | unknown | dead/partial device (Xiaomi cloud device offline or diagnostic param unreported) | 2026-07-15 17:13 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |

### tuya (24)

| entity_id | state | reason | went unavail./last change | Auto? | UI? | recommended action |
|---|---|---|---|---|---|---|
| `binary_sensor.signalizatsiia_dvernogo_datchika_door` | unavailable | dead device / stale Tuya cloud state | 2026-07-15 15:11 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `light.dimmer_switch_11_light_1` | unavailable | dead device / stale Tuya cloud state | 2026-07-15 15:11 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `light.dimmer_switch_11_light_2` | unavailable | dead device / stale Tuya cloud state | 2026-07-15 15:11 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `scene.otkrylas_dver` | unknown | by-design (Tuya cloud scene: scenes carry no state) | 2026-07-15 15:12 | no | no | leave (by-design) |
| `scene.turn_off_all_sockets` | unknown | by-design (Tuya cloud scene: scenes carry no state) | 2026-07-15 15:12 | YES | no | LEAVE (referenced by automation/UI — dead device, keep entity) |
| `scene.turn_on_all_sockets` | unknown | by-design (Tuya cloud scene: scenes carry no state) | 2026-07-15 15:12 | YES | no | LEAVE (referenced by automation/UI — dead device, keep entity) |
| `scene.vkliuchit_svet_nad_akvariumom` | unknown | by-design (Tuya cloud scene: scenes carry no state) | 2026-07-15 15:12 | no | no | leave (by-design) |
| `scene.vkliuchit_svet_nad_stolom` | unknown | by-design (Tuya cloud scene: scenes carry no state) | 2026-07-15 15:12 | no | no | leave (by-design) |
| `scene.vkliuchit_svet_ostrov` | unknown | by-design (Tuya cloud scene: scenes carry no state) | 2026-07-15 15:12 | no | no | leave (by-design) |
| `scene.vkliuchit_svet_stena` | unknown | by-design (Tuya cloud scene: scenes carry no state) | 2026-07-15 15:12 | no | no | leave (by-design) |
| `scene.vkliuchit_svet_tv_zona` | unknown | by-design (Tuya cloud scene: scenes carry no state) | 2026-07-15 15:12 | no | no | leave (by-design) |
| `scene.vkliuchit_svet_u_lestnitsy` | unknown | by-design (Tuya cloud scene: scenes carry no state) | 2026-07-15 15:12 | no | no | leave (by-design) |
| `scene.vkliuchit_svet_zanaveski` | unknown | by-design (Tuya cloud scene: scenes carry no state) | 2026-07-15 15:12 | no | no | leave (by-design) |
| `scene.vykliuchit_ostrov_svet` | unknown | by-design (Tuya cloud scene: scenes carry no state) | 2026-07-15 15:12 | no | no | leave (by-design) |
| `scene.vykliuchit_svet_nad_akvariumom` | unknown | by-design (Tuya cloud scene: scenes carry no state) | 2026-07-15 15:12 | no | no | leave (by-design) |
| `scene.vykliuchit_svet_nad_stolom` | unknown | by-design (Tuya cloud scene: scenes carry no state) | 2026-07-15 15:12 | no | no | leave (by-design) |
| `scene.vykliuchit_svet_pervyi_etazh` | unknown | by-design (Tuya cloud scene: scenes carry no state) | 2026-07-15 15:12 | no | no | leave (by-design) |
| `scene.vykliuchit_svet_stena` | unknown | by-design (Tuya cloud scene: scenes carry no state) | 2026-07-15 15:12 | no | no | leave (by-design) |
| `scene.vykliuchit_svet_tv_zona` | unknown | by-design (Tuya cloud scene: scenes carry no state) | 2026-07-15 15:12 | no | no | leave (by-design) |
| `scene.vykliuchit_svet_u_lestnitsi` | unknown | by-design (Tuya cloud scene: scenes carry no state) | 2026-07-15 15:12 | no | no | leave (by-design) |
| `scene.vykliuchit_svet_zanaveski` | unknown | by-design (Tuya cloud scene: scenes carry no state) | 2026-07-15 15:12 | no | no | leave (by-design) |
| `scene.vykliuchit_vtoroi_etazh_koridor` | unknown | by-design (Tuya cloud scene: scenes carry no state) | 2026-07-15 15:12 | no | no | leave (by-design) |
| `select.dimmer_switch_11_power_on_behavior` | unavailable | dead device / stale Tuya cloud state | 2026-07-15 15:11 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `sensor.signalizatsiia_dvernogo_datchika_battery` | unavailable | dead device / stale Tuya cloud state | 2026-07-15 15:11 | YES | YES | LEAVE (referenced by automation/UI — dead device, keep entity) |

### mobile_app (18)

| entity_id | state | reason | went unavail./last change | Auto? | UI? | recommended action |
|---|---|---|---|---|---|---|
| `device_tracker.unknown` | unknown | ghost (orphan of DELETED SM-T595 companion app) | 2026-07-15 15:11 | no | no | owner-gated-remove (ghost) |
| `notify.unknown` | unknown | ghost (orphan of DELETED SM-T595 companion app) | 2026-07-15 15:11 | no | no | owner-gated-remove (ghost) |
| `notify.unknown_2` | unknown | ghost (orphan of DELETED SM-T595 companion app) | 2026-07-15 15:11 | no | no | owner-gated-remove (ghost) |
| `sensor.activity_2` | unavailable | ghost (orphan of DELETED SM-T595 companion app) | 2026-07-15 15:11 | no | no | owner-gated-remove (ghost) |
| `sensor.audio_output_2` | unavailable | ghost (orphan of DELETED SM-T595 companion app) | 2026-07-15 15:11 | no | no | owner-gated-remove (ghost) |
| `sensor.average_active_pace_2` | unavailable | ghost (orphan of DELETED SM-T595 companion app) | 2026-07-15 15:11 | no | no | owner-gated-remove (ghost) |
| `sensor.bssid_2` | unavailable | ghost (orphan of DELETED SM-T595 companion app) | 2026-07-15 15:11 | no | no | owner-gated-remove (ghost) |
| `sensor.connection_type_2` | unavailable | ghost (orphan of DELETED SM-T595 companion app) | 2026-07-15 15:11 | no | no | owner-gated-remove (ghost) |
| `sensor.distance_2` | unavailable | ghost (orphan of DELETED SM-T595 companion app) | 2026-07-15 15:11 | no | no | owner-gated-remove (ghost) |
| `sensor.floors_ascended_2` | unavailable | ghost (orphan of DELETED SM-T595 companion app) | 2026-07-15 15:11 | no | no | owner-gated-remove (ghost) |
| `sensor.floors_descended_2` | unavailable | ghost (orphan of DELETED SM-T595 companion app) | 2026-07-15 15:11 | no | no | owner-gated-remove (ghost) |
| `sensor.geocoded_location_2` | unavailable | ghost (orphan of DELETED SM-T595 companion app) | 2026-07-15 15:11 | no | no | owner-gated-remove (ghost) |
| `sensor.last_update_trigger_2` | unavailable | ghost (orphan of DELETED SM-T595 companion app) | 2026-07-15 15:11 | no | no | owner-gated-remove (ghost) |
| `sensor.sim_1_2` | unavailable | ghost (orphan of DELETED SM-T595 companion app) | 2026-07-15 15:11 | no | no | owner-gated-remove (ghost) |
| `sensor.sim_2_2` | unavailable | ghost (orphan of DELETED SM-T595 companion app) | 2026-07-15 15:11 | no | no | owner-gated-remove (ghost) |
| `sensor.ssid_2` | unavailable | ghost (orphan of DELETED SM-T595 companion app) | 2026-07-15 15:11 | no | no | owner-gated-remove (ghost) |
| `sensor.steps_2` | unavailable | ghost (orphan of DELETED SM-T595 companion app) | 2026-07-15 15:11 | no | no | owner-gated-remove (ghost) |
| `sensor.storage_2` | unavailable | ghost (orphan of DELETED SM-T595 companion app) | 2026-07-15 15:11 | no | no | owner-gated-remove (ghost) |

### matter (15)

| entity_id | state | reason | went unavail./last change | Auto? | UI? | recommended action |
|---|---|---|---|---|---|---|
| `binary_sensor.occupancysensor_zaniatost` | unavailable | dead device (Matter device offline/unpaired) | 2026-07-15 15:12 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `button.gateway_identifikatsiia` | unavailable | dead device (Matter device offline/unpaired) | 2026-07-15 15:12 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `event.4_scene_switch_knopka` | unavailable | dead device (Matter device offline/unpaired) | 2026-07-15 15:12 | no | no | leave (by-design) |
| `event.4_scene_switch_knopka_2` | unavailable | dead device (Matter device offline/unpaired) | 2026-07-15 15:12 | no | no | leave (by-design) |
| `event.4_scene_switch_knopka_3` | unavailable | dead device (Matter device offline/unpaired) | 2026-07-15 15:12 | no | no | leave (by-design) |
| `event.4_scene_switch_knopka_4` | unavailable | dead device (Matter device offline/unpaired) | 2026-07-15 15:12 | no | no | leave (by-design) |
| `light.1_dimmer_switch` | unavailable | dead device (Matter device offline/unpaired) | 2026-07-15 15:12 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `light.2dimmerswitch` | unavailable | dead device (Matter device offline/unpaired) | 2026-07-15 15:12 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `light.2dimmerswitch_2` | unavailable | dead device (Matter device offline/unpaired) | 2026-07-15 15:12 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `number.1_dimmer_switch_na_urovne` | unavailable | dead device (Matter device offline/unpaired) | 2026-07-15 15:12 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `number.2dimmerswitch_na_urovne` | unavailable | dead device (Matter device offline/unpaired) | 2026-07-15 15:12 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `number.2dimmerswitch_na_urovne_2` | unavailable | dead device (Matter device offline/unpaired) | 2026-07-15 15:12 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `number.occupancysensor_hold_time` | unavailable | dead device (Matter device offline/unpaired) | 2026-07-15 15:12 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `sensor.occupancysensor_batareia` | unavailable | dead device (Matter device offline/unpaired) | 2026-07-15 15:12 | YES | YES | LEAVE (referenced by automation/UI — dead device, keep entity) |
| `update.gateway_obnovlenie_proshivki` | unavailable | dead device (Matter device offline/unpaired) | 2026-07-15 15:12 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |

### smartthings (4)

| entity_id | state | reason | went unavail./last change | Auto? | UI? | recommended action |
|---|---|---|---|---|---|---|
| `binary_sensor.signalizatsiia_dvernogo_datchika_door_2` | unavailable | ghost (orphaned SmartThings cloud entity) | 2026-07-15 15:12 | no | no | owner-gated-remove (ghost) |
| `light.lg_tv` | unavailable | ghost (orphaned SmartThings cloud entity) | 2026-07-15 15:12 | no | no | owner-gated-remove (ghost) |
| `sensor.signalizatsiia_dvernogo_datchika_battery_2` | unavailable | ghost (orphaned SmartThings cloud entity) | 2026-07-15 15:12 | YES | YES | LEAVE (referenced by automation/UI — dead device, keep entity) |
| `switch.podsvetka_ostrov` | unavailable | ghost (orphaned SmartThings cloud entity) | 2026-07-15 15:12 | no | no | owner-gated-remove (ghost) |

### roborock (3)

| entity_id | state | reason | went unavail./last change | Auto? | UI? | recommended action |
|---|---|---|---|---|---|---|
| `binary_sensor.kiborg_water_box_attached` | unavailable | dead device (Roborock vacuum offline/setup_error) | 2026-07-15 15:12 | no | YES | LEAVE (referenced by automation/UI — dead device, keep entity) |
| `select.kiborg_mop_intensity` | unknown | dead device (Roborock vacuum offline/setup_error) | 2026-07-15 15:11 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `select.kiborg_mop_mode` | unknown | dead device (Roborock vacuum offline/setup_error) | 2026-07-15 15:11 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |

### cloud (3)

| entity_id | state | reason | went unavail./last change | Auto? | UI? | recommended action |
|---|---|---|---|---|---|---|
| `binary_sensor.remote_ui` | unavailable | by-design (Nabu Casa cloud not logged in) | 2026-07-15 15:11 | no | no | leave (by-design) |
| `stt.home_assistant_cloud` | unknown | by-design (Nabu Casa cloud not logged in) | 2026-07-15 15:11 | no | no | leave (by-design) |
| `tts.home_assistant_cloud` | unknown | by-design (Nabu Casa cloud not logged in) | 2026-07-15 15:11 | no | no | leave (by-design) |

### androidtv_remote (2)

| entity_id | state | reason | went unavail./last change | Auto? | UI? | recommended action |
|---|---|---|---|---|---|---|
| `media_player.mitv_mssp2` | unavailable | dead device (Android TV MiTV offline) | 2026-07-15 15:12 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `remote.mitv_mssp2` | unavailable | dead device (Android TV MiTV offline) | 2026-07-15 15:12 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |

### dlna_dmr (2)

| entity_id | state | reason | went unavail./last change | Auto? | UI? | recommended action |
|---|---|---|---|---|---|---|
| `media_player.solas_tv` | unavailable | dead device (DLNA media player powered off) | 2026-07-15 15:11 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |
| `media_player.xbox` | unavailable | dead device (DLNA media player powered off) | 2026-07-15 15:11 | no | no | leave (retries when device returns) / owner-gated-remove if device retired |

### google_generative_ai_conversation (2)

| entity_id | state | reason | went unavail./last change | Auto? | UI? | recommended action |
|---|---|---|---|---|---|---|
| `stt.google_ai_stt` | unknown | by-design (stt/tts provider unused) | 2026-07-15 15:11 | no | no | leave (by-design) |
| `tts.google_ai_tts` | unknown | by-design (stt/tts provider unused) | 2026-07-15 15:11 | no | no | leave (by-design) |

### google_translate (1)

| entity_id | state | reason | went unavail./last change | Auto? | UI? | recommended action |
|---|---|---|---|---|---|---|
| `tts.google_translate_en_com` | unknown | by-design (stt/tts provider unused) | 2026-07-15 15:11 | no | no | leave (by-design) |

## B. Registered but no state — integration-disabled / by-design (114)

These are **not ghosts**. Every one is `disabled_by=integration` — verbose/diagnostic entities that the
integration auto-disables on creation (HACS pre-release toggles, nordpool sub-averages, hassio addon
cpu/mem sensors, tuya per-plug current/power/voltage, sun azimuth, etc.). Leave as-is; re-enable individually
only if a dashboard needs one.

| platform | count | example entity_ids |
|---|---|---|
| hassio | 47 | `binary_sensor.advanced_ssh_web_terminal_running`, `binary_sensor.deconz_running`, `binary_sensor.duck_dns_running` … |
| tuya | 18 | `sensor.akvarium_svet_current`, `sensor.akvarium_svet_power`, `sensor.akvarium_svet_voltage` … |
| nordpool | 17 | `sensor.nord_pool_lv_daily_average`, `sensor.nord_pool_lv_exchange_rate`, `sensor.nord_pool_lv_off_peak_1_average` … |
| hacs | 17 | `switch.apexcharts_card_pre_release`, `switch.auto_entities_pre_release`, `switch.button_card_pre_release` … |
| roborock | 4 | `button.kiborg_reset_air_filter_consumable`, `button.kiborg_reset_main_brush_consumable`, `button.kiborg_reset_sensor_consumable` … |
| matter | 4 | `sensor.4_scene_switch_tekushchee_polozhenie_perekliuchatelia`, `sensor.4_scene_switch_tekushchee_polozhenie_perekliuchatelia_2`, `sensor.4_scene_switch_tekushchee_polozhenie_perekliuchatelia_3` … |
| sun | 3 | `binary_sensor.sun_solar_rising`, `sensor.sun_solar_azimuth`, `sensor.sun_solar_elevation` … |
| oralb | 2 | `sensor.io_series_6_7_a913_sector_timer`, `sensor.io_series_6_7_a913_signal_strength` … |
| google | 1 | `calendar.working_location` … |
| ipp | 1 | `sensor.hp_laserjet_200_color_m251n_uptime` … |

All 114 confirmed `disabled_by=integration`: **True**

## Bucket summary

- **dead/offline device (leave; retries)**: 69
- **by-design (leave)**: 33
- **ghost / orphan (owner-gated-remove)**: 21
- **referenced-but-unavailable (LEAVE)**: 6
- **integration-disabled no-state (by-design, leave)**: 114
- **Live unavailable/unknown total**: 129

## Owner-gated ghost removal candidates (do NOT remove now)

21 orphaned entities from deleted integrations/devices. Owner said DO NOT delete registry
entries now — listed for a future owner-approved cleanup. (Removal of SmartThings/mobile_app ghosts is
irreversible via registry and may re-appear unless removed at the cloud source.)

- `binary_sensor.signalizatsiia_dvernogo_datchika_door_2` (smartthings)
- `device_tracker.unknown` (mobile_app)
- `light.lg_tv` (smartthings)
- `notify.unknown` (mobile_app)
- `notify.unknown_2` (mobile_app)
- `sensor.activity_2` (mobile_app)
- `sensor.audio_output_2` (mobile_app)
- `sensor.average_active_pace_2` (mobile_app)
- `sensor.bssid_2` (mobile_app)
- `sensor.connection_type_2` (mobile_app)
- `sensor.distance_2` (mobile_app)
- `sensor.floors_ascended_2` (mobile_app)
- `sensor.floors_descended_2` (mobile_app)
- `sensor.geocoded_location_2` (mobile_app)
- `sensor.last_update_trigger_2` (mobile_app)
- `sensor.sim_1_2` (mobile_app)
- `sensor.sim_2_2` (mobile_app)
- `sensor.ssid_2` (mobile_app)
- `sensor.steps_2` (mobile_app)
- `sensor.storage_2` (mobile_app)
- `switch.podsvetka_ostrov` (smartthings) — **already reversibly disabled this session (`disabled_by:user`)**; full registry removal remains owner-gated

## Action taken this session (reversible)

- `switch.podsvetka_ostrov` (smartthings, config_entry `01HAENTRYIDPLACEHOLDER0000`) set to
  **`disabled_by: user`** via WS `config/entity_registry/update`. Registry entry **retained** (not deleted).
  Re-enable with `disabled_by: null`.
- Evidence it is unused: 0 hits in live automations.yaml / scripts.yaml / scenes.yaml / configuration.yaml;
  0 hits in any `/config/www/*` dashboard or repo `tablet/`,`miniapp/`. The kitchen island is driven by
  live entities `switch.svet_pervyi_etazh_1_ostrov_i_stol` (off, available),
  `switch.vkliuchit_svet_ostrov` (off, available) and Tuya wall remote `event.ostrov_vykliuchatel_button_1..4`
  (battery 100%). Verified `disabled_by` was `None` before, `user` after; entry still present.
