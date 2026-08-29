"""Contract tests for the boiler fault watchdog automation.

Background
----------
An R0 read-only audit (2026-07-17) established the correct fault semantics:

* ``binary_sensor.boiler_alarm`` (ecoNET ``curr.alarmOutput``) is **NOT** a
  fault flag.  It asserts routinely during normal summer operation — the daily
  ``Догорание`` (fire burn-out) idle cycle while the electric ТЭН heats DHW and
  Nord Pool is cheap.  The original watchdog (which alerted on ``alarmOutput``)
  produced ~10 false alarms/day and the misleading text
  "погас огонь / нет тепла".  See ``docs/audit/ECONET_ALARMOUTPUT_SEMANTICS.md``
  and ``docs/audit/BOILER_WATCHDOG_RUNTIME_2026-07-17.md``.
* The ONLY true fault indicator is ``sensor.boiler_mode == 'Авария'`` (ecoNET
  mode 9).  No ``alarmCode``/``alarmState`` field exists on this controller.

The fix (``docs/audit/boiler_watchdog_fix.patch``) re-points the watchdog
(id ``1789400001001``) to fire on ``sensor.boiler_mode == 'Авария'`` and keeps it
strictly *notification-only*: its sole action is ``telegram_bot.send_message``.
It must NEVER command a device — no boiler/switch/climate/select/number/script/
input_boolean/input_datetime/rest_command call (which is why dedup uses the
automation's own ``this.attributes.last_triggered`` instead of a write-latch).

These tests are pure and hermetic — they parse the proposed patch and assert a
scenario matrix that encodes the corrected behaviour:

  (a) summer-normal (alarmOutput on, CWU≈40, Догорание)  -> NO alert
  (b) real fault (boiler_mode == Авария)                  -> exactly ONE alert
  (c) boiler_mode unknown/unavailable                     -> NO fault alert
  (d) flapping alarmOutput                                 -> NO alert (not watched)
  (e) restart / ha_startup_grace                           -> suppressed
  (f) one alert + one recovery per episode                 -> dedup + gated recovery

plus the standing notification-only / zero-command contract.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
OWNER_CHAT_ID = 100000000
WATCHDOG_ID = "1789400001001"
BOILER_MODE_ENTITY = "sensor.boiler_mode"
BOILER_ALARM_ENTITY = "binary_sensor.boiler_alarm"  # the WRONG signal — must NOT be watched
FAULT_MODE = "Авария"
GRACE_ENTITY = "input_boolean.ha_startup_grace"
# The existing boiler-notify automation the patch must NOT touch.
EXISTING_BOILER_AUTOMATIONS = ("1779000001002",)

# The only service the watchdog is permitted to call.
ALLOWED_SERVICE = "telegram_bot.send_message"

# Service-call domains that would mean the watchdog is commanding a device.
# If ANY of these appears as an action, the notification-only contract is broken.
FORBIDDEN_DOMAINS = {
    "boiler", "siren", "switch", "light", "lock", "climate", "select", "number",
    "script", "input_boolean", "input_number", "input_datetime", "cover",
    "fan", "vacuum", "media_player", "scene", "button", "valve",
    "humidifier", "water_heater",
    "notify",  # notify entity path is not used; watchdog uses telegram_bot only
    "rest_command",  # would be how one commands the ecoNET boiler
}

_PATCH = (
    Path(__file__).resolve().parent.parent / "docs" / "audit" / "boiler_watchdog_fix.patch"
)


# --------------------------------------------------------------------------- #
# Helpers: parse the proposed patch
# --------------------------------------------------------------------------- #
def _patch_lines() -> list[str]:
    if not _PATCH.exists():
        pytest.skip(f"patch not found: {_PATCH}")
    return _PATCH.read_text(encoding="utf-8").splitlines()


def _hunk_body_lines() -> list[str]:
    """Return only the diff *body* lines (inside @@ hunks), excluding the leading
    comment header and the ---/+++ file lines."""
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


def _new_side_lines() -> list[str]:
    """Reconstruct the *post-patch* (new) side of the hunk: context lines (' ')
    plus added lines ('+'), with the diff marker stripped. Removed lines dropped.

    (The shared ``- id: '1789400001001'`` header is unchanged, so difflib emits
    it as *context*, not as an added line — an added-only parse would miss it.)
    """
    out: list[str] = []
    for ln in _hunk_body_lines():
        if ln.startswith("+") or ln.startswith(" "):
            out.append(ln[1:])
        # '-' (removed) and any other markers are dropped
    return out


def _added_watchdog_block() -> dict:
    """Extract the post-patch automation block (id 1789400001001) and parse it.

    The block starts at ``- id: '1789400001001'`` and runs until the next
    top-level ``- id:`` line (or end of the reconstructed new side).
    """
    new_side = _new_side_lines()
    start = None
    for i, ln in enumerate(new_side):
        if ln.strip() == f"- id: '{WATCHDOG_ID}'":
            start = i
            break
    assert start is not None, f"new side does not contain block id {WATCHDOG_ID}"
    end = len(new_side)
    for j in range(start + 1, len(new_side)):
        if new_side[j].startswith("- id:"):
            end = j
            break
    fragment = "\n".join(new_side[start:end])
    parsed = yaml.safe_load(fragment)
    assert isinstance(parsed, list) and len(parsed) == 1, "expected exactly one new automation"
    return parsed[0]


def _triggers(block: dict) -> list[dict]:
    trigs = block.get("triggers") or block.get("trigger")
    assert isinstance(trigs, list) and trigs, "watchdog needs triggers"
    return trigs


def _choose_branches(block: dict) -> list[dict]:
    """Return the list of choose branches in the (single) top-level choose action."""
    actions = block.get("actions") or block.get("action")
    assert isinstance(actions, list) and actions, "watchdog needs actions"
    chooses = [a["choose"] for a in actions if isinstance(a, dict) and "choose" in a]
    assert len(chooses) == 1, "expected exactly one top-level choose"
    return chooses[0]


# --------------------------------------------------------------------------- #
# Generic walkers
# --------------------------------------------------------------------------- #
def _walk_service_calls(node) -> list[str]:
    """Recursively collect every service invocation (``action:``/``service:``)
    anywhere in an automation's actions (through choose/if/parallel/repeat/etc.)."""
    calls: list[str] = []
    if isinstance(node, dict):
        for key in ("action", "service"):
            val = node.get(key)
            if isinstance(val, str) and "." in val:
                calls.append(val)
        for v in node.values():
            calls.extend(_walk_service_calls(v))
    elif isinstance(node, list):
        for item in node:
            calls.extend(_walk_service_calls(item))
    return calls


