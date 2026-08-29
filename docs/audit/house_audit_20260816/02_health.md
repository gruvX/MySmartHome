# House Health & Data Trust Audit — 2026-08-16

STATUS: COMPLETE

**Three-line verdict:** the house *hardware* is in decent shape — ~20 genuinely broken devices out
of 817 entities, most of them cosmetic. The house *data* is not: the Tuya cloud link froze all six
energy counters for **15 days (01–16 Aug)** without ever marking them unavailable, and it aborted
**100 automation runs** in the last 10 days. The bedroom climate sensor has been dead **16 days**
while both UIs still present it as fact.
Method: READ-ONLY. HA REST `/api/states`, `/api/history/period`, WebSocket read commands,
Supervisor logs via SSH. No service calls, no writes, no restarts.

## 0. Platform baseline

| Item | Value |
|---|---|
| HA Core | **2026.8.2** (CLAUDE.md still says 2026.7.1 — stale doc) |
| Entities in state machine | 817 |
| Timezone / currency | Europe/Riga / EUR |
| HA state | RUNNING |
| Last restart | ~7.3 h before audit (all boot-time `last_changed` cluster there) |

> **Trust caveat #1:** `last_changed` on `unavailable` entities is reset by the HA restart.
> Anything that was already dead before the restart shows only "7.3h". Real downtime must be
> taken from the recorder history, not from the live state object.

## 1. Availability census (817 entities)

Raw: **213** entities are `unavailable` (68) or `unknown` (145).
That headline number is misleading; classified:

| Class | Count | Meaning |
|---|---|---|
| (b) Normally stateless domains | 129 | `button` 69, `scene` 19, `event` 28, `tts` 3, `stt` 2, `notify` 3, `text` 1 — these are `unknown` by design until pressed/fired. **Not a fault.** |
| (c) Diagnostic / config attributes | ~50 | Mijia air purifier `zhimi_..._mb3` internals (motor-speed presets, rfid, aqi debug, filter-time, hw-version). Device itself is ONLINE (PM2.5 reports fine) — these are miot props HA polls but the device never answers. Cosmetic. |
| (a) Genuinely broken / offline devices | see §1.1 | |
| (d) Orphans of removed/absent devices | see §1.1 | |

### 1.1 Genuinely broken / offline devices (class a) and orphans (class d)

**Downtime method:** the recorder `states` table only holds **2026-08-06 01:12 → now (10.5 days)**.
Every entity below has exactly ONE state row in that whole window (the one written at the
2026-08-16 05:56 UTC reboot) — i.e. they were already dead before the window opened.
Exact death dates come from the **long-term statistics** table, which reaches back to 2024-12-16.

#### Dead, with a datable death (from long-term statistics)

| Device / entity | Last real data | Down for | Verdict |
|---|---|---|---|
| **`sensor.lumi_...bedroom_th...temperature_p_2_1` + `..._relative_humidity_p_2_2`** — the **СПАЛЬНЯ (bedroom) temp/humidity** shown on the tablet AND Mini App home screens | **2026-07-31 11:00** | **16 days** | **class (a) REAL BREAK — highest-impact finding.** Xiaomi/Lumi Zigbee sensor stopped reporting. Both UIs still render a bedroom tile for it. |
| `sensor.homelab_gate3_rc2_*` (9 Proxmox guest metrics: cpu/mem/disk/net/uptime) | 2026-07-29 10:00 | 18 days | class (a)/(d) — Proxmox guest `gate3-rc2` gone or renamed |
| `sensor.hp_laserjet_200_color_m251n*` (5 entities) | 2026-07-25 10:00 | 22 days | class (a) printer offline — cosmetic |
| `sensor.signalizatsiia_dvernogo_datchika_battery` (+ door binary_sensors, x2 each) | 2026-07-23 09:00 | 24 days | class (a) — a door/alarm sensor that is NOT the primary `binary_sensor.door_sensor_door` |
| `sensor.intellektualnyi_dvernoi_zvonok_battery` (doorbell) | 2026-07-20 10:00 | 27 days | class (a) |
| `sensor.sm_t595_battery_level_2` | 2026-07-12 20:00 | 34 days | class (d) **orphan** — tablet mobile_app entries deleted 2026-07-12 by owner. Expected. |
| `sensor.occupancysensor_batareia` + `binary_sensor.occupancysensor_zaniatost` | 2025-12-18 | ~8 months | class (d) orphan |
| `sensor.temperature_lumi_bedroom_th`, `sensor.humidity_...`, `sensor.shliuz_undefinedtype_singleton` | 2026-01-01 | ~7.5 months | class (d) orphan (old naming of the same Lumi device) |
| `sensor.temperature_humidity_sensor_94df_*`, `_a88d_*` (9 entities) | 2025-12-17 | ~8 months | class (d) orphan |
| `sensor.temperature_humidity_sensor_7da3_*` (4) | 2025-09-01 | ~11.5 months | class (d) orphan |
| `sensor.mi_body_composition_scale_c361_*` (3) | 2025-10-15 / 2026-01-06 | 7–10 months | class (d) orphan (scale unused) |

