# MySmartHome — Reconciled Audit Summary & Prioritized Backlog

**Reviewer:** audit-review-agent · **Date:** 2026-07-15 · **Scope:** READ-ONLY reconciliation of all
audit outputs. No production change, no device command, no commit/push, no secrets.

**Inputs reconciled:** `AUTOMATION_INVENTORY.md` + `automation_inventory.json`,
`AUTOMATION_CONFLICTS.md`, `AUTOMATION_RUNTIME.md`, `ENERGY_INVENTORY.md` + `energy_inventory.json`,
`ENERGY_COST_MODEL.md`, `ENERGY_DATA_QUALITY.md`.
**Missing input:** `TABLET_INFORMATION_ARCHITECTURE.md` was not produced — the tablet/info-architecture
audit is an **open gap** (see backlog T1).

---

## 1. Executive summary

The four automation/energy audits are broadly consistent and mutually reinforcing. Cross-checking
static conflict findings against runtime evidence and energy-sensor trust ratings produced **no hard
contradictions**, but several severity disagreements that are reconciled below.

**Headline findings — verification verdict:**

| Headline claim | Source | Verdict |
|---|---|---|
| **C1** Tuya auto-reload (`1748000001005`) can defeat/delay the emergency water shut-off | CONFLICTS | **Split.** The *dead config-entry error* (`01OLDENTRY…`) is **CONFIRMED** by runtime (errors every run). The *leak-defeat chain* is a **plausible static inference, NOT runtime-confirmed** — see contradiction #1. Still top-priority (water). |
| Ghost-entity typos (`sensor.boiler_temp_co/_cwu`, `…ev_energiia_total`, `signalizatsiia…_2_battery`) | INVENTORY, CONFLICTS(M3) | **CONFIRMED.** Inventory found 5 ghosts; conflicts caught only the EV one. Inventory is the more complete source. |
| gidro = 79% of monthly €, connectivity flapping | DATA-QUALITY | **CONFIRMED** and arithmetically self-consistent (41.85/53.08 = 79%). |
| EV daily attribution unreliable (stale-then-jump +110 kWh) | DATA-QUALITY | **CONFIRMED** from statistics; monthly aggregate roughly OK. |
| No whole-home / main meter exists | INVENTORY, DATA-QUALITY, COST-MODEL | **CONFIRMED** by all three independently. |
| Nord Pool price = **EUR/kWh, 15-minute** market interval | COST-MODEL | **CONFIRMED** from `unit_of_measurement` + price-change timestamps. |

**Unit consistency (task 4): PASS.** Energy sensors are uniformly `kWh` / `total_increasing`; price is
`EUR/kWh`; the one W sensor (`sensor.75_qled_power`) is correctly Watts; `sensor.boiler_power = 99%` is
correctly identified as **burner-output %, not watts** (energy inventory). Cost math is
`kWh × EUR/kWh = EUR` throughout. No W-vs-kW or Wh-vs-kWh confusion found.

**Dangerous-live-test guard (task 5): 3 recommendations would be unsafe if executed literally on
production** — flagged inline and rewritten to safe equivalents:
- CONFLICTS C1 test "simulate `binary_sensor.vannaia_moisture` off→on" — on live HA this **fires the real
  leak shut-off (valve close + siren)**. Use trace replay / a dev instance, never spoof moisture live.
- CONFLICTS H1 test "trigger each alert" — triggering the real leak/smoke/security automations closes the
  valve / sounds the siren. Verify button rendering with a **standalone test message** through
  `notify.telegram_owner` only; do not fire the safety automations.
- CONFLICTS H2 test "force a price change / toggle floors" — prefer the static code fix + observe the next
  natural price tick over commanding heating on/off.

All other recommendations are code-only, read-only checks, or safe toggles (presence, force a non-safety
entity `unavailable`).

---

## 2. Inter-report contradictions & severity reconciliations

