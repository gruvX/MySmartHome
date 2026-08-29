# Boiler watchdog 1789400001001 — runtime post-mortem (2026-07-17)

**Scope:** R0 read-only. Why the boiler watchdog (`automation.storozh_kotla_signal_trevogi_tolko_uvedomlenie`, id `1789400001001`) sent ~10 duplicate Telegram messages on 2026-07-17, and whether any objective fault existed.
**Evidence:** HA history (`binary_sensor.boiler_alarm`, `sensor.boiler_mode`, `sensor.boiler_cwu_temperature`, `switch.smart_plug_2_socket_1`), HA logbook for the automation, automation state (`last_triggered`), and the deployed YAML block. No device was commanded, changed, reloaded or deployed.

---

## 1. Verdict (TL;DR)

- **Fire count: exactly 10 alarm messages** (logbook-confirmed), all the DOWN branch («⚠️ Котёл: сигнал тревоги … Возможно погас огонь / нет тепла»). **Zero recovery messages.**
- **Root cause: `binary_sensor.boiler_alarm` was flapping `on ↔ unavailable` (ecoNET WiFi drops), not `on ↔ off`.** Every `unavailable → on` transition re-arms the `to:'on' for:5m` DOWN trigger, and since the underlying alarm stays asserted, it re-fires each cycle. `mode: single` + `for:` gives **no dedup and no cooldown** across re-arm cycles, so one continuous alarm episode produced 10 identical alerts.
- **No objective fault existed.** It is a hot summer day (outside 28.9°C, CO/heating loop cold at ~35°C = no space-heating demand). The solid-fuel boiler is at rest (`mode: Догорание` = embers dying out) and hot water is being actively heated by the **electric ТЭН** (`switch.smart_plug_2_socket_1` ON since 05:15), with **CWU rising 38→56°C and thermostatically cycling 50–56°C** throughout the whole alert window. `alarmOutput` = "no flame", which in summer with electric DHW is the **normal, expected steady state**, not a heat outage.

---

## 2. Fire count + timeline

Logbook (`automation.storozh_kotla_signal_trevogi_tolko_uvedomlenie`, 2026-07-17, UTC) shows **10 "triggered by state of binary_sensor.boiler_alarm" events** (plus 2 message-less entries at 09:27:36 = HA restart re-registration, not fires). `last_triggered = 10:33:59Z`.

Each fire = the DOWN branch armed by a `→ on` transition 5 min earlier:

| # | Fired (UTC) | Armed by `→on` at | Preceding transition |
|---|-------------|-------------------|----------------------|
| 1 | 06:27:21 | 06:22:21 | off → on (first assert) |
| 2 | 06:37:52 | 06:32:52 | unavailable → on |
| 3 | 06:53:20 | 06:48:20 | unavailable → on |
| 4 | 07:10:50 | 07:05:50 | unavailable → on |
| 5 | 07:21:50 | 07:16:50 | unavailable → on |
| 6 | 08:46:15 | 08:41:15 | unavailable → on |
| 7 | 09:46:29 | 09:41:29 | unavailable → on (post-restart) |
| 8 | 10:08:59 | 10:03:59 | unavailable → on |
| 9 | 10:15:29 | 10:10:29 | unavailable → on |
| 10 | 10:33:59 | 10:28:59 | unavailable → on |

`binary_sensor.boiler_alarm` history: `off` overnight (with WiFi blips) → **first `on` at 06:22:21** → thereafter **only `on` / `unavailable`, never `off`**, still `on` at report time (~5 h continuous alarm episode). Because the state never reached `off`, the recovery (`up`) trigger (`from:'on' to:'off' for:2m`) **never fired** — all 10 messages are the alarm text, no alert/recovery pairing.

Note the long continuous `on` stretches with a **single** fire (07:16:50→08:41 ≈ 84 min = 1 fire; 08:41:15→09:41 ≈ 60 min = 1 fire): this proves `mode:single`+`for:` correctly de-dupes within one uninterrupted `on` segment. **The repeats come entirely from the `unavailable` blips re-arming the `to:'on'` trigger** — i.e. `on↔unavailable` flapping, not `on↔off` flapping.

### HA restart contribution
Automation `last_changed = 09:29:12Z`; two message-less logbook rows at 09:27:36Z = HA restart / reload re-registration. The restart itself did not fire the automation, and the `ha_startup_grace` guard on the DOWN branch suppressed the immediate post-restart window (no fire between 09:27 restart and the 09:46:29 fire, which is a normal post-grace flap cycle). So the restart added state churn but was **not** a cause of the duplicates.

---

## 3. Real-fault assessment (independent, from history)

During the entire alert window (06:22–10:34 UTC) the runtime state was unambiguously **healthy summer rest**:

| Signal | Value during window | Meaning |
|--------|--------------------|---------|
| `sensor.boiler_outside_temperature` | 28.9°C | hot summer — no space-heating demand |
| `sensor.boiler_co_temperature` (heating loop) | ~35°C, cold | heating circuit idle by design |
| `sensor.boiler_mode` | **Догорание** throughout | wood boiler fire burnt out / at rest |
| `switch.smart_plug_2_socket_1` (electric ТЭН) | **ON since 05:15** | DHW heated by electricity |
| `sensor.boiler_cwu_temperature` (DHW) | **38.7 → 56.6°C, then cycling 50–56°C** | hot water actively produced & maintained — healthy |