#### Dead, NOT datable (non-numeric → no statistics; ≥10.5 days by DB evidence)

These have no long-term statistics because they are not numeric, so the only honest statement
is **"dead for at least 10.5 days"** (the whole retained window) — the true start is unknowable
without older backups.

- `media_player.xbox`, `media_player.solas_tv`, `media_player.mitv_mssp2` + `remote.mitv_mssp2`, `light.lg_tv` — media devices, powered off. Mostly class (a) benign.
- `light.1_dimmer_switch`, `light.2dimmerswitch`, `light.2dimmerswitch_2` + their `number.*_na_urovne` — **class (a): three dimmer switches offline.** Worth owner confirmation — are these physically installed?
- `binary_sensor.lumi_...living_motion...motion_state` — Lumi motion sensor dead.
- `sensor.lumi_...zigbee_ieee...` smoke sensor (concentration/status/battery/voltage) — **class (a): a Lumi SMOKE sensor is dead.** Note the *primary* smoke sensor used by the siren automation is `binary_sensor.wifi_th_smoke_sensor_smoke` (different device) — but a second, dead smoke detector is a life-safety item worth telling the owner about.
- `binary_sensor.kiborg_water_box_attached` — Roborock vacuum (known `setup_error`).
- `update.gateway_obnovlenie_proshivki` — Lumi gateway firmware update entity.
- `sensor.*_2` block + `device_tracker.unknown` + `sensor.pressure` + `sensor.kiosk_*` (18 entities, friendly name "phone") — **class (d) orphan**: a mobile_app / Fully Kiosk device registration whose device is gone.
- `binary_sensor.remote_ui` (Nabu Casa cloud remote — not subscribed), `sensor.storage_local_storage_usage_percentage`.

**Honest count:** of 213 `unavailable`/`unknown`, only about **20 entities represent a device the
owner would call broken**, and of those only **one (the bedroom temp/humidity sensor) is
currently surfaced as fact in the UIs**. The rest are stateless domains, miot diagnostic props,
or orphans of hardware deliberately removed.

## 5. Recorder / history reality

| Fact | Value |
|---|---|
| `recorder:` block in configuration.yaml | **absent** — recorder comes from `default_config:` |
| Effective `purge_keep_days` | **10 (the default)** — confirmed empirically: oldest `states` row = 2026-08-06 01:12, now = 2026-08-16 14:06 → 10.5 days |
| Exclusions | **none** (no recorder block ⇒ nothing excluded; 838 entities in `states_meta`) |
| DB | SQLite `/config/home-assistant_v2.db`, **262 MB** + 5.3 MB WAL |
| Disk | /dev/sda8 30.8 G, 10.1 G used, **19.4 G free (34%)** — no space pressure |
| `states` rows | 856,860 over 10.5 d |
| `statistics_short_term` | 2026-08-06 → now (also 10 d), 437,854 rows |
| **`statistics` (long-term, hourly)** | **2024-12-16 10:00 → now, 544,810 rows, 195 metrics** |
| Long-term metrics fresh (<3 h) | 157 / 195 |

