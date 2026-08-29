# Automation & Operational Health Report — 2026-07-16

Read-only production health audit (REST + WebSocket + SSH, no devices touched, nothing
deployed). Window: since last HA Core restart **2026-07-15 15:11** (~48h uptime),
system_log covers this whole window.

- HA Core **2026.7.1**, state **RUNNING**, 587 entities, **50 automations** (47 ON, 3 intentionally OFF).
- Counts: **Critical 0 · High 1 · Medium 2 · Low 6**

---

## 🔴 HIGH (surface immediately)

### H1 — Alarm siren offline: smoke & intrusion sirens will NOT sound
`siren.alarm`, `select.alarm_volume`, `number.alarm_time` are all **`unavailable`
since 2026-07-16 09:55** (~6h). These are the exact actuators the life-safety
automations drive:

- **🔥 Задымление — сирена** (`1779200002001`): `select.select_option` →
  `number.set_value` → `siren.turn_on` on `siren.alarm`.
- **🛡 Охрана — тревога** (`1779200003001`): same three actuators.

Impact right now: if smoke or an armed-intrusion event fires, all three service
calls hit an unavailable device → **no audible siren**. Detection and Telegram
alerting are unaffected — the smoke/door/motion sensors report fine
(`binary_sensor.wifi_th_smoke_sensor_smoke`, `door_sensor_door`,
`motion_sensor_motion` all `off`/healthy), and both automations still send their
`telegram_bot.send_message` alert. Only the physical siren is dead.

Likely a physical/Zigbee-Tuya dropout of the alarm siren device (went unavailable
at a single instant, all three entities together). **Owner action:** power-cycle /
re-pair the alarm siren; consider a watchdog alert on `siren.alarm == unavailable`
(none exists today). Note the leak-v4 response path is unaffected — its actuators
(`switch.voda_kran_switch_1` valve = on/available, hydrophore plug = available).

---

## 🟠 MEDIUM

### M1 — Invalid-auth request flood (~4,278 in ~24h) from ≥4 LAN clients
`homeassistant.components.http.ban`: **count 4278**, mostly `Requested URL:
'/api/states'`, from `192.168.1.44` (Windows Chrome), `192.168.1.36` (Android),
`192.168.1.43`, `192.168.1.60`. Spans the full window (~178/h). These are LAN
clients (tablet / dashboards / mini-app) polling with **stale/expired or empty
bearer tokens** — matches the known "stale localStorage token" class of issue, but
across multiple devices and not self-healing over 24h.

- Also produces the related `InsecureKeyLengthWarning: HMAC key is 0 bytes`
  (`auth/jwt_wrapper.py`) — a client presenting an empty token.
- **No functional lockout:** `http:` has no `login_attempts_threshold` (default
  `-1` = auto-ban disabled) and there is no `/config/ip_bans.yaml`. So this is log
  flooding + broken clients, not an outage.
- Risk: floods the security log and masks any genuine intrusion attempt; the
  affected UIs are probably showing stale/no data on those devices.
- **Owner action:** re-bootstrap the token on each offending client (tablet
  `?token=`, mini-app re-auth); identify the Windows Chrome `.44` dashboard tab.

### M2 — `binary_sensor.boiler_alarm` = ON for ~4.5h, no notification path
`binary_sensor.boiler_alarm` (device_class `problem`, reflects ecoNET
`curr.alarmOutput`) has been **on since 2026-07-16 14:11**. **Zero automations
reference it** — nothing alerts on it. Boiler `mode` reads `Работа` (running
normally) and the boiler-notify automation (`1779000001002`) only watches
`Выключен`/`Авария`, so this alarm output is invisible to the owner. Most likely a
benign alarm-output relay signal rather than a fault, but it is **unverified**.
Owner should confirm what `alarmOutput` means on this unit and, if it can indicate
a real fault, wire a Telegram alert to it.

---

## 🟢 LOW / backlog

- **L1** — `♨️ Рециркуляция ГВС` (`1789000001001`) logged `Already running` ×4 at
  03:55. `mode: single` + `time_pattern:/10` + presence + night_saver triggers can
  overlap for an instant. Actions are idempotent and instant → benign noise.
  Consider `mode: queued` or a small debounce.
