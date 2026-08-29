# -*- coding: utf-8 -*-
"""Locks the 2026-08-19 fix for "the EV did not charage overnight, three times".

INCIDENT
--------
input_datetime.ev_charge_start history:
    08-18 18:23:40 -> 2026-08-19 03:45:00   (owner requested the night charge)
    08-18 19:49:47 -> 2026-08-19 14:15:00   (planner overwrote it 1h26m later)

At 03:45 the helper held 14:15, so automation 1778800001002 ("EV автозарядка 2ч",
trigger ``time at: input_datetime.ev_charge_start``) never fired. The independent
watchdog 1790100001001 waited on the SAME helper, so it never fired either and the
owner got no warning at all.

The overwriter is the planner 1778800001001 via ev_best2h.py. Its old guard
protected HOURS OF THE DAY (22:00-08:00) instead of protecting an explicitly
requested night charge, and the owner sets night charges in the evening (18:23),
so the planner was free to clobber it between 18:23 and 22:00 -- and did.

FIX UNDER TEST
--------------
* input_boolean.ev_night_requested makes an explicit night request sticky.
* The planner gets a hard condition that applies to ALL its trigger ids
  (price_update, ha_start, daily_14h), degrading OPEN if a helper is missing.
* input_datetime.ev_night_window_start records the requested window so the
  watchdog has a stable reference that the planner cannot silently re-arm.
* The flag doubles as the "verdict not yet delivered" token, which is what
  guarantees EXACTLY ONE Telegram message per request.
"""
from __future__ import annotations

import datetime
import difflib
import hashlib
import importlib.util
import io
import re
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "tests" / "fixtures" / "ev_night_automations.yaml"
BASELINE = REPO / "docs" / "audit" / "ev_night2h.deployed_baseline.py"
PATCHED = REPO / "docs" / "audit" / "ev_night2h.deployed_patched.py"

# md5 of /config/ev_night2h.py BEFORE this fix, and of the artifact this fix
# produced. Both are HISTORICAL: the 2026-08-19 auto-charge package moved the
# night window to 23:00-07:00 and made the confirmation unconditional, so the
# live file is newer (see tests/test_ev_auto_daily.py, which locks that step
# against docs/audit/ev_night2h.deployed_v2.py). These two constants keep
# guarding the property THIS fix had to have: it removed no deployed line.
DEPLOYED_BASELINE_MD5 = "484da629ce171726964780666d5423f6"
DEPLOYED_PATCHED_MD5 = "f396c59ac57238751e14f227a9e1b1c5"

# .gitignore keeps verbatim copies of deployed scripts LOCAL ("*deployed_baseline*",
# "*deployed_patched*"); only the human-readable .diff is committed. So the
# script-level tests below skip in a clean clone, while the automation-level tests
# — which carry the actual behavioural lock — always run against the committed
# fixture tests/fixtures/ev_night_automations.yaml.
_have_scripts = BASELINE.is_file() and PATCHED.is_file()
needs_scripts = pytest.mark.skipif(
    not _have_scripts,
    reason=("verbatim deployed copies are gitignored (kept local by owner policy); "
            "see docs/audit/ev_night_sticky_request.diff for the committed diff"),
)

PLANNER = "1778800001001"
CHARGER = "1778800001002"
WATCHDOG = "1790100001001"
LIFECYCLE = "1790500001001"

FLAG = "input_boolean.ev_night_requested"
WINDOW = "input_datetime.ev_night_window_start"
SEEN = "input_datetime.ev_night_charge_seen"
SCHED = "input_datetime.ev_charge_start"

# Sticky-request expiry: window start + 3h (= window end + 1h).
EXPIRY_SECONDS = 10800


@pytest.fixture(scope="module")
def autos() -> dict:
    data = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    return {str(a["id"]): a for a in data}


