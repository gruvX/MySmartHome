"""Contract tests for the safe ``/noop_test`` Telegram callback handler.

Proposal
--------
``docs/audit/noop_test.patch`` adds a *diagnostic* Telegram button, ``/noop_test``,
that proves the callback pipeline (bot -> HA -> answer) works WITHOUT touching any
device.  It is deliberately harmless and clearly non-emergency.

The patch makes two additive changes to ``/config/automations.yaml``:

1. Automation ``1778700001005`` «Telegram обработчик кнопок» (the queued handler)
   gets a new ``/noop_test`` branch whose entire sequence is a single ``stop:`` —
   this suppresses the handler's ``default:`` "unknown command" reply and its
   trailing ``answer_callback_query`` for this one command (so the command is
   answered exactly once, by automation #2, with no duplicate-answer warning and
   no "unknown command" spam).  Every existing life-safety branch is untouched.

2. A new dedicated automation ``1778700001006`` «Telegram: /noop_test» that:
   * gates to ``chat_id == 100000000`` AND ``callback_data == '/noop_test'``;
   * ALWAYS answers the callback first (clears the Telegram spinner) even when
     throttled, so a rapidly-tapped button never hangs;
   * sends the fixed confirmation text at most once per cooldown window;
   * uses ``mode: single`` + a ``this.attributes.last_triggered`` guard as the
     throttle (no new helper entities).

These tests are pure, hermetic contract tests.  They parse the *patched* copy of
``automations.yaml`` (produced by applying ``docs/audit/noop_test.patch`` to the
read-only copy fetched 2026-07-15) and assert the safety contract:

* the ``/noop_test`` logic issues NO device service call anywhere — only
  ``telegram_bot.answer_callback_query`` and ``telegram_bot.send_message``;
* the confirmation message text is EXACTLY the approved string;
* the spinner is always acknowledged (an ``answer_callback_query`` is present);
* a robust cooldown is present (``mode: single`` + ``last_triggered`` guard);
* the existing life-safety callback branches are unchanged (none removed).

No network, no HA, no devices are touched.  If the patch or the audited
automations change, regenerate the fixture (see ``_patched_automations``).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parent.parent
PATCH = REPO / "docs" / "audit" / "noop_test.patch"

HANDLER_ID = "1778700001005"          # «Telegram обработчик кнопок» (queued)
NOOP_ID = "1778700001006"             # new dedicated /noop_test automation
CHAT_ID = 100000000

# The one message the noop button is allowed to send — must match byte-for-byte.
APPROVED_TEXT = "✅ Тестовая кнопка работает. Действия с домом не выполнялись."

# The ONLY service calls the noop feature may ever make.
ALLOWED_SERVICES = {
    "telegram_bot.answer_callback_query",
    "telegram_bot.send_message",
}

# Life-safety callback branches that MUST survive untouched in the handler.
LIFE_SAFETY_CALLBACKS = {
    "/security_arm", "/security_disarm", "/siren_off", "/siren_alarm",
    "/leak_confirm", "/moisture_false_alarm", "/ev_stop", "/ev_start",
    "/patrol_off_yes", "/patrol_off_no",
}


# --------------------------------------------------------------------------- #
# Fixtures — reconstruct the patched automations.yaml from the checked-in copy
# --------------------------------------------------------------------------- #
def _read_original() -> str | None:
    """Return the read-only base automations.yaml text if one is available.

    Priority:
      1. ``NOOP_BASE_AUTOMATIONS`` env var pointing at a copy on disk.
      2. The reversed patch applied to nothing — not possible; so if no base is
         found we return None and dependent tests are skipped.  (The base file is
         not committed to the public repo for secret-hygiene reasons.)
    """
    env = os.environ.get("NOOP_BASE_AUTOMATIONS")
    if env and Path(env).is_file():
        return Path(env).read_text(encoding="utf-8")
    # Common scratch locations used while producing the patch.
    for cand in (
        REPO / "docs" / "audit" / "automations.yaml",
        REPO / "backups" / "automations.yaml",
    ):
        if cand.is_file():
            return cand.read_text(encoding="utf-8")
    return None


def _apply_patch(original: str) -> str:
    """Apply docs/audit/noop_test.patch to *original* text, return patched text."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        target = Path(d) / "automations.yaml"
        target.write_text(original, encoding="utf-8")
        res = subprocess.run(
            ["patch", "-p1", "--force", str(target)],
            input=PATCH.read_text(encoding="utf-8"),
            text=True,
            capture_output=True,
            cwd=d,
        )
        if res.returncode != 0:
            raise RuntimeError(f"patch failed: {res.stdout}\n{res.stderr}")
        return target.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def _patched_automations():
    """The full patched automations list (base + noop_test.patch), or skip."""
    base = _read_original()
    if base is None:
        pytest.skip(
            "base automations.yaml not available (fetch read-only and set "
            "NOOP_BASE_AUTOMATIONS=/path/to/automations.yaml to run these). "
            "Patch-level structure tests still run against the diff itself."
        )
    patched = _apply_patch(base)
    data = yaml.safe_load(patched)
    assert isinstance(data, list), "automations.yaml must be a list of automations"
    return {a.get("id"): a for a in data if isinstance(a, dict)}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _service_calls(node) -> list[str]:
    """Recursively collect every ``action:``/``service:`` string under *node*."""
    found: list[str] = []

    def walk(n) -> None:
        if isinstance(n, dict):
            for key in ("action", "service"):
                v = n.get(key)
                if isinstance(v, str):
                    found.append(v)
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for x in n:
                walk(x)

    walk(node)
    return found


