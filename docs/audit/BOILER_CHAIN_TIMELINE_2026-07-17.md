# Boiler / Electric-Boiler Chain — Timeline & Verdict for 2026-07-17

**Scope:** R0 read-only reconstruction. No device commanded, nothing reloaded.
**Sources:** HA history/logbook (REST `/api/history`), `scratch_automations.yaml`,
`docs/boiler_api.md`, `docs/audit/boiler_alarm_watchdog.patch`.
**Timezone:** all times Europe/Riga (UTC+3). Data window observed: `2026-07-17 00:00` → `~14:21` (current time).

---

## 1. The full normal-summer chain (confirmed link-by-link from YAML)

```
Nord Pool price drops ≤ 0.10 EUR/kWh
        │  sensor.nord_pool_lv_current_price
        ▼
[Automation 1766138420302] "🔥 Бойлер по Nord Pool (threshold 0.10)"
   cond: price ≤ 0.10 AND plug off AND ev_charger off AND ev_status != charger_charging
        │  action: switch.turn_on
        ▼
switch.smart_plug_2_socket_1  →  ON   (electric boiler / ТЭН powered)
        │  state on
        ▼
[Automation 1778900001001] "Котёл — откл. ГВС при работе бойлера"
   trigger id=plug_on ; guard: boiler_mode not in [Выключен/unavail]; time 07:00–22:00;
   guard: input_boolean.turbo_hot_water == off
        │  action: rest_command.disable_boiler_cwu
        ▼
Boiler CWU (ГВС) setpoint  →  40 °C          (docs/boiler_api.md)
        │
        ▼
Pellet boiler stops actively heating DHW → burns out its fuel
   → sensor.boiler_mode = "Догорание", sensor.boiler_power = 0
   → (fuel exhausted) binary_sensor.boiler_alarm = on  (ecoNET curr.alarmOutput = "погас огонь")
        │
        │   DHW is now heated ELECTRICALLY by the ТЭН → sensor.boiler_cwu_temperature rises
        ▼
When electric boiler turns OFF (price > 0.10, or EV starts charging):
[Automation 1778900001001] trigger id=plug_off → rest_command.enable_boiler_cwu
Boiler CWU setpoint  →  55 °C   (pellet boiler resumes DHW responsibility)
```

**Confirmed rest_commands** (`docs/boiler_api.md`):
`disable_boiler_cwu` → 40 °C · `enable_boiler_cwu` → 55 °C · `turbo_boiler_cwu` → 65 °C (turbo mode).

**Interacting automations checked:**
- **EV/Boiler interlock `1779000001001`** — turns the electric boiler OFF when the EV starts
  charging, and back ON when EV stops and price < 0.10. On 07-17 the EV never charged
  (`switch.ev_charger_switch` = off all day; status only `charger_insert`/`charger_free`),
  so it never interfered with the boiler plug.
- **Turbo `1748000001002/003`** — `input_boolean.turbo_hot_water` stayed `off` all day, so the
  65 °C path and the turbo restore path were never invoked; the plain interlock was in charge.
- **Boiler-mode notifications `1779000001002`** — only reports 40↔55 setpoint moves that are NOT
  both within {40,55}, and mode changes only involving Выключен/Авария; a routine 40→55 flip is
  intentionally silent.

---

## 2. Chronological timeline — 2026-07-17 (Europe/Riga)

Boiler REST sensors flap to `unavailable` roughly every ~10–60 min and recover within ~30 s
(known ecoNET WiFi drop, `192.168.1.10`). Those flaps are omitted below as noise; they do not
change any state on recovery.

| Time | Event | State snapshot | Class |
|------|-------|----------------|-------|
| 00:00 | Day start | price 0.174; plug **off**; CWU setpoint **40**; mode **Догорание**; alarm **off**; power 0. DHW 47.3 °C, CO 54.2 °C | Normal summer rest (setpoint 40 carried over from 07-16 22:07) |
| 00:00–08:00 | Expensive night | price 0.14–0.19; plug stays off; DHW slowly drifts down 47→~39 °C (standby loss); CO cools 54→41 °C | Normal (no electric heat: price > 0.10) |
| 08:15 | Price collapses | `nord_pool_current_price` 0.165 → **0.081** (≤0.10) | Trigger point |
| **08:15:30** | **Electric boiler ON** | `switch.smart_plug_2_socket_1` off→**on** (autom. 1766138420302) | Normal — cheap-price heating |
| ~08:16 | Interlock fires | `disable_boiler_cwu` → setpoint 40 (already 40, no visible move). DHW bottoms at **38.7 °C** and begins rising | Normal |
| 08:30 | Price floor | 0.015; stays ~0.012–0.015 through 14:00 | Normal |
| 08:16→ | Electric DHW heating | `sensor.boiler_cwu_temperature` climbs steadily: 38.7 → 47 (09:13) → 50 (09:38) → 55 (10:23) → **56.7 peak (12:24)** | Normal — ТЭН working |
| **09:22:21** | **boiler_alarm → ON** | `binary_sensor.boiler_alarm` off→**on** (ecoNET alarmOutput). Pellet flame out / fuel burned through. Remains ON through end of window | **Benign in summer** (see §4) |
| 09:22–14:21 | Alarm active, steady | plug **on**; CWU setpoint **40**; mode **Догорание**; power **0**; DHW held/heated 47→56 °C; CO keeps cooling 40→35.7 °C (no space-heat demand) | Normal summer rest + flame-out |
| 12:46 / 13:41 | EV status blips | `charger_insert`→`charger_free`→`charger_insert`; EV switch stays off — no charging, no interlock action | Normal |
| ~14:21 | End of observed data (now) | plug still on, setpoint 40, mode Догорание, alarm on, DHW ~56 °C | Episode ongoing |

