# Telegram Life-Safety Alert Buttons — Audit (finding H1)

**Date:** 2026-07-15 · **HA:** Core 2026.7.1 · **Scope:** read-only + one authorized DEV notifier test · **Status:** confirmed broken, patch prepared (NOT deployed)

## TL;DR

Every life-safety Telegram alert that carries an action button
(leak v4, leak v2, smoke, security, and the `/leak_confirm` + `/siren_alarm`
callback replies) sends the button via **`notify.send_message` + `inline_keyboard`**.
That combination is **rejected by Home Assistant with HTTP 400** — the notify entity's
service schema accepts only `message` and `title`. **Result: in a real leak / smoke /
security event, the buttoned notification is not merely missing its button — the whole
message is never delivered.**

The working method (already used by the "Telegram меню" automation) is
**`telegram_bot.send_message`** with an integer `chat_id` and an `inline_keyboard`
shaped `[[["Label","/cb"]]]`. That returns HTTP 200 and renders a tappable button.

A minimal, reviewed-but-**unapplied** patch is in
[`telegram_notify.patch`](./telegram_notify.patch). **Do not deploy without a human
in the loop — production deploy of life-safety notifications is out of autonomous scope.**

---

## 1. Proof (controlled DEV test, 2026-07-15)

Two harmless `🧪 ТЕСТ`-labelled messages (callback `/noop_test`, which no automation
handles) were sent to chat `100000000`, plus baseline controls. Raw results:

| # | Service | Payload | HTTP result |
|---|---------|---------|-------------|
| A | `telegram_bot.send_message` | `chat_id:100000000` + `inline_keyboard:[[["…","/noop_test"]]]` | **200 OK** |
| B | `notify.send_message` | `entity_id:notify.…` + `inline_keyboard:[[["…","/noop_test"]]]` | **400 Bad Request** |
| C | `notify.send_message` | `message` only (no keyboard) | 200 OK (on retry; a first attempt hit a transient 500) |
| D | `telegram_bot.send_message` | `message` only (no keyboard) | transient 500, then fine |

The 500s in C/D were **transient Telegram flood-control** from rapid test sends (they
moved between services on retry and cleared on their own) — not a code defect. The
**deterministic** results are A = 200 and B = 400.

Corroborating evidence from the HA services registry (read-only):

- `notify.send_message` fields = **`message`, `title`** (nothing else).
- `telegram_bot.send_message` fields = `message`, `chat_id`, **`inline_keyboard`**, `keyboard`, `parse_mode`, … .

The notify entity `notify.telegram_owner`
("telegram_ownerTelegramBot Abstract (100000000)", `supported_features: 1`) is the
telegram_bot integration's per-chat notify entity. Its `async_send_message` only takes
message/title, so any extra `inline_keyboard` key fails voluptuous validation → 400.

> **Owner confirmation still useful:** please verify test message **A** shows a
> tappable "🧪 Тест-кнопка A" button and that test **B** either arrived without a
> button or did not arrive. (Backend proof already shows B = 400 / no delivery.)

---

## 2. Affected alerts

`inline_keyboard` sent via `notify.send_message` — every one of these is broken:

| Automation id | Alias | State | Block(s) — button(s) |
|---|---|---|---|
| `1748000001001` | 🚨 Утечка воды v4 | **ON** | leak_check → `🚰 ЗАКРЫТЬ КРАН /leak_confirm`, `🚫 Ложная тревога /moisture_false_alarm`; auto-close → `🔕 /siren_off` |
| `1775638334800` | 🚨 Утечка воды v2 | OFF (`initial_state:false`) | leak_detected → `🚫 /moisture_false_alarm`; auto-close → `🔕 /siren_off` |
| `1778700001005` | 📲 Telegram обработчик кнопок | **ON** | `/leak_confirm` reply → `🔕 /siren_off`; `/siren_alarm` reply → `🔕 /siren_off` |
| `1779200002001` | 🔥 Задымление — сирена | **ON** | smoke_on → `🔕 /siren_off` |
| `1779200003001` | 🛡 Охрана — тревога | **ON** | trigger → `✅ Снять охрану /security_disarm`, `🔕 /siren_off` |