def _choose_branches(automation: dict) -> list[dict]:
    branches: list[dict] = []
    for act in automation.get("actions", []) or []:
        if isinstance(act, dict) and "choose" in act:
            for br in act["choose"] or []:
                if isinstance(br, dict):
                    branches.append(br)
    return branches


def _branch_callbacks(branch: dict) -> str:
    return " ".join(
        c.get("value_template", "")
        for c in branch.get("conditions", []) or []
        if isinstance(c, dict)
    )


# --------------------------------------------------------------------------- #
# Tests that need the patched automations (skipped if base file absent)
# --------------------------------------------------------------------------- #
def test_dedicated_noop_automation_exists(_patched_automations):
    assert NOOP_ID in _patched_automations, (
        f"dedicated /noop_test automation {NOOP_ID} missing after patch"
    )


def test_noop_issues_no_device_command(_patched_automations):
    """The whole noop feature may ONLY call the two telegram_bot ack services."""
    noop = _patched_automations[NOOP_ID]
    calls = _service_calls(noop.get("actions", []))
    unexpected = [c for c in calls if c not in ALLOWED_SERVICES]
    assert not unexpected, (
        f"/noop_test automation makes non-ack service calls: {unexpected}. "
        "It must never touch water/siren/security/switch/climate/helpers."
    )
    # And the handler's /noop_test branch must have ZERO service calls (just stop).
    handler = _patched_automations[HANDLER_ID]
    noop_branch = [
        b for b in _choose_branches(handler) if "/noop_test" in _branch_callbacks(b)
    ]
    assert len(noop_branch) == 1, "expected exactly one /noop_test branch in handler"
    branch_calls = _service_calls(noop_branch[0].get("sequence", []))
    assert branch_calls == [], (
        f"handler /noop_test branch must issue no service calls, got {branch_calls}"
    )


def test_noop_acknowledges_callback(_patched_automations):
    """The spinner must always be cleared -> an answer_callback_query is present."""
    noop = _patched_automations[NOOP_ID]
    calls = _service_calls(noop.get("actions", []))
    assert "telegram_bot.answer_callback_query" in calls, (
        "/noop_test must answer the callback query to clear the Telegram spinner"
    )


def test_noop_sends_only_approved_text(_patched_automations):
    """Any send_message in the noop automation must use the approved text exactly."""
    noop = _patched_automations[NOOP_ID]

    messages: list[str] = []

    def collect(n):
        if isinstance(n, dict):
            if n.get("action") == "telegram_bot.send_message":
                data = n.get("data", {}) or {}
                messages.append(data.get("message"))
            for v in n.values():
                collect(v)
        elif isinstance(n, list):
            for x in n:
                collect(x)

    collect(noop.get("actions", []))
    assert messages, "expected the noop automation to contain a confirmation message"
    for msg in messages:
        assert msg == APPROVED_TEXT, (
            f"noop send_message text {msg!r} != approved {APPROVED_TEXT!r}"
        )


