# Water-Safety Chain Audit & Test Plan

**Scope:** Read-only end-to-end audit of the leak-protection chain on HA (192.168.1.45:8123).
**Date:** 2026-07-15 (audit run ~15:1x UTC, shortly after a HA restart).
**Method:** Live YAML (`/config/automations.yaml`, `/config/configuration.yaml` via sudo cat), REST `/api/states`, `/api/history`, `/api/logbook`, and the persisted automation trace store `/config/.storage/trace.saved_traces`. **No device commands were issued; the physical valve was never touched; no leak was provoked.**

> No secrets appear in this document (tokens, passwords, SSH creds, and the raw Telegram chat-id are deliberately omitted / masked).

---

## 1. Chain diagram — real entities + current state

```
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ MOISTURE SENSORS (device_class: moisture, Tuya cloud)                       │
 │   binary_sensor.vannaia_moisture         = off   (Ванная)                   │
 │   binary_sensor.garazh_moisture          = off   (Гараж)                    │
 │   binary_sensor.kukhnia_moisture         = off   (Кухня)                    │
 │   binary_sensor.water_sensor_4_moisture  = off   (Душевая 1эт)              │
 │   (all last_changed 15:11:59Z = restored on restart)                        │
 └───────────────┬──────────────────────────────────────────────────────────┘
                 │ state -> 'on' for 3 min   (trigger id: leak_check)
                 ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ GATE 1  input_boolean.ha_startup_grace  = **on**  ← STUCK ON (see F1)       │
 │         condition: leak_check requires grace == 'off'  → CURRENTLY FALSE    │
 ├──────────────────────────────────────────────────────────────────────────┤
 │ GATE 2  input_boolean.tuya_reconnect_grace = off                           │
 │         set 'on' 5 min by autom. 1748000001004 when any sensor→unavailable │
 │         condition: leak_check requires grace == 'off'                       │
 ├──────────────────────────────────────────────────────────────────────────┤
 │ GATE 3  input_boolean.moisture_bypass_<room> = off (per-sensor manual mute)│
 │ GATE 4  from_state not in ['unavailable','unknown']                        │
 └───────────────┬──────────────────────────────────────────────────────────┘
                 │ (all gates pass)
                 ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ LEAK AUTOMATION v4   id 1748000001001                                       │
 │   entity_id = automation.ha_startup_grace_period  ← LEGACY SLUG (see F3)    │
 │   state = on (enabled) | mode: parallel max 10 | last_triggered 06:42:25Z   │
 │   1) notify (⚠️ ДАТЧИК ВЛАГИ) + inline buttons [ЗАКРЫТЬ КРАН /leak_confirm] │
 │      [Ложная тревога /moisture_false_alarm]                                 │
 │   2) delay 5 min                                                            │
 │   3) recheck: sensor still on? & tuya_reconnect_grace off? & bypass off?    │
 │        └─ if yes → SHUTOFF branch                                           │
 └───────────────┬──────────────────────────────────────────────────────────┘
                 │ SHUTOFF branch (auto, after 5 min) OR /leak_confirm (manual, instant)
                 ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ ACTIONS                                                                     │
 │   switch.turn_off  switch.zigbee_plug_2_socket_1   (гидрофор / hydrophore)  │
 │   switch.turn_off  switch.voda_kran_switch_1       (water valve)            │
 │       ⇒ valve CLOSED == switch OFF.  Current state = **on == OPEN (normal)**│
 │   siren.alarm on (high, 120s) + notify "🚨 УТЕЧКА — КРАН ЗАКРЫТ"           │
 │   ✗ NO read-back / confirmation that the valve actually closed (see F2)     │
 └────────────────────────────────────────────────────────────────────────────┘

 CLEARED path: sensor -> 'off' for 15s (id: leak_cleared) → notify only.
               Valve is NEVER re-opened automatically (open = manual only). ✅ safe.
```

