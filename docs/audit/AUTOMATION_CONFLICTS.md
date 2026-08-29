# Automation Conflict & Dangerous-Interaction Audit

Home Assistant @ 192.168.1.45:8123 — Core 2026.7.x.
Generated: 2026-07-15. READ-ONLY analysis. **No production change was made.**

Sources: live `/config/automations.yaml` (47 automation blocks), `/config/scripts.yaml`
(5 scripts), `/config/configuration.yaml` (helpers + `template:` presence sensor), and the
live `/api/states` + `/api/config/config_entries` snapshots (enabled/disabled state, ghost
entities, config-entry existence). No `docs/audit/automation_inventory.json` existed, so
files were read directly.

Priority order used for severity (per task): water/leak → smoke → boiler/heating →
EV/power → security → energy → lights.

---

## Summary of Critical / High findings

**Critical (1)**
- **C1** — Tuya cloud auto-reload (`1748000001005`) fires on a *genuine* leak (moisture
  `off`→`on`) and reloads the Tuya integration, which drops the moisture sensors + water
  valve to `unavailable`. That trips the 5-min reconnect-grace (`1748000001004`) which
  **blocks** the leak-shutoff automation and resets its 3-minute confirm timer — i.e. it
  can delay/defeat the emergency water shut-off during a real leak. It also targets a
  **deleted config-entry ID** (`01HAENTRYIDPLACEHOLDER0000`) that no longer exists → the
  second reload call errors every time.

**High (3)**
- **H1** — Emergency Telegram alerts (leak v4, smoke siren, security alarm, and the
  `/leak_confirm` + `/siren_alarm` callback replies) send action buttons via
  `notify.send_message` + `inline_keyboard`, a combination the project's own gotchas list
  documents as **unsupported** (buttons dropped). The "🔴 close valve", "turn off siren"
  and "disarm" buttons in life-safety alerts likely never render. (Verify against the
  abstract notifier — two other automations were already converted away from this pattern.)
- **H2** — Floor-heating Nord Pool automations (`1767188164410` bathroom, `1776085158491`
  shower) do **not** check `input_boolean.rezhim_zhara` in their "price expensive → auto"
  branch, so they re-enable the floor climate that the "Жара" summer mode just turned off.
  **Live proof:** `input_boolean.rezhim_zhara = on` yet `climate.floor_heating_2 =
  heat_cool` (re-enabled). Same missing guard for the shower's start/price path.
- **H3** — Leak v2 (`1775638334800`) is a full duplicate of leak v4 targeting the same
  moisture sensors, valve and siren. Currently disabled, but only guarded by
  `initial_state: false`; if re-enabled (has happened before per project notes) both fire →
  double valve-close + double siren. Kept at High because it is a water-safety duplicate.

---

## Entity → Automation cross-reference (shared-control entities)

Entities written by 2+ automations/scripts (conflict surface). "R" = read-only reference.