1. **C1 leak-defeat: "Critical conflict" (CONFLICTS) vs "No inter-automation conflicts found" (RUNTIME).**
   Both agree the second `reload_config_entry` on the deleted `01OLDENTRY…` entry **errors every run**
   (runtime: 4 runs, error each). They diverge on the *leak-defeat* interaction. Runtime evidence
   partially undercuts it: during **today's leak-v4 run at 06:42**, the Tuya auto-reload did **not**
   fire (its `last_triggered` = 2026-07-14 02:43, on an `→unavailable` event, not a genuine `off→on`
   leak). So the dangerous `off→on`-triggered reload has **not been observed happening on a real leak**.
   **Reconciled:** keep as the #1 water item because the trigger config genuinely includes `→on` and the
   mechanism is credible, but split severity — **dead-entry error = CONFIRMED (fix now)**; **leak-defeat =
   needs-canary**. The single safe fix (drop the `→on` trigger + delete the dead reload step) closes both.

2. **Leak v2 duplicate: High (CONFLICTS H3) vs "resolved" (RUNTIME).** Both agree v2 is `off` +
   `initial_state:false`. CLAUDE.md records it was found re-enabled once (2026-07-12). **Reconciled to
   Medium:** real residual risk (manual UI re-enable) but well-guarded; fix is a clean delete, not urgent.