**What this bounds for a new history screen:**
- Any screen showing *state history / timelines / on-off logs* can honestly go back **10 days only**.
- Any screen showing *numeric trends* (energy kWh, price, temperatures, batteries) can honestly
  go back **~20 months**, but only for the **195 metrics that have `state_class`**. A trend chart
  must be driven by the statistics API, not the history API, or it will silently truncate at 10 days.
- Automatic full backups exist daily (`/backup`, ~190 MB, 3 retained: Aug 14/15/16) — labelled
  `2026.7.4` although core is now 2026.8.2.

## 2. Staleness — with per-class judgement

There is **no single valid threshold**. Applying one is exactly what produced the earlier false
"protection is blind" alarm. Correct classes:

| Class | Expected cadence | Silence verdict | Current state |
|---|---|---|---|
| **Battery Zigbee/Tuya leak + door + smoke sensors** (`*_moisture`, `door_sensor_door`, `wifi_th_smoke_sensor_smoke`) | **event-driven sleepers** — report only on change, plus a slow heartbeat | **A day of silence is NORMAL and means "dry/closed", not "blind".** Never age these out in the UI. | 4 moisture sensors last updated 5.5–7.4 h ago = since reboot. **Healthy.** |
| **Leak truth sensor** `sensor.leak_protection_status` = `ok`, `sensor.tuya_leak_cloud` = `normal` | recomputed continuously | fresh 0.1 h | **The one authoritative leak signal — healthy.** UI must read only this. |
| **Mains-powered energy counters** (Tuya plugs) | seconds–minutes | hours of silence IS a fault | see §6 — 2 of 6 are stale/frozen |
| **ecoNET boiler REST** | 30 s poll (`regParams`) + slower params endpoint | minutes | temps fresh 0.07–0.25 h; setpoints/mode/power/fuel 1.75 h (slower endpoint — normal) |
| **Nord Pool price** | new value each market interval | minutes | `current/next/previous_price` fresh (0.1 h) — **but see §6.3, tomorrow's prices are missing** |
| **Room temp/humidity (BLE/Zigbee)** | 10–60 min | hours = suspect, days = dead | Кухня 0.6 h OK; Гостиная (Mijia Pro) 7.2 h = since reboot, borderline; **Спальня dead 16 days** |
| **Weather station / outdoor** | ~30–60 min | | 0.7–1.3 h — healthy |
| **Presence** `binary_sensor.prisutstvie_owner` = `on` | changes only on arrival/departure, `delay_off` 10 min | silence normal | 7.4 h (since reboot) — **normal**, do not age out |
| **Batteries** | daily-ish | days = suspect | see §3 |

## 3. Batteries — worst first

| % | Device | Reporting? |
|---|---|---|
| **unavailable** | `signalizatsiia_dvernogo_datchika_battery` ×2 (door/alarm sensor) | **NO — silent since 2026-07-23 (24 d).** These are the "Сигн.1 / Сигн.2 at 0%" from the project notes: they did not just hit 0, they went off the air. |
| **unavailable** | `lumi_...zigbee_ieee...battery_level` (Lumi **smoke** detector) | **NO — ≥10.5 d** |
| **unavailable** | `occupancysensor_batareia` | NO — since 2025-12 (orphan) |
| **20 %** | `sensor.perenosnoi_pult_battery` — Переносной пульт (portable remote) | yes — **lowest live battery, replace** |
| **23 %** | `miaomiaoc_..._living...battery_level` — Mijia Pro, **ГОСТИНАЯ temp/humidity** | yes — **replace soon; this is the last working living-room climate sensor** |
| **38 %** | `miaomiaoc_..._bedroom2...battery_level` — "Спальня доп. датчик" | yes |
| 42 / 43 / 43 % | `kukhnia_battery`, `_2`, `_3` (Кухня) | yes |
| 55 % | `garazh_battery` (Гараж leak sensor) | yes |
| 55 % ×2 | `battery_level`, `battery_level_2` ("phone") | stale — orphan device, ignore |
| 70 % | `wifi_th_smoke_sensor_battery` — **primary smoke detector** | yes — healthy |
| 83 % | `door_sensor_battery` — Входная дверь | yes |
| 89 / 90 / 97 % | Сценарный пульт, PIR motion, IO Series 6/7 | yes |
| 100 % ×6 | `vannaia`, `water_sensor_4` (leak), motion, 2 wall switches, vacuum, SM-T595 | yes |

