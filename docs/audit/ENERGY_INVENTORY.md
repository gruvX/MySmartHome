# Energy Inventory & Measurement Audit

Generated 2026-07-15 (read-only). Source: HA REST `/api/states`, `core.entity_registry`,
`core.device_registry`, `configuration.yaml`, `/config/.storage/` on 192.168.1.45:8123.

## Headline findings

- **HA Energy Dashboard is NOT configured** — no `/config/.storage/energy` file exists.
  Every load below has `in_energy_dashboard = false`.
- **No whole-home / main meter exists.** No grid, main, or `utility_meter` energy sensor;
  no `utility_meter:` helper in config. Only per-device plug metering.
  (`sensor.electricity_maps_grid_fossil_fuel_percentage` is grid CO2 mix, not consumption.)
- **Cost is computable per-device only** (metered kWh delta x Nord Pool LV price), which is what
  the `cost_month_*` accumulators do (automation `1785000001001`). Whole-home cost is not derivable.
- **8 loads have true cumulative kWh metering (class B).** The rest are unmeasured
  (floors/lights estimable = D; ecoNET electrical / valve / misc outlets = E).
- **Counter resets are real and handled:** Tuya `*_total_energy` counters reset to 0; guard
  automation `gard_sbrosa_schetchika_energii` (`1786000001001`) re-bases `input_number.midnight_*`
  when total < snapshot. Live 0-values on boiler/towel/bed-backlight are consistent with recent resets.

## Quality classes

`A` exact interval metering · `B` cumulative kWh · `C` power only · `D` nameplate x on-time estimate · `E` no data

| # | Load | On/off entity | Power sensor | Energy sensor | Unit | dev_class / state_class | Integration | Update | Avail | In dash | Class |
|---|------|---------------|--------------|---------------|------|--------------------------|-------------|--------|-------|---------|-------|
| 1 | EV charger | `switch.ev_charger_switch` | – | `sensor.ev_charger_energy` = 882.8 | kWh | energy / total_increasing | command_line (ev_query.py→Tuya Cloud) | 300s | ✅ | ❌ | **B** |
| 2 | Boiler electric TEN (CWU) | `switch.smart_plug_2_socket_1` | – | `sensor.boiler_total_energy` = 0 | kWh | energy / total_increasing | tuya | cloud push | ✅ (flaps) | ❌ | **B** |
| 3 | Towel warmer (Коларифер) | `switch.kalarifer_socket_1` | – | `sensor.terarium_total_energy` = 0 | kWh | energy / total_increasing | tuya | cloud push | ✅ | ❌ | **B** |
| 4 | Aquarium light | `switch.akvarium_svet_socket_1` | – | `sensor.akvarium_svet_total_energy` = 0.023 | kWh | energy / total_increasing | tuya | cloud push | ✅ | ❌ | **B** |
| 5 | Hot-water recirc (Черепаха) | `switch.retserkuliatsiia_goriachai_vody_socket_1` | – | `sensor.cherepakha_total_energy` = 0.001 | kWh | energy / total_increasing | tuya | cloud push | ✅ | ❌ | **B** |
| 6 | Hydrophore / pump | `switch.zigbee_plug_2_socket_1` | – | `sensor.zigbee_plug_2_total_energy` = 275.69 | kWh | energy / total_increasing | tuya | cloud push | ✅ | ❌ | **B** |
| 7 | Bed backlight (Подсветка кровати) | `switch.zigbee_plug_socket_1` | – | `sensor.zigbee_plug_total_energy` = 0.0 | kWh | energy / total_increasing | tuya | cloud push | ✅ | ❌ | **B** |
| 8 | TV 75" QLED | `switch.svet_tv_zona_switch_1` (zone light) | `sensor.75_qled_power` = 0 W | `sensor.75_qled_energy` = 0.0 | W / kWh | power+energy / measurement+total_increasing | smartthings | cloud poll (min) | ✅ | ❌ | **B** |
| 9 | Floor heating — bathroom | `climate.floor_heating` (preset) | – | – | – | – | tuya climate | state | ✅ | ❌ | **D** |
| 10 | Floor heating — shower 1F | `climate.floor_heating_2` (preset) | – | – | – | – | tuya climate | state | ✅ | ❌ | **D** |
| 11 | Lighting (aggregate) | many `light.*` / `switch.*` | – | – | – | – | tuya/xiaomi/smartthings | state | mixed | ❌ | **D** |
| 12 | Boiler ecoNET electrical (fan/feeder/pumps) | `switch.boiler` proxy | – | – | – | – | rest (ecoNET24) | 30s | ✅ | ❌ | **E** |
| 13 | Water shutoff valve | `switch.voda_kran_switch_1` | – | – | – | – | tuya | state | ✅ | ❌ | **E** |
| 14 | Misc unmetered outlets/relays | `switch.kukhnia_poloski_*`, `switch.gostinnaia_zanaveska_*`, `switch.smart_switch_2ch_*`, `switch.220v_..._switch_*`, `switch.outlet*` | – | – | – | – | tuya | state | mixed | ❌ | **E** |

## Notes per load

- **EV (1):** cumulative kWh only, no instantaneous power. `sensor.ev_charger_status` = `charger_charging`
  while `switch.ev_charger_switch` = off (status comes from the cloud sensor, not the switch). Largest total.
- **Boiler TEN (2):** device "Бойлер". Reads 0 kWh now (reset/idle; plug WiFi drops in the weak-signal boiler zone).
- **Towel warmer (3) & recirc (5):** entity-name mismatches — the `kalarifer` switch pairs with the
  `terarium` energy sensor (one plug), and the `retserkuliatsiia` switch pairs with the `cherepakha` energy sensor.
- **Bed backlight (7):** metered but **absent from the CLAUDE.md energy table and from `cost_month_*`** — its kWh
  is measured yet not cost-tracked. Candidate to add.
- **TV (8):** the only load exposing both W (power/measurement) and kWh (energy/total_increasing). Extra SmartThings
  variants exist (`_energy_difference`, `_power_energy`, `_energy_saved`). `switch.svet_tv_zona` drives TV-zone
  lighting, not the set. Not in cost accumulators.
- **Floors (9,10):** electrically UNMEASURED. On/off + duration are known via `climate` state, so a
  nameplate x on-time estimate is feasible (class D) but not currently done.
- **ecoNET (12):** all `sensor.boiler_*` are temperatures (°C) or percentages. `sensor.boiler_power` = 99% is
  **burner output %, not watts**. Primary fuel is pellets; electrical auxiliaries are unmetered.

## Counts

- **B (cumulative kWh, cost-computable):** 8 → EV, Boiler TEN, Towel warmer, Aquarium, Recirc, Hydrophore, Bed backlight, TV.
- **D (unmeasured, estimable via nameplate×time):** 3 → Floor heating bathroom, Floor heating shower, Lighting.
- **E (no data):** 3 → Boiler ecoNET electrical, Water valve, Misc outlets.
- **A / C:** 0.

## Recommendations

1. Enable the HA Energy Dashboard and register the 8 class-B sensors (`state_class`/`device_class` already correct).
2. Add a **whole-home meter** (CT clamp / smart meter) to enable house-level cost and a metered-vs-total gap.
3. Add `sensor.zigbee_plug_total_energy` (bed backlight) to `cost_month_*` tracking.
4. For floors, add nameplate-based template estimators (class D) or metered plugs (class B).
