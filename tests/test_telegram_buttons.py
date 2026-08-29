"""Contract tests for Telegram inline-button rendering on life-safety alerts.

Audit finding H1
----------------
Life-safety Telegram alerts (leak v4, leak v2, smoke, security + the /leak_confirm
and /siren_alarm callback replies) send an ``inline_keyboard`` via
``notify.send_message``.  The telegram_bot integration's notify ENTITY only accepts
``message`` + ``title`` (verified live against HA 2026.7: the service exposes exactly
those two fields), so the extra ``inline_keyboard`` key is rejected with HTTP 400 and
NO alert is delivered.  The working method is ``telegram_bot.send_message`` with
``chat_id`` + ``inline_keyboard`` shaped ``[[["Label","/cb"]]]`` (this is what the
Telegram menu automation uses, and it renders).

These are pure, mocked contract tests — they make NO network calls and never touch
the real HA instance.  They encode the working contract as a validator and assert:

1. The working payload (telegram_bot.send_message + list-of-lists keyboard + int
   chat_id) passes; the broken payload (notify.send_message + inline_keyboard) fails.
2. Every button ``callback_data`` used by a life-safety alert has a handler branch in
   the callback-handler automation (so converting the service does not orphan a
   button).

The alert->button map and the handler set below reflect the audited
``/config/automations.yaml`` (4106 lines, fetched 2026-07-15) and the proposed patch
``docs/audit/telegram_notify.patch``.  If the automations change, update these
fixtures.
"""
from __future__ import annotations

import pytest

# --------------------------------------------------------------------------- #
# The working contract
# --------------------------------------------------------------------------- #
CHAT_ID = 100000000

# telegram_bot.send_message service data schema (fields that matter here).
# Confirmed against the live HA services registry 2026-07-15:
#   telegram_bot.send_message fields include: message, chat_id, inline_keyboard, ...
#   notify.send_message       fields:          message, title   (NOTHING else)
TELEGRAM_BOT_ALLOWED_KEYS = {
    "message", "title", "chat_id", "target", "parse_mode", "disable_notification",
    "disable_web_page_preview", "keyboard", "inline_keyboard", "message_tag",
    "reply_to_message_id", "message_thread_id", "additional_fields",
}
NOTIFY_SEND_MESSAGE_ALLOWED_KEYS = {"entity_id", "message", "title"}


class ContractError(ValueError):
    """Raised when a Telegram action payload violates the button-render contract."""


def validate_inline_keyboard(kb: object) -> None:
    """A valid inline_keyboard is list[ rows ] -> list[ buttons ] -> [label, data].

    e.g. ``[[["🚰 Close valve", "/leak_confirm"]]]`` (one row, one button).
    """
    if not isinstance(kb, list) or not kb:
        raise ContractError("inline_keyboard must be a non-empty list of rows")
    for row in kb:
        if not isinstance(row, list) or not row:
            raise ContractError("each keyboard row must be a non-empty list of buttons")
        for btn in row:
            if not (isinstance(btn, list) and len(btn) == 2):
                raise ContractError("each button must be a [label, callback_data] pair")
            label, data = btn
            if not isinstance(label, str) or not label:
                raise ContractError("button label must be a non-empty string")
            if not isinstance(data, str) or not data:
                raise ContractError("button callback_data must be a non-empty string")
            # callbacks are /commands or https:// deep-links
            if not (data.startswith("/") or data.startswith("https://")):
                raise ContractError(f"unexpected callback_data {data!r}")


def validate_action(action: str, data: dict) -> None:
    """Validate a single automation action ``{action: ..., data: {...}}``.

    Enforces the rule at the heart of H1: an ``inline_keyboard`` may ONLY be sent
    via ``telegram_bot.send_message`` (with an integer ``chat_id``), never via
    ``notify.send_message``.
    """
    if action == "notify.send_message":
        extra = set(data) - NOTIFY_SEND_MESSAGE_ALLOWED_KEYS
        if extra:
            raise ContractError(
                f"notify.send_message rejects extra keys {sorted(extra)} "
                "(schema is message/title only -> HTTP 400, no message delivered). "
                "Use telegram_bot.send_message for buttons."
            )
        return
    if action == "telegram_bot.send_message":
        if "inline_keyboard" in data:
            if not isinstance(data.get("chat_id"), int):
                raise ContractError(
                    "telegram_bot.send_message with inline_keyboard must set an "
                    "integer chat_id (target: is deprecated, breaks HA 2026.9.0)"
                )
            validate_inline_keyboard(data["inline_keyboard"])
        return
    raise ContractError(f"unknown telegram action {action!r}")