**Action list for the owner: portable remote (20 %) and the living-room Mijia Pro (23 %).**
The two door-alarm battery sensors and the Lumi smoke detector need *investigation*, not batteries —
they stopped transmitting entirely.

## 4. Integration health

**Config entries: 39 total, 36 loaded, 3 not.** No Tuya/Nord Pool/Telegram/boiler entry is failing.

| Entry | State | Reality |
|---|---|---|
| `ipp` — HP LaserJet M251n | `setup_retry` | printer offline 22 d. Noise. |
| `androidtv_remote` — MiTV-MSSP2 | `setup_retry` — can't connect 192.168.1.63:6466 | TV off. Noise. |
| `homekit` — Интеллектуальный дверной звонок bridge | `not_loaded` | fails because `camera.intellektualnyi_dvernoi_zvonok` is unavailable. Cosmetic. |

### Top recurring log errors — 10-day core log (2026-08-06 → 2026-08-16), 819 ERROR + 680 WARNING lines

| # | Count | What | Verdict |
|---|---|---|---|
| 1 | **~392** | `Error rendering availability template for sensor.boiler_* / binary_sensor.boiler_*: 'value_json' is undefined` (26 boiler entities × ~15–20) | **REAL but bursty, not chronic.** Traced to exactly **two** ecoNET outages: **2026-08-10 16:35–16:39** (336 errors) and **2026-08-11 ~03:00** (56). The `regParams` REST call returned an error body, `value_json` was undefined, and the *availability* template itself threw. The hostname pin to `ecoNET300.local` has held since — no ecoNET failures 08-11 → 08-16. Cosmetically the availability templates should guard `value_json is defined`. |
| 2 | **229 hits of `sign invalid` / 249 `network error`** | **Tuya cloud auth desync** | **THE root disease, still live.** Present on 9 of 10 days (peaks 22/day on 08-15 and 20/day on 08-07). |
| 2b | **100 automation runs aborted mid-script** by it | `polotentsesushitel_po_nord_pool` **41**, `nochnaia_ekonomiia_primenit` **28**, `teplyi_pol_dushevaia_1et` **12**, `ev_zariadka_avtozariadka_2ch` **11**, `boiler_kalorifer_po_tsene` **8** | **REAL and consequential** — these are heating/cost automations silently failing to act. |
| 3 | 37 | `roborock.coordinator: Error fetching roborock data` | Noise (entry loads, cloud flaky). |
| 4 | 90 | `xiaomi_home` sets entity ID with wrong domain (`xiaomi_home.zhimi_..._alarm`) | Noise now; **breaks in HA 2027.5**. Custom-integration bug. |
| 5 | 57 | `Template variable warning: 'peer_busy' is undefined` in the **new `tuya_selfheal` automation** (added 2026-08-16) | **REAL, fresh regression** — the self-heal automation added today has an undefined variable. |
| 6 | 21 | `Template variable warning: 'pf_raw' is undefined` — price-forecast template | **REAL** — the new `price_forecast` templating is broken. |
| 7 | 44 | `Referenced entities calendar.semia / calendar.prazdniki_latvii / calendar.holidays / calendar.owner_mail are missing or not currently available` | **REAL for the UI** — the Calendar card has no data source. |
| 8 | 12 | `📲 Telegram обработчик кнопок: Query is too old / query id is invalid` (08-16 11:12–12:06) | Benign-ish: stale inline buttons pressed after expiry. |
| 9 | 12 | `Бойлер / Тёплый пол по Nord Pool: In 'template' condition: TypeError` on 2026-08-09 13:00–17:00 | A 4-hour window where a price template broke. Worth a look. |
| 10 | 7 | `xiaomi_home miot_client: mips disconnect / try reconnect` | Xiaomi cloud link flaps. Correlates with dead Lumi entities. |

