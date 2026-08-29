# ecoNET `curr.alarmOutput` — confirmed semantics (R0 read-only investigation)

**Date:** 2026-07-17 · **Scope:** READ-ONLY. No boiler/plug commands, no writes, no reloads.
**Sources:** live ecoNET REST `GET /econet/regParams` (192.168.1.10), HA `/api/states` +
`/api/history` (6 days), `sudo cat /config/configuration.yaml`, prior audit docs.

## TL;DR
`curr.alarmOutput` is a **genuine physical alarm-output relay** on the ecoMAX controller
(confirmed by the companion field `alarmOutputWorks` = the relay's actual energized state),
**but on this installation it asserts routinely during normal, no-fault summer operation** —
specifically the daily `Догорание` (fire burn-out) idle cycle when DHW is already satisfied by
the electric TEN and there is no heat demand. It has also been observed ON while the boiler was
in `Работа` (running normally) and `Надзор`. **`alarmOutput=on` alone does NOT prove a fault.**
The real fault indicator is `mode == Авария` (mode 9), which did **not** occur once in 6 days
despite 5 separate multi-hour `alarmOutput=on` episodes.

## 1. Exact HA mapping
`/config/configuration.yaml` (~line 306), REST platform binary_sensor (NOT plum_ecomax):

```yaml
- name: "Boiler Alarm"
  unique_id: boiler_alarm
  value_template: "{% if value_json.curr is defined and value_json.curr.alarmOutput is defined %}{{ value_json.curr.alarmOutput }}{% endif %}"
  availability:   "{{ value_json.curr is defined and value_json.curr.alarmOutput is defined }}"
  device_class: problem
  icon: mdi:alarm-light
```

- Entity: `binary_sensor.boiler_alarm`, `device_class: problem`.
- Maps 1:1 to ecoNET `curr.alarmOutput` (JSON boolean). No `payload_on/off` override; HA maps
  `True`→`on`, `False`→`off` (verified live: `alarmOutput=True` ⇒ state `on`).
- Availability drops to `unavailable` whenever the field is missing — frequent because the
  ecoNET WiFi at 192.168.1.10 flaps (known hardware issue). Over 6 days: 112 `unavailable`
  vs 84 `off` vs 50 `on` state points — heavy flap noise.

## 2. Alarm/error/status fields present in the live payload
`GET /econet/regParams` → `curr` (68 fields). The **only** alarm/error/status-class fields:

| Field | Live value | Meaning |
|-------|-----------|---------|
| `alarmOutput` | `True` | Alarm-output relay commanded/asserted state (→ `binary_sensor.boiler_alarm`) |
| `alarmOutputWorks` | `True` | The alarm output relay's actual energized state (hardware confirm). NOT surfaced in HA. |
| `statusCO` | `0` | CO (space-heating) circuit status code — operational, not a fault code |
| `statusCWU` | `4` | CWU (DHW) circuit status code — operational, not a fault code |
| `mode` | `5` (`Догорание`) | Controller operating mode; `9` = `Авария` is the true fault mode |

**Not present:** there is no `alarmCode`, `alarmState`, `alarms[]`, `error`, `errorCode`,
`lockCode`, `warningOutput`, or fault-list array in the payload. Dedicated alarm-list endpoints
were probed GET-only and do **not** exist on this controller
(`/econet/rmAlarms`, `/getAlarms`, `/rmCurrentAlarms`, `/alarms` all return
`'Controller' object has no attribute ...`). `docs/boiler_api.md` documents only `regParams`
read + `rmCurrNewParam` writes; it says nothing about `alarmOutput`.
There is **no plum_ecomax boiler entity** — only `update.plum_ecomax_..._integration_update`
(the HACS integration's own update entity); all boiler telemetry is the REST sensors above.

## 3. Is alarmOutput a fault flag, a benign relay, or multi-purpose? → (b)/(c), EVIDENCE-BASED

Live snapshot at investigation time (the exact "low-CWU-setpoint Догорание" scenario):
`mode=Догорание`, `boilerPower=0`, `feeder=False`, `fan=False`, `fanPower=0`
(no combustion), `tempCWU=56.3` **above** `tempCWUSet=40` (DHW hot, held low by the boiler-plug
automation; electric TEN covers DHW), `tempCO=35.7` vs `tempCOSet=67` — **and `alarmOutput=True`.**
This is an idle, no-demand burn-out, not a fault.

6-day mode↔alarm cross-tabulation (`binary_sensor.boiler_alarm` vs `sensor.boiler_mode`):

```
alarm=on  modes : Догорание, Надзор, Работа, Режим 12
alarm=off modes : Выключен, Догорание, Нагрев ЦО, Надзор, Ожидание, Работа, Режим 12
mode=Работа  alarm=on x5   <-- ALARM ON WHILE RUNNING NORMALLY
mode=Надзор  alarm=on x5
mode=Догорание alarm=on x40 / off x100
```

`alarmOutput=on` occurs across **normal running modes** (`Работа`, `Надзор`), which a genuine
"boiler is faulted / fire is out" flag would never do. So it is not a clean fault flag → it is a
physical relay that is **ON during normal operation** (option b), behaving as a generic /
multi-purpose configurable H-output (option c) on this unit.

Decisive: a clean **daily cycle** — `alarmOutput` turns ON in the early morning during
`Догорание` and clears in the afternoon at the transition to `Надзор`, every day:

```
07-13 15:14 on(Догорание) -> 17:28 off(Надзор)
07-14 04:59 on(Догорание) -> 16:15 off(Надзор)   (~11 h)
07-15 06:43 on(Догорание) -> 14:32 off(Надзор)   (~7.8 h)
07-16 08:37 on(Догорание) -> 15:59 off(Надзор)   (~7.4 h)  <-- the "incident"
07-17 06:22 on(Догорание) -> still on
```

**`mode=Авария` (real fault, mode 9) never appeared once in the 6-day window.** All five
alarm-on episodes were benign burn-out cycles.

### Correction to prior audit conclusion
`BACKLOG_DIAGNOSTICS_2026-07-16.md` (Item 2) called the 07-16 `alarmOutput=on` a
"genuine controller alarm — house had no heat for ~7 h." The multi-day evidence shows the 07-16
episode was **one instance of a normal daily burn-out cycle** (identical on/off pattern on 07-13,
14, 15, 17), not an anomalous fault — in July, Riga, with electric-TEN DHW and CWU setpoint held
at 40, the boiler sitting in `Догорание` all morning is expected idle behavior.

## 4. Better real-fault signals (since alarmOutput alone is insufficient)
No dedicated fault code exists in the payload; use these instead / in combination:
1. **`sensor.boiler_mode == 'Авария'`** (mode 9) — the controller's true fault mode. Primary.
2. **Sustained `tempCO` collapse below `tempCOSet`** while `feeder`/`fan` are active and it is
   heating season (space-heat demand) — indicates a failing/failed burn. Requires context; not
   a single flag.
3. `statusCO` / `statusCWU` codes (not currently surfaced in HA) could be decoded for a
   finer-grained circuit status, but their code tables are not documented on this unit.
4. If `alarmOutput` is used at all, it must be **gated** (e.g. AND `mode in Авария/Выключен`,
   or require heating-season + CO demand) — never treated as a standalone alarm.

## 5. Direct answers
- **alarmOutput semantics:** a real, hardware-backed alarm-output relay (`alarmOutputWorks`
  confirms energization), configured/behaving on this unit to assert during the daily
  no-demand `Догорание` burn-out and even during normal `Работа`/`Надзор`.
- **Does `alarmOutput=on` alone prove an alarm?** **No.** It fires routinely with no fault
  (0 `Авария` events across 5 alarm-on episodes / 6 days).
- **Is `alarmOutput=on` during low-CWU-setpoint `Догорание` normal?** **Yes — normal, expected
  summer idle behavior**, not a fault. This is exactly the current live state.
- **HA mapping:** `binary_sensor.boiler_alarm` (device_class problem) ← REST `curr.alarmOutput`
  (True→on), availability gated on the field being present.
- **Implication for `boiler_alarm_watchdog.patch`:** as written (alert on `boiler_alarm`
  on for >5 min, 24/7) it would fire **every morning** on the benign burn-out cycle. It should
  key off `mode == Авария` (and/or gated conditions above), not raw `alarmOutput`.
```