| Entity | Writers (automation id / script / callback) |
|---|---|
| `switch.smart_plug_2_socket_1` (boiler plug) | `1766138420302` Boiler-NordPool (on≤0.10/off>0.10), `1775106692658` Boiler-sync-on-start **(OFF)**, `1778800001002` EV-2h (off during charge / on after if ≤0.04), `1779000001001` EV+Boiler interlock (off on EV-charge / on when EV-stop & <0.10), `1748000001002` Turbo (on), callbacks `/boiler_on` `/boiler_off` `/sockets_off`, `1766844364781` Telegram-AI |
| `switch.ev_charger_switch` | `1774376407472` EV-by-price **(OFF)**, `1778800001002` EV-2h (on→off after 2h), callbacks `/ev_on` `/ev_off` `/ev_start` `/ev_stop` `/night`, `1766844364781` Telegram-AI |
| `switch.kalarifer_socket_1` (towel warmer) | `1783000001001` Towel-NordPool (on≤0.04 if !night_saver & !zhara / off>0.04), `1784000001002` NightSaver-apply (off at night / on if ≤0.04 morning), `script.rezhim_zhara_on` (off), `script.scene_away` R-no, callbacks `/kalar_on` `/kalar_off`, Telegram-AI |
| `climate.floor_heating` / `_2` | `1767188164410` + `1776085158491` NordPool preset, `1784000001002` NightSaver-apply, `script.rezhim_zhara_on/off`, callbacks `/floor1_on/off` `/floor2_on/off`, Telegram `/temp` (R) |
| `switch.retserkuliatsiia_goriachai_vody_socket_1` (recirc pump) | `1789000001001` Recirc-schedule (time_pattern /10 + presence), callbacks `/chep_on` `/chep_off`, Telegram-AI (turtle). **Not** touched by NightSaver (correctly removed). |
| `switch.voda_kran_switch_1` (water valve) | `1748000001001` Leak-v4 (off), `1775638334800` Leak-v2 (off, disabled), `/leak_confirm` (off), `/water_on` (on), Telegram-AI |
| `switch.zigbee_plug_2_socket_1` (hydrophore) | `1748000001001` Leak-v4 (off), `1775638334800` Leak-v2 (off), `/leak_confirm` `/gidro_on` `/gidro_off`, Telegram-AI |
| `siren.alarm` | `1748000001001` Leak-v4, `1779200002001` Smoke, `1779200003001` Security, `/siren_off` `/siren_alarm` `/security_disarm` `/leak_confirm` |
| `input_boolean.night_saver` | `1784000001001` schedule (on/off), `/night_saver_on` `/night_saver_off` |
| `input_boolean.ev_manual_mode` | `1778700001005` (`/ev_on/off/start/stop`, `/night`), `1748000001006` reset, `1778800001002` (R condition) |
| `input_boolean.tuya_reconnect_grace` | `1748000001004` grace (on/off), `/moisture_false_alarm` (on) |
| accent lights (kukhnia_poloski, gostinnaia_zanaveska, svet_tv_zona, smart_switch_2ch, dream_color_rgb) | `1768228398352` Night-patrol via `/patrol_off_yes`, `1779200001002` Presence-left, `script.scene_away`, `script.scene_cinema`, `/night`, `/light_all_off` (light.turn_off all) |

---

## CRITICAL

### C1 — Tuya auto-reload during a real leak defeats the water shut-off + dead config-entry ID
- **Automations:** `1748000001005` (☁️ Tuya авто-перезагрузка), interacting with
  `1748000001004` (Tuya grace) and `1748000001001` (Leak v4). Lines ~3333-3363 / ~3311-3332 /
  1-135.
- **Evidence / how it triggers:** `1748000001005` triggers on moisture
  `to: 'on' from: 'off'` (a genuine leak) *and* on `to: unavailable`. Action: `delay 30s` →
  `homeassistant.reload_config_entry entry_id: 01HAENTRYIDPLACEHOLDER0000` →
  `homeassistant.reload_config_entry entry_id: 01HAENTRYIDPLACEHOLDER0000`.
  - `01HAENTRYIDPLACEHOLDER0000` **no longer exists** (verified against
    `/api/config/config_entries` — only `01JF7HWA…` tuya entry is loaded). The second call
    raises an error every invocation.
  - Reloading the live Tuya entry (`01JF7…`, which owns the moisture sensors **and** the
    valve `switch.voda_kran_switch_1` + hydrophore) makes them briefly `unavailable`.
    That `unavailable` transition fires `1748000001004`, setting
    `input_boolean.tuya_reconnect_grace` ON for 5 min. Leak v4's shut-off path is gated by
    `tuya_reconnect_grace == off`, so **the emergency valve closure is blocked for ~5 min**.
    In addition, moisture bouncing `on → unavailable → on` restarts Leak v4's
    `for: 00:03:00` confirm timer.
- **Home impact:** During an actual leak, water shut-off can be delayed by up to ~5.5 min
  (grace window + timer reset), or suppressed if the grace keeps re-arming. Water is the
  top-priority system, so this is Critical.