No database, memory, or disk errors anywhere in the window.

## 6. Energy accounting quality — the most damaged area

### 6.1 What is metered, and what is not

Metered (7 plugs, of which 6 are used by the cost model):

| Load | Switch | Counter | Counter type |
|---|---|---|---|
| Boiler ТЭН | `switch.smart_plug_2_socket_1` (**on**) | `sensor.boiler_total_energy` | **daily-reset** (0 → 7–45 kWh/day) |
| Полотенцесушитель | `switch.kalarifer_socket_1` (off) | `sensor.terarium_total_energy` | **daily-reset** (0 → 0.2–2.2 kWh/day) |
| Аквариум | `switch.akvarium_svet_socket_1` (on) | `sensor.akvarium_svet_total_energy` | daily-reset |
| Рециркуляция ГВС | `switch.retserkuliatsiia_...` (off) | `sensor.cherepakha_total_energy` | daily-reset |
| Гидрофор | `switch.zigbee_plug_2_socket_1` (on) | `sensor.zigbee_plug_2_total_energy` | **lifetime cumulative** (251 → 329 kWh) |
| EV charger | `switch.ev_charger_switch` (off) | `sensor.ev_charger_energy` | **lifetime cumulative** (1019 → 1036 kWh) |
| TV 75" QLED | — | `sensor.75_qled_energy` = **0.0**, `zigbee_plug_total_energy` = **0.0** | dead meters, excluded from the cost model |

**NOT metered — no sensor exists at all:**
- **Electric floor heating** (`climate.floor_heating`, `climate.floor_heating_2`) — a major seasonal load that the price automations actively switch. Completely invisible to the cost model.
- All lighting (15 lights + ~80 switches), kitchen appliances, washing machine, oven, IT/network, the HA VM host itself, the ecoNET boiler's own pumps/fan.
- **There is no whole-house / grid meter entity anywhere in HA.**

> **Honest statement for the UI:** the "энергия" figures describe **6 smart plugs**, not the house.
> Any label that reads "потребление дома" or "月/месяц: € X" is a category error. It must read
> "по 6 розеткам" or similar.

### 6.2 THE BIG ONE — 15 days of energy metering were lost, and today's numbers are corrupted

Evidence from two independent tables (`statistics` hourly + `states` row counts):

- **All six Tuya energy counters froze at a constant value on 2026-08-01 and did not move again
  until the 2026-08-16 05:56 reboot.** Example: `zigbee_plug_2_total_energy` sat at exactly
  `313.05` for every hour of 08-02 … 08-15; `boiler_total_energy` sat at `12.748`;
  `ev_charger_energy` at `1019.0`.
- They did **not** go `unavailable` — they held a plausible-looking number. This is the worst
  failure mode for a dashboard: **stale data that looks live.** A UI freshness check based on
  `unavailable` would have shown "all green" for two weeks.
- The states table proves it: **zero state rows** for these entities across 08-06 → 08-15
  (states are only written on change), then 9–135 rows on 08-16 alone.
- Cause: the Tuya cloud `sign invalid` disease (§7). Today's reboot re-authenticated it.

**Consequences that are live right now:**

1. **August month-to-date cost `input_number.cost_month_total` = €0.90 is not a cheap month — it
   is a broken meter.** The 23:58 accrual ran every night on a frozen counter, computed a delta
   of 0, and added €0.00. **14 of the first 15 days of August are recorded as zero consumption.**
2. **Today's (2026-08-16) "today kWh" is inflated by up to 15 days of catch-up** on the two
   cumulative counters: гидрофор shows **+15.99 kWh today** against a July norm of ~2.5 kWh/day
   (≈6× overstated); EV shows **+16.97 kWh today** while `sensor.ev_charger_status` is
   `charger_free`. Tonight's 23:58 accrual will book that backlog as one day's cost.