3. **Floor heating vs "Жара": High conflict (CONFLICTS H2) vs "confirmed-working" (RUNTIME).** Not a true
   contradiction — runtime means "runs as coded", conflicts means "coded without the `rezhim_zhara`
   guard on the expensive→auto branch". Live proof (`rezhim_zhara=on` while `climate.floor_heating_2=
   heat_cool`) is corroborated by inventory (`input_boolean.rezhim_zhara = on`). **Kept High.**

4. **Bed backlight (`sensor.zigbee_plug_total_energy`): "add it to cost tracking" (ENERGY_INVENTORY
   rec #3) vs "NO — DEAD, flat 1.32, state 0" (DATA-QUALITY).** Direct tension. **Reconciled:** do **not**
   add it to `cost_month_*` until the sensor is verified live — adding a dead sensor tracks nothing.

5. **TV `sensor.75_qled_energy`: class B "cumulative kWh" (ENERGY_INVENTORY) vs "DEAD, always 0"
   (DATA-QUALITY).** Inventory's class-B label is optimistic; effectively dead. Not cost-impacting (no
   `cost_month_*` uses TV). **Reconciled:** treat TV as unmetered; low priority cleanup.

6. **Automation count:** CONFLICTS says "47 automation blocks" in file; INVENTORY says 46 in file + 1
   `.storage` orphan = 47 entities. Minor; inventory's breakdown is authoritative.

**Cost-model sensor trust check (task 2): PASS.** All six sensors the accumulator uses are rated at least
"mostly/partial" trustworthy by data-quality (gidro YES, boiler YES, akv OK, chep OK, terarium MOSTLY,
EV PARTIAL). None is rated DEAD. Separately, the **accumulation *method*** is flawed — it prices the day's
kWh at the `(min+max)/2` price midpoint (COST-MODEL §0) — a real accuracy bug independent of sensor trust.

---

## 3. Gaps found (missed or under-covered by the individual audits)

- **Ghost coverage:** conflicts caught 1 ghost (EV); inventory caught 5. The battery-alert typo
  `sensor.signalizatsiia_dvernogo_datchika_2_battery` means the **Сигн.2 door-sensor battery is silently
  unmonitored** — security-adjacent, only in inventory.
- **Boiler REST boolean/text template errors** (`curr.*` for `fan/feeder/pumpCO/pumpCWU/pumpCirculation/
  alarmOutput`) still spam (RUNTIME); CLAUDE.md claims the 2026-07-12 fix covered these — it only fixed
  the *numeric* fields. Affects reliability of `binary_sensor.boiler_alarm/…_pump/…_fan`. Missed by the
  automation-focused audits' headline lists.
- **`Устройство недоступно` (`1778900002001`)** did not fire during real device drops (e.g. the multi-day
  boiler-plug outage). Trigger-coverage gap flagged by runtime; not in the conflicts report.
- **`♨️ Рециркуляция ГВС` (`1789000001001`)** is live but absent from CLAUDE.md's active list (runtime).
- **Tablet information-architecture audit not delivered** — no `TABLET_INFORMATION_ARCHITECTURE.md`.
- **"Гидрофон" label plausibility:** a steady 2–3 kWh/day (79% of the bill) reads like a pump/appliance,
  not a hydrophone — worth an owner sanity-check (DATA-QUALITY).

---

## 4. Prioritized backlog (owner criticality order)

Severity: **C**ritical / **H**igh / **M**edium / **L**ow. "Approval?" = needs owner sign-off before any
change. "Canary" = safe pre-deploy verification. All fixes are **not applied** (design-only here).

### (1) Leak / water

| ID | Item | Sev | Evidence | Safe fix approach | Approval? | Canary | Rollback |
|---|---|---|---|---|---|---|---|
| **W1** | Tuya auto-reload (`1748000001005`) errors on deleted entry `01OLDENTRY…` **and** can (statically) delay leak shut-off by reloading the valve's Tuya entry + arming reconnect-grace | **C** | CONFLICTS C1 (static) + RUNTIME (dead-entry error CONFIRMED every run) | Delete the `01OLDENTRY…` reload + its `delay`; restrict trigger to `→unavailable` only (drop the `→on` genuine-leak trigger). Code-only edit. | **Yes** (water safety) | Trace-replay or dev instance; **never spoof moisture on live HA** | Restore original block from git/backup, reload automations |
| **W2** | Leak v4 (`1748000001001`) action buttons ("🔴 close valve"/siren-off) use `notify.send_message`+`inline_keyboard` — per project gotcha, buttons likely dropped | **H** | CONFLICTS H1 (documented gotcha, not runtime-verified) | Convert to `telegram_bot.send_message` + `chat_id` + `inline_keyboard`, matching working menu automations | Yes | Send a **standalone** test message via the notifier to confirm rendering; do NOT trigger the leak automation | Restore block, reload |
| **W3** | Leak v2 (`1775638334800`) full duplicate of v4; disabled + `initial_state:false` but re-enabled once historically | **M** (↓ from H) | CONFLICTS H3; RUNTIME "resolved" | Delete v2 entirely (v4 supersedes) | Yes | N/A (removal of a disabled dup) | Re-add block from git |
| **W4** | Leak v4 fired 06:42 today — genuine vs false unconfirmed; also `water_sensor_4_moisture` missing from v4's "cleared" trigger (no all-clear) | **L** | RUNTIME; CONFLICTS L3 | Read-only logbook check of 06:42; add sensor to the cleared-trigger list | No | Read-only logbook (safe) | N/A / restore |

### (2) Smoke

| ID | Item | Sev | Evidence | Safe fix approach | Approval? | Canary | Rollback |
|---|---|---|---|---|---|---|---|
| **S1** | Smoke siren (`1779200002001`) siren-off button uses the same unsupported `notify.send_message`+`inline_keyboard`; automation never fired (unexercised) | **H** | CONFLICTS H1; RUNTIME (never fired) | Convert to `telegram_bot.send_message` | Yes | Standalone notifier test message only; **do not spoof smoke** | Restore block |

### (3) Boiler / heating

| ID | Item | Sev | Evidence | Safe fix approach | Approval? | Canary | Rollback |
|---|---|---|---|---|---|---|---|
| **B1** | Floor-heating Nord Pool automations (`1767188164410`, `1776085158491`) re-enable floors that "Жара" turned off — expensive→auto branch lacks the `rezhim_zhara` guard | **H** | CONFLICTS H2 (live proof: `rezhim_zhara=on` + `floor_heating_2=heat_cool`) | Add `is_state('input_boolean.rezhim_zhara','off')` to the expensive→auto branch of both | Yes | Static review + observe next natural price tick | Restore blocks, reload |
| **B2** | Котёл-ГВС (`1778900001001`) throttle condition mixes tz-aware `now()` with naive `as_datetime()` → TypeError 18×/3d; plug-on/off Telegram notifications silently never sent (CWU setpoint control still works) | **M** | RUNTIME not-working(partial) | Use `as_timestamp(now()) - as_timestamp(...)` in both `gvs_last_notify_on/off` branches | Yes | Static review; watch log for cleared error | Restore block, reload |
| **B3** | ecoNET boiler REST template sensors still error on boolean/text fields (`fan/feeder/pumpCO/pumpCWU/pumpCirculation/alarmOutput`); CLAUDE.md "fixed 2026-07-12" only covered numeric fields — affects `binary_sensor.boiler_alarm/pumps/fan` reliability | **M** | RUNTIME (log spam active) | Apply the `{% if curr and curr.FIELD is defined %}…{% else %}…` + per-field availability guard to the boolean/text value_templates too; `homeassistant.reload_all` | Yes | Inspect rendered states post-reload | Restore configuration.yaml block |
| **B4** | Бойлер sync-on-start (`1775106692658`, disabled) uses 0.04 vs current 0.10 policy; would race the main boiler automation if re-enabled | **L** | CONFLICTS M2; INVENTORY (off) | Delete (main boiler automation already handles start) | Yes | N/A | Restore block |
| **B5** | EV 2-h post-charge boiler restore (`1778800001002`) uses 0.04 vs 0.10 boiler policy; self-heals within ~30 s | **L/watch** | CONFLICTS M4 | Align threshold to 0.10 | No | N/A | Restore |

### (4) EV / power

| ID | Item | Sev | Evidence | Safe fix approach | Approval? | Canary | Rollback |
|---|---|---|---|---|---|---|---|
| **E1** | EV energy daily attribution unreliable — `ev_query.py` cache returns stale flat value then dumps +110 kWh on one day | **M** | DATA-QUALITY | Ensure `ev_query.py` emits a fresh value, or mark the sensor `unavailable` when the fetch is stale (so stats record a gap, not a false flat+spike) | No (script-side, off-device logic) | Compare next-day sensor vs Tuya app | Revert script |
| **E2** | Ghost `sensor.ev_charger_ev_energiia_total` in Самодиагностика v3 + morning brief → EV always 0 kWh; real sensor is `sensor.ev_charger_energy` | **M** | CONFLICTS M3; INVENTORY | Repoint to `sensor.ev_charger_energy` | No | Read-only: run `/diag` after fix | Restore string |
| **E3** | Old "EV по цене рынка" (`1774376407472`, disabled) would fight the scheduler+interlock and uses 0.04/0.05 thresholds if re-enabled | **L** | CONFLICTS M1; INVENTORY (off) | Delete | Yes | N/A | Restore block |
| **E4** | Розетки v7 (`1765801568958`) steady notification noise on each window edge | **L** | CONFLICTS L4; RUNTIME | Optional debounce/quiet-hours tuning | No | N/A | Restore |

*EV+Boiler interlock (`1779000001001`) verified consistent by both conflicts and runtime — no action
(logged here to prevent a re-flag).*

### (5) Security

| ID | Item | Sev | Evidence | Safe fix approach | Approval? | Canary | Rollback |
|---|---|---|---|---|---|---|---|
| **Sec1** | Security alarm (`1779200003001`) disarm/siren-off buttons use unsupported `notify.send_message`+`inline_keyboard` | **H** | CONFLICTS H1 | Convert to `telegram_bot.send_message` | Yes | Standalone notifier test message; do not trigger the alarm | Restore block |
| **Sec2** | Battery alert (`1775638921592`) skips Сигн.2 via ghost typo `…_datchika_2_battery` (real: `…_datchika_battery_2`); Сигн.1/Сигн.2 batteries also physically 0%/dead | **M** | INVENTORY (ghost) + CLAUDE.md open issue | Fix the entity typo; owner replaces the two door-sensor batteries (physical) | Yes (physical battery swap) | Read-only: confirm alert now lists Сигн.2 | Restore string |
| **Sec3** | `Устройство недоступно` (`1778900002001`) did not fire during real device drops (boiler plug offline days) — trigger coverage unverified | **M** | RUNTIME unconfirmed | Verify trigger list vs current devices; test by forcing a **non-safety** entity `unavailable` | No | Force a test sensor unavailable (safe) | N/A |
| **Sec4** | Presence автоматики (`1779200001002/003`) + Охрана never fired in window — unconfirmed; presence-return also has ghost refs `sensor.boiler_temp_co/_cwu` (welcome msg shows unknown temps) | **L/M** | RUNTIME unconfirmed; INVENTORY ghosts | Fix the two boiler-temp ghost typos; confirm presence via a real leave/return | No | Safe presence toggle (only turns off lights) | Restore strings |

### (6) Energy accounting

| ID | Item | Sev | Evidence | Safe fix approach | Approval? | Canary | Rollback |
|---|---|---|---|---|---|---|---|
| **EA1** | Cost accumulator (`1785000001001`) prices daily kWh at the `(min+max)/2` price midpoint — systematically wrong in either direction | **H** (within energy) | COST-MODEL §0 | Replace with a correct-by-construction daily job summing exact 15-min `interval_kWh × interval_price` (prototype `tools/energy_cost/`, 27 tests pass, not deployed) | Yes | Run new logic read-only alongside old for a few days; compare | Keep old automation until parity confirmed |
| **EA2** | No whole-home / grid meter → sum-of-devices can't be validated; unmetered loads (lights, floors, appliances) excluded from cost | **M** | INVENTORY + DATA-QUALITY + COST-MODEL | Add a grid CT clamp / smart-meter feed (hardware) | Yes (hardware) | N/A | N/A |
| **EA3** | gidro (`zigbee_plug_2`, 79% of the bill) flaps to `unavailable` frequently — totals intact, granularity degraded | **M** | DATA-QUALITY | Improve Zigbee/Tuya signal (router node / reserve) near the plug | Yes (physical) | Monitor gap count | N/A |
| **EA4** | Boiler plug (`smart_plug_2_socket_1`) weak-WiFi zone dropped **2026-07-04 entirely** from stats + 06-23 freeze → month under-counts ~1 day | **M** | DATA-QUALITY | Reserve IP / improve WiFi in boiler area (same zone as ecoNET) | Yes (physical) | Monitor for missing day-points | N/A |
| **EA5** | HA Energy Dashboard never configured; 8 class-B sensors ready to register | **L** | ENERGY_INVENTORY | Enable dashboard, add the 8 sensors | No | N/A | Remove from dashboard |
| **EA6** | TV `75_qled_*` (4 sensors) dead/misconfigured — `state_class: total` on kWh, negative `sum`; `midnight_tv_energy` tracks a zero sensor | **L** | DATA-QUALITY | Exclude the 3 non-cumulative QLED sensors from recorder or fix `state_class`; drop `midnight_tv_energy` if TV cost isn't tracked. **Do NOT** add dead `zigbee_plug_total_energy` (bed backlight) to cost tracking (contradiction #4) until verified live | No | N/A | Restore config |
| **EA7** | Verify "Гидрофон" label — 2–3 kWh/day steady reads like a pump/appliance | **L** | DATA-QUALITY | Owner confirms device identity | No | N/A | N/A |

### (7) Lights / scenes

| ID | Item | Sev | Evidence | Safe fix approach | Approval? | Canary | Rollback |
|---|---|---|---|---|---|---|---|
| **LT1** | `light.turn_off entity_id: all` in `/night` + `/light_all_off` turns off every light globally (blunt but intended) | **L** | CONFLICTS L6 | Optional: scope to intended lights | No | N/A | Restore |

*Scenes (`scene_away/cinema/guests`, `rezhim_zhara_on/off`) verified fine by inventory; no action.*

### (8) Tablet / info

| ID | Item | Sev | Evidence | Safe fix approach | Approval? | Canary | Rollback |
|---|---|---|---|---|---|---|---|
| **T1** | Tablet information-architecture audit not delivered (`TABLET_INFORMATION_ARCHITECTURE.md` absent) | **L** | This review | Re-run the tablet IA audit (read-only) | No | N/A | N/A |
| **T2** | Orphan automation `automation.ai_status_doma_kazhdye_2_chasa` (`1766840617096`) — `unavailable`, only in `.storage`, not in YAML | **L** | INVENTORY + RUNTIME + CONFLICTS L1 | Remove via WS `config/entity_registry/remove` | No | N/A | Re-create not needed |

---

## 5. Confirmed vs Unconfirmed vs Needs-Canary

| Finding | Status | Basis |
|---|---|---|
| W1 dead config-entry error (`01OLDENTRY…`) | **Confirmed** | Runtime: errors every run (4/3d) |
| W1 leak-defeat interaction | **Needs-canary** | Static chain; did NOT co-occur with today's 06:42 leak run |
| W2/S1/Sec1 inline_keyboard buttons dropped | **Needs-canary** | Documented gotcha; verify via standalone test message |
| W3 leak v2 duplicate (disabled+hardened) | **Confirmed** | Both reports; state off + initial_state:false |
| W4 leak-v4 06:42 genuine vs false | **Needs-canary** (read-only logbook) | Runtime flag |
| B1 floor heating overrides Жара | **Confirmed** | Live state proof + inventory |
| B2 Котёл-ГВС datetime TypeError | **Confirmed** | 18 log errors/3d |
| B3 boiler REST boolean/text template errors | **Confirmed** | Active log spam |
| E1 EV stale-then-jump attribution | **Confirmed** | Statistics (+110 kWh single day) |
| E2 EV ghost sensor → 0 kWh | **Confirmed** | Missing from `/api/states` |
| Sec2 battery-alert skips Сигн.2 (ghost typo) | **Confirmed** | Registry cross-check |
| Sec3 `Устройство недоступно` coverage | **Needs-canary** | Didn't fire on real drops |
| Sec4 presence/охрана automations | **Needs-canary** | Never fired (owner home) |
| Микроклимат alerts (`1786000001002`) | **Needs-canary** | No threshold crossed since 07-12 |
| EA1 cost midpoint method wrong | **Confirmed** | Method inspection |
| EA2 no whole-home meter | **Confirmed** | 3 reports |
| EA3 gidro flapping / 79% | **Confirmed** | Stats gap analysis |
| EA4 boiler plug data loss (07-04) | **Confirmed** | Missing day-point |
| EA6 TV sensors dead/misconfigured | **Confirmed** | Always-0 / negative sum |

**Tally:** **Confirmed = 14** · **Needs-canary = 6** (W1-defeat, W2/S1/Sec1 button-render [1 shared root
cause], W4, Sec3, Sec4, Микроклимат) · Hardware/physical items (EA2/EA3/EA4, Sec2 batteries) are separate.

---

## 6. Open questions for the owner

1. **W1:** Approve dropping the `→on` (genuine-leak) trigger from the Tuya auto-reload so it can never
   run during a leak? (It was only ever meant for the stale-`unavailable` case.)
2. **W2/S1/Sec1:** Confirm whether `notify.send_message`+`inline_keyboard` renders buttons on your
   current HA (a 30-second standalone test message will settle it) — decides if the conversion is needed.
3. **EA1:** Approve replacing the midpoint cost automation with the per-interval accumulator? Historical
   months before ~10 days ago **cannot** be recomputed exactly (recorder purge) — accept forward-only?
4. **EA2:** Willing to add a whole-home CT-clamp / smart-meter feed to unlock house-level cost + the
   unaccounted-consumption metric?
5. **Tariff:** Supply the actual supplier margin, Sadales tīkls distribution, excise, OIK, VAT, and fixed
   daily charge so reported € is a full bill, not spot-only? (COST-MODEL §4 — no values were invented.)
6. **EA7 / "Гидрофон":** Is the 79%-of-bill plug really a hydrophone, or a pump/appliance mislabeled?
7. **Sec2:** Schedule replacement of the two dead door-sensor batteries (Сигн.1/Сигн.2)?
8. **T1:** Do you still want the tablet information-architecture audit produced?

---

## 7. Verification of this deliverable

- **Secret scan:** grep for JWT/`Bearer`/known passwords across `docs/audit/` → **0 secrets** (only
  "REDACTED"/"no secrets" notices in prior reports). No `secret_scan` binary present; grep-based
  equivalent used.
- **`git diff --check`:** clean (see run log).
- **Files created:** `docs/audit/SMART_HOME_AUDIT_SUMMARY.md` (this file only). No production change, no
  device command, no commit/push.