- **SAFE fix (do NOT apply):** (a) Remove the deleted `01OLDENTRY…` reload step. (b) Restrict
  `1748000001005` to trigger **only** on `to: unavailable` (the stale-state case it was
  built for), never on a genuine `off→on` leak transition. (c) Optionally exclude the valve
  entity from the reloaded scope, or add a condition that skips the reload while any leak
  confirm is in flight.
- **Test:** In dev, simulate `binary_sensor.vannaia_moisture` `off→on`; confirm no Tuya
  reload occurs and Leak v4 timer runs uninterrupted; separately simulate `→unavailable`
  and confirm exactly one reload of `01JF7…` with no error for a second entry.
- **Rollback:** Restore the original `1748000001005` block from
  `/config/automations.yaml` (git/backup) and `homeassistant.reload` automations.

---

## HIGH

### H1 — Life-safety Telegram action buttons use an unsupported service+field combo
- **Automations / lines:** Leak v4 `1748000001001` (lines 56-70 initial alert, 113-122
  "valve closed / siren-off" button); Smoke `1779200002001` (3163-3172 siren-off button);
  Security `1779200003001` (3230-3240 disarm / siren-off buttons); handler `1778700001005`
  `/leak_confirm` (1485-1493) and `/siren_alarm` (1570-1578). Disabled Leak v2
  `1775638334800` also (1141, 1181).
- **How it triggers / evidence:** All use `action: notify.send_message` with
  `data: { inline_keyboard: [...] }`. The project's own gotchas (`CLAUDE.md` → "Telegram
  bot" + Known-Bugs "2 automations had bad inline_keyboard … Converted to
  telegram_bot.send_message") document that `inline_keyboard` is **not** honored by
  `notify.send_message`; the message text sends but the buttons are dropped. Two automations
  were already migrated for exactly this reason; the leak/smoke/security ones were left on
  the old pattern.