def _walk(node):
    """Yield every dict in a nested structure."""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _templates(node):
    """Yield every template string found anywhere in the structure."""
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, str) and "{{" in v or (isinstance(v, str) and "{%" in v):
                yield k, v
            else:
                yield from _templates(v)
    elif isinstance(node, list):
        for v in node:
            yield from _templates(v)


# --------------------------------------------------------------------------- #
# 1. The deployed standalone script: pure-addition patch, correct write order
# --------------------------------------------------------------------------- #
@needs_scripts
@pytest.mark.unit
def test_deployed_baseline_and_patched_md5():
    assert hashlib.md5(BASELINE.read_bytes()).hexdigest() == DEPLOYED_BASELINE_MD5
    assert hashlib.md5(PATCHED.read_bytes()).hexdigest() == DEPLOYED_PATCHED_MD5


@needs_scripts
@pytest.mark.unit
def test_patch_removes_no_deployed_lines():
    """The night-request patch must be a pure superset of the deployed script."""
    base = BASELINE.read_text(encoding="utf-8").splitlines()
    patched = PATCHED.read_text(encoding="utf-8").splitlines()
    removed = [
        line[1:]
        for line in difflib.unified_diff(base, patched, lineterm="")
        if line.startswith("-") and not line.startswith("---")
    ]
    assert removed == [], f"patch removed deployed lines: {removed}"


@needs_scripts
@pytest.mark.unit
def test_window_helper_is_written_before_the_schedule():
    """Order matters: the stable window reference must be written BEFORE
    ev_charge_start, so the overwrite detector sees the two agree and does not
    raise a false alarm on our own write."""
    src = PATCHED.read_text(encoding="utf-8")
    i_window = src.index(WINDOW)
    i_seen = src.index(SEEN)
    i_sched = src.index('"entity_id": "input_datetime.ev_charge_start"')
    i_flag = src.index(FLAG)
    assert i_window < i_sched, "window reference written after the schedule"
    assert i_seen < i_sched, "charge-seen reset written after the schedule"
    assert i_flag > i_sched, "sticky flag armed before the schedule write was checked"


class _ReconfigurableIO(io.StringIO):
    def reconfigure(self, *a, **k):
        return None


def _load_patched():
    spec = importlib.util.spec_from_file_location("ev_night_patched", PATCHED)
    mod = importlib.util.module_from_spec(spec)
    old = sys.stdout
    sys.stdout = _ReconfigurableIO()
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.stdout = old
    return mod


