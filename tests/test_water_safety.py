"""Water-safety chain structural + logic tests (audit findings F1/F2/F3).

These tests parse the *actual* automations YAML the deploy would ship and assert
the three life-safety fixes are in place:

  FIX B (F1/F3): exactly one automation manages the `ha_startup_grace` lifecycle
                 (turns it ON then, after a delay, OFF); the leak automation still
                 gates on grace being off.
  FIX C (F2):    both valve-close paths (leak-v4 auto-close + the /leak_confirm
                 button handler) read the valve state back (a `wait_template` on
                 `switch.voda_kran_switch_1`) BEFORE claiming "ПОДТВЕРЖДЕНО", and
                 carry a not-confirmed CRITICAL branch. No path auto-re-opens the
                 valve.

Pure/hermetic: YAML parsing only — no network, no HA, no devices.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parent.parent
_CANDIDATES = ["scratch_automations.yaml", "automations.yaml"]

VALVE = "switch.voda_kran_switch_1"
# leak-v4 refers to the valve through a Jinja variable (`valve_entity`) set in its
# `variables:` block; the /leak_confirm handler uses the literal entity id. Either
# spelling denotes the same physical valve for our structural assertions.
VALVE_TOKENS = (VALVE, "valve_entity")
GRACE = "input_boolean.ha_startup_grace"


def _refs_valve(text: str) -> bool:
    return isinstance(text, str) and any(tok in text for tok in VALVE_TOKENS)
LEAK_V4_ID = "1748000001001"
HANDLER_ID = "1778700001005"
GRACE_MGR_ID = "1789200001001"


# --------------------------------------------------------------------------- #
# Loading helpers
# --------------------------------------------------------------------------- #
def _yaml_path() -> Path:
    for name in _CANDIDATES:
        p = _ROOT / name
        if p.exists():
            return p
    pytest.skip(f"none of {_CANDIDATES} found under {_ROOT}")


def _load() -> list[dict]:
    with _yaml_path().open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _by_id(blocks: list[dict], aid: str) -> dict:
    for b in blocks:
        if str(b.get("id")) == aid:
            return b
    raise AssertionError(f"automation id {aid} not found")


@pytest.fixture(scope="module")
def blocks() -> list[dict]:
    return _load()


# --------------------------------------------------------------------------- #
# Generic recursive walkers
# --------------------------------------------------------------------------- #
def _walk_dicts(node):
    """Yield every dict anywhere in the structure (order not guaranteed)."""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk_dicts(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_dicts(v)


def _in_order_events(seq):
    """In-order traversal of an action *sequence*, descending into choose/default/
    nested sequences, yielding tagged events so we can assert relative ordering.

    Events:
      ("wait_valve",)      a wait_template that references the valve entity
      ("msg", text)        a telegram_bot.send_message message string
    """
    if isinstance(seq, dict):
        seq = [seq]
    if not isinstance(seq, list):
        return
    for step in seq:
        if not isinstance(step, dict):
            continue
        # wait_template referencing the valve
        wt = step.get("wait_template")
        if _refs_valve(wt):
            yield ("wait_valve",)
        # a telegram message
        if step.get("action") == "telegram_bot.send_message":
            data = step.get("data") or {}
            msg = data.get("message", "")
            if isinstance(msg, str):
                yield ("msg", msg)
        # descend, preserving order
        if "choose" in step:
            for opt in step.get("choose") or []:
                yield from _in_order_events(opt.get("sequence"))
            if step.get("default") is not None:
                yield from _in_order_events(step.get("default"))
        if "sequence" in step:
            yield from _in_order_events(step.get("sequence"))


def _leak_confirm_seq(handler: dict):
    """Extract the /leak_confirm branch sequence from the callback handler."""
    for step in handler["actions"]:
        for opt in step.get("choose", []) if isinstance(step, dict) else []:
            conds = opt.get("conditions") or []
            text = " ".join(
                c.get("value_template", "") for c in conds if isinstance(c, dict)
            )
            if "/leak_confirm" in text:
                return opt["sequence"]
    raise AssertionError("/leak_confirm branch not found in handler")


def _leak_v4_autoclose_seq(leak: dict):
    """Extract the auto-close (default) shutoff sequence from leak-v4."""
    for step in leak["actions"]:
        if not isinstance(step, dict) or "choose" not in step:
            continue
        for opt in step["choose"]:
            conds = opt.get("conditions") or []
            text = " ".join(
                c.get("value_template", "") for c in conds if isinstance(c, dict)
            )
            if "leak_check" in text:
                # inside this leak_check branch there is: notify, delay, choose{...default}
                for inner in opt["sequence"]:
                    if isinstance(inner, dict) and "choose" in inner:
                        return inner.get("default")
    raise AssertionError("leak-v4 auto-close default branch not found")


# --------------------------------------------------------------------------- #
# FIX A — Telegram delivery: no life-safety notify+inline_keyboard remains
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_no_notify_send_message_carries_inline_keyboard(blocks):
    """H1: notify.send_message + inline_keyboard is rejected by HA (HTTP 400) and
    the whole message is dropped. After FIX A none may remain anywhere."""
    offenders = []
    for b in blocks:
        for d in _walk_dicts(b):
            if d.get("action") == "notify.send_message":
                data = d.get("data") or {}
                if isinstance(data, dict) and "inline_keyboard" in data:
                    offenders.append(b.get("id"))
    assert not offenders, f"notify+inline_keyboard still present in: {offenders}"


@pytest.mark.unit
@pytest.mark.parametrize("aid", ["1748000001001", "1775638334800",
                                 "1778700001005", "1779200002001",
                                 "1779200003001"])
def test_safety_automations_use_telegram_bot_for_buttons(blocks, aid):
    """Every affected safety automation now sends buttoned alerts via
    telegram_bot.send_message with an integer chat_id (never `target:`)."""
    b = _by_id(blocks, aid)
    tg_with_kbd = [
        d for d in _walk_dicts(b)
        if d.get("action") == "telegram_bot.send_message"
        and isinstance(d.get("data"), dict)
        and "inline_keyboard" in d["data"]
    ]
    assert tg_with_kbd, f"{aid} has no telegram_bot.send_message with a keyboard"
    for d in tg_with_kbd:
        # Публичный репозиторий: личный chat_id владельца тут не пиним.
        # Смысл проверки — что адресат задан целым chat_id, а НЕ через target:
        # (target: сломается в 2026.9.0). Конкретное число — дело владельца.
        cid = d["data"].get("chat_id")
        assert isinstance(cid, int) and cid > 0, "must use int chat_id"
        assert "target" not in d, "must not use deprecated target:"


# --------------------------------------------------------------------------- #
# FIX B — startup-grace lifecycle restored (F1/F3)
# --------------------------------------------------------------------------- #
def _toggles_grace(block):
    on = off = False
    for d in _walk_dicts(block):
        act = d.get("action")
        tgt = d.get("target") or {}
        ent = tgt.get("entity_id") if isinstance(tgt, dict) else None
        if ent == GRACE:
            if act == "input_boolean.turn_on":
                on = True
            elif act == "input_boolean.turn_off":
                off = True
    return on, off


@pytest.mark.unit
def test_exactly_one_automation_manages_grace_lifecycle(blocks):
    """Exactly one automation must turn ha_startup_grace ON *and* OFF."""
    managers = [b["id"] for b in blocks if all(_toggles_grace(b))]
    assert managers == [GRACE_MGR_ID], f"grace lifecycle managers: {managers}"


@pytest.mark.unit
def test_grace_manager_does_on_delay_off_in_order(blocks):
    """The grace manager runs turn_on -> delay -> turn_off, in that order,
    triggered by homeassistant start, mode: restart."""
    mgr = _by_id(blocks, GRACE_MGR_ID)
    assert mgr.get("mode") == "restart"
    trigs = mgr["triggers"]
    assert any(
        t.get("trigger") == "homeassistant" and t.get("event") == "start"
        for t in trigs
    ), "must trigger on homeassistant start"

    seq = []
    for step in mgr["actions"]:
        if step.get("action") == "input_boolean.turn_on":
            seq.append(("on", (step.get("target") or {}).get("entity_id")))
        elif "delay" in step:
            seq.append(("delay", step["delay"]))
        elif step.get("action") == "input_boolean.turn_off":
            seq.append(("off", (step.get("target") or {}).get("entity_id")))
    kinds = [k for k, _ in seq]
    assert kinds == ["on", "delay", "off"], f"unexpected action order: {kinds}"
    assert seq[0][1] == GRACE and seq[2][1] == GRACE
    assert str(seq[1][1]) == "0:15:00" or seq[1][1] == "00:15:00"


@pytest.mark.unit
def test_grace_stuck_diagnostic_exists(blocks):
    """A diagnostic automation warns (via telegram_bot) if grace stays ON >20 min."""
    diag = _by_id(blocks, "1789200001002")
    trig = diag["triggers"][0]
    assert trig.get("entity_id") == GRACE
    assert trig.get("to") == "on"
    assert str(trig.get("for")) in ("0:20:00", "00:20:00")
    tg = [d for d in _walk_dicts(diag)
          if d.get("action") == "telegram_bot.send_message"]
    assert tg, "diagnostic must notify via telegram_bot.send_message"


@pytest.mark.unit
def test_leak_v4_requires_grace_off(blocks):
    """leak-v4 must still gate leak_check on ha_startup_grace == off."""
    leak = _by_id(blocks, LEAK_V4_ID)
    cond_text = " ".join(
        c.get("value_template", "")
        for c in leak.get("conditions", [])
        if isinstance(c, dict)
    )
    assert GRACE in cond_text and "'off'" in cond_text


# --------------------------------------------------------------------------- #
# FIX C — valve close read-back (F2)
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_leak_v4_autoclose_reads_back_before_confirming(blocks):
    seq = _leak_v4_autoclose_seq(_by_id(blocks, LEAK_V4_ID))
    events = list(_in_order_events(seq))
    kinds = [e[0] for e in events]
    assert "wait_valve" in kinds, "auto-close must wait_template on the valve"
    confirmed = [
        i for i, e in enumerate(events)
        if e[0] == "msg" and "ПОДТВЕРЖДЕНО" in e[1] and "НЕ ПОДТВЕРЖДЕНО" not in e[1]
    ]
    notconf = [
        i for i, e in enumerate(events)
        if e[0] == "msg" and "НЕ ПОДТВЕРЖДЕНО" in e[1]
    ]
    assert confirmed, "must have a confirmed 'ПОДТВЕРЖДЕНО' message"
    assert notconf, "must have a not-confirmed CRITICAL branch"
    wait_idx = kinds.index("wait_valve")
    assert wait_idx < min(confirmed), "read-back must precede the confirmed message"


@pytest.mark.unit
def test_leak_confirm_handler_reads_back_before_confirming(blocks):
    seq = _leak_confirm_seq(_by_id(blocks, HANDLER_ID))
    events = list(_in_order_events(seq))
    kinds = [e[0] for e in events]
    assert "wait_valve" in kinds, "/leak_confirm must wait_template on the valve"
    confirmed = [
        i for i, e in enumerate(events)
        if e[0] == "msg" and "ПОДТВЕРЖДЕНО" in e[1] and "НЕ ПОДТВЕРЖДЕНО" not in e[1]
    ]
    notconf = [
        i for i, e in enumerate(events)
        if e[0] == "msg" and "НЕ ПОДТВЕРЖДЕНО" in e[1]
    ]
    assert confirmed and notconf
    assert kinds.index("wait_valve") < min(confirmed)


@pytest.mark.unit
@pytest.mark.parametrize("extract", ["autoclose", "leak_confirm"])
def test_no_valve_close_path_reopens_the_valve(blocks, extract):
    """Safety invariant: no close path may ever issue switch.turn_on on the valve
    (the valve is opened manually only)."""
    if extract == "autoclose":
        seq = _leak_v4_autoclose_seq(_by_id(blocks, LEAK_V4_ID))
    else:
        seq = _leak_confirm_seq(_by_id(blocks, HANDLER_ID))
    reopen = [
        d for d in _walk_dicts(seq)
        if d.get("action") == "switch.turn_on"
        and (d.get("target") or {}).get("entity_id") == VALVE
    ]
    assert not reopen, "close path must never re-open the valve"


# --------------------------------------------------------------------------- #
# FIX C — logic/trace test: valve stays 'on' after close -> CRITICAL path chosen
# --------------------------------------------------------------------------- #
def _choose_block_from(seq):
    """Return the (conditions-bearing) choose block that decides confirmed vs not."""
    for step in _flatten(seq):
        if isinstance(step, dict) and "choose" in step:
            # the read-back choose is the one whose option condition tests the valve
            for opt in step["choose"]:
                text = " ".join(
                    c.get("value_template", "")
                    for c in (opt.get("conditions") or [])
                    if isinstance(c, dict)
                )
                if _refs_valve(text) and "'off'" in text:
                    return step
    raise AssertionError("read-back choose block not found")


def _flatten(seq):
    if isinstance(seq, dict):
        seq = [seq]
    for step in seq or []:
        yield step
        if isinstance(step, dict):
            if "choose" in step:
                for opt in step["choose"]:
                    yield from _flatten(opt.get("sequence"))
                yield from _flatten(step.get("default"))
            if "sequence" in step:
                yield from _flatten(step.get("sequence"))


def _select_branch(choose_step, valve_state: str):
    """Trace-level evaluator: emulate HA `choose` for the valve read-back.

    The confirmed option's condition is `is_state(valve, 'off')`; if the valve is
    not reported 'off', HA falls through to `default`. Returns the chosen message.
    """
    for opt in choose_step["choose"]:
        text = " ".join(
            c.get("value_template", "")
            for c in (opt.get("conditions") or [])
            if isinstance(c, dict)
        )
        if _refs_valve(text) and "'off'" in text:
            # confirmed branch selected only when valve actually reports off
            if valve_state == "off":
                for s in opt["sequence"]:
                    if s.get("action") == "telegram_bot.send_message":
                        return s["data"]["message"]
    # not confirmed -> default
    default = choose_step.get("default")
    for s in _flatten(default):
        if isinstance(s, dict) and s.get("action") == "telegram_bot.send_message":
            return s["data"]["message"]
    raise AssertionError("no message resolved from choose")


@pytest.mark.unit
@pytest.mark.parametrize("valve_state,expect_confirmed", [
    ("off", True),
    ("on", False),
    ("unavailable", False),
    ("unknown", False),
])
def test_autoclose_branch_selection_by_valve_state(blocks, valve_state, expect_confirmed):
    seq = _leak_v4_autoclose_seq(_by_id(blocks, LEAK_V4_ID))
    choose = _choose_block_from(seq)
    msg = _select_branch(choose, valve_state)
    if expect_confirmed:
        assert "ПОДТВЕРЖДЕНО" in msg and "НЕ ПОДТВЕРЖДЕНО" not in msg
    else:
        # the CRITICAL not-confirmed message must be selected, and must surface
        # the live valve state to the owner for a physical check.
        assert "НЕ ПОДТВЕРЖДЕНО" in msg
        assert VALVE in msg or "states(" in msg


@pytest.mark.unit
def test_leak_confirm_branch_selection_when_valve_stuck_on(blocks):
    """Mock trace: /leak_confirm with the valve still 'on' after the close command
    must select the CRITICAL not-confirmed path (no false 'closed' assurance)."""
    seq = _leak_confirm_seq(_by_id(blocks, HANDLER_ID))
    choose = _choose_block_from(seq)
    msg = _select_branch(choose, "on")
    assert "НЕ ПОДТВЕРЖДЕНО" in msg