def test_noop_has_robust_cooldown(_patched_automations):
    """Cooldown must be HA-native: mode:single + a last_triggered throttle guard."""
    noop = _patched_automations[NOOP_ID]
    assert noop.get("mode") == "single", (
        "cooldown relies on mode:single to drop concurrent duplicate taps"
    )
    blob = yaml.safe_dump(noop, allow_unicode=True)
    assert "last_triggered" in blob, (
        "expected a last_triggered-based throttle guard for the send_message"
    )


def test_noop_gated_to_owner_and_command(_patched_automations):
    """The automation must fire only for the owner chat AND only for /noop_test."""
    noop = _patched_automations[NOOP_ID]
    conds = yaml.safe_dump(noop.get("conditions", []), allow_unicode=True)
    assert str(CHAT_ID) in conds, "must gate on the owner chat_id"
    assert "/noop_test" in conds, "must gate on callback_data == '/noop_test'"


def test_existing_life_safety_branches_unchanged(_patched_automations):
    """The patch must not remove/alter any existing life-safety callback branch."""
    handler = _patched_automations[HANDLER_ID]
    present = set()
    for br in _choose_branches(handler):
        vt = _branch_callbacks(br)
        for cb in LIFE_SAFETY_CALLBACKS:
            if f"'{cb}'" in vt or f'"{cb}"' in vt:
                present.add(cb)
    missing = LIFE_SAFETY_CALLBACKS - present
    assert not missing, f"life-safety branches missing after patch: {sorted(missing)}"


def test_patched_yaml_parses(_patched_automations):
    """Applying the patch must yield a still-parseable automations list."""
    assert HANDLER_ID in _patched_automations
    assert NOOP_ID in _patched_automations


# --------------------------------------------------------------------------- #
# Tests on the patch artifact itself (always run; no base file needed)
# --------------------------------------------------------------------------- #
def test_patch_file_exists_and_is_additive():
    assert PATCH.is_file(), f"missing patch: {PATCH}"
    text = PATCH.read_text(encoding="utf-8")
    added = [
        ln
        for ln in text.splitlines()
        if ln.startswith("+") and not ln.startswith("+++")
    ]
    removed = [
        ln
        for ln in text.splitlines()
        if ln.startswith("-") and not ln.startswith("---")
    ]
    assert added, "patch adds nothing"
    assert not removed, (
        f"patch must be purely additive but removes lines: {removed}"
    )


def test_patch_targets_only_automations_yaml():
    text = PATCH.read_text(encoding="utf-8")
    file_headers = [ln for ln in text.splitlines() if ln.startswith("+++ ")]
    assert file_headers, "no target file header in patch"
    for h in file_headers:
        assert h.endswith("automations.yaml"), f"unexpected patch target: {h}"


def test_patch_carries_deploy_and_rollback_note():
    text = PATCH.read_text(encoding="utf-8").upper()
    assert "DEPLOY PLAN" in text, "patch header must include a deploy plan"
    assert "ROLLBACK" in text, "patch header must include a rollback plan"
    assert "NOT APPLIED" in text, "patch must warn it is a proposal, not applied"


def test_patch_added_lines_have_no_device_service_calls():
    """No added '+' line may introduce a device-touching service call."""
    text = PATCH.read_text(encoding="utf-8")
    banned = (
        "switch.turn_on", "switch.turn_off",
        "siren.turn_on", "siren.turn_off",
        "input_boolean.turn_on", "input_boolean.turn_off",
        "script.turn_on", "climate.", "number.set_value",
        "select.select_option", "homeassistant.turn_on", "homeassistant.turn_off",
        "valve.", "cover.", "light.turn_on", "light.turn_off",
    )
    offenders = []
    for ln in text.splitlines():
        if not ln.startswith("+") or ln.startswith("+++"):
            continue
        low = ln.lower()
        if low.lstrip("+ ").startswith("#"):  # skip comment lines
            continue
        for b in banned:
            if b in low:
                offenders.append(ln.strip())
    assert not offenders, (
        f"patch introduces device service calls in the noop path: {offenders}"
    )


def test_patch_added_message_text_is_approved():
    """The only confirmation string the patch adds must be the approved text."""
    text = PATCH.read_text(encoding="utf-8")
    assert APPROVED_TEXT in text, "approved confirmation text absent from patch"
