# Tablet — «Статус автоматизаций» (READ-ONLY info model)

**Generated:** 2026-07-15 (read-only design; no automations/services triggered, no production files edited)
**HA:** Core 2026.7.1 @ 192.168.1.45:8123 · Europe/Riga · EUR
**Purpose:** an **information-only** panel for the tablet that answers "are my automations healthy?"
at a glance. **No `automation.trigger` / `turn_on` / `turn_off` buttons** — this panel never acts,
it only reports. Control lives elsewhere; this is a health dashboard.

Consumes the audit set: `docs/audit/automation_inventory.json`, `AUTOMATION_RUNTIME.md`,
`AUTOMATION_CONFLICTS.md`. Every tile below names an **entity/source that actually exists**
(verified against the inventory + a live `/api/states` snapshot on 2026-07-15).

---

## Design rules (apply to every tile)

1. **No fake "all OK".** If the backing data is missing/unreadable → render **`нет данных`**
   (grey, italic), never a green "всё хорошо".
2. **Show freshness.** Every tile carries a last-update stamp (HH:MM). If the stamp is older
   than the tile's expected cadence → mark it `устарело` (amber).
3. **Info-only.** No trigger/run/enable buttons. Tapping a tile may (optionally) open a
   read-only detail list; it must never call a service.
4. **Respect expected cadence.** "Long-not-run" is **not** an error for seasonally-idle
   automations (turbo-heat, smoke siren, future-dated Tailscale). Each automation is judged
   against its own expected frequency (see the cadence table), not a flat threshold.
5. **Counts are live-derived**, everything editorial (errors, conflicts, cadence class) is
   sourced from the dated audit and stamped with the audit time, so the reader can tell a
   live number from an analysis finding.

---

## Live snapshot used for the numbers below (2026-07-15 ~20:45 local)

| Fact | Value | Source |
|---|---|---|
| automation entities live | **47** | `/api/states` filter `automation.*` |
| state `on` | **44** | same |
| state `off` | **3** | same |
| state `unavailable` | **0** | same (the documented orphan `1766840617096` was **removed on the last reload** — L1 resolved) |
| `input_boolean.night_saver` | **off** | `/api/states` |
| `input_boolean.rezhim_zhara` | **on** | `/api/states` |
| `input_boolean.ev_manual_mode` | **on** | `/api/states` |
| `sensor.ev_charger_status` | **charger_pause** | `/api/states` |
| `sensor.nord_pool_lv_current_price` | **0.1825 EUR/kWh** | `/api/states` |

> Note: the 3 `off` automations are the intentionally-disabled ones —
> `ev_zariadka_po_tsene_0_04` (1774376407472), `boiler_sync_posle_starta_ha` (1775106692658),
> `utechka_vody_avariinoe_otkliuchenie` = Leak v2 (1775638334800). This matches "3 disabled"
> in the runtime audit.

---

## TILE SOURCE MAP

Legend for **Freshness**: how often the tile's data can change / how stale is "too stale".
Legend for **Fallback**: what renders when the source is unreadable/absent.

### 1. Активные автоматизации (active count)
| | |
|---|---|
| **Shows** | count of `automation.*` with state `on` → **44** |
| **Source entity** | live `/api/states`, filter `entity_id LIKE 'automation.%' AND state=='on'` |
| **Derivation** | plain count. In `hass.states`. |
| **Freshness** | real-time (state stream). Stamp = time of last `/api/states` read. |
| **Fallback** | if states unreadable → `нет данных` (do NOT show 0) |

### 2. Отключённые (disabled)
| | |
|---|---|
| **Shows** | count of `automation.*` with state `off` → **3** (+ tap = list of the 3 aliases) |
| **Source entity** | live `/api/states`, `state=='off'` |
| **Derivation** | plain count. In `hass.states`. Cross-check names vs audit "disabled" list. |
| **Freshness** | real-time |
| **Fallback** | `нет данных` |

### 3. Недоступные / осиротевшие (unavailable / orphan)
| | |
|---|---|
| **Shows** | count of `automation.*` with state `unavailable` → **0** ("нет осиротевших") |
| **Source entity** | live `/api/states`, `state=='unavailable'` |
| **Derivation** | plain count. In `hass.states`. |
| **Note** | Was 1 (`automation.ai_status_doma_kazhdye_2_chasa`, id 1766840617096) per audit; it **vanished on the last reload** (predicted by conflicts L1). Reflect **current = 0**, sub-label "орфан 1766840617096 удалён". |
| **Freshness** | real-time |
| **Fallback** | `нет данных` |