- **L2** — `miniapp_auth` does a blocking `open('/config/www/today_prices.json')`
  inside the event loop (`custom_components/miniapp_auth/__init__.py:235`). 1
  occurrence. Wrap in an executor.
- **L3** — `switch.podsvetka_ostrov` is `unavailable` again. Per project notes it
  was removed 2026-07-12 via `entity_registry/remove`; SmartThings has recreated
  it. Cosmetic — island is controlled by other live entities.
- **L4** — `xiaomi_home` deprecation warnings (wrong-domain entity IDs count 95;
  `battery_level`/`location_name` overrides) — breaks in HA 2027.5/2027.7. Upstream
  custom-integration issue.
- **L5** — `ipp.coordinator` timeout (count 19, printer offline) and `xiaomi`
  `mips disconnect` (count 3) — transient / known-offline noise.
- **L6** — ~133 entities `unavailable`/`unknown`: offline TVs (LG/MiTV/Xbox/SOLAS),
  air-purifier debug params, unused legacy `scene.*`, orphaned Zigbee (door magnet,
  occupancy sensor). Long-standing; no automation depends on them except the H1
  alarm cluster (tracked above).

---

## ✅ Healthy / verified

- **Clean reload after recent fixes:** all 50 automations loaded, none in an
  error/unavailable state; HA RUNNING ~48h. 3 OFF are intentional (EV-old
  `1774376407472`, boiler-sync `1775106692658`, **leak-v2 `1775638334800` with
  `initial_state: false` confirmed** and state = off).
- **Startup grace lifecycle** — manager `1789200001001` (start→grace ON→15min→OFF,
  `mode: restart`) present+ON; **>20min stuck-grace diagnostic** `1789200001002`
  present+ON. `input_boolean.ha_startup_grace` currently **off** (not stuck).
- **Leak-v4** (`1748000001001`, entity `automation.ha_startup_grace_period`) ON;
  conditions sane — from/to-state guards, `ha_startup_grace`, `tuya_reconnect_grace`,
  and per-sensor `moisture_bypass_*` all checked; 3-min confirm on, 15s clear.
  No trigger since restart (no leak/moisture events).
- **Telegram safety** — all life-safety alerts use `telegram_bot.send_message`
  (smoke `1779200002001`, security `1779200003001`, leak-v4, device-unavailable
  `1778900002001`). `/noop_test` (`1778700001006`) present, always clears the
  callback spinner and calls **no** device services; handler `1778700001005` intact
  (leak_confirm / security / siren callbacks present).
- **Boiler REST templates** — all 20 `curr` value_templates carry per-field
  `is defined` guards + 21 `availability:` lines → **no `''`/ValueError spam**.
  Sensors live (mode `Работа`, CWU 47.5°C, CO 34.4°C).
- **EV** — planner `1778800001001`, autocharge `1778800001002`, interlock
  `1779000001001` armed; **0 errored traces**. `sensor.ev_charger_energy`=897.99
  (command_line OK), status `charger_insert`, no `cloud_error`.
- **Shadow collector** `1789100001001` — firing every 15min, 0 errors,
  `/config/shadow_snapshots.jsonl` growing (96 snapshots, latest 18:30 local).
  (Series-B note: keep prod cost accounting unchanged until a clean 24h/midnight
  window is confirmed.)
- **Frequency / churn** — no runaway automations. Nord Pool heating autos fire
  ~hourly on price change; shadow /15min; recirc /10min. Energy-reset guard
  `1786000001001` and boiler-notify `1779000001002`: 0 errors.
- **Guard consistency** — `rezhim_zhara`=ON, `night_saver`=OFF, `ev_manual_mode`=OFF;
  towel (`1783000001001`) and floor-heating autos guard on **both** night_saver and
  rezhim_zhara; boiler Nord Pool intentionally excluded from zhara (GVS by design);
  night-saver apply excludes boiler+EV. No conflicting simultaneous actions found.
- **No Telegram notification flood.** **No Tuya reconnect churn** (grace autos
  `1748000001004/5` last fired ~61h ago).

## Regressed vs. previous audit
- **NEW:** siren cluster offline (H1); auth flood (M1); boiler alarm output ON (M2);
  `switch.podsvetka_ostrov` reappeared (L3).
- **Held:** leak-v2 hardening, grace lifecycle+diagnostic, boiler guards,
  /noop_test, shadow cadence, telegram-bot safety — all intact.