# --------------------------------------------------------------------------- #
# Audited life-safety alerts: which buttons each one shows (post-fix contract)
# --------------------------------------------------------------------------- #
# (alert id, human name, list of button callback_data it renders)
LIFE_SAFETY_ALERT_BUTTONS = {
    "1748000001001": (  # Утечка воды v4 (ENABLED)
        "leak_v4",
        [["/leak_confirm", "/moisture_false_alarm"], ["/siren_off"]],
    ),
    "1775638334800": (  # Утечка воды v2 (DISABLED but still converted)
        "leak_v2",
        [["/moisture_false_alarm"], ["/siren_off"]],
    ),
    "1778700001005": (  # Telegram обработчик кнопок — /leak_confirm & /siren_alarm replies
        "callback_handler_replies",
        [["/siren_off"], ["/siren_off"]],
    ),
    "1779200002001": (  # Задымление — сирена (ENABLED)
        "smoke",
        [["/siren_off"]],
    ),
    "1779200003001": (  # Охрана — тревога (ENABLED)
        "security",
        [["/security_disarm"], ["/siren_off"]],
    ),
}

# callback_data handled by automation 1778700001005 "Telegram обработчик кнопок".
# (Full set extracted from the audited automations.yaml `callback_data == '/x'` branches.)
HANDLED_CALLBACKS = {
    "/security_arm", "/security_disarm", "/siren_off", "/siren_alarm",
    "/leak_confirm", "/moisture_false_alarm", "/ev_stop", "/ev_start",
    "/patrol_off_yes", "/patrol_off_no",
}


# --------------------------------------------------------------------------- #
# Tests: the validator itself
# --------------------------------------------------------------------------- #
def test_working_method_passes():
    """telegram_bot.send_message + int chat_id + list-of-lists keyboard is valid."""
    validate_action(
        "telegram_bot.send_message",
        {
            "chat_id": CHAT_ID,
            "message": "leak!",
            "inline_keyboard": [[["🚰 Close valve", "/leak_confirm"]]],
        },
    )


def test_broken_method_is_rejected():
    """notify.send_message + inline_keyboard must be flagged (this is H1)."""
    with pytest.raises(ContractError):
        validate_action(
            "notify.send_message",
            {
                "entity_id": "notify.telegram_owner",
                "message": "leak!",
                "inline_keyboard": [[["🚰 Close valve", "/leak_confirm"]]],
            },
        )


def test_plain_notify_without_keyboard_is_allowed():
    """notify.send_message is fine for buttonless alerts (message/title only)."""
    validate_action(
        "notify.send_message",
        {"entity_id": "notify.telegram_owner", "message": "hi"},
    )


def test_telegram_bot_keyboard_requires_int_chat_id():
    """A string chat_id (or target:) must be rejected for keyboard sends."""
    with pytest.raises(ContractError):
        validate_action(
            "telegram_bot.send_message",
            {"chat_id": "100000000", "message": "x",
             "inline_keyboard": [[["a", "/b"]]]},
        )


@pytest.mark.parametrize(
    "kb",
    [
        [],                              # empty
        [[]],                            # empty row
        [[["only-label"]]],              # missing callback_data
        [[["label", 123]]],             # non-string callback
        [["label", "/cb"]],             # missing a nesting level (row of strings)
        [[["label", "bad_no_slash"]]],  # callback not a /command or url
    ],
)
def test_malformed_keyboards_rejected(kb):
    with pytest.raises(ContractError):
        validate_inline_keyboard(kb)


# --------------------------------------------------------------------------- #
# Tests: every life-safety button has a handler
# --------------------------------------------------------------------------- #
def test_all_life_safety_buttons_have_handlers():
    """No life-safety button may emit a callback_data without a handler branch."""
    orphans = []
    for aid, (name, rows) in LIFE_SAFETY_ALERT_BUTTONS.items():
        for row in rows:
            for cb in row:
                if cb not in HANDLED_CALLBACKS:
                    orphans.append(f"{name} ({aid}) button {cb!r} has no handler")
    assert not orphans, "Orphaned life-safety buttons:\n  " + "\n  ".join(orphans)


def test_life_safety_alerts_render_via_working_contract():
    """Each life-safety alert, expressed as the post-fix telegram_bot payload,
    must satisfy the working contract."""
    for aid, (name, rows) in LIFE_SAFETY_ALERT_BUTTONS.items():
        keyboard = [[[f"btn {cb}", cb] for cb in row] for row in rows]
        validate_action(
            "telegram_bot.send_message",
            {"chat_id": CHAT_ID, "message": f"{name} alert", "inline_keyboard": keyboard},
        )


def test_current_broken_payloads_would_fail_contract():
    """Sanity: the SAME alerts, expressed the CURRENT (broken) way, are rejected —
    documenting exactly what the patch fixes."""
    for aid, (name, rows) in LIFE_SAFETY_ALERT_BUTTONS.items():
        keyboard = [[[f"btn {cb}", cb] for cb in row] for row in rows]
        with pytest.raises(ContractError):
            validate_action(
                "notify.send_message",
                {
                    "entity_id": "notify.telegram_owner",
                    "message": f"{name} alert",
                    "inline_keyboard": keyboard,
                },
            )