Hot water was being made the whole time; there was **no heat outage and no equipment fault**. `binary_sensor.boiler_alarm` (`curr.alarmOutput`) reflects "no flame in the wood boiler", which is the intended state whenever the household runs on the electric ТЭН — every summer day. **Conclusion: false-positive during normal summer rest.** This also means the watchdog, as written, will fire ~10×/day for the rest of summer.

(This contradicts the 2026-07-16 "7.4 h unnoticed outage" premise that motivated the watchdog: `alarmOutput` alone does not distinguish "wood boiler resting while electric DHW works" from "heat genuinely lost". The domain/chain agent should confirm what the 07-16 event actually was, but from history the 07-17 fires had no fault signature.)

---

## 4. Test assumptions to remove (`tests/test_boiler_watchdog.py`)

The following encode the unproven "`alarmOutput` = fire out / no heat = alertable fault" assumption and must be revised:

1. **Docstring background, lines 5–7** — states as fact that `binary_sensor.boiler_alarm` "trips when the flame goes out / there is no heat." Runtime shows flame-out is the *normal* summer state with electric DHW active. This framing must be corrected (alarmOutput = flame-out, which is only a fault when heat is actually demanded/expected).
2. **`test_trigger_watches_boiler_alarm_on_for_5min` (lines 190–204)** — asserts a single **unconditional** DOWN alert on `to:'on'` with only a 5-min `for:`, no `from:` filter and `conditions: []`. This bakes in "any alarm-on ⇒ alert" and forbids the suppression logic the fix needs. Relax so the alert may be gated (from-filter and/or suppression conditions) and de-duped.
3. **`test_recovery_branch_present` (lines 207–221)** — asserts a recovery message keyed purely on `on→off`, unconditionally paired with the alarm signal. Recovery should only be sent if a real alert was actually issued for that episode; this assertion must allow episode-scoped recovery.

Keep unchanged (still correct): the notification-only contract — `test_watchdog_issues_zero_device_commands`, `test_watchdog_never_commands_the_boiler`, `test_watchdog_has_no_device_targets`, `test_messages_owner_chat_id`, additivity/uniqueness. The watchdog must remain zero-command.

---

## 5. Proposal (redesign — notification-only preserved)

Goal: **one alert per real fault episode, cooldown if it persists, single recovery, no summer false-positives — without losing a genuine heating fault.** All notification-only.

1. **Ignore `unavailable` flapping (kills the 10× repeat).** Do not re-arm on `unavailable→on`. Either add `not_from: unavailable` (or `from: 'off'`) to the DOWN trigger, or gate on a template that treats the alarm as continuously-on across brief `unavailable` gaps. This alone collapses today's 10 fires to at most 1 per genuine off→on episode.

2. **Dedup — one alert per episode.** Use an `input_boolean` / `input_datetime` latch (e.g. `boiler_alarm_alerted`) set when the first alert is sent and cleared only on a confirmed recovery. Condition the DOWN alert on the latch being off, so a persistent alarm never re-alerts. (`mode:single`+`for:` is insufficient because `unavailable` blips break the segment.)

3. **Cooldown ~60 min if the fault persists.** If still in fault after the latch was set, allow at most one reminder per 60 min (compare `now()` to the stored `input_datetime`). Persistent-but-known faults nag hourly, not every few minutes.

4. **Single recovery, only after a real alert.** The `up` recovery message must be conditioned on the dedup latch being set (i.e. an alert was actually sent for this episode); otherwise stay silent. Clear the latch on recovery. Today's run would have sent 0 recovery messages either way (alarm never cleared), which is the desired behaviour.

5. **Separate `unknown`/`unavailable` handling.** Treat sensor loss distinctly from a real alarm: never emit the "погас огонь / нет тепла" alarm on `unavailable`. If desired, a *separate*, heavily-debounced "boiler telemetry offline >N min" notice (once, with cooldown) can flag the chronic ecoNET WiFi drops — but that is an availability notice, not a heat-fault alarm.

6. **Normal-summer suppression (the key false-positive fix).** Suppress the alarm when the flame-out is expected because the house is intentionally on electric DHW / not heating. Suppress when ALL of:
   - electric ТЭН active: `switch.smart_plug_2_socket_1 == on`, AND
   - DHW healthy/rising: `sensor.boiler_cwu_temperature` above a floor (e.g. ≥ its setpoint − margin, ~≥45°C) or trending up, AND
   - no space-heating demand: outside temp high / CO loop cold / boiler in a rest mode (`Догорание`).

   Only alert on `alarmOutput` when heat is genuinely expected but absent — e.g. CWU falling below the floor while the ТЭН is off, or a space-heating demand exists and the wood boiler is neither firing nor being backed by the ТЭН. This preserves detection of a genuine outage (the 07-16 scenario) while silencing the summer-rest steady state that produced today's 10 messages.

**Deploy note:** any dedup latch requires a new `input_boolean`/`input_datetime` (configuration.yaml + reload) and re-work of the automation; per project invariants this is a change requiring owner approval, backup, and canary — out of scope for this R0 read-only audit.