def _walk_condition_entities(node) -> list[str]:
    """Collect every entity_id referenced by a *condition* (state/numeric_state)."""
    found: list[str] = []
    if isinstance(node, dict):
        if "condition" in node and "entity_id" in node:
            ent = node["entity_id"]
            found.extend(ent if isinstance(ent, list) else [ent])
        for v in node.values():
            found.extend(_walk_condition_entities(v))
    elif isinstance(node, list):
        for item in node:
            found.extend(_walk_condition_entities(item))
    return found


def _dump(block: dict) -> str:
    return yaml.dump(block, allow_unicode=True)


# --------------------------------------------------------------------------- #
# Structural sanity
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_patch_parses_and_yields_one_new_block():
    block = _added_watchdog_block()
    assert block["id"] == WATCHDOG_ID
    assert block.get("mode") == "single"


# --------------------------------------------------------------------------- #
# Notification-only / zero-command contract (kept from the original suite)
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_watchdog_issues_zero_device_commands():
    """The heart of the contract: the ONLY service call is telegram_bot.send_message."""
    block = _added_watchdog_block()
    calls = _walk_service_calls(block.get("actions", []))
    assert calls, "watchdog has no actions at all"
    assert set(calls) == {ALLOWED_SERVICE}, (
        f"watchdog must ONLY call {ALLOWED_SERVICE}; found {sorted(set(calls))}"
    )
    offending = [c for c in calls if c.split(".", 1)[0] in FORBIDDEN_DOMAINS]
    assert not offending, f"watchdog commands device(s): {offending}"


@pytest.mark.unit
def test_watchdog_never_commands_the_boiler():
    """Extra-strict: no boiler command in any form (service call OR entity target)."""
    block = _added_watchdog_block()
    dumped = _dump(block)
    assert "rest_command" not in dumped, "watchdog must not call rest_command (boiler write)"
    calls = _walk_service_calls(block.get("actions", []))
    for c in calls:
        assert not c.startswith(("climate.", "switch.", "select.", "number.", "rest_command.")), (
            f"watchdog issues a boiler-controlling call: {c}"
        )


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
def test_dedup_uses_no_write_latch():
    """Dedup/cooldown must be a pure READ of this.attributes.last_triggered — a
    write-latch (input_boolean/input_datetime .set) would break zero-command."""
    block = _added_watchdog_block()
    dumped = _dump(block)
    assert "last_triggered" in dumped, "dedup must use this.attributes.last_triggered"
    for forbidden in ("input_datetime.set_datetime", "input_boolean.turn_on",
                      "input_boolean.turn_off"):
        assert forbidden not in dumped, f"watchdog must not write a latch: {forbidden}"


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