3. **The midnight baselines were rebased to 0 by the reset guard.** `midnight_boiler_energy`,
   `_akv`, `_chep`, `_kalarifer`, `_tv` are all **0.0** — the guard (`🔄 Гард сброса счётчика`)
   saw the post-reboot `0` reading, concluded "counter reset", and re-based. For the daily-reset
   counters that is accidentally correct; combined with the catch-up it is not safe to trust.
   `midnight_gidro`=313.05 and `midnight_ev`=1019.0 are the pre-reboot frozen values — these two
   are the ones that will over-bill tonight.

### 6.3 The cost formula is a rough estimate, and it is biased high

From automation `1785000001001` (23:58 daily):

```
avg      = (nord_pool_lv_lowest_price + nord_pool_lv_highest_price) / 2
cost_day = max(counter_now - midnight_baseline, 0) * avg
```

Quantified error sources, worst first:

| # | Source | Direction & size |
|---|---|---|
| 1 | **Missing 14 days of August data** (§6.2) | month figure understated by ~14/16 of true usage — dominant |
| 2 | **`avg` is the midpoint of the day's min and max spot price**, not a consumption-weighted average | **systematically overstates.** Today lowest=0.00566, highest=0.10251 → avg=0.054 €/kWh, while the actual current price is **0.0062 €/kWh** — an **8.7× overstatement** at this moment. The whole point of the automations is to consume at the *lowest* hours, so the true weighted price is near the daily minimum, never the midpoint. |
| 3 | **Spot price only — no grid tariff, no VAT, no fixed fees** | **understates the real bill.** In Latvia the invoice = spot + Sadales tīkls distribution + mandatory procurement + 21 % VAT. The retail total is typically **2–3× the spot component**, and at today's near-zero spot (0.006 €/kWh) the spot part is a rounding error against the fixed charges. |
| 4 | **Only 6 plugs metered; floor heating and everything else invisible** | understates house consumption by an unknown but large factor |
| 5 | `max(delta, 0)` silently swallows counter resets mid-day | undercounts on reset days |
| 6 | Daily-reset vs lifetime-cumulative counters are mixed in one formula | correct only while both behave; broke this month |
| 7 | Accrual is a single 23:58 sample — any outage across 23:58 loses the whole day | e.g. an HA restart at 23:57 |

> **Verdict for the new UI:** these are **spot-price estimates over 6 smart plugs**, not a bill,
> and right now they are additionally corrupted by a 15-day data loss. The number must be
> labelled as an estimate, must carry the "6 plugs" scope, and **must not be shown for August 2026
> at all** without a "данные за 02–15.08 отсутствуют" warning.

### 6.4 Nord Pool: tomorrow's prices are not available

- `binary_sensor.nord_pool_lv_tomorrow_price_available` = **off** at 17:05 local (they are
  normally published ~13:00–14:00).
- `sensor.nord_pool_lv_last_updated` = **2026-08-15 11:07 UTC — 27 hours ago.** The integration
  has not refreshed its dataset for over a day.
- `sensor.nord_pool_lv_current_price` carries **only** `state_class`, `unit_of_measurement`,
  `friendly_name` — there is **no `tomorrow` attribute**. The project note that
  `state_attr('sensor.nord_pool_lv_current_price','tomorrow')` yields tomorrow's prices is
  **wrong for the current integration version**; any UI or automation relying on it gets `None`.
- `current` / `next` / `previous` price still tick (0.1 h fresh) because they are derived from the
  already-loaded day. **Today's prices are trustworthy; tomorrow's do not exist.**
- Related live template bug: **21× `'pf_raw' is undefined`** — the new `price_forecast` template
  is broken.

## 7. Reliability risks