def _run(sched_status: int):
    """Run main() with every HA/Elering call stubbed. No network, no devices."""
    mod = _load_patched()
    calls: list[tuple[str, dict]] = []

    def fake_post(path, data):
        calls.append((path, dict(data)))
        if path.endswith("set_datetime") and data.get("entity_id") == SCHED:
            return sched_status
        return 200

    mod.ha_post = fake_post
    mod.ha_get = lambda path: {"state": "2026-08-18 09:00:00"}
    base = datetime.datetime(2026, 8, 19, 0, 45, tzinfo=datetime.timezone.utc)
    mod.fetch_lv_prices = lambda: [
        {"dt": base + datetime.timedelta(minutes=15 * i), "price": 0.01}
        for i in range(8)
    ]

    class Frozen(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.datetime(2026, 8, 18, 15, 23, tzinfo=datetime.timezone.utc)

    mod.datetime.datetime = Frozen
    code = None
    old = sys.stdout
    sys.stdout = _ReconfigurableIO()
    try:
        mod.main()
    except SystemExit as exc:
        code = exc.code
    finally:
        sys.stdout = old
    return calls, code


def _entities(calls, service_suffix):
    return [d.get("entity_id") for p, d in calls if p.endswith(service_suffix)]


@needs_scripts
@pytest.mark.unit
def test_success_path_arms_the_request_in_the_right_order():
    calls, code = _run(200)
    assert code is None
    written = _entities(calls, "input_datetime/set_datetime")
    assert written == [WINDOW, SEEN, SCHED], written
    assert _entities(calls, "input_boolean/turn_on") == [FLAG]
    # the schedule and the stable reference must carry the SAME datetime
    vals = {d["entity_id"]: d.get("datetime") for p, d in calls
            if p.endswith("input_datetime/set_datetime")}
    assert vals[WINDOW] == vals[SCHED] == "2026-08-19 03:45:00"
    assert vals[SEEN] == "1970-01-01 00:00:00"


@needs_scripts
@pytest.mark.unit
def test_failed_schedule_write_does_not_arm_the_request():
    """A request with no schedule would block the planner for nothing."""
    calls, code = _run(500)
    assert code == 1
    assert _entities(calls, "input_boolean/turn_on") == []
    notified = [d for p, d in calls if p.endswith("notify/send_message")]
    assert len(notified) == 1
    assert "Заявка НЕ поставлена" in notified[0]["message"]


@needs_scripts
@pytest.mark.unit
def test_reproduces_the_incident_window():
    """18.08 18:23 local really does resolve to the 19.08 03:45 window."""
    calls, _ = _run(200)
    vals = [d.get("datetime") for p, d in calls
            if p.endswith("input_datetime/set_datetime") and d["entity_id"] == SCHED]
    assert vals == ["2026-08-19 03:45:00"]


# --------------------------------------------------------------------------- #
# 2. The planner condition — applies to ALL triggers, degrades OPEN
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_planner_still_has_its_three_original_triggers(autos):
    """The three the sticky guard was written for must all still be there.

    2026-08-19 added two more (``tomorrow_published`` when the day-ahead prices
    publish, and the hourly ``periodic`` safety net for a plan that went stale).
    Both are equally covered: the night/day-request guard below is asserted NOT to
    mention ``trigger.id`` at all, so it applies to every trigger the planner ever
    grows.
    """
    ids = {t["id"] for t in autos[PLANNER]["triggers"]}
    assert {"price_update", "ha_start", "daily_14h"} <= ids
    assert ids == {"price_update", "ha_start", "daily_14h",
                   "tomorrow_published", "periodic"}


@pytest.mark.unit
def test_planner_night_guard_is_not_gated_on_trigger_id(autos):
    """The old guard only protected price_update. The bug also reached the plan
    through ha_start (any restart) and the 14:05 run, so the new guard must not
    mention trigger.id at all."""
    guard = autos[PLANNER]["conditions"][0]["value_template"]
    assert "trigger.id" not in guard, "night guard must apply to every trigger"
    assert FLAG in guard
    assert WINDOW in guard
    assert str(EXPIRY_SECONDS) in guard


@pytest.mark.unit
def test_planner_keeps_its_original_hour_guard(autos):
    """The pre-existing 08-22 rule must survive untouched."""
    kept = autos[PLANNER]["conditions"][1]["value_template"]
    assert kept == "{{ trigger.id != 'price_update' or (8 <= now().hour < 22) }}"


@pytest.mark.unit
def test_planner_guard_degrades_open_when_helpers_are_missing(autos):
    """A missing helper must let the planner run (today's behaviour), never error.

    states() returns 'unknown' for a missing entity, so `req == 'on'` is False;
    state_attr() returns None, so `| float(0)` is 0 and `ws > 0` is False. Either
    way the guard is `not (False and ...)` -> True -> the planner runs.
    """
    guard = autos[PLANNER]["conditions"][0]["value_template"]
    assert "| float(0)" in guard, "window timestamp must be float-coerced"
    assert re.search(r"ws\s*\|\s*float\(0\)\s*\)?\s*>\s*0|ws\s*>\s*0", guard), guard
    assert "not (" in guard.replace("\n", " ")


@pytest.mark.unit
def test_planner_guard_expires_so_a_stuck_flag_cannot_wedge_it(autos):
    """The guard is bounded by the RECORDED window, not by the flag alone, so a
    flag stuck ON stops mattering at window start + 3h."""
    guard = autos[PLANNER]["conditions"][0]["value_template"]
    assert "now().timestamp()" in guard
    assert str(EXPIRY_SECONDS) in guard


# --------------------------------------------------------------------------- #
# 3. The watchdog — stable reference, and only one branch owns the verdict
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_watchdog_gains_a_trigger_on_the_stable_window_helper(autos):
    """It used to wait only on ev_charge_start, which silently re-armed when the
    planner changed the value -- that is why it never warned the owner."""
    trigs = autos[WATCHDOG]["triggers"]
    at = {t.get("at"): t.get("id") for t in trigs if t.get("trigger") == "time"}
    assert at.get(SCHED) == "planned_start", at
    assert at.get(WINDOW) == "night_planned_start", at


@pytest.mark.unit
def test_watchdog_delays_ten_minutes_for_both_planned_start_triggers(autos):
    gate = autos[WATCHDOG]["actions"][0]
    ids = gate["if"][0]["id"]
    assert set(ids) == {"planned_start", "night_planned_start"}, ids
    assert gate["then"][0]["delay"] == "00:10:00"


def _branches(autos, aid):
    for act in autos[aid]["actions"]:
        if isinstance(act, dict) and "choose" in act:
            return act["choose"]
    raise AssertionError("no choose block in " + aid)


@pytest.mark.unit
def test_old_watchdog_branch_yields_to_the_night_branch(autos):
    """Both time triggers fire at once when the two helpers agree. Without this
    guard the owner would get two messages about one event."""
    branch = next(b for b in _branches(autos, WATCHDOG)
                  if b["alias"] == "Плановый старт был, а зарядки нет")
    guards = [c.get("value_template", "") for c in branch["conditions"]]
    assert any(FLAG in g and "not is_state" in g for g in guards), guards


@pytest.mark.unit
def test_night_branch_sends_one_message_then_clears_the_flag(autos):
    branch = next(b for b in _branches(autos, WATCHDOG)
                  if b["alias"].startswith("Ночная заявка — плановый старт"))
    sends = [a for a in branch["sequence"]
             if a.get("action") == "telegram_bot.send_message"]
    offs = [a for a in branch["sequence"]
            if a.get("action") == "input_boolean.turn_off"]
    assert len(sends) == 1
    assert len(offs) == 1
    assert offs[0]["target"]["entity_id"] == FLAG
    # the flag must be turned off AFTER the message, so a send failure retries
    assert branch["sequence"].index(sends[0]) < branch["sequence"].index(offs[0])


@pytest.mark.unit
def test_night_branch_requires_the_flag_and_absence_of_charging(autos):
    branch = next(b for b in _branches(autos, WATCHDOG)
                  if b["alias"].startswith("Ночная заявка — плановый старт"))
    conds = " ".join(c.get("value_template", "") for c in branch["conditions"])
    assert FLAG in conds
    assert "charger_charging" in conds


# --------------------------------------------------------------------------- #
# 4. The lifecycle automation — clear rule, expiry, and never-silent guarantee
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_lifecycle_has_the_four_triggers(autos):
    ids = {t["id"] for t in autos[LIFECYCLE]["triggers"]}
    assert ids == {"charging", "completed", "overwritten", "sweep"}


@pytest.mark.unit
def test_lifecycle_watches_the_schedule_helper_for_overwrites(autos):
    trig = next(t for t in autos[LIFECYCLE]["triggers"] if t["id"] == "overwritten")
    assert trig["entity_id"] == SCHED


@pytest.mark.unit
def test_completion_clear_mirrors_ev_manual_mode_reset(autos):
    """1748000001006 resets ev_manual_mode on charger_end/charger_free; the night
    request clears on the same signals."""
    trig = next(t for t in autos[LIFECYCLE]["triggers"] if t["id"] == "completed")
    assert set(trig["to"]) == {"charger_end", "charger_free"}


@pytest.mark.unit
def test_completion_clear_only_applies_once_the_window_has_started(autos):
    """Without this gate a charger_free BEFORE the window (car not yet plugged in
    at request time) would clear the request instantly and the bug would return."""
    branch = next(b for b in _branches(autos, LIFECYCLE)
                  if b["alias"].startswith("Зарядка завершена"))
    conds = " ".join(c.get("value_template", "") for c in branch["conditions"])
    assert "now().timestamp() >=" in conds


@pytest.mark.unit
def test_sweep_expiry_is_window_start_plus_three_hours(autos):
    branch = next(b for b in _branches(autos, LIFECYCLE)
                  if "поздний вердикт" in b["alias"])
    conds = " ".join(c.get("value_template", "") for c in branch["conditions"])
    assert str(EXPIRY_SECONDS) in conds
    assert "now().timestamp() >" in conds


@pytest.mark.unit
def test_sweep_always_clears_the_flag_even_when_it_stays_silent(autos):
    """A stuck flag must not disable the planner forever."""
    branch = next(b for b in _branches(autos, LIFECYCLE)
                  if "поздний вердикт" in b["alias"])
    tail = branch["sequence"][-1]
    assert tail["action"] == "input_boolean.turn_off"
    assert tail["target"]["entity_id"] == FLAG
    # the message lives behind an `if`, the clear does not
    assert "if" in branch["sequence"][0]


@pytest.mark.unit
def test_sweep_only_reports_when_charging_was_never_observed(autos):
    branch = next(b for b in _branches(autos, LIFECYCLE)
                  if "поздний вердикт" in b["alias"])
    guard = branch["sequence"][0]["if"][0]["value_template"]
    assert "seen" in guard and "ws" in guard


# Branches that deliver a night-request VERDICT. Each must send exactly one
# message and then clear the flag, because the flag is the token that guarantees
# the owner hears about a failed night charge exactly once.
VERDICT_BRANCHES = {
    (WATCHDOG, "Ночная заявка — плановый старт был, а зарядки нет"),
    (LIFECYCLE, "Плановое время перезаписано поверх активной заявки — РОВНО одно сообщение"),
    (LIFECYCLE, "Окно прошло — поздний вердикт и срок истечения заявки"),
}

# Branches that must NOT touch the flag: pre-existing watchdog logic that the fix
# deliberately leaves alone.
NON_VERDICT_BRANCHES = {
    (WATCHDOG, "Плановый старт был, а зарядки нет"),
    (WATCHDOG, "Зарядка идёт дольше планового окна"),
}


def _branch(autos, aid, alias):
    for b in _branches(autos, aid):
        if b["alias"] == alias:
            return b
    raise AssertionError(f"branch {alias!r} not found in {aid}")


@pytest.mark.unit
def test_every_verdict_branch_sends_once_then_clears_the_flag(autos):
    """The flag is the "verdict not yet delivered" token: whichever branch speaks
    turns it off, so the owner gets EXACTLY ONE message per night request."""
    for aid, alias in VERDICT_BRANCHES:
        branch = _branch(autos, aid, alias)
        seq = branch["sequence"]
        sends = [d for d in _walk(seq)
                 if d.get("action") == "telegram_bot.send_message"]
        clears = [d for d in _walk(seq)
                  if d.get("action") == "input_boolean.turn_off"
                  and d.get("target", {}).get("entity_id") == FLAG]
        assert len(sends) == 1, f"{alias}: {len(sends)} sends"
        assert len(clears) == 1, f"{alias}: {len(clears)} flag clears"


@pytest.mark.unit
def test_verdict_branches_clear_the_flag_after_sending(autos):
    """Clearing first would lose the verdict if the Telegram call failed."""
    for aid, alias in VERDICT_BRANCHES:
        seq = _branch(autos, aid, alias)["sequence"]
        # top-level index of the step containing the send vs the clear
        def idx(pred):
            for i, step in enumerate(seq):
                if any(pred(d) for d in _walk(step)):
                    return i
            raise AssertionError(f"{alias}: step not found")
        i_send = idx(lambda d: d.get("action") == "telegram_bot.send_message")
        i_clear = idx(lambda d: d.get("action") == "input_boolean.turn_off"
                      and d.get("target", {}).get("entity_id") == FLAG)
        assert i_send < i_clear, f"{alias}: flag cleared before the message was sent"


@pytest.mark.unit
def test_pre_existing_watchdog_branches_do_not_touch_the_flag(autos):
    """The fix must not change what the old branches do."""
    for aid, alias in NON_VERDICT_BRANCHES:
        seq = _branch(autos, aid, alias)["sequence"]
        clears = [d for d in _walk(seq)
                  if d.get("action") in ("input_boolean.turn_off", "input_boolean.turn_on")
                  and d.get("target", {}).get("entity_id") == FLAG]
        assert clears == [], f"{alias} unexpectedly writes {FLAG}"


@pytest.mark.unit
def test_no_other_branch_sends_a_night_verdict(autos):
    """Guards against a future edit adding a second message path for one request."""
    found = set()
    for aid in (WATCHDOG, LIFECYCLE):
        for b in _branches(autos, aid):
            seq = b.get("sequence", [])
            if any(d.get("action") == "input_boolean.turn_off"
                   and d.get("target", {}).get("entity_id") == FLAG
                   for d in _walk(seq)) and any(
                   d.get("action") == "telegram_bot.send_message" for d in _walk(seq)):
                found.add((aid, b["alias"]))
    assert found == VERDICT_BRANCHES, found ^ VERDICT_BRANCHES


@pytest.mark.unit
def test_lifecycle_never_commands_a_device(autos):
    """This automation must only touch helpers and Telegram."""
    allowed = {
        "input_boolean.turn_off", "input_boolean.turn_on",
        "input_datetime.set_datetime", "telegram_bot.send_message",
    }
    used = {d["action"] for d in _walk(autos[LIFECYCLE]) if "action" in d}
    assert used <= allowed, used - allowed


@pytest.mark.unit
def test_lifecycle_is_queued_so_the_flag_check_serialises(autos):
    """Parallel mode would let two triggers both pass the flag check and send
    two messages."""
    assert autos[LIFECYCLE]["mode"] == "queued"
    assert autos[LIFECYCLE]["max"] >= 2


# --------------------------------------------------------------------------- #
# 5. Telegram discipline — the bot entry defaults to markdown and silently
#    rejects any message containing a bare entity_id.
# --------------------------------------------------------------------------- #
ENTITY_RE = re.compile(
    r"\b(?:sensor|switch|input_boolean|input_datetime|binary_sensor|climate|"
    r"automation|script)\.[a-z0-9_]+"
)


@pytest.mark.unit
def test_all_new_telegram_messages_declare_parse_mode_html(autos):
    for aid in (WATCHDOG, LIFECYCLE):
        for node in _walk(autos[aid]):
            if node.get("action") == "telegram_bot.send_message":
                data = node.get("data", {})
                assert data.get("parse_mode") == "html", (
                    f"{aid}: telegram message without parse_mode html"
                )


@pytest.mark.unit
def test_entity_ids_in_message_text_are_wrapped_in_code_tags(autos):
    """A bare entity_id makes Telegram reject the whole message."""
    for aid in (WATCHDOG, LIFECYCLE):
        for node in _walk(autos[aid]):
            if node.get("action") != "telegram_bot.send_message":
                continue
            msg = node["data"]["message"]
            # strip Jinja so we only inspect literal prose
            prose = re.sub(r"\{[%{].*?[%}]\}", "", msg, flags=re.S)
            for m in ENTITY_RE.finditer(prose):
                start, end = m.span()
                window = prose[max(0, start - 8):end + 9]
                assert "<code>" in window and "</code>" in window, (
                    f"{aid}: bare entity_id {m.group(0)!r} in message text"
                )


@pytest.mark.unit
def test_new_messages_escape_every_state_interpolation(autos):
    """Free text must go through `| e`. Scoped to the messages this fix adds --
    the pre-existing branches are deliberately byte-identical.

    `cause` and `stale_note` are exempt because they are composed with `| e`
    applied to each state value at construction time (see the shared jinja
    preamble); escaping them again would double-escape.
    """
    # Composed strings, exempt for different reasons:
    #   cause / stale_note - embed state values already passed through `| e`
    #   who                - built from literal prose only (asserted below)
    PRE_ESCAPED = {"cause", "stale_note", "who"}
    checked = 0
    for aid, alias in VERDICT_BRANCHES:
        for node in _walk(_branch(autos, aid, alias)["sequence"]):
            if node.get("action") != "telegram_bot.send_message":
                continue
            msg = node["data"]["message"]
            preamble, _, body = msg.rpartition("-%}")
            for expr in re.findall(r"\{\{(.*?)\}\}", body, flags=re.S):
                token = expr.strip()
                if token in PRE_ESCAPED:
                    continue
                assert "| e" in expr, f"{alias}: unescaped interpolation {token!r}"
                checked += 1
    assert checked >= 6, f"expected several escaped interpolations, saw {checked}"


@pytest.mark.unit
def test_cause_and_stale_note_escape_their_inputs(autos):
    """The two composed strings must escape the state values they embed."""
    branch = _branch(autos, WATCHDOG,
                     "Ночная заявка — плановый старт был, а зарядки нет")
    msg = branch["sequence"][0]["data"]["message"]
    # the fallback that embeds a raw status string
    assert "'статус ' ~ (s | e)" in msg
    # the source attribute embedded in the staleness note
    assert "| e) ~ ', возраст '" in msg


@pytest.mark.unit
def test_who_is_composed_from_literal_prose_only(autos):
    """`who` is emitted without `| e`, so it must never embed a context id or
    state value -- it only classifies the writer."""
    branch = _branch(autos, LIFECYCLE,
                     "Плановое время перезаписано поверх активной заявки — РОВНО одно сообщение")
    msg = branch["sequence"][0]["data"]["message"]
    who_block = re.findall(r"set who = ([^-]*?)-%\}", msg, flags=re.S)
    assert who_block, "no `who` assignments found"
    for assignment in who_block:
        assert "~" not in assignment, f"who concatenates a value: {assignment!r}"
        for forbidden in ("user_id", "parent_id", "states(", "state_attr("):
            assert forbidden not in assignment, (
                f"who embeds {forbidden} unescaped: {assignment!r}")


@pytest.mark.unit
def test_new_messages_distinguish_stale_data_from_a_real_cause(autos):
    """Requirement: never report a confident failure cause from stale Tuya data,
    and distinguish it from charger_free / charger_pause / charger_end."""
    for aid, alias in VERDICT_BRANCHES:
        for node in _walk(_branch(autos, aid, alias)["sequence"]):
            if node.get("action") != "telegram_bot.send_message":
                continue
            msg = node["data"]["message"]
            if "перебита" in msg:
                continue  # the overwrite verdict has a known cause, not a status
            assert "нет свежих данных от зарядки" in msg, alias
            assert "charger_free" in msg and "машина не подключена" in msg, alias
            assert "charger_pause" in msg and "зарядка на паузе" in msg, alias
            assert "charger_end" in msg and "зарядка уже завершена" in msg, alias
            assert "stale_age" in msg, f"{alias}: staleness not consulted"


# --------------------------------------------------------------------------- #
# 6. Nothing else moved
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_charger_automation_still_triggers_on_the_schedule_helper(autos):
    """1778800001002 is deliberately left byte-identical; it must keep waiting on
    ev_charge_start, which the fix now protects instead of replacing."""
    trigs = autos[CHARGER]["triggers"]
    assert len(trigs) == 1
    assert trigs[0]["at"] == SCHED


@pytest.mark.unit
def test_fixture_matches_the_deployed_automation_ids(autos):
    assert set(autos) == {PLANNER, CHARGER, WATCHDOG, LIFECYCLE}