Supporting automations:
- `1748000001004` "🚨 Tuya: Grace период" — sensor→unavailable ⇒ tuya_reconnect_grace on 5 min. **state: on.**
- `1748000001005` "☁️ Tuya: авто-перезагрузка" — sensor→unavailable OR off→on ⇒ delay 30s ⇒ reload Tuya entry. **Now single-entry (`01HAENTRYIDPLACEHOLDER0000`); the dead `gg-` entry reload was removed in Series A — confirmed clean.**
- `1775638334800` leak **v2** — `initial_state: false`, entity `automation.utechka_vody_avariinoe_otkliuchenie` = **off** (correctly disabled/hardened).

---

## 2. Findings

| # | Severity | Finding |
|---|----------|---------|
| **F1** | **CRITICAL** | **`input_boolean.ha_startup_grace` is stuck ON, so automatic leak shutoff is currently DISABLED.** History shows a single state point `on` spanning ≥2026-07-11 → now with no transitions. No `initial:` is set (input_boolean restores its last state = on), and **no automation or script anywhere turns it off** (`grep` of automations.yaml/scripts.yaml/scenes.yaml: the entity is only *read*, never a `turn_on`/`turn_off` target). Because leak-v4's `leak_check` requires `is_state('input_boolean.ha_startup_grace','off')`, that condition is permanently FALSE. A real leak would: fire `leak_check` after 3 min → fail the grace condition → send **no** notification, close **nothing**, sound **no** siren. Manual rescue via the Telegram `/leak_confirm` button is also unavailable because the button only ships inside the (suppressed) leak_check notification. |
| **F2** | **HIGH** | **No valve-state confirmation after closing.** Both the auto SHUTOFF branch and the `/leak_confirm` handler call `switch.turn_off` on `switch.voda_kran_switch_1` and then immediately notify "🚨 УТЕЧКА — КРАН ЗАКРЫТ" with no `wait_template`/read-back/retry. The valve is a Tuya cloud switch that flaps (it went `unavailable` 14:37→14:38 today). If the close command lands while the valve is unavailable/offline, it silently no-ops yet the message falsely asserts the valve is closed — dangerous false assurance during a real leak. |
| **F3** | **HIGH (root cause of F1)** | **Automation-id collision destroyed the startup-grace manager.** Leak-v4 lives in YAML under `id: '1748000001001'` — the *same* id CLAUDE.md documents for the "🛡️ HA Startup Grace Period" automation. Leak-v4 overwrote it, but the entity registry kept the legacy slug, so leak-v4's entity is `automation.ha_startup_grace_period` (friendly name "…v4", state on). The automation that used to do `homeassistant.start → grace on → delay 15m → grace off` **no longer exists**, which is exactly why F1's flag is stuck on. |
| **F4** | **MEDIUM** | **Collateral: the "🚨 Устройство недоступно" alert (`1778900002001`) is also gated on `ha_startup_grace == 'off'`** and is therefore also permanently suppressed while F1 persists — including 5-min-unavailable alerts for the four moisture sensors and the boiler plug. |
| **F5** | **MEDIUM** | **Grace-window design gap (independent of F1).** Even with a correctly-cycling 15-min grace: if a real leak begins at restart and the sensor stays continuously `on`, the `for: 00:03:00` fires `leak_check` once (~T+3m) while grace is still on → condition fails → **no re-arm** until the sensor toggles off→on. A persistent leak during the grace window is silently ignored. |
| **F6** | **MEDIUM** | **5-minute recheck omits the startup-grace flag & valve health.** The post-delay branch re-checks only `tuya_reconnect_grace`/`bypass`, not `ha_startup_grace`, and never checks whether `switch.voda_kran_switch_1` is available before firing the shutoff + "кран закрыт" message. |
| **F7** | **LOW** | **`leak_cleared` trigger covers only 3 of 4 sensors** (v4 lines 15–22 list vannaia/garazh/kukhnia; `water_sensor_4_moisture` is missing). A cleared shower-floor sensor sends no courtesy "cleared" notice. Safety-neutral (valve is never auto-opened), but inconsistent. |
| **F8** | **LOW** | **Misleading "cleared" message on Tuya reconnect.** When a sensor recovers `unavailable→off`, `leak_cleared` fires (`>180s` condition passes) and sends "Датчик больше не фиксирует утечку … Гидрофор и кран остаются выключены. Открой кран вручную." — even though no leak occurred and the valve is open. This is exactly the 06:42 event (see §3). |