# --------------------------------------------------------------------------- #
# Scenario matrix
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_scenario_a_summer_normal_alarmoutput_does_not_alert():
    """(a) alarmOutput on during Догорание/electric-DHW is NORMAL summer state.

    The watchdog must not watch binary_sensor.boiler_alarm at all, so no
    alarmOutput value (on/flapping) can ever produce an alert.
    """
    block = _added_watchdog_block()
    trig_entities = {t.get("entity_id") for t in _triggers(block)}
    assert BOILER_ALARM_ENTITY not in trig_entities, (
        "watchdog must NOT trigger on binary_sensor.boiler_alarm (false-positive source)"
    )
    cond_entities = set(_walk_condition_entities(block.get("actions", []))) | set(
        _walk_condition_entities(block.get("conditions", []))
    )
    assert BOILER_ALARM_ENTITY not in cond_entities, (
        "watchdog must NOT gate on binary_sensor.boiler_alarm either"
    )


@pytest.mark.unit
def test_scenario_b_real_fault_avaria_alerts_exactly_once():
    """(b) sensor.boiler_mode -> 'Авария' is the true fault: exactly ONE alarm
    trigger, 5-min debounce, and one alarm-message branch."""
    block = _added_watchdog_block()
    trigs = _triggers(block)
    # every trigger watches ONLY sensor.boiler_mode
    assert all(t.get("entity_id") == BOILER_MODE_ENTITY for t in trigs), (
        "watchdog must watch only sensor.boiler_mode"
    )
    alarm = [t for t in trigs if t.get("to") == FAULT_MODE]
    assert len(alarm) == 1, "need exactly one state->'Авария' alarm trigger"
    assert alarm[0].get("id") == "alarm"
    assert str(alarm[0].get("for")) in ("0:05:00", "00:05:00"), (
        "alarm trigger must use a 5-minute `for:` debounce"
    )
    # exactly one alarm-message branch, keyed on trigger.id == 'alarm'
    branches = _choose_branches(block)
    alarm_branches = [
        b for b in branches
        if any("'alarm'" in c.get("value_template", "")
               for c in b.get("conditions", []) if isinstance(c, dict))
    ]
    assert len(alarm_branches) == 1, "expected exactly one alarm branch"
    msgs = [c for c in _walk_service_calls(alarm_branches)]  # sanity: has a send
    assert msgs, "alarm branch must send a message"
    # accurate + neutral text: mentions АВАРИЯ, drops the false 'погас огонь/нет тепла'
    dumped = _dump(alarm_branches[0])
    assert "АВАРИЯ" in dumped, "alarm message must name the АВАРИЯ mode"
    assert "погас" not in dumped and "нет тепла" not in dumped, (
        "must remove the false 'погас огонь / нет тепла' text (alarmOutput != no-heat)"
    )


@pytest.mark.unit
def test_scenario_c_unknown_unavailable_never_fault_alerts():
    """(c) telemetry loss (unknown/unavailable) must never emit the fault alarm.

    No trigger enters the alarm on `to: unknown/unavailable`, and the recovery
    branch is blocked when the new state is unavailable/unknown.
    """
    block = _added_watchdog_block()
    for t in _triggers(block):
        assert t.get("to") not in ("unknown", "unavailable"), (
            "no trigger may fire on transition to unknown/unavailable"
        )
    # alarm trigger's `to` is exactly the fault mode, nothing else.
    alarm = [t for t in _triggers(block) if t.get("id") == "alarm"]
    assert alarm and alarm[0].get("to") == FAULT_MODE
    # recovery branch guards against unavailable/unknown target state.
    dumped = _dump(block)
    assert "'unavailable'" in dumped and "'unknown'" in dumped, (
        "recovery must be guarded against unavailable/unknown target states"
    )


@pytest.mark.unit
def test_scenario_d_flapping_alarmoutput_is_not_a_trigger():
    """(d) alarmOutput flapping on<->unavailable (the old 10x-repeat bug) can no
    longer cause anything: it is not a trigger."""
    block = _added_watchdog_block()
    assert all(t.get("entity_id") != BOILER_ALARM_ENTITY for t in _triggers(block))


