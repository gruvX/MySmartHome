# Automation Runtime Audit — MySmartHome

**Generated:** 2026-07-15 (read-only audit; no automations or services were triggered)
**HA:** Core 2026.7.1 @ 192.168.1.45:8123
**Evidence window:** stored traces (last few hrs, 13 automations) · logbook run-counts (last 3 days) · `last_triggered` (all) · core logs `2026-07-12 21:46 → 2026-07-15 17:45` · `system_log/list` · trace storage `/config/.storage/trace.saved_traces`

## Method / data sources
- **REST `/api/states`** — `last_triggered`, `mode`, `current` for all 47 automation entities.
- **`trace.saved_traces`** (WS-equivalent) — per-run `script_execution`, timing, last_step, errors for the 13 recently-active automations.
- **WS `logbook/get_events`** (3-day window) — count of *condition-passing* runs per automation.
- **Core logs** (supervisor `core/logs`, 3000 lines) + **WS `system_log/list`** — template/service errors.
- **`automations.yaml`** — trigger/condition/action inspection for root-cause.

### Key semantic note (used throughout)
`last_triggered` and logbook entries advance **only when top-level conditions pass**. Traces are recorded on **every** trigger fire (incl. `failed_conditions`). So a stale `last_triggered` with fresh `failed_conditions` traces = automation is firing but correctly gated (e.g. security when disarmed), **not** broken.

---

## Verdict counts (47 total)
| Verdict | Count |
|---|---|
| confirmed-working | 30 |
| probably-working | 7 |
| unconfirmed | 4 |
| not-working | 2 |
| disabled | 3 |
| obsolete | 1 |

**No inter-automation conflicts found.** The former Утечка v2/v4 duplicate is resolved (v2 disabled + `initial_state:false`).

---

## Full runtime table