### Confirmed-GOOD (no action)
- Valve is **never auto-opened** — `leak_cleared` only notifies; opening is manual only. No automation path can re-open the valve into an unresolved leak.
- **Multi-sensor handling is safe:** `mode: parallel, max: 10`; each sensor runs independently; a `leak_cleared` on sensor A while sensor B still leaks does not re-open the valve. No race that reopens water.
- Repeated-trigger spam is bounded by `for: 3min` + parallel runs.
- Leak **v2** is correctly disabled and hardened (`initial_state: false`).
- Tuya auto-reload (`1748000001005`) is clean (single live entry; dead `gg-` entry reference removed in Series A — verified).

---

## 3. Was the 06:42 event real? — NO, it was a benign Tuya reconnect

Reconstructed from history + logbook + trace store:

- `binary_sensor.kukhnia_moisture` was `unavailable` (Tuya cloud drop) from 2026-07-14 18:00 and recovered **directly to `off` at 06:42:10Z** (never `on`).
- Leak-v4 (`automation.ha_startup_grace_period`) shows `last_triggered = 2026-07-15T06:42:25Z` — i.e. the **`leak_cleared`** trigger (off for 15s = 06:42:10+15s), *not* `leak_check`. Its `>180s` elapsed condition passed (unavailable since the prior day), so it ran the cleared/notify branch.
- **No valve action occurred:** `switch.voda_kran_switch_1` history is `on` all day (only a 14:37→14:38 `unavailable` blip from an unrelated restart). No `leak_check` run, no siren, no shutoff.

**Verdict: false/benign.** It was a Tuya-reconnect recovery that fired the courtesy "cleared" branch (finding F8), not a real leak and not an emergency shutoff. There were no persisted `leak_check` traces for either leak automation on 2026-07-15.

---

## 4. Is emergency shutoff currently reliable? — NO

**Automatic emergency shutoff is currently non-functional (F1/F3).** With `ha_startup_grace` stuck on, a genuine leak produces no alert, no siren, and no valve closure, and the rescue button never reaches the phone. The only working path today is **fully manual**: the owner independently notices water and toggles `switch.voda_kran_switch_1` off from the Mini App / tablet / Dev Tools. Even once F1 is fixed, F2 (no valve-close confirmation) and F5 (grace-window blind spot) leave residual risk.

**Interim mitigation (owner decision, not performed here):** set `input_boolean.ha_startup_grace` to `off` now to immediately re-enable the chain, then fix root cause F3 (give leak-v4 its own id and recreate a real start→on→15m→off grace automation, or add `initial: off` + a proper manager).

---

## 5. SAFE canary test plan

> ⚠️ **REQUIRES SEPARATE OWNER APPROVAL TO EXECUTE. DO NOT RUN NOW.**
> Every step below is designed so the **physical valve `switch.voda_kran_switch_1` is never commanded** and **no real leak is provoked.** Do not set a real moisture sensor `on` against the *live* automation unless the valve/hydrophore/siren targets have first been redirected to dummies (Phase B), because after 5 min the live automation would close the real valve.

### Phase A — Zero-touch verification (read-only; safe to run anytime)
1. **Template dry-run (Developer Tools → Template):** paste leak-v4's gate conditions with a simulated `leak_check` trigger and confirm the outcome. With `ha_startup_grace = on` the grace condition returns `false` — this *proves F1* without side effects.
2. **State/attribute reads only:** confirm `automation.ha_startup_grace_period` (=leak-v4) is `on`, `input_boolean.ha_startup_grace` value, and the 4 sensor states — all via `/api/states` (already captured in this audit).
3. **Observe a natural Tuya reconnect** (sensor → `unavailable` → `off`) in the logbook to watch the F8 "cleared" message appear — purely observational.