@pytest.mark.unit
def test_scenario_e_startup_grace_suppresses_alarm():
    """(e) after an HA restart the ha_startup_grace guard suppresses the alarm."""
    block = _added_watchdog_block()
    branches = _choose_branches(block)
    alarm_branch = next(
        b for b in branches
        if any("'alarm'" in c.get("value_template", "")
               for c in b.get("conditions", []) if isinstance(c, dict))
    )
    grace = [
        c for c in alarm_branch.get("conditions", [])
        if isinstance(c, dict) and c.get("entity_id") == GRACE_ENTITY
    ]
    assert grace, "alarm branch must keep the ha_startup_grace guard"
    assert grace[0].get("state") == "off", "grace guard must require ha_startup_grace == off"


@pytest.mark.unit
def test_scenario_f_one_alert_one_recovery_per_episode():
    """(f) dedup (one alert per episode + hourly cooldown) and a single,
    episode-gated recovery message."""
    block = _added_watchdog_block()
    dumped = _dump(block)

    # Dedup / cooldown: alarm branch gated on this.attributes.last_triggered with a
    # ~60-minute (3600s) cooldown.
    branches = _choose_branches(block)
    alarm_branch = next(
        b for b in branches
        if any("'alarm'" in c.get("value_template", "")
               for c in b.get("conditions", []) if isinstance(c, dict))
    )
    cooldown = [
        c for c in alarm_branch.get("conditions", [])
        if isinstance(c, dict) and "last_triggered" in c.get("value_template", "")
    ]
    assert cooldown, "alarm branch must have a last_triggered cooldown gate"
    assert "3600" in cooldown[0]["value_template"], "cooldown must be ~60 min (3600s)"

    # Recovery: exactly one trigger from 'Авария', 2-min debounce, id 'recover'.
    recover_trigs = [t for t in _triggers(block) if t.get("from") == FAULT_MODE]
    assert len(recover_trigs) == 1, "need exactly one from-'Авария' recovery trigger"
    assert recover_trigs[0].get("id") == "recover"
    assert str(recover_trigs[0].get("for")) in ("0:02:00", "00:02:00"), (
        "recovery trigger must use a 2-minute `for:` debounce"
    )
    # Recovery branch is episode-gated (only if an alert was plausibly sent) and
    # its message is distinct.
    recover_branch = next(
        b for b in branches
        if any("'recover'" in c.get("value_template", "")
               for c in b.get("conditions", []) if isinstance(c, dict))
    )
    assert any(
        "last_triggered is not none" in c.get("value_template", "")
        for c in recover_branch.get("conditions", []) if isinstance(c, dict)
    ), "recovery must only fire if the automation actually alerted (episode gate)"
    assert "снят" in _dump(recover_branch), "recovery message must be distinct (…снят)"


# --------------------------------------------------------------------------- #
# Patch hygiene
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_patch_touches_only_the_watchdog_and_not_1779000001002():
    """The patch modifies ONLY the 1789400001001 block; it must not reference the
    existing boiler-notify automation 1779000001002 (or any other id) in any
    changed line."""
    body = _hunk_body_lines()
    changed = [ln[1:] for ln in body if ln.startswith(("+", "-"))]
    for aid in EXISTING_BOILER_AUTOMATIONS:
        assert not any(aid in ln for ln in changed), (
            f"patch touches existing boiler automation {aid}"
        )
    # The only `- id:` value appearing in changed lines is the watchdog itself.
    id_vals = {
        ln.strip()
        for ln in changed
        if ln.strip().startswith("- id:")
    }
    assert id_vals <= {f"- id: '{WATCHDOG_ID}'"}, (
        f"patch changes an id line other than the watchdog: {id_vals}"
    )


@pytest.mark.unit
def test_watchdog_id_is_preserved_in_place():
    """This is an in-place re-point of the SAME automation: id 1789400001001 is
    unchanged (kept as context) while the block body is rewritten (old alias
    removed, new alias added)."""
    body = _hunk_body_lines()
    id_line = f"- id: '{WATCHDOG_ID}'"
    # id header is present (unchanged context) and survives on the new side.
    assert any(ln[1:].strip() == id_line for ln in body if ln and ln[0] in " +"), (
        "watchdog id header must be preserved"
    )
    removed = [ln[1:] for ln in body if ln.startswith("-")]
    added = [ln[1:] for ln in body if ln.startswith("+")]
    # In-place rewrite: the OLD alarmOutput-era text is removed, the NEW Авария
    # text is added.
    assert any("сигнал тревоги" in ln for ln in removed), (
        "old alarmOutput-era block must be removed"
    )
    assert any("режим АВАРИЯ" in ln or "Авария" in ln for ln in added), (
        "new Авария block must be added"
    )
