# Water-Leak Canary — Run Plan (install / drive / observe / teardown)

> **DO NOT RUN until independent review of `verify_isolation.py` passes.**
> Every step here only toggles `test_*` / `dummy_*` helpers. **No production
> valve, moisture sensor, siren, or security entity is ever touched.**
> All notifications are LOCAL `persistent_notification` (no Telegram), banner
> `🧪 ТЕСТ — реальной протечки нет`.

Chain proved (compressed timings, structurally identical to prod leak-v4 incl. FIX C read-back):

```
test_moisture_1 off -> on -> (for 10s) -> conditions pass (test_grace off)
   -> warn TEST notify -> delay 10s -> dummy_hydro off -> dummy_valve off
   -> wait valve==off (timeout 5s) -> settle 3s -> re-check
   -> CONFIRMED TEST notify  ✅
```

---

## 0. Pre-flight (mandatory)
```bash
cd /home/user/projects/MySmartHome
python docs/audit/water_canary/verify_isolation.py      # must print "ISOLATION CHECK: PASS"
python -c "import yaml,sys; list(yaml.safe_load_all(open('docs/audit/water_canary/canary.yaml'))); print('YAML OK')"
```
Only proceed if both pass.

## 1. Install (helpers + automation)
The canary uses `ha_ssh` for SSH and the admin token from `local_secrets.json`
(read **in-process**, never printed). `/config` is root-owned, so writes go via a
temp file + `sudo cp` (per project convention).

1. **Helpers** — merge PART 1 of `canary.yaml` (the six `input_boolean` child keys)
   into `/config/configuration.yaml` under the existing `input_boolean:` block.
   Then reload:
   ```
   POST /api/services/input_boolean/reload
   ```
   Confirm the six helpers exist and hold their `initial` values:
   `input_boolean.test_moisture_1=off`, `test_moisture_2=off`,
   `dummy_valve=on`, `dummy_hydro=on`, `test_grace=off`, `test_valve_fail=off`.

2. **Automation** — append PART 2 (`- id: 'test_water_canary_0001' ...`) to
   `/config/automations.yaml`, then reload:
   ```
   POST /api/services/automation/reload
   ```
   Confirm `automation.test_kanareika_utechki_mock_izolirovano` (or the slug HA
   assigns) is `on`.

## 2. Drive the scenarios (toggle helpers only)
Use `POST /api/services/input_boolean/turn_on|turn_off` with `{"entity_id": "..."}`.
After each, watch **Developer Tools → traces** for `test_water_canary_0001` and
**Settings → Notifications** for the `🧪 ТЕСТ` persistent notifications.
Reset helpers between cases (moisture off, dummy_valve on, dummy_hydro on).

| # | Case | Drive | Expected |
|---|------|-------|----------|
| 1 | **Happy path (confirm)** | `test_moisture_1` on; wait ~25s | warn TEST notify -> after delay `dummy_valve` flips **off**, `dummy_hydro` off -> **CONFIRMED** TEST notify. `dummy_valve` state = off. |
| 2 | **Grace blocks (pre-trigger)** | `test_grace` on; then `test_moisture_1` on | leak_check condition fails -> **no notify, no valve change** (trace stops at conditions). |
| 3 | **False alarm mid-delay** | `test_moisture_1` on; within the 10s delay set `test_grace` on | warn notify sent, then post-delay branch -> "Ложная тревога" TEST notify, `dummy_valve` **stays on**. |
| 4 | **Self-cleared** | `test_moisture_1` on; before delay ends set it **off** | "снялся сам" TEST notify, `dummy_valve` untouched (on). |
| 5 | **NOT confirmed / valve fail (CRITICAL)** | `test_valve_fail` on; then `test_moisture_1` on | canary SKIPS the valve turn_off -> read-back wait **times out** -> settle -> **CRITICAL «НЕ ПОДТВЕРЖДЕНО»** TEST notify. (Same code path models an *unavailable* valve.) |
| 6 | **Timeout path** | (same as #5) | the 5s `wait_template` timeout is exercised and falls through to CRITICAL — confirmed by trace timing. |
| 7 | **Repeated trigger — no loop** | `test_moisture_1` on/off/on rapidly | each `on`-for-10s produces at most one run; automation never self-retriggers; no runaway. |
| 8 | **Multi-sensor — no storm** | `test_moisture_1` **and** `test_moisture_2` on together | two independent parallel runs (mode parallel/max 10), one notify each — no notification storm; `for:` debounce bounds it. |
| 9 | **Cleared branch** | after any run, `test_moisture_1` off for 5s | "mock-датчик снят, DUMMY-кран НЕ открывается автоматически" TEST notify. Proves no auto-reopen. |

## 3. Observe
- Traces: Developer Tools → Traces → `test_water_canary_0001` — inspect which
  `choose` branch ran and the read-back re-check outcome.
- Notifications: each result is a `persistent_notification` with id
  `test_canary_result_input_boolean.test_moisture_N` (overwrites per sensor).
- Never expect any Telegram message, siren, or change to a real switch.

## 4. TEARDOWN (always run when done)
1. **Disable then remove the automation**: delete the `test_water_canary_0001`
   block from `/config/automations.yaml`; `POST /api/services/automation/reload`.
2. **Remove the six helpers** from `/config/configuration.yaml`;
   `POST /api/services/input_boolean/reload`.
3. **Clear leftover notifications**: for each, `POST /api/services/persistent_notification/dismiss`
   with the `test_canary_*` ids (or dismiss in the UI).
4. **Re-verify**: no `test_*` / `dummy_*` entities remain in `/api/states`; no
   `test_water_canary_0001` automation; production leak-v4 unchanged.

> Teardown touches only the canary artifacts — production automations, helpers,
> and the real valve/sensors are never modified by this plan.
