# EV «Elering API недоступен» Telegram spam — audit

- **Date:** 2026-07-17
- **Scope:** R0 READ-ONLY investigation. No HA/device/repo changes made.
- **Question:** Why does the phone get repeated «Elering API недоступен» (EV) Telegram messages, and how to make it one-per-incident with recovery — **without touching EV charging logic**.

---

## 1. What emits the message

**Emitting script:** `/config/ev_best2h.py` (repo: `ev_best2h.py`), line 52:

```
notify("⚠️ EV планировщик: Elering API временно недоступен. Расписание не изменено.")
```

Sent via `notify.send_message` → `notify.telegram_owner` (Telegram, chat 100000000).

**Driving automation:** `1778800001001` — «🚗 EV зарядка — планировщик».
It calls `action: shell_command.ev_find_best2h`, and in `configuration.yaml`:

```
shell_command:
  ev_find_best2h: python3 /config/ev_best2h.py
```

**Trigger of the message inside the script** (`ev_best2h.py` main):
`ev.fetch_lv_prices()` raises → `except` → `ev.log_err(...)` + `notify("⚠️ ... недоступен ...")` + `sys.exit(1)`.
`fetch_lv_prices()` (in `ev_common.py`) already retries the Elering day-ahead HTTP fetch 4× with backoff `delays=(0,3,8,15)`s (~26s total) before raising `RuntimeError`. So the message fires **once per script run**, only after that run's retries are exhausted.

**Related but dormant:** `ev_day2h.py` and `ev_night2h.py` contain the same pattern with slightly different text
(`⚠️ EV Дневная: Elering API недоступен (сервис временно не отвечает). Расписание не изменено, попробуй позже.` / `... EV Ночная: ...`).
Shell commands `ev_day2h` / `ev_night2h` are defined in `configuration.yaml` but **no automation in `/config/automations.yaml` calls them** (only `ev_find_best2h` is wired). So the live spammer today is **`ev_best2h.py` only**; the other two share the defect and would spam identically if ever wired.

---

## 2. Message count / cadence and what drives repeats

The `home-assistant.log` file is not present on the box (only a 0-byte `home-assistant.log.fault`), so an exact historical send-count is not recoverable from logs. Cadence is derived from the planner's trigger logbook + the trigger definition.

**Planner `1778800001001` triggers:**
1. `state` of `sensor.nord_pool_lv_lowest_price` — **condition** gates it to `8 <= now().hour < 22`. Rare in practice (4 state changes in 3 days).
2. `homeassistant` `event: start` — **no time condition**; runs after a 1-min delay on **every HA restart**, at any hour.
3. `time at 14:05:00` (daily).

`mode: single` (no self-overlap), but each separate trigger still runs the script once.

**Planner trigger logbook (last 7 days = 18 triggers):**

| Date | daily 14:05 | HA-start runs |
|------|:-:|:-:|
| 2026-07-10 | – | 3 |
| 2026-07-11 | 1 | – |
| 2026-07-12 | 1 | 3 |
| 2026-07-13 | 1 | – |
| 2026-07-14 | 1 | – |
| 2026-07-15 | 1 | 4 |
| 2026-07-16 | 1 | – |
| 2026-07-17 | 1 | 1 |

**Root cause of the repeats:** there is **no cross-run state / cooldown / dedup / recovery** anywhere. If Elering is unreachable, every planner run during the outage emits a fresh identical message, unconditionally. The in-run 4× retry only smooths a single run's transient blip; it does nothing across runs.
So the observed spam pattern is a burst of **HA restarts** (e.g. 4 restarts on 2026-07-15, 3 on 2026-07-10/07-12) while Elering is down → up to one message per restart, plus the daily 14:05 run. Because the HA-start branch has **no 08–22 guard**, restarts at night also spam. A single multi-hour Elering outage spanning several restarts therefore yields several near-identical messages.

---

## 3. Does an API failure lose the last good EV schedule?

**No — the last good schedule is preserved.** On `fetch_lv_prices()` failure, `ev_best2h.py` sends the message and `sys.exit(1)` **before** ever calling `input_datetime/set_datetime`. `input_datetime.ev_charge_start` is only written on a successful fetch (and only re-notifies if the value actually changed, `local_str != old_val`). The message text «Расписание не изменено» is accurate.

Verified live: `input_datetime.ev_charge_start = 2026-07-17 15:30:00`, `last_changed = 2026-07-17T09:30Z` (i.e. set by the last **successful** run at 12:30 local). Elering is currently reachable.

**Conclusion:** the scheduling side is already correct on failure. The only defect is **notification spam** (no dedup + no recovery).

---

## 4. Does current behavior have one-per-incident + cooldown + recovery?

**No.**
- One-per-incident: **absent** — one message per failing run.
- Cooldown: **absent**.
- Recovery message when Elering returns: **absent** (no «Elering восстановлен» is ever sent).

---

## 5. Proposal (NOT implemented — notification behavior only)

**Out of scope / do NOT change:** trigger set, the 08–22 condition, window-selection logic, retry counts, and all `input_datetime.ev_charge_start` writing. EV charging schedule/logic stays exactly as-is. Only the *notification* around Elering failure changes.

**Recommended: centralize a small persistent state flag in the scripts (via `ev_common.py`).**
Add a tiny state file next to the existing cache, e.g. `/config/.ev_cache/elering_notify_state.json`:

```json
{ "failing": false, "fail_since": null, "last_notify_ts": 0 }
```

Then wrap the notify decisions:

1. **On fetch failure** (currently line 52 of `ev_best2h.py`):
   - If `failing == false` **OR** `now - last_notify_ts >= COOLDOWN` (suggest `COOLDOWN = 6h`):
     send **one** message, set `failing=true`, set `fail_since` (first failure) and `last_notify_ts=now`.
   - Else: **suppress** (silent). Still `sys.exit(1)`; schedule already untouched.
   - Result: at most one «недоступен» per 6h even across a restart storm.

2. **On the next successful fetch**:
   - If `failing == true`: send **one** recovery message, e.g.
     `✅ EV планировщик: Elering снова доступен. Расписание обновлено.`
     (include the outage duration from `fail_since` if desired), then clear the flag (`failing=false`).
   - If `failing == false`: no extra message (keep current behavior — only notify when the plan value changed).

3. Put both helpers (`elering_note_failure()` / `elering_note_recovery()`) in **`ev_common.py`** so `ev_day2h.py` / `ev_night2h.py` share the same one-per-incident + recovery behavior if they are ever wired. Use one shared state key (or per-script keys) as preferred.

**Notes / options:**
- The state file should reuse the existing atomic-write + `fcntl` lock style already in `ev_query.py` (`save_json`), so concurrent runs don't corrupt it.
- Alternative HA-side gate (an `input_boolean.elering_down` helper checked in the automation) is possible, but the message is emitted from Python, so keeping dedup in the script is a single source of truth and less coupling. Prefer the script approach.
- Optional, orthogonal hardening (still notification-only): add the same `8 <= hour < 22` guard to the HA-start branch so night restarts can't notify. Not required if the cooldown/dedup is in place.

**Net effect:** one clear message per Elering incident, a 6h cooldown ceiling, and exactly one recovery message when the API returns — with zero change to EV charging behavior and the already-correct schedule preservation left intact.