| Rank | Risk | Evidence in the retained window | Impact |
|---|---|---|---|
| **1** | **Tuya cloud `sign invalid`** | **229 occurrences / 249 `network error` over 10 days**, on 9 of 10 days (peaks 22 on 08-15, 20 on 08-07). **100 automation runs aborted mid-script**: `polotentsesushitel` 41, `nochnaia_ekonomiia_primenit` 28, `teplyi_pol_dushevaia_1et` 12, `ev_zariadka_avtozariadka_2ch` 11, `boiler_kalorifer_po_tsene` 8 | **Severe.** Two distinct harms: (a) automations abort *part-way*, leaving the house in a half-applied state with no error surfaced to the owner; (b) states **freeze at their last value instead of going unavailable** — which is what destroyed 15 days of energy metering (§6.2). Any new UI must treat Tuya-sourced values as suspect-by-default and show an explicit "last confirmed at" stamp. |
| **2** | **Energy metering blackout 2026-08-01 → 2026-08-16** | §6.2 | 15 days of cost data lost; today's figures inflated |
| **3** | **Bedroom climate sensor dead 16 days** | last stats 2026-07-31 11:00 | Both UIs render a Спальня tile with no data behind it |
| 4 | **ecoNET boiler host** | 2 outages only: **08-10 16:35–16:39** and **08-11 ~03:00** (~392 template errors). Clean 08-11 → 08-16. | **Improved** — the `ecoNET300.local` hostname pin appears to have fixed the DHCP drift. Residual defect: the boiler `availability:` templates themselves throw when `value_json` is undefined, so an outage produces an error storm instead of a clean "unavailable". |
| 5 | **Xiaomi cloud (`xiaomi_home`) link flaps** | 7× `mips disconnect / try reconnect`, 08-06 → 08-16 | Correlates with the dead Lumi bedroom/motion/smoke entities |
| 6 | **New regressions introduced today (2026-08-16)** | 57× `'peer_busy' is undefined` in the fresh `tuya_selfheal` automation; 21× `'pf_raw' is undefined` in price_forecast | Two just-deployed features have undefined template variables |
| 7 | **Calendar entities missing** | 44× `calendar.semia / prazdniki_latvii / holidays / owner_mail are missing or not currently available` | The Calendar card on the tablet home screen has no data source |
| 8 | Weak-WiFi zone (boiler area) | boiler plug + ecoNET are the two devices in it; both had outages | Physical fix (reserve IP / signal) still outstanding |
| 9 | `xiaomi_home` wrong entity-ID domain | 90× warning | Breaks in HA **2027.5** — schedule, not urgent |
| 10 | Host/VM restart | host uptime **7 h 23 m** — whole VM rebooted 2026-08-16 ~06:43 | Not itself a fault, but it reset all `last_changed`, and it is what *fixed* the Tuya freeze |

**Not a risk:** disk (19.4 G free, 34 % used), database (262 MB, no errors), memory, recorder purge.

## 8. What I could NOT determine, and why

1. **Exact downtime of non-numeric dead entities** (media players, the 3 dimmer switches, the Lumi
   motion + smoke sensors, the "phone" orphan block). They have no long-term statistics because they
   are not numeric, and the `states` table only reaches back 10.5 days. All I can prove is
   **"≥ 10.5 days"**. Older daily backups (`/backup`, 3 retained: Aug 14/15/16) are all inside the
   same window, so they would not help either.
2. **Whether the 3 offline dimmer switches and the dead Lumi smoke detector are physically
   installed** or are leftovers of removed hardware. Distinguishing (a) from (d) here needs the
   owner's eyes, not the API.
3. **Whether today's `+15.99 kWh` (гидрофор) and `+16.97 kWh` (EV) are pure catch-up or contain
   some genuine consumption.** The frozen period destroyed the intermediate samples, so the split
   is unrecoverable. Only the totals are sound.
4. **Whether the Nord Pool "tomorrow" gap is a today-only miss or chronic** — `last_updated`
   proves 27 h of no refresh, but the retained window does not let me count how often this
   recurred before 08-06.
5. **Root cause of the Tuya `sign invalid`** — from HA's side it is only observable as a symptom.
   Determining whether it is clock skew, token rotation, or Tuya-side rate limiting would require
   changes/instrumentation, which is out of scope for a read-only audit.
6. **Real electricity cost.** No grid meter and no tariff data exist in HA, so the true bill
   cannot be computed at all — only the spot-price estimate over 6 plugs described in §6.3.
