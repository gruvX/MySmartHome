"""Contract tests for the siren-availability watchdog automation.

Background
----------
On 2026-07-16 09:55 the alarm siren actuator (``siren.alarm``) plus its config
entities (``select.alarm_volume``, ``number.alarm_time``) all went
``unavailable``.  The smoke-siren automation (``1779200002001``) and the
intrusion automation (``1779200003001``) both drive ``siren.alarm`` via
``siren.turn_on``; when the entity is unavailable that call is a silent no-op and
NO sound is produced.  There was no availability watchdog, so a dead siren would
only be discovered during a real fire/intrusion.

The fix (``docs/audit/siren_watchdog.patch``) appends ONE new automation
(id ``1789300001001``) that is *notification-only*: its sole action is
``telegram_bot.send_message``.  It must NEVER command a device.

These tests are pure and hermetic — they parse the proposed patch and assert:

1. The watchdog issues ZERO device commands (only ``telegram_bot.send_message``).
2. It triggers on ``siren.alarm`` -> unavailable/unknown with a 15-minute ``for``
   debounce, and has a recovery branch.
3. It messages the owner chat_id 100000000.
4. Its chosen id ``1789300001001`` is unique w.r.t. the read-only fetched
   automations (the patch is purely additive and collides with nothing).
5. The existing siren automations (``1779200002001`` / ``1779200003001``) are
   NOT modified by the patch.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
OWNER_CHAT_ID = 100000000
WATCHDOG_ID = "1789300001001"
SIREN_ENTITY = "siren.alarm"
EXISTING_SIREN_AUTOMATIONS = ("1779200002001", "1779200003001")

# The only service the watchdog is permitted to call.
ALLOWED_SERVICE = "telegram_bot.send_message"

# Service-call domains that would mean the watchdog is commanding a device.
# If ANY of these appears as an action, the notification-only contract is broken.
FORBIDDEN_DOMAINS = {
    "siren", "switch", "light", "lock", "climate", "select", "number",
    "script", "input_boolean", "input_number", "input_datetime", "cover",
    "fan", "vacuum", "media_player", "scene", "button", "valve",
    "humidifier", "water_heater", "notify",  # notify entity has no keyboard; watchdog uses telegram_bot
}

_PATCH = Path(__file__).resolve().parent.parent / "docs" / "audit" / "siren_watchdog.patch"


# --------------------------------------------------------------------------- #
# Helpers: parse the proposed patch
# --------------------------------------------------------------------------- #
def _patch_lines() -> list[str]:
    if not _PATCH.exists():
        pytest.skip(f"patch not found: {_PATCH}")
    return _PATCH.read_text(encoding="utf-8").splitlines()


def _hunk_body_lines() -> list[str]:
    """Return only the diff *body* lines (inside @@ hunks), excluding the
    leading comment header and the ---/+++ file lines."""
    lines = _patch_lines()
    out: list[str] = []
    in_hunk = False
    for ln in lines:
        if ln.startswith("@@"):
            in_hunk = True
            continue
        if in_hunk:
            out.append(ln)
    assert out, "patch contains no @@ hunk body"
    return out


def _added_watchdog_block() -> dict:
    """Extract the newly-added automation block from the patch and parse it.

    Added lines are '+'-prefixed.  The block we want starts at the added line
    ``- id: '1789300001001'`` and runs to the end of the added content.
    """
    added: list[str] = []
    for ln in _hunk_body_lines():
        if ln.startswith("+"):
            added.append(ln[1:])  # strip the '+' marker
    # find the start of the new automation list item
    start = None
    for i, ln in enumerate(added):
        if ln.strip() == f"- id: '{WATCHDOG_ID}'":
            start = i
            break
    assert start is not None, f"added lines do not contain a new block id {WATCHDOG_ID}"
    fragment = "\n".join(added[start:])
    parsed = yaml.safe_load(fragment)
    assert isinstance(parsed, list) and len(parsed) == 1, "expected exactly one new automation"
    return parsed[0]


# --------------------------------------------------------------------------- #
# Service-call walker
# --------------------------------------------------------------------------- #
def _walk_service_calls(node) -> list[str]:
    """Recursively collect every service invocation (``action:``/``service:``)
    anywhere in an automation's actions (through choose/if/parallel/repeat/etc.)."""
    calls: list[str] = []
    if isinstance(node, dict):
        for key in ("action", "service"):
            val = node.get(key)
            # a `choose`/`if`/`repeat` block also has an "action:" only when it is
            # a real service call (a string like "domain.service").
            if isinstance(val, str) and "." in val:
                calls.append(val)
        for v in node.values():
            calls.extend(_walk_service_calls(v))
    elif isinstance(node, list):
        for item in node:
            calls.extend(_walk_service_calls(item))
    return calls


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_patch_parses_and_yields_one_new_block():
    block = _added_watchdog_block()
    assert block["id"] == WATCHDOG_ID
    assert block.get("mode") == "single"