**Normal-vs-anomalous marking:** every observed state on 07-17 is the *expected* summer-rest
configuration. The only entry that "looks" like a fault — `boiler_alarm = on` — is the pellet
boiler's flame-out signal, which is benign here because DHW is covered electrically (§4).

---

## 3. CWU setpoint restoration (40 → 55) — verification

**On 07-17 the 40→55 restoration was never triggered — correctly, not a bug.** The electric
boiler turned on at 08:15:30 and stayed on for the entire observable day (prices ≤0.015), so the
interlock's `plug_off` branch (`enable_boiler_cwu` → 55) had no OFF event to act on. The setpoint
is *legitimately held at 40* by design while the electric boiler is on — it is **not stuck**.

**Why the day already opened at 40** (plug was off 00:00–08:15 yet setpoint = 40): on 07-16 the
boiler fired (mode Работа/Нагрев ЦО ~18:39–20:01) and the setpoint settled to 40 at 22:07 — after
the interlock's 22:00 time cutoff — so no restore-to-55 ran overnight. It carried into 07-17.

**The restoration mechanism is proven working on the prior day (07-16):** setpoint cleanly tracked
the plug on every transition inside the 07:00–22:00 window —

| 07-16 time | plug | CWU setpoint |
|-----------|------|--------------|
| 17:30:30 → off | off | **55** at 17:30:35 (`enable_boiler_cwu`) |
| 18:00:42 → on | on | **40** at 18:01:10 (`disable_boiler_cwu`) |
| 18:15:30 → off | off | **55** at 18:15:40 (`enable_boiler_cwu`) |

So `enable_boiler_cwu` (→55) is functional; it simply had no OFF-event to fire on 07-17.
No restart/unavailable in the window left the setpoint in a wrong state — every `unavailable`
flap recovered to the same 40 within ~30 s.

---

## 4. Verdict on the 2026-07-17 alarmOutput episode

**NORMAL — no real heating fault.**

During the `binary_sensor.boiler_alarm = on` episode (09:22:21 → ongoing) all three "expected
summer-rest" conditions held simultaneously:

1. **Electric boiler ON** — `switch.smart_plug_2_socket_1` = on since 08:15:30, continuously
   (turned on ~1 h *before* the alarm onset and never dropped).
2. **CWU setpoint ≈ 40** — held at 40 °C the whole episode by interlock 1778900001001.
3. **Boiler mode = Догорание** with `boiler_power = 0` — pellet boiler idle/burning out.

The alarmOutput is a *true* signal at the device level (the pellet flame is out / fuel is spent),
but its normal consequence — loss of hot water — is fully mitigated: the electric ТЭН is actively
heating DHW, and `sensor.boiler_cwu_temperature` rose from 38.7 °C to 56.7 °C across the episode.
The CO (space-heating) circuit is merely cooling down (54→36 °C), which is expected in July with no
heat demand. This is exactly the intended summer economics: cheap Nord Pool price → heat DHW
electrically and let the solid-fuel boiler burn out.

**Contrast / caveat:** this is distinct from the flagged **07-16 incident**
(`docs/audit/boiler_alarm_watchdog.patch`: "реальный простой отопления ~7.4 ч", alarm 11:37→18:59)
where the boiler was out but not backed by sustained cheap electric heating. The discriminator
between "benign summer flame-out" and "real fault" is exactly whether the electric boiler is ON
with DHW temperature rising — which it is on 07-17. Note the proposed notification-only watchdog
would still fire a "погас огонь" alert after 5 min on 07-17; that alert would be a true-positive at
the sensor level but operationally benign here.