- **Home impact:** On a real leak, fire, or intrusion, the actionable buttons ("🔴 close
  valve", "turn off siren", "disarm") do not appear, so the user cannot respond from the
  alert. The underlying automatic actions (auto valve-close after timeout, siren) still run;
  only the interactive buttons are lost.
- **Verify first:** Send a test alert through `notify.telegram_owner` with
  an `inline_keyboard` and confirm whether buttons render. If they DO render, downgrade this
  to False-positive (and the earlier "fix" was unnecessary).
- **SAFE fix (do NOT apply):** Convert these emergency alerts to
  `telegram_bot.send_message` with `chat_id: 100000000` + `inline_keyboard: [[["Label",
  "/cb"]]]` (the format already used by the working menu/handler automations).
- **Test:** Trigger each alert in dev; confirm buttons appear and callbacks
  (`/siren_off`, `/security_disarm`, `/leak_confirm`) fire.
- **Rollback:** Restore original blocks from git/backup; reload automations.

### H2 — Floor-heating Nord Pool automations override "Жара" (and turn heating back on)
- **Automations / lines:** `1767188164410` bathroom (expensive branch 935-943),
  `1776085158491` shower (branches 1302-1338; triggers include `homeassistant start` +
  price). `script.rezhim_zhara_on` turns both floors off.
- **How it triggers / evidence:** The "cheap → manual 30 °C" branch of both automations
  correctly checks `input_boolean.rezhim_zhara == off` and
  `input_boolean.night_saver == off`. The "expensive → auto" branch does **not**. Its
  condition is only `price_now > 0.04 and current_preset != "auto"` (bathroom) /
  `price_now > threshold and (hvac != heat_cool or preset != auto)` (shower). When "Жара"
  turns the floor `off`, the next Nord Pool tick (>0.04, which is almost always) makes the
  shower automation call `climate.set_hvac_mode: heat_cool` + `preset auto` — re-enabling
  the climate entity within ~2 min. **Live proof:** `input_boolean.rezhim_zhara = on` but
  `climate.floor_heating_2 = heat_cool` (should be `off`). Bathroom uses only
  `set_preset_mode: auto` (no `set_hvac_mode`), so it is less likely to physically re-heat,
  but it still fights the intended state.
- **Home impact:** Summer "no-heating" mode silently defeated → unwanted floor heating and
  wasted energy; user thinks heating is off.
- **SAFE fix (do NOT apply):** Add
  `and is_state('input_boolean.rezhim_zhara','off')` (and, if desired,
  `night_saver` consistency) to the "expensive → auto" branch of **both** automations, or
  have `rezhim_zhara_on` also block via the existing pattern. Consider having the shower's
  auto branch not force `heat_cool` while Жара is on.
- **Test:** Set `rezhim_zhara` on, force a `sensor.nord_pool_lv_current_price` change
  >0.04, confirm both floor climates stay `off`.
- **Rollback:** Restore original automation blocks; reload.

### H3 — Leak v2 is a live duplicate of Leak v4 (disabled, guarded only by initial_state)
- **Automations / lines:** `1775638334800` (Leak v2, 1089-1214, currently OFF) vs
  `1748000001001` (Leak v4, 1-135, ON). Both `mode: parallel max: 10`.
- **How it triggers:** Same moisture triggers, same `switch.turn_off` of valve +
  hydrophore, same `siren.turn_on`. If v2 is re-enabled (project notes record it being found
  re-enabled on 2026-07-12), both fire on one leak → duplicate siren/valve/notify, and both
  independently arm 5-min timers.
- **Home impact:** Double-actioned leak response, duplicate alerts. Currently mitigated by
  `initial_state: false` (survives reload/restart) but not immune to a manual UI enable.
- **SAFE fix (do NOT apply):** Delete v2 entirely (v4 supersedes it), rather than relying on
  `initial_state`.
- **Test:** Confirm only v4 present; simulate leak; single siren/valve/notify.
- **Rollback:** Re-add v2 block from git/backup.

---

## MEDIUM

### M1 — Old "EV зарядка по цене рынка" (`1774376407472`, disabled) would fight the scheduler
If re-enabled it drives `switch.ev_charger_switch` on `≤0.04` / off `>0.05` via a
`time_pattern /30` + price triggers, conflicting with the 2-h scheduler (`1778800001002`)
and the EV+Boiler interlock (`1779000001001`). Its `0.04/0.05` thresholds also differ from
the current `0.10` policy. **Fix:** delete rather than leave disabled. **Test:** ensure only
scheduler/interlock control EV. **Rollback:** restore block.

### M2 — "Бойлер sync после старта HA" (`1775106692658`, disabled) conflicts on HA start
Uses `0.04` threshold to set the boiler on `homeassistant start`, but the main boiler
automation (`1766138420302`, also start-triggered) uses `0.10`. If re-enabled, two start
handlers race on `switch.smart_plug_2_socket_1` with different thresholds. Currently OFF.
**Fix:** delete; the main boiler automation already handles start. **Rollback:** restore.

### M3 — `sensor.ev_charger_ev_energiia_total` referenced but does not exist
In Самодиагностика v3 (`1765960140022`, line ~400):
`ev_kwh: {{ states('sensor.ev_charger_ev_energiia_total') | float(0) }}`. Verified missing
from `/api/states` (the correct sensor is `sensor.ev_charger_energy`). The 3×/day
self-diagnostic always reports EV = 0.0 kWh. Ghost-entity reference; cosmetic but
misleading. **Fix:** point to `sensor.ev_charger_energy`. **Test:** run `/diag`, confirm EV
kWh non-zero when charging. **Rollback:** restore.

### M4 — EV 2-h post-charge boiler restore threshold (`0.04`) inconsistent with boiler policy (`0.10`)
`1778800001002` restores the boiler after a charge only if price `≤0.04`, while the boiler
policy is `≤0.10`. Net effect self-heals within ~30 s (the boiler automation's price trigger
turns it on at ≤0.10 anyway), so impact is a brief gap, not a stuck-off. **Fix:** align to
`0.10` for consistency. Watch-level.

---

## LOW / WATCH

- **L1 — Ghost automation entity** `automation.ai_status_doma_kazhdye_2_chasa`
  (id `1766840617096`, "🧠🏠 AI статус дома каждые 4 часа") shows state `on` but is
  `"restored": true, supported_features: 0` and is **absent from `automations.yaml`** — an
  orphaned registry entry, not actually running. It will vanish on the next automation
  reload. Cleanup: remove from the entity registry. Not a duplicate of the live self-diag
  (`automation.polnaia_samodiagnostika_doma_ai`), which exists and is fine.
- **L2 — `scene.before_night_saver` is a runtime scene** created by `1784000001002` via
  `scene.create` only when night-saver turns on; it is not persisted across a HA restart.
  Verified currently MISSING. The off-branch uses `continue_on_error`, so no crash, but the
  aquarium's pre-night state may not be restored if HA restarted mid-night. Watch.
- **L3 — `water_sensor_4_moisture` excluded from Leak v4's "cleared" trigger** (only in the
  `on` trigger, lines 15-20). A leak on that sensor never sends an "all-clear" message
  (valve stays closed until manual reopen anyway). Minor.