**8 broken blocks across 5 automations** (4 enabled, 1 disabled).

Buttonless `notify.send_message` calls in the same automations (leak "cleared",
"false alarm", battery/price reports, etc.) are **fine** — they send only `message`
and are unaffected.

### Callback handlers — all present

Every button's `callback_data` already has a matching branch in the callback handler
`1778700001005`, so the fix needs **no handler changes**:

`/leak_confirm` ✓ · `/moisture_false_alarm` ✓ · `/siren_off` ✓ · `/security_disarm` ✓

(`/siren_alarm` also has a handler but is never emitted as a button — a harmless
dead branch, not a rendering problem.)

---

## 3. Correct payload formats (this HA version)

**`telegram_bot.send_message` — USE THIS for buttons:**
```yaml
- action: telegram_bot.send_message
  data:
    chat_id: 100000000                 # integer; NOT target: (deprecated → breaks 2026.9.0)
    message: "…"
    inline_keyboard:                   # list of rows → list of buttons → [label, callback]
    - - - "🚰 ЗАКРЫТЬ КРАН!"
        - /leak_confirm
      - - "🚫 Ложная тревога"
        - /moisture_false_alarm        #  == [[["🚰 …","/leak_confirm"],["🚫 …","/moisture_false_alarm"]]]
```

**`notify.send_message` — message/title ONLY (no buttons):**
```yaml
- action: notify.send_message
  target:
    entity_id: notify.telegram_owner
  data:
    message: "…"        # inline_keyboard here => HTTP 400, message NOT delivered
```

---

## 4. Minimal patch

[`docs/audit/telegram_notify.patch`](./telegram_notify.patch) — unified diff, **not
applied**. Per broken block it does one 4-line → 3-line swap:

```
-      - action: notify.send_message
-        target:
-          entity_id: notify.telegram_owner
-        data:
+      - action: telegram_bot.send_message
+        data:
+          chat_id: 100000000
```

`message` and `inline_keyboard` are left byte-for-byte identical. The keyboard shape
already in the files (`[[["Label","/cb"]]]`) is exactly what `telegram_bot.send_message`
expects, so no keyboard reshaping is needed.

---

## 5. Deploy plan (human-run — DO NOT auto-deploy)

> **STOP — production deploy of life-safety notifications is out of autonomous scope.**
> The steps below are for a human operator in a maintenance window.

1. **Backup:** `cp /config/automations.yaml /config/automations.yaml.bak_h1_YYYYMMDD`.
2. **Apply** `telegram_notify.patch` to `/config/automations.yaml` (with fuzz; line
   numbers are from the 2026-07-15 copy). Re-inspect the 8 blocks by eye.
3. **Validate YAML:** HA Developer Tools → *Check Configuration* (or
   `ha core check`). Must pass before reload.
4. **Reload:** `POST /api/services/automation/reload` (no restart needed).
5. **Verify safely (no real emergency):** call the callback handler paths that send a
   button — e.g. tap the Mini App / a menu button that fires `/siren_alarm`, then
   immediately `/siren_off` — and confirm the reply now shows a tappable button.
   Do **not** trigger a real leak/smoke/security event. Optionally send a
   `🧪 ТЕСТ` `telegram_bot.send_message` mirroring the leak-alert keyboard with
   `/noop_test` and confirm it renders.
6. **Confirm with owner** the buttons render, then close H1.

### Rollback
- Restore the backup: `cp /config/automations.yaml.bak_h1_YYYYMMDD /config/automations.yaml`
  then `POST /api/services/automation/reload`.
- The change is self-contained (service name + `chat_id`), touches no handlers, no
  helpers, no entities — rollback is a single file restore with zero side effects.

---

## 6. Tests

`tests/test_telegram_buttons.py` — pure, mocked, no network. Encodes the working
contract as a validator and asserts: the working payload passes, the broken
`notify + inline_keyboard` payload is rejected, malformed keyboards are rejected, and
**every life-safety button `callback_data` has a handler**. It also documents, per
alert, that the current (broken) form fails and the post-fix form passes.
