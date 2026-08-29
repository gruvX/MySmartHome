"""Contract tests for the watchdog START-UP GRACE guard patch.

Background
----------
The 7 infrastructure watchdogs are NOTIFICATION-ONLY automations that page the
owner when a piece of infrastructure goes down:

    siren    1789300001001  (siren.alarm unavailable)
    boiler   1789400001001  (binary_sensor.boiler_alarm on)
    proxmox  1789500001001  (node mylab offline)          <- restart-sensitive
    proxmox  1789500001002  (a running VM unexpectedly stopped)
    proxmox  1789500001003  (a storage pool >= 90 %)
    proxmox  1789500001004  (backup problem)
    proxmox  1789500001005  (node metric stalled/unavailable) <- restart-sensitive

Right after Home Assistant (re)starts, entities go transiently
``unavailable``/``unknown`` while integrations reload.  With a short ``for:``
debounce a watchdog could FALSE-ALARM during that settling window.

The fix (``docs/audit/watchdog_restart_guard.patch``) adds ONE condition to the
state-based DOWN/alert branch of EACH of the 7 watchdogs::

    - condition: state
      entity_id: input_boolean.ha_startup_grace
      state: 'off'

It re-uses the EXISTING helper ``input_boolean.ha_startup_grace`` (set ON at
``homeassistant.start`` and OFF after 15 min by automation 1789200001001).  The
condition lives INSIDE the ``choose`` branch (AND'd with the existing
``{{ trigger.id == 'down'/'problem' }}`` template), so it is evaluated at ACTION
time — after the trigger's ``for:`` debounce — and a genuine outage that
persists past the grace window still alerts.  RECOVERY branches
(``up``/``problem_ok``/``fresh``) and the self-checking staleness branches
(``stale``/``stale_check``) are deliberately NOT guarded.

These tests are pure and hermetic.  They parse the proposed patch plus a
committed snapshot of the 7 pristine watchdog blocks
(``tests/fixtures/watchdog_base.yaml``) and assert:

1.  The pre-patch fixture is exactly the 7 target watchdogs, each
    notification-only (only ``telegram_bot.send_message``) and each WITHOUT the
    grace guard yet.
2.  The patch is purely additive (it removes/modifies no existing content) and
    every hunk adds exactly the 3-line grace guard — nothing else.  It adds no
    ``action:``/``service:`` call and no ``- id:`` line, so it can neither turn
    a watchdog into a device command nor change/create an automation id.
3.  Each of the 7 watchdogs (identified by its unique alert message) gains the
    guard on its DOWN/alert branch, and the guard is inserted between the
    ``trigger.id == 'down'/'problem'`` template and that branch's ``sequence:``
    (i.e. it is AND'd into the alert condition, and the branch still calls only
    ``telegram_bot.send_message``).
4.  The guard reads ``input_boolean.ha_startup_grace == 'off'`` (read-only reuse
    of the shared helper; it never writes it).
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
OWNER_CHAT_ID = 100000000
GRACE_HELPER = "input_boolean.ha_startup_grace"
ALLOWED_SERVICE = "telegram_bot.send_message"

# The 7 target watchdogs and a UNIQUE substring of their DOWN/alert message,
# used to map each patch hunk to the exact automation it edits.
WATCHDOG_ALERT_MSG = {
    "1789300001001": "Сирена недоступна более 15 мин",
    "1789400001001": "Котёл: сигнал тревоги (alarmOutput) активен",
    "1789500001001": "узел mylab недоступен > 5 мин",
    "1789500001002": "ВМ остановлена —",
    "1789500001003": "хранилище заполнено —",
    "1789500001004": "статус резервного копирования = проблема",
    "1789500001005": "метрика узла (ЦП) недоступна > 30 мин",
}
WATCHDOG_IDS = list(WATCHDOG_ALERT_MSG)

# The exact 3-line guard the patch must add (added-line bodies, '+' stripped).
GUARD_LINES = [
    "      - condition: state",
    f"        entity_id: {GRACE_HELPER}",
    "        state: 'off'",
]

# Recovery / self-checking branch tokens that must NOT be guarded.
UNGUARDED_TOKENS = ("up", "problem_ok", "fresh", "stale", "stale_check")

# Service-call domains that would mean a watchdog is commanding a device.
FORBIDDEN_DOMAINS = {
    "siren", "switch", "light", "lock", "climate", "select", "number",
    "script", "input_boolean", "input_number", "input_datetime", "cover",
    "fan", "vacuum", "media_player", "scene", "button", "valve",
    "humidifier", "water_heater", "notify", "homeassistant", "hassio",
}

_ROOT = Path(__file__).resolve().parent.parent
_PATCH = _ROOT / "docs" / "audit" / "watchdog_restart_guard.patch"
_FIXTURE = _ROOT / "tests" / "fixtures" / "watchdog_base.yaml"


# --------------------------------------------------------------------------- #
# Fixture (pristine, pre-patch watchdog blocks)
# --------------------------------------------------------------------------- #
def _fixture_blocks() -> dict[str, dict]:
    if not _FIXTURE.exists():
        pytest.skip(f"fixture not found: {_FIXTURE}")
    docs = yaml.safe_load(_FIXTURE.read_text(encoding="utf-8"))
    return {b["id"]: b for b in docs}


# --------------------------------------------------------------------------- #
# Patch parsing
# --------------------------------------------------------------------------- #
def _patch_text() -> str:
    if not _PATCH.exists():
        pytest.skip(f"patch not found: {_PATCH}")
    return _PATCH.read_text(encoding="utf-8")


def _hunks() -> list[list[str]]:
    """Split the diff body into hunks (each a list of lines incl. the @@ header)."""
    lines = _patch_text().splitlines()
    hunks: list[list[str]] = []
    cur: list[str] | None = None
    for ln in lines:
        if ln.startswith("@@"):
            if cur is not None:
                hunks.append(cur)
            cur = [ln]
        elif cur is not None:
            cur.append(ln)
    if cur is not None:
        hunks.append(cur)
    return hunks


def _body_lines() -> list[str]:
    """All diff-body lines across every hunk (excludes @@ headers and ---/+++)."""
    out: list[str] = []
    for h in _hunks():
        out.extend(h[1:])  # drop the @@ header
    assert out, "patch has no hunk body"
    return out


# --------------------------------------------------------------------------- #
# Service-call walker (for the fixture blocks)
# --------------------------------------------------------------------------- #
def _walk_service_calls(node) -> list[str]:
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


def _find_chat_ids(node) -> list:
    ids = []
    if isinstance(node, dict):
        if "chat_id" in node:
            ids.append(node["chat_id"])
        for v in node.values():
            ids.extend(_find_chat_ids(v))
    elif isinstance(node, list):
        for i in node:
            ids.extend(_find_chat_ids(i))
    return ids


def _alert_branch(block: dict) -> dict:
    """Return the state-based DOWN/alert branch (trigger.id == down|problem)."""
    for br in block["actions"][0]["choose"]:
        for c in br.get("conditions", []):
            vt = c.get("value_template", "") if isinstance(c, dict) else ""
            if "trigger.id ==" in vt and ("'down'" in vt or "'problem'" in vt):
                return br
    raise AssertionError(f"{block.get('id')}: no down/problem alert branch")


# --------------------------------------------------------------------------- #
# Fixture (baseline) tests
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_fixture_is_the_seven_target_watchdogs():
    blocks = _fixture_blocks()
    assert list(blocks) == WATCHDOG_IDS, "fixture must hold exactly the 7 targets in order"
    for wid, b in blocks.items():
        assert b.get("mode") == "single", f"{wid} must be mode: single"
        acts = b.get("actions")
        assert isinstance(acts, list) and acts and "choose" in acts[0], f"{wid} needs a choose"


@pytest.mark.unit
@pytest.mark.parametrize("wid", WATCHDOG_IDS)
def test_fixture_watchdog_is_notification_only(wid):
    """Baseline: each watchdog only ever calls telegram_bot.send_message and
    messages the owner — the property the guard patch must preserve."""
    block = _fixture_blocks()[wid]
    calls = _walk_service_calls(block.get("actions", []))
    assert calls, f"{wid} has no actions"
    assert set(calls) == {ALLOWED_SERVICE}, f"{wid} must ONLY call {ALLOWED_SERVICE}; got {sorted(set(calls))}"
    assert not [c for c in calls if c.split(".", 1)[0] in FORBIDDEN_DOMAINS]
    assert set(_find_chat_ids(block.get("actions", []))) == {OWNER_CHAT_ID}


@pytest.mark.unit
@pytest.mark.parametrize("wid", WATCHDOG_IDS)
def test_fixture_alert_branch_not_yet_guarded(wid):
    """Pre-patch, the DOWN/alert branch has NO grace guard (so the patch is a
    real change) but DOES have a recovery branch to keep working."""
    block = _fixture_blocks()[wid]
    alert = _alert_branch(block)
    guarded = any(
        isinstance(c, dict) and c.get("condition") == "state" and c.get("entity_id") == GRACE_HELPER
        for c in alert["conditions"]
    )
    assert not guarded, f"{wid}: alert branch already guarded in fixture (nothing to add)"
    # a recovery branch exists (trigger.id up/problem_ok/fresh)
    tokens = " ".join(
        c.get("value_template", "")
        for br in block["actions"][0]["choose"]
        for c in br.get("conditions", [])
        if isinstance(c, dict)
    )
    assert any(t in tokens for t in ("'up'", "'problem_ok'", "'fresh'")), f"{wid}: no recovery branch"


# --------------------------------------------------------------------------- #
# Patch tests
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_patch_targets_the_config_file():
    text = _patch_text()
    assert "--- a/automations.yaml" in text and "+++ b/automations.yaml" in text


@pytest.mark.unit
def test_patch_has_exactly_seven_hunks():
    assert len(_hunks()) == len(WATCHDOG_IDS), "expected one hunk per target watchdog (7)"


@pytest.mark.unit
def test_patch_is_purely_additive():
    """No existing content is deleted or modified: no real '-' body line."""
    removed = [ln[1:] for ln in _body_lines() if ln.startswith("-") and not ln.startswith("---")]
    assert removed == [], f"patch deletes/modifies existing content: {removed!r}"


@pytest.mark.unit
def test_patch_adds_only_grace_guards():
    """Every added line belongs to the 3-line grace guard, repeated 7×; the
    patch adds no service call, no target, and no id line."""
    added = [ln[1:] for ln in _body_lines() if ln.startswith("+") and not ln.startswith("+++")]
    assert added == GUARD_LINES * len(WATCHDOG_IDS), f"unexpected added lines: {added!r}"
    joined = "\n".join(added)
    assert "action:" not in joined and "service:" not in joined, "patch must add no service call"
    assert "target:" not in joined, "patch must add no target"
    assert "- id:" not in joined, "patch must add/change no automation id"


@pytest.mark.unit
def test_patch_touches_no_untargeted_automation_id():
    """No '- id:' line appears in any hunk body at all (added, removed OR
    context edited), i.e. the patch changes nothing at automation-boundary
    level and cannot alter/rename an id."""
    for ln in _body_lines():
        body = ln[1:] if ln[:1] in "+- " else ln
        assert not body.lstrip().startswith("- id:"), f"patch hunk references an id boundary: {ln!r}"


@pytest.mark.unit
@pytest.mark.parametrize("wid", WATCHDOG_IDS)
def test_each_watchdog_gains_guard_on_its_down_branch(wid):
    """The hunk carrying this watchdog's unique alert message adds the guard,
    placed after its down/problem trigger.id template and before that branch's
    sequence: — i.e. AND'd into the alert condition — and the branch still calls
    only telegram_bot.send_message."""
    needle = WATCHDOG_ALERT_MSG[wid]
    hunk = next((h for h in _hunks() if any(needle in ln for ln in h)), None)
    assert hunk is not None, f"{wid}: no hunk contains its alert message {needle!r}"

    # locate the added guard inside this hunk
    add_idx = [i for i, ln in enumerate(hunk) if ln.startswith("+") and not ln.startswith("+++")]
    assert [hunk[i][1:] for i in add_idx] == GUARD_LINES, f"{wid}: guard not added verbatim"

    # the context line immediately ABOVE the guard is the down/problem template
    above = hunk[add_idx[0] - 1]
    assert above.lstrip(" +-").startswith("value_template:") and "trigger.id ==" in above, (
        f"{wid}: guard not attached to a trigger.id branch (got {above!r})"
    )
    assert "'down'" in above or "'problem'" in above, (
        f"{wid}: guard must sit on the DOWN/alert branch, not {above!r}"
    )
    # it must NOT be a recovery / self-checking branch
    for tok in UNGUARDED_TOKENS:
        assert f"'{tok}'" not in above, f"{wid}: guard wrongly attached to '{tok}' branch"

    # the context line immediately BELOW the guard is that branch's sequence:
    below = hunk[add_idx[-1] + 1]
    assert below.lstrip(" +-").rstrip() == "sequence:", f"{wid}: guard not placed before sequence: (got {below!r})"

    # the branch's action (elsewhere in the hunk) is telegram_bot only
    actions = [ln for ln in hunk if "action:" in ln]
    assert actions, f"{wid}: hunk shows no action"
    assert all(ALLOWED_SERVICE in a for a in actions), f"{wid}: non-telegram action in branch: {actions}"


@pytest.mark.unit
def test_all_seven_hunks_uniquely_mapped():
    """Every hunk maps to exactly one target watchdog (no hunk unaccounted,
    none double-counted)."""
    hunks = _hunks()
    matched = []
    for h in hunks:
        hits = [wid for wid, msg in WATCHDOG_ALERT_MSG.items() if any(msg in ln for ln in h)]
        assert len(hits) == 1, f"hunk matched {hits} watchdogs (want exactly 1)"
        matched.append(hits[0])
    assert sorted(matched) == sorted(WATCHDOG_IDS), f"hunk→watchdog mapping incomplete: {matched}"


@pytest.mark.unit
def test_guard_is_readonly_reuse_of_grace_helper():
    """The guard READS the shared helper (state == off); it never turns it on/off
    (that stays the job of the grace manager 1789200001001)."""
    text = _patch_text()
    added = [ln[1:] for ln in _body_lines() if ln.startswith("+") and not ln.startswith("+++")]
    joined = "\n".join(added)
    assert f"entity_id: {GRACE_HELPER}" in joined
    assert "state: 'off'" in joined
    # no write to the helper anywhere in the added content
    assert "input_boolean.turn_on" not in joined and "input_boolean.turn_off" not in joined