### Phase B — Full end-to-end canary with a MOCK sensor and DUMMY valve (config changes → approval required)
Goal: exercise notify → 5-min delay → shutoff-branch decision → dummy toggle, **without ever touching the real valve.**
1. Create scratch helpers: `input_boolean.valve_test`, `input_boolean.hydro_test`, `input_boolean.mock_moisture` (mock as a stand-in trigger source).
2. Clone leak-v4 into a **test copy** with a *new unique id*, and in the copy set `valve_entity: input_boolean.valve_test`, `hydrofor_entity: input_boolean.hydro_test`, replace `siren.turn_on` with a notify-only step, and add `input_boolean.mock_moisture` as the trigger. **Do not modify the production automation.**
3. Temporarily set `ha_startup_grace = off` and `tuya_reconnect_grace = off` so the test copy can proceed.
4. Toggle `input_boolean.mock_moisture` on; after 3 min confirm the ⚠️ notification + buttons arrive; either tap `/moisture_false_alarm` (verify no dummy toggle) or wait the 5 min and confirm **`input_boolean.valve_test` flips off** (proving the shutoff logic) while the real `switch.voda_kran_switch_1` stays untouched.
5. **Teardown:** delete the test-copy automation and the three scratch helpers; restore `ha_startup_grace` to the value the owner wants (ideally the F3 fix). Re-verify production state.

### Phase C — Valve-close-confirmation regression (after F2 fix; approval required)
Once a valve read-back is added, verify against the dummy valve that, when the (dummy) valve reports `unavailable`, the automation raises a "close FAILED" notification instead of "КРАН ЗАКРЫТ". Never test this against the real valve.

---

## 6. Verification
- Output scrubbed: no tokens, passwords, SSH keys, or raw chat-id in this file.
- `git diff --check`: clean (only new untracked file `docs/audit/WATER_SAFETY_TEST_PLAN.md`).

---

## 7. Executable canary package (fully isolated) — `docs/audit/water_canary/`

Phase B above is now realised as a **self-contained, mock-only canary** that
mirrors leak-v4's logic (including the FIX C valve read-back) on `test_*` /
`dummy_*` helpers. It touches **no production valve, moisture sensor, siren, or
security entity** — an isolation checker enforces this before any run.

**Files:**
| File | Role |
|------|------|
| `water_canary/canary.yaml` | Mock helpers (6 `input_boolean.*`) + automation `test_water_canary_0001` (leak_check + leak_cleared, mirror logic, compressed timings). |
| `water_canary/run_plan.md` | Install → drive (9 scenarios) → observe traces → **teardown**. Toggles only `test_*`/`dummy_*` helpers. |
| `water_canary/verify_isolation.py` | Greps the package; **exits non-zero** on any production reference (valve, real moisture, `siren.*`, `security_armed`, Telegram, real device service calls). Must pass BEFORE install. |
| `water_canary/README.md` | Overview + real→mock entity map. |

**Mock entity list:** `input_boolean.test_moisture_1`, `test_moisture_2`,
`dummy_valve` (on=OPEN/off=CLOSED), `dummy_hydro`, `test_grace` (grace gate),
`test_valve_fail` (knob that forces the not-confirmed/CRITICAL path).
Notifications = `persistent_notification.create`, banner `🧪 ТЕСТ — реальной
протечки нет`. Only callback string used is `/noop_test`.

**Chain proven (compressed):** `test_moisture on → for 10s → gates pass →
warn TEST notify → delay 10s → dummy_hydro off → dummy_valve off → wait valve==off
(timeout 5s) → settle 3s → re-check → CONFIRMED TEST notify`.

**Negative cases modeled:** grace-on-before-trigger = blocked (no action);
grace-on-mid-delay = false-alarm (valve untouched); self-cleared = valve
untouched; `test_valve_fail` = valve stays on → read-back timeout → CRITICAL «не
подтверждено»; the timeout path itself; repeated triggers bounded by `for:` +
`mode: parallel` (no loop); multiple mock sensors run as independent parallel
runs (no notification storm); leak_cleared never auto-reopens the dummy valve.

**Run order:** (1) `python docs/audit/water_canary/verify_isolation.py` must print
`ISOLATION CHECK: PASS`; (2) independent review; (3) follow `run_plan.md`.

**Teardown (mandatory when done):** delete automation `test_water_canary_0001`
from `automations.yaml` + reload; remove the 6 helpers from `configuration.yaml`
+ reload; dismiss `test_canary_*` persistent notifications; re-verify no `test_*`
/`dummy_*` entities remain and production leak-v4 is unchanged. Teardown touches
only canary artifacts.

> **Not deployed.** The package is local-only; nothing has been installed or run.