### 4. Последняя ошибка (last error)
| | |
|---|---|
| **Shows** | most relevant current automation error, or "нет активных ошибок" |
| **Source** | **NOT in `hass.states`.** Derived from trace inspection (WS `trace/get` / `trace.saved_traces`) + core `system_log/list`; here sourced from `AUTOMATION_RUNTIME.md`. |
| **Current state** | **Котёл — откл. ГВС (1778900001001)** datetime `TypeError` (offset-naive vs aware) — the audit's 18×/3d error — is treated as **RESOLVED/fixed** (per task). Remaining open error: **Tuya авто-перезагрузка (1748000001005)** still calls a **deleted config-entry** `01OLDENTRY…` → errors every run (conflicts **C1**). Show that as the current "last error" (severity: критично — see warnings tile). |
| **Derivation** | pick newest error across automations from traces/logs; label with automation alias + short reason. |
| **Freshness** | tie to the **audit timestamp** (2026-07-15), NOT "now" — this is an analysis finding, not a live entity state. Stamp: "аудит 2026-07-15". |
| **Fallback** | if trace/log source unreadable → `нет данных` (never "нет ошибок" on missing data) |

### 5. Давно не запускались (long-not-run, cadence-aware)
| | |
|---|---|
| **Shows** | automations whose `last_triggered` age **exceeds their own expected cadence** — split into "ожидаемо (сезон/будущее)" vs "проверить" |
| **Source entity** | `state_attr('automation.<x>','last_triggered')` (in `hass.states`) |
| **Derivation** | age = now − last_triggered. **Expected cadence is NOT in states** — it comes from the trigger type in `automations.yaml` / the audit's cadence classification (table below). An automation is only flagged **"проверить"** if age ≫ its cadence AND it isn't seasonal/future. |
| **Expected-idle (do NOT flag as error)** | Турбо нагрев акт/деакт (1748000001002/003, ~52d — seasonal, no cheap prices); Задымление — сирена (1779200002001, never — no smoke, correct); Tailscale ключ истекает (1779200001001, fires 2026-11-01 — future); HA авто-установка 03:00 (1782000001002, never — nothing to install, correctly gated). |
| **Genuinely unconfirmed (soft-flag "проверить")** | Присутствие ушёл/вернулся (1779200001002/003, never in window — owner home, needs canary); Устройство недоступно (1778900002001, 12.5d — didn't fire on real drops, verify coverage); Микроклимат алерты (1786000001002, never — no crossing yet). |
| **Freshness** | real-time for the ages; cadence class stamped "аудит 2026-07-15" |
| **Fallback** | if `last_triggered` absent → show "никогда" + cadence class, never "ошибка" |

### 6. Слишком частые (too-frequent)
| | |
|---|---|
| **Shows** | automations running far more than needed (no-op churn) → **~280×/3д** each: Бойлер NordPool (1766138420302), Полотенцесушитель (1783000001001), Тёплый пол душевая (1776085158491); + shadow-сбор 15-мин (1789100001001) by design |
| **Source** | **NOT in `hass.states`.** Run-counts derived from WS `logbook/get_events` (3-day window) or `trace_count`; here from `AUTOMATION_RUNTIME.md`. |
| **Derivation** | count condition-passing runs per automation over N days; flag those with a plain `state`-tick trigger on `sensor.nord_pool_lv_current_price` (fires every ~15 min). Contrast: Тёплый пол ванная uses a `numeric_state` crossing trigger → only 12 runs. |
| **Freshness** | rolling window; stamp = audit date (or the window end if computed live) |
| **Fallback** | `нет данных` |

### 7. Активные режимы (active modes — live)
| | |
|---|---|
| **Shows** | 3 mode pills + EV status: **Ночная экономия = OFF**, **Жара = ON**, **EV ручной режим = ON**, EV статус = `charger_pause` |
| **Source entities** | `input_boolean.night_saver`, `input_boolean.rezhim_zhara`, `input_boolean.ev_manual_mode`, `sensor.ev_charger_status` — all verified live |
| **Derivation** | direct state read. All in `hass.states`. |
| **Freshness** | real-time; stamp = last `/api/states` read |
| **Fallback** | per pill: if a helper is missing/unavailable → that pill shows `нет данных`, others still render |
| **Cross-flag (info)** | H2: Жара=ON while `climate.floor_heating_2=heat_cool` — summer mode is being fought by the floor-heating price automations. Surface as a small "конфликт H2" note under the Жара pill (info only). |

### 8. Время последнего аудита (audit time)
| | |
|---|---|
| **Shows** | "аудит 2026-07-15 · окно улик до 17:45" |
| **Source** | **NOT a live entity.** Static metadata from `automation_inventory.json → meta.generated` + `AUTOMATION_RUNTIME.md` evidence window. |
| **Derivation** | read from the audit artifacts at build time. |
| **Freshness** | fixed per audit run; its age tells the reader how stale the editorial tiles (4, 6, warnings) are. |
| **Fallback** | if meta missing → `нет данных` |

### 9. Предупреждения: Telegram / вода / котёл (warnings — info)
| | |
|---|---|
| **Shows** | 3 info rows surfacing the audit's cross-cutting findings (NO action buttons): |
| | • **Вода/утечка (C1, критично):** Tuya авто-перезагрузка на реальной протечке перезагружает Tuya → датчики влаги + кран уходят в `unavailable` → grace блокирует аварийное закрытие крана до ~5 мин + мёртвый entry_id `01OLDENTRY…` ошибается каждый раз. |
| | • **Telegram (H1, высокий):** аварийные оповещения (утечка v4, дым, охрана, `/leak_confirm`, `/siren_alarm`) шлют кнопки через `notify.send_message`+`inline_keyboard` — комбинация не поддерживается → кнопки не рендерятся. Требует проверки живым тестом. |
| | • **Котёл (инфо):** REST-датчики `sensor.boiler_*` всё ещё спамят `dict has no attribute 'alarmOutput'/'fan'/...` (булевы/текст поля не поправлены 2026-07-12). Датчик-логика ГВС 40↔55° работает; страдают только уведомления/лог. |
| **Source** | **NOT in `hass.states`.** From `AUTOMATION_CONFLICTS.md` (C1, H1) + `AUTOMATION_RUNTIME.md` (boiler REST note). |
| **Derivation** | static analysis findings; each row links to the finding id (C1/H1) for traceability. |
| **Freshness** | stamp = audit date. These persist until fixed; re-run the audit to refresh. |
| **Fallback** | if the audit file is absent at build → hide the tile (do NOT invent "всё чисто") |

---

## Which tiles need data NOT in `hass.states` (and how derived)

| Tile | In states? | If not — derivation |
|---|---|---|
| 1 Active count | ✅ yes | count `automation.*`==on |
| 2 Disabled | ✅ yes | count `automation.*`==off |
| 3 Unavailable/orphan | ✅ yes | count `automation.*`==unavailable |
| 4 **Last error** | ❌ **no** | WS `trace/get` / `trace.saved_traces` per-run `error` + core `system_log/list`. State of `automation.*` never exposes last_error. Here: from `AUTOMATION_RUNTIME.md`. |
| 5 Long-not-run | ⚠️ partial | `last_triggered` **is** in states; **expected cadence is NOT** — comes from trigger type in `automations.yaml` + audit classification (seasonal/future/scheduled). |
| 6 **Too-frequent** | ❌ **no** | run-counts over a window from WS `logbook/get_events` (condition-passing runs) or per-automation `trace_count`. States has no run-counter. |
| 7 Active modes | ✅ yes | direct `input_boolean.*` / `sensor.ev_charger_status` |
| 8 **Audit time** | ❌ **no** | static metadata: `automation_inventory.json → meta.generated`, runtime evidence window |
| 9 **Warnings (C1/H1/boiler)** | ❌ **no** | static findings from `AUTOMATION_CONFLICTS.md` + `AUTOMATION_RUNTIME.md` |

**Implementation note for whoever wires this live** (frontend agent owns `tablet-panel.js`):
tiles 1-3 and 7 are cheap `/api/states` reads; tile 5 needs `last_triggered` (states) plus a
small static cadence map bundled from this doc; tiles 4, 6, 8, 9 are **build-time editorial**
data — either baked from the latest audit JSON or fetched from a small generated
`automations_status.json`. Do NOT synthesize "OK" for 4/6/9 from live states — if the audit
data is absent, render `нет данных` / hide.

---

## Cadence classification (for tile 5 — expected frequency)

| Automation (id) | Expected cadence | Long-idle verdict |
|---|---|---|
| Турбо нагрев акт/деакт (1748000001002/003) | only при очень дешёвой цене (сезонно) | ✅ ожидаемо-простаивает (~52д) |
| Задымление — сирена (1779200002001) | только при дыме | ✅ ожидаемо (событий не было) |
| Охрана — тревога (1779200003001) | только при взломе (armed) | ✅ ожидаемо (24д, корректно gated) |
| Tailscale ключ истекает (1779200001001) | одноразово 2026-11-01 | ✅ ожидаемо (будущее) |
| HA авто-установка доп. 03:00 (1782000001002) | ежедневно, но только если есть апдейт | ✅ ожидаемо (нечего ставить) |
| Присутствие ушёл/вернулся (1779200001002/003) | при уходе/возврате | ⚠️ проверить (не сработали — хозяин дома; нужен канареечный тест) |
| Устройство недоступно (1778900002001) | при недоступности устройства | ⚠️ проверить (12.5д; не сработало при реальных дропах) |
| Микроклимат алерты (1786000001002) | при кроссинге порога | ⚠️ проверить (создан 07-12, порог не пересечён) |
| Месячный отчёт (1785000001002) | 1-е число месяца | ✅ ожидаемо (следующий 08-01) |
| Всё «ежедневное»/«по цене» | ежедневно / каждый тик цены | ✅ свежее (<1д) |

---

## Verification
- **No secrets** in this doc or the mock (no tokens/passwords/keys/chat_id/JWT). Config-entry
  IDs shown (`01OLDENTRY…`) are non-secret identifiers already in `CLAUDE.md`.
- **Live data** read in-process from `local_secrets.json` (token never printed to logs/files).
- All named entities verified to **exist** against `/api/states` + `automation_inventory.json`
  (or explicitly marked "NOT in states → derived").
- Mock: `docs/audit/automations_status_mock/index.html` (+ `screenshot.png`) — de-identified
  **ДЕМО**, no hass, no token, no network, info-only (zero action buttons).
</content>