| Automation (id) | Expected behavior | Actual runs (3-day) / last_triggered | Errors | Verdict |
|---|---|---|---|---|
| 🔥 Бойлер по Nord Pool (1766138420302) | ON≤0.10 / OFF>0.10 on each price update | 280 runs · 0.0d · traces `finished`, 0.001s no-op | none | confirmed-working |
| 🔥 Полотенцесушитель Nord Pool (1783000001001) | ON≤0.04 / OFF>0.04 | 280 · 0.1d · traces clean | none | confirmed-working |
| 🔥 Тёплый пол душевая (1776085158491) | preset manual30/auto by price | 280 · 0.0d · traces clean | none | confirmed-working (see "frequent triggers" note) |
| 🔥 Тёплый пол ванная (1767188164410) | preset manual30/auto by price | 12 · 0.0d | none | confirmed-working (efficient crossing trigger) |
| ⚡ Цены дня — Elering (1748100001001) | fetch day-ahead prices | 12 · 0.1d · trace 0.38s finished | none | confirmed-working |
| 🚗 EV планировщик (1778800001001) | compute best-2h window | 9 · 0.1d · trace 60.2s (deliberate `delay` step, not stuck) | none | confirmed-working |
| ⚡🔥 EV+Бойлер интерлок (1779000001001) | pause boiler while EV charges | 12 · 0.1d · trace 0.22s finished | none | confirmed-working |
| 🔄 Гард сброса счётчика (1786000001001) | re-base midnight snapshot on counter reset | 6 · 0.0d · traces `failed_conditions` (no reset needed) | none | confirmed-working |
| 🔥 Котёл: уведомления (1779000001002) | notify on Выключен/Авария only | 31 · 0.0d · mostly `failed_conditions`, 1 `finished` | none | confirmed-working |
| 🛡 Охрана — тревога (1779200003001) | siren+notify when armed & sensor trips | last real 23.9d · today traces `failed_conditions` (disarmed) | none | confirmed-working (correctly gated) |
| ♨️ Рециркуляция ГВС (1789000001001) | recirc pump by schedule+presence | 23 · 0.0d · traces clean | none | confirmed-working *(not in CLAUDE.md active list — add it)* |
| 🔌 Уведомления розеток v7 (1765801568958) | plug on/off alerts, 20s debounce | 12 · 0.0d · `failed_conditions` guards | none | confirmed-working |
| ⏰ Скоро дешёвое (1765800619701) | pre-alert cheap price | 5 · 0.0d · trace finished | none | confirmed-working |
| 📊 Прогноз цен v4.2 (1765800603456) | daily price forecast | 5 · 0.1d | none | confirmed-working |
| 🧠 Самодиагностика v3 (1765960140022) | 11/15/19:00 if not all-ok | 9 · 0.1d | none | confirmed-working |
| 🔄 HA: проверка обновлений (1782000001001) | daily 10:00 notify | 3 · 0.3d | none | confirmed-working |
| 🔋 Батареи алерт (1775638921592) | daily low-battery alert | 7 · 0.4d | none | confirmed-working |
| ☀️ Утренний брифинг (1778700001001) | daily 07:00 | 3 · 0.4d | none | confirmed-working |
| 🌙 Ночная экономия: расписание (1784000001001) | 22:00 on / 05:00 off | 6 · 0.5d | none | confirmed-working |
| 🌙 Ночная экономия: применить (1784000001002) | apply night saver | 10 · 0.5d | none | confirmed-working |
| 🕛 Снимок энергии полночь (1778700001002) | 00:01 snapshot | 3 · 0.7d | none | confirmed-working |
| 💶 Учёт стоимости (1785000001001) | 23:58 accrue day→month | 3 · 0.7d | none | confirmed-working |
| 🌙 Ночной патруль (1768228398352) | 23:30 lights-off prompt | 3 · 0.8d | none | confirmed-working |
| 📊 Отчёт потребления (1778700001003) | 23:00 daily report | 3 · 0.8d | none | confirmed-working |
| 🚨 Tuya grace 1 (1748000001004) | block leak alarm after reconnect | 4 · 1.5d | none | confirmed-working |
| 🚗 EV сброс ручного (1748000001006) | reset ev_manual_mode | 2 · 2.0d | none | confirmed-working |
| 🤖 Telegram AI Gemini (1766844364781) | AI command handler | 1 · 2.8d (event-driven) | none | confirmed-working |
| 📲 Telegram меню (1778700001004) | inline menu | 3 · 2.8d | none | confirmed-working |
| 📲 Telegram обработчик кнопок (1778700001005) | callback dispatch | 5 · 2.8d | none | confirmed-working |
| 🔄 HA: авто-установка доп. 03:00 (1782000001002) | install addon updates if any available | never fired · condition `or` of `update.*==on` never true at 03:00 | none | confirmed-working (correctly gated — nothing to install) |
| 💶 Месячный отчёт (1785000001002) | 1st-of-month report+reset | last 10.2d; next 08-01 00:05 | none | probably-working (schedule not due in window) |
| 🚗 EV автозарядка 2ч (1778800001002) | 2h charge + interlock | 1 · 1.1d | none | probably-working |
| ⚠️ Tailscale ключ истекает (1779200001001) | fire 2026-11-01 09:00 | never (future) | none | probably-working (future schedule, verified) |
| 🔥 Турбо нагрев активация (1748000001002) | extra floor heat at very-cheap price | last 51.8d | none | probably-working — **unused** (no cheap-enough prices this season) |
| 🔥 Турбо нагрев деактивация (1748000001003) | end turbo heat | last 51.8d | none | probably-working — **unused** |
| 🔥 Задымление — сирена (1779200002001) | siren on smoke | never fired | none | probably-working — unused (no smoke events) |
| 🚨 Утечка воды v4 (1748000001001) | 3-min-confirm leak shutoff | 1 · **0.3d (fired 06:42 today)** | none in captured logs | probably-working — **confirm 06:42 run was real leak vs false** |
| 🚶 Присутствие: ушёл (1779200001002) | lights-off on leave | never fired (owner home entire window; sensor stayed `on`) | none | unconfirmed |
| 🏠 Присутствие: вернулся (1779200001003) | welcome on return | never fired (same) | none | unconfirmed |
| 🚨 Устройство недоступно (1778900002001) | alert on device unavailable | last 12.4d | none | unconfirmed — hasn't fired despite past device drops; verify trigger coverage |
| 🌡 Микроклимат: алерты (1786000001002) | temp>28/hum>70/PM2.5>35 crossings | never fired (created 07-12; no threshold crossed) | none | unconfirmed |
| **Котёл — откл. ГВС (1778900001001)** | plug on→CWU 40°C / off→55°C + throttled Telegram | 18 · 0.1d · trace `finished` | **18× template TypeError in 3 days** | **not-working (partial)** — see below |
| **☁️ Tuya авто-перезагрузка (1748000001005)** | reload Tuya on moisture unavailable/false-on | 4 · 1.5d | **ERROR on removed entry_id every run** | **not-working (partial)** — see below |
| 🚨 Утечка воды v2 (1775638334800) | (superseded by v4) | state **off**, hardened `initial_state:false` | — | disabled |
| 🚗 EV зарядка по цене рынка (1774376407472) | (replaced by scheduler) | state **off** · last 98.2d | — | disabled |
| 🔄 Бойлер sync после старта HA (1775106692658) | (safe to re-enable) | state **off** · last 98.3d | — | disabled |
| 🧠🏠 AI статус дома 4ч (1766840617096) | AI Task status brief | **unavailable** — no config, orphan registry entry | n/a | obsolete |

---

## not-working — details & evidence

### 1. Котёл — откл. ГВС при работе бойлера (`1778900001001`)
**Symptom:** recurring `WARNING ...automation.kotel_otkl_gvs_pri_rabote_boilera ... In 'template' condition: TypeError: can't subtract offset-naive and offset-aware datetimes` — **18 occurrences in 3 days** (fires on every `switch.smart_plug_2_socket_1` on/off; the boiler plug is back **online** now so it fires often), in both `choice 1` and `choice 2`.