@pytest.mark.unit
def test_watchdog_issues_zero_device_commands():
    """The heart of the contract: the ONLY service call is telegram_bot.send_message."""
    block = _added_watchdog_block()
    calls = _walk_service_calls(block.get("actions", []))
    assert calls, "watchdog has no actions at all"
    assert set(calls) == {ALLOWED_SERVICE}, (
        f"watchdog must ONLY call {ALLOWED_SERVICE}; found {sorted(set(calls))}"
    )
    # explicit belt-and-suspenders: no forbidden domain appears as a service
    offending = [c for c in calls if c.split(".", 1)[0] in FORBIDDEN_DOMAINS]
    assert not offending, f"watchdog commands device(s): {offending}"


@pytest.mark.unit
def test_watchdog_has_no_device_targets():
    """A notification-only automation carries no target entity_id at all
    (telegram_bot.send_message routes by chat_id)."""
    block = _added_watchdog_block()

    def find_targets(node):
        found = []
        if isinstance(node, dict):
            if "target" in node:
                found.append(node["target"])
            for v in node.values():
                found.extend(find_targets(v))
        elif isinstance(node, list):
            for i in node:
                found.extend(find_targets(i))
        return found

    assert not find_targets(block.get("actions", [])), "watchdog must not target any entity"


@pytest.mark.unit
def test_trigger_watches_siren_unavailable_for_15min():
    block = _added_watchdog_block()
    trigs = block.get("triggers") or block.get("trigger")
    assert isinstance(trigs, list) and trigs, "watchdog needs triggers"
    # every trigger must be a state trigger on siren.alarm
    assert all(t.get("entity_id") == SIREN_ENTITY for t in trigs), (
        "watchdog must watch only siren.alarm (single consolidated alert)"
    )
    # a DOWN trigger: to unavailable/unknown with a 15-minute debounce
    down = [t for t in trigs if t.get("to") in ("unavailable", "unknown")]
    assert down, "missing a state->unavailable/unknown trigger"
    assert {t.get("to") for t in down} == {"unavailable", "unknown"}, (
        "watchdog should catch both unavailable and unknown"
    )
    assert all(str(t.get("for")) == "0:15:00" or t.get("for") == "00:15:00" for t in down), (
        "DOWN triggers must use a 15-minute `for:` debounce"
    )


@pytest.mark.unit
def test_recovery_branch_present():
    block = _added_watchdog_block()
    trigs = block.get("triggers") or block.get("trigger")
    up = [t for t in trigs if t.get("from") in ("unavailable", "unknown")]
    assert up, "missing a recovery trigger (from unavailable/unknown)"
    # the recovery messages should differ from the down alert (a distinct branch)
    text = yaml.dump(block, allow_unicode=True)
    assert "снова доступна" in text or "recovered" in text.lower(), (
        "expected a distinct recovery message"
    )


@pytest.mark.unit
def test_messages_owner_chat_id():
    block = _added_watchdog_block()

    def find_chat_ids(node):
        ids = []
        if isinstance(node, dict):
            if "chat_id" in node:
                ids.append(node["chat_id"])
            for v in node.values():
                ids.extend(find_chat_ids(v))
        elif isinstance(node, list):
            for i in node:
                ids.extend(find_chat_ids(i))
        return ids

    chat_ids = find_chat_ids(block.get("actions", []))
    assert chat_ids, "no chat_id found — message would not reach the owner"
    assert set(chat_ids) == {OWNER_CHAT_ID}, f"messages must go to {OWNER_CHAT_ID}; got {chat_ids}"


@pytest.mark.unit
def test_patch_is_additive_and_does_not_touch_existing_siren_automations():
    """The patch must only ADD lines; it must not delete/modify existing content,
    and must not reference the existing siren automations at all."""
    body = _hunk_body_lines()
    removed = [ln[1:] for ln in body if ln.startswith("-")]
    added = [ln[1:] for ln in body if ln.startswith("+")]

    # The only "removed" line is the last context line of the file, re-added
    # identically because the file has no trailing newline (a diff artifact).
    # Assert: every removed line reappears verbatim among the added lines.
    for r in removed:
        assert r in added, f"patch deletes/modifies existing content: {r!r}"

    # The existing siren automations must not appear in any changed hunk line.
    for aid in EXISTING_SIREN_AUTOMATIONS:
        assert not any(aid in ln for ln in (removed + added)), (
            f"patch touches existing siren automation {aid}"
        )


@pytest.mark.unit
def test_chosen_id_is_unique_and_new():
    """The chosen id is fresh: it is only ever ADDED by the patch, never present
    as pre-existing (removed/context) content."""
    body = _hunk_body_lines()
    added = [ln[1:] for ln in body if ln.startswith("+")]
    context_or_removed = [ln[1:] for ln in body if ln.startswith((" ", "-"))]
    id_line = f"- id: '{WATCHDOG_ID}'"
    assert any(ln.strip() == id_line for ln in added), "new id must be added by the patch"
    assert not any(WATCHDOG_ID in ln for ln in context_or_removed), (
        f"id {WATCHDOG_ID} already exists in the target file (collision)"
    )