- **L4 — Notification volume:** boiler (`1766138420302`) and towel (`1783000001001`) send a
  Telegram message on every price crossing; the recirc pump toggled by `1789000001001` is
  logged by "Розетки v7" (`1765801568958`) on each window edge. No loop, but steady noise.
- **L5 — `input_boolean.ev_manual_mode` can stay ON up to 3 h** (reset only on
  `charger_end/free` or 3-h timeout, `1748000001006`), blocking the scheduler for that long
  after a manual `/ev_on`/`/ev_start`. By design; note that a `charger_pause` (current live
  state) does not reset it.
- **L6 — `light.turn_off entity_id: all`** in `/night` and `/light_all_off` turns off every
  light entity globally, including any intentionally-on lights. Blunt but intended.
- **L7 — Many manual (Telegram/AI) writers overlap with the automatic controllers** on the
  boiler plug, towel, floors and lights. Mostly harmless (last-writer-wins, guarded by
  conditions) but means a manual action can be reverted by the next price tick (e.g. manual
  `/boiler_on` at price >0.10 is undone within 30 s by `1766138420302`).

---

## False-positive / verified-OK

- **Boiler-NordPool vs EV+Boiler interlock:** consistent — both restore the boiler at the
  same `<0.10` threshold and the interlock only turns the boiler off while EV charges; the
  boiler automation's ON branch is guarded by `ev_charger_switch off` and
  `ev_charger_status != charger_charging`. No on/off fight.
- **Night-saver schedule ↔ apply:** `1784000001001` sets the helper; `1784000001002`
  reacts to it and does not write the helper back — no cycle.
- **Recirc pump removed from night-saver:** confirmed `1784000001002` does not touch
  `switch.retserkuliatsiia…`; only `1789000001001` controls it, and it self-guards on
  `night_saver == off`. No conflict.
- **Presence sensor** `binary_sensor.prisutstvie_owner` has `delay_off: 10min` debounce;
  the "left/returned" automations trigger on it (not raw GPS) — good.
- **`single`/`restart`/`parallel` modes:** the leak/notify parallel-max-10 automations and
  the `restart`-mode grace/interlock/turbo automations are used appropriately; no
  never-finishing `restart` action or dropped-event `single` risk of note beyond the items
  above.

---

## Assumptions
- Enabled/disabled state, ghost entities and config-entry existence were read from the live
  API; the on-disk `automations.yaml` reflects the current deployed file (matches the
  `automation: !include automations.yaml` in `configuration.yaml`).
- **H1 rests on the project's documented gotcha** that `notify.send_message` ignores
  `inline_keyboard`; it was not runtime-verified (would require sending a live alert, which
  is out of the read-only scope). Flagged with an explicit "verify first" step.
- The floor-heating "Жара" evidence (H2) is inferred from the live state combination
  (`rezhim_zhara=on` + `floor_heating_2=heat_cool`); the exact re-enabling event was not
  captured from logbook.
