# Life-Safety Incident — 2026-07-15

## Severity: CRITICAL (two independent life-safety gaps) — RESOLVED (interim + permanent), pending owner physical canary.

## Root cause
1. **Leak protection disabled.** Automation-id **collision**: leak-v4 «Утечка воды — аварийное отключение v4» was authored under `id: 1748000001001`, the SAME id previously used by the «HA Startup Grace Period» automation. In HA one id = one automation, so leak-v4 **overwrote** the grace automation. The grace lifecycle (`start → grace on → 15 min → grace off`) ceased to exist, so `input_boolean.ha_startup_grace` — once set `on` (on an HA start) — was **never turned off**. leak-v4's `leak_check` condition requires `ha_startup_grace == 'off'`; with it stuck `on`, the condition was permanently false → **a real leak would produce no notification, no siren, and no valve closure**, and the `/leak_confirm` rescue button (shipped inside the suppressed message) never reached the phone.
2. **Life-safety Telegram alerts undeliverable.** Leak/smoke/security alerts used `notify.send_message` with an `inline_keyboard` in the service data. The notify ENTITY schema accepts only `message`/`title`, so HA returned **HTTP 400 and delivered nothing** — even if leak detection had worked, the alert + action buttons would not arrive. (Proven live: `notify+inline_keyboard`→400; `telegram_bot.send_message+inline_keyboard`→200.)
3. **No valve-state confirmation.** Both the auto-close and `/leak_confirm` did `switch.turn_off` on the Tuya valve then immediately reported «КРАН ЗАКРЫТ» with no read-back; the valve flaps (went unavailable 14:37→14:38 that day), so a failed close would be falsely reported as success.

## Detection
2026-07-15, during the authorized parallel audit (water-safety-agent + telegram-safety-agent), independently confirmed by the orchestrator against live YAML + state/history/trace.

## Window of possible non-protection
`input_boolean.ha_startup_grace` shows a single `on` history point spanning **≥2026-07-11 → 2026-07-15**; leak protection was likely suppressed for that period. (The grace flag also gated the «устройство недоступно» alert, so battery/offline alerts for the moisture sensors were suppressed too.) No actual leak occurred in the window (the 2026-07-15 06:42 leak-v4 firing was a benign `leak_cleared` courtesy notice from `kukhnia_moisture` recovering `unavailable→off`, NOT a real leak; the valve was never commanded).

## Fixes applied (2026-07-15)
**Interim (restored protection immediately):** after a clean preflight (all 4 moisture sensors `off`+available, no active leak, valve open+available, no automation triggers on the helper), set `input_boolean.ha_startup_grace` → `off`. Verified: helper off, leak-v4 enabled, valve untouched, no siren/notify fired.

**Permanent (deployed, `automation.reload`, no HA restart):**
- **B — grace lifecycle restored.** New automation `1789200001001` «HA Startup Grace (restored)» — trigger `homeassistant start`, `mode: restart`, `turn_on grace → delay 15m → turn_off grace`. Because it triggers only on real HA start (not on `automation.reload`), a reload will never strand the helper `on`; `mode: restart` restarts the timer predictably on an in-grace restart. New diagnostic `1789200001002` alerts (telegram_bot) if grace stays `on` > 20 min. leak-v4 id left unchanged (avoids orphaning its entity).
- **A — Telegram delivery.** All 8 life-safety buttoned blocks (5 automations) converted `notify.send_message`+`inline_keyboard` → `telegram_bot.send_message` with `chat_id: 100000000` (message + inline_keyboard byte-identical; all callback_data & handlers unchanged). Deployed: 0 broken `notify+inline` remain.
- **C — valve read-back.** Both close paths (leak-v4 auto-close + `/leak_confirm`) now, after `switch.turn_off`: `wait_template` valve `off` (timeout 20 s) + 3 s settle → **confirmed** → «✅ Кран закрыт, состояние ПОДТВЕРЖДЕНО»; **else** → CRITICAL «🚨 …состояние крана НЕ ПОДТВЕРЖДЕНО (сейчас: {{state}}). Проверьте физически!». No auto-reopen, no retry loop.

## Evidence
- Preflight + interim: moisture all `off`; grace `on→off`; valve stayed `on`; no siren/notify.
- Deploy: `check_config` valid; `automation.reload` (no restart); leak-v4 loaded+enabled; grace helper `off` after reload; new automations active; valve untouched.
- Structural: 49 automations, 49 unique ids (collision class eliminated for the new ones); leak_check still gates on grace-off; grace-gate + tuya-gate render `True`.
- Tests: `tests/test_water_safety.py` + `tests/test_automation_ids.py` + `tests/test_telegram_buttons.py` = 36 passed (unique-ids; single grace lifecycle owner; leak requires grace off; startup on→delay→off; both close paths do read-back before claiming success; not-confirmed CRITICAL branch selected when valve stays on).
- Independent review: PASS (no safety trigger/condition weakened; no new physical command; reload won't strand grace).

## Unverified physical scenarios (require owner-approved canary — NOT performed)
- End-to-end real leak → shutoff (needs the Phase-B mock-sensor/dummy-valve canary in `WATER_SAFETY_TEST_PLAN.md`; never commands the physical valve).
- Live Telegram button render + tap: the working method is proven (200) but the orchestrator's repeated test sends hit Telegram flood-control (500) — a single real alert is not flood-limited. Owner to glance at Telegram to confirm a «🧪 ТЕСТ» message shows a tappable button.

## Rollback
`/config/backups/pre_lifesafety/automations.yaml.bak` → restore + `automation.reload` (auto-rollback was armed: on invalid config or missing leak automation it would restore automatically — not needed, deploy was valid).

## Prevention (tests added, wired into CI)
- unique-automation-id test; exactly-one-grace-lifecycle-owner test; leak-requires-grace-off test; startup on→delay→off test; valve read-back test; + the 20-min grace-stuck diagnostic automation in HA itself.

## Residual risks
- Physical shutoff path unproven without the canary (above).
- Tuya valve/sensor WiFi flapping (hardware) — read-back now surfaces a failed close instead of hiding it, but a physically-stuck valve still needs manual action.
- Moisture sensors update on change; a fully offline sensor is now surfaced again (grace no longer suppresses the unavailable alert).