**Root cause:** the notification-throttle condition
```jinja
{{ (now() - as_datetime(states('input_datetime.gvs_last_notify_on')
      if states(...) not in ['unknown','unavailable'] else '1970-01-01 00:00:00')).total_seconds() > 14400 }}
```
`now()` is tz-aware; `as_datetime('YYYY-MM-DD HH:MM:SS')` (the input_datetime state string) and the `'1970-01-01 00:00:00'` fallback are **naive** → subtraction raises. HA treats the errored condition as **False**, so the Telegram "boiler on/off" notifications are **silently never sent**.

**Scope:** the primary action (`rest_command.disable_boiler_cwu` / `enable_boiler_cwu`, setting CWU 40↔55 °C) runs *before* the broken `if`, so **core CWU setpoint control still works** — only the throttled notifications are dead, plus log spam every run.

**Fix (not applied):** wrap with `as_local(as_datetime(...))` (or use `as_timestamp(now()) - as_timestamp(...)`). Same pattern appears in both `gvs_last_notify_on` and `gvs_last_notify_off` branches.

### 2. ☁️ Tuya: авто-перезагрузка при обрыве датчика влаги (`1748000001005`)
**Symptom:** `ERROR ... Error executing script. Error for call_service at pos 4: 01HAENTRYIDPLACEHOLDER0000` (2026-07-14).

**Root cause:** action list reloads **two** config entries:
- pos 2: `01HAENTRYIDPLACEHOLDER0000` — active `ap-` Tuya entry ✅
- pos 4: `01HAENTRYIDPLACEHOLDER0000` — the **removed `gg-` duplicate** (deleted 2026-07-04). Reload raises because the entry no longer exists.

**Scope:** the active Tuya entry IS reloaded (primary purpose works); the automation then errors out on the dead entry_id. **Fix (not applied):** delete the pos-3/pos-4 `delay` + second `reload_config_entry` block. This is a direct leftover of the documented `gg-` removal.

---

## obsolete
- **🧠🏠 AI статус дома каждые 4 часа (`1766840617096`)** — state `unavailable`. Present **only** in `/config/.storage/core.entity_registry` (`config_entry_id: null`, `disabled_by: null`); **not** in `automations.yaml` nor any config. Orphaned registry entry from a deleted UI automation (AI Task). Safe to remove via WS `config/entity_registry/remove`.

## unused (armed but not exercised)
- Турбо нагрев активация/деактивация (`1748000001002/003`) — 51.8 days idle; price never dropped low enough this season. Wiring looks correct; seasonal.
- Задымление — сирена (`1779200002001`) — never fired (no smoke). Correct to keep armed.

---

## Notable runtime observations
- **Suspiciously frequent (by design, not broken):** Бойлер, Полотенцесушитель, and Тёплый пол душевая each ran **280×/3 days (~every 15 min)** because their trigger is a plain `state` change on `sensor.nord_pool_lv_current_price` (fires on every price tick), guarded by fast (0.001 s) `choose` no-ops. By contrast **Тёплый пол ванная** uses `numeric_state` threshold-crossing (12 runs) — the cleaner pattern. Consider migrating the other three to crossing triggers to cut ~800 no-op runs/3 days.
- **Longest run:** EV планировщик 60.2 s — confirmed a deliberate `delay` step in the trace (lets `ev_best2h.py` populate cache), **not** a stuck wait.
- **Restart/reload at ~14:22 today:** all key entities `last_changed` 14:22:52–58 (reload_all-style re-init). **No leak/security false-trigger** events found at 14:2x; `ha_startup_grace` + Tuya-grace automations are in place. Leak v4's 06:42 run was **before** this reload, so not restart-induced.
- **Boiler smart plug recovered:** `switch.smart_plug_2_socket_1` is `on` (changed 14:43) — the CLAUDE.md "offline since 07-04" issue appears resolved; this is why Котёл-ГВС now fires (and errors) frequently.
- **Out-of-scope but active errors (not automations):** boiler REST **template sensors** still spam `dict object has no attribute 'alarmOutput'/'fan'/'feeder'/'pumpCO'/'pumpCWU'/'pumpCirculation'` (old `{% if value_json.curr is defined %}` form). CLAUDE.md claims these were fixed 2026-07-12 — the numeric fields were, but these **boolean/text `curr.*` fields were not**. Worth a follow-up on `sensor.boiler_*` REST value_templates.

## Needs a safe canary to confirm
- **Присутствие ушёл / вернулся** — toggle `binary_sensor.prisutstvie_owner` (or leave/return) to observe the off→on / on→off actions actually fire.
- **Утечка воды v4** — confirm the 06:42 run was a genuine moisture event vs. false; check whether the siren actually engaged (3-min confirm may have cancelled).
- **🚨 Устройство недоступно** — force a monitored entity to `unavailable` to verify its trigger list still covers current devices (didn't fire during real device drops).
- **🌡 Микроклимат алерты** — no threshold crossed since 07-12; canary by temporarily lowering a threshold in a test copy.

## Files created
- `docs/audit/AUTOMATION_RUNTIME.md` (this file) — the only file written to the repo.

*No secrets (tokens/passwords/keys) appear in this report. Config-entry IDs shown are non-secret identifiers already documented in CLAUDE.md.*
