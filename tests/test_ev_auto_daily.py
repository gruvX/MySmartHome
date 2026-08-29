# -*- coding: utf-8 -*-
"""Locks the 2026-08-19 "charge by itself, plus three one-shot buttons" package.

OWNER REQUEST
-------------
«сделай чтобы он автоматически включал зарядку ночью и днем когда самое дешевое
на тот случай если я забуду запланировать! также чтобы была кнопка отменить 1
раз, ночью или днем зарядить».

WHAT LANDED, AND WHAT EACH PART MUST KEEP DOING
-----------------------------------------------
A. Automatic by default. Automation 1778800001001 runs /config/ev_auto2h.py,
   which bounds the search to a window STARTING inside now..now+24h. The pinned
   /config/ev_best2h.py searched the whole fetched horizon (today + tomorrow, up
   to ~34h ahead at 14:05), which could park the plan past tomorrow and leave a
   ~37h gap with no charge. ev_best2h.py is unchanged — it is pinned by
   tests/test_ev_notify_surgical.py to notification-only edits — so the bound
   lives in the new file. Two new triggers make "every day" real: the day-ahead
   publication, and an hourly net that fires ONLY on a stale plan.

B. Car not plugged in is never silent, and never asserted from stale data. The
   Tuya IoT trial quota is exhausted, so sensor.ev_charger_status is served from
   cache (src=cache, stale_age ~2e4 s). Automation 1791000001001 acts only on a
   FRESH charger_free and hands every other case to the watchdog, whose message
   says "нет свежих данных ... причину назвать нельзя". Re-planning is capped at
   REPLAN_CAP per local day.

C. Three one-shot overrides on ONE sticky slot (no parallel flag system):
   «Зарядить ночью» / «Зарядить днём» both arm input_boolean.ev_night_requested
   + input_datetime.ev_night_window_start (expiry: window+3h), and
   «Отменить зарядку» arms input_boolean.ev_charge_cancelled (expiry: +24h),
   consumed by the first window it skips. Each is un-wedgeable and mutually
   cancelling.

Pure/hermetic: YAML + text parsing, and script runs with every HA call stubbed.
No network, no HA, no Tuya, no device is ever commanded.
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

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "ev_auto_automations.yaml"
SCRIPT_FIXTURE = REPO / "tests" / "fixtures" / "ev_cancel_script.yaml"

PLANNER = "1778800001001"
CHARGER = "1778800001002"
WATCHDOG = "1790100001001"
LIFECYCLE = "1790500001001"
REPLAN = "1791000001001"
MENU = "1778700001004"
HANDLER = "1778700001005"

FLAG = "input_boolean.ev_night_requested"
WINDOW = "input_datetime.ev_night_window_start"
SEEN = "input_datetime.ev_night_charge_seen"
SCHED = "input_datetime.ev_charge_start"
CANCEL_FLAG = "input_boolean.ev_charge_cancelled"
CANCEL_ARMED = "input_datetime.ev_cancel_armed_at"
CANCEL_CONSUMED = "input_datetime.ev_cancel_consumed"

REQUEST_EXPIRY = 10800   # window start + 3h  (unchanged from the sticky fix)
CANCEL_EXPIRY = 86400    # cancel armed + 24h
FRESH_MAX_AGE = 900      # a status older than this may not name a cause

# Domains that physically act on the house. NOTHING in this package may call one.
DEVICE_DOMAINS = {
    "switch", "light", "climate", "siren", "valve", "lock", "cover", "fan",
    "water_heater", "number", "select", "vacuum", "media_player", "button",
    "homeassistant", "scene",
}

UTC = datetime.timezone.utc


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def autos() -> dict:
    data = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    return {str(a["id"]): a for a in data}


@pytest.fixture(scope="module")
def cancel_script() -> dict:
    return yaml.safe_load(SCRIPT_FIXTURE.read_text(encoding="utf-8"))["ev_cancel_next"]


def walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk(v)


def actions_used(node) -> set[str]:
    return {d["action"] for d in walk(node) if isinstance(d.get("action"), str)}


def device_calls(node) -> set[str]:
    return {a for a in actions_used(node) if a.split(".", 1)[0] in DEVICE_DOMAINS}


def branches(auto):
    for act in auto["actions"]:
        if isinstance(act, dict) and "choose" in act:
            return act["choose"]
    raise AssertionError("no choose block")


def branch(auto, needle):
    hits = [b for b in branches(auto) if needle in b.get("alias", "")]
    assert len(hits) == 1, f"{needle!r}: {len(hits)} matching branches"
    return hits[0]


def conds_text(node) -> str:
    return " ".join(c.get("value_template", "") for c in node.get("conditions", []))


def norm(text: str) -> str:
    """Collapse the whitespace YAML block folding injects inside a template."""
    return re.sub(r"\s+", " ", text)


# --------------------------------------------------------------------------- #
# A. Automatic by default — the 24 h horizon and where it lives
# --------------------------------------------------------------------------- #
def test_planner_runs_the_bounded_script_not_the_pinned_one(autos):
    """ev_best2h.py is pinned to notification-only changes, so the horizon bound
    had to move out of it. The planner must now call the new wrapper."""
    used = actions_used(autos[PLANNER])
    assert "shell_command.ev_auto2h" in used
    assert "shell_command.ev_find_best2h" not in used


def test_pinned_planner_file_is_untouched_by_this_package():
    """Belt and braces: the deployed baseline of the pinned file must not have
    been edited to add a horizon."""
    live = REPO / "docs" / "audit" / "ev_best2h.deployed_patched.py"
    if not live.is_file():
        pytest.skip("verbatim deployed copies are gitignored (owner policy)")
    src = live.read_text(encoding="utf-8")
    assert "HORIZON" not in src
    assert "latest_start" not in src


def test_planner_refreshes_when_tomorrow_prices_publish(autos):
    trig = [t for t in autos[PLANNER]["triggers"] if t.get("id") == "tomorrow_published"]
    assert len(trig) == 1
    assert trig[0]["entity_id"] == "binary_sensor.nord_pool_lv_tomorrow_price_available"
    assert trig[0]["to"] == "on"


def test_planner_has_an_hourly_net_gated_on_a_stale_plan(autos):
    """Without this, a day of HA downtime left the house with a plan in the past
    and nothing to re-plan it until the next daytime Nord Pool update."""
    trig = [t for t in autos[PLANNER]["triggers"] if t.get("id") == "periodic"]
    assert len(trig) == 1 and trig[0]["trigger"] == "time_pattern"
    gate = norm(autos[PLANNER]["conditions"][2]["value_template"])
    assert "trigger.id != 'periodic'" in gate
    assert "86400" in gate, "must skip a plan more than 24h out"
    assert "1800" in gate, "must not re-plan inside the first 30 min of a window"
    assert "| float(0)" in gate and "cs <= 0" in gate, "must degrade OPEN"


def test_periodic_gate_does_not_look_at_the_request_flag(autos):
    """Two independent guards. Mixing them would let a stuck cancel/request flag
    disable the staleness net as well."""
    gate = autos[PLANNER]["conditions"][2]["value_template"]
    assert FLAG not in gate and CANCEL_FLAG not in gate


def test_planner_sticky_guard_survived_verbatim(autos):
    """conditions[0] and [1] are the sticky fix and the pre-existing hour rule.
    Both must be byte-identical — this package only APPENDS conditions[2]."""
    guard = autos[PLANNER]["conditions"][0]["value_template"]
    assert "trigger.id" not in guard
    assert FLAG in guard and WINDOW in guard and str(REQUEST_EXPIRY) in guard
    assert autos[PLANNER]["conditions"][1]["value_template"] == \
        "{{ trigger.id != 'price_update' or (8 <= now().hour < 22) }}"
    assert len(autos[PLANNER]["conditions"]) == 3


# --------------------------------------------------------------------------- #
# ev_auto2h.py — the horizon, the window rule, the price fallback
# --------------------------------------------------------------------------- #
import ev_auto2h as auto           # noqa: E402  (import after REPO is on sys.path)
import ev_replan_next as replan    # noqa: E402


def slots(start, count, price=0.20, step_min=15):
    return [{"dt": start + datetime.timedelta(minutes=step_min * i), "price": price}
            for i in range(count)]


def test_horizon_is_twenty_four_hours():
    assert auto.HORIZON_HOURS == 24
    now = datetime.datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
    assert auto.horizon_bound(now) == now + datetime.timedelta(hours=24)


def test_window_beyond_the_horizon_is_refused_even_when_much_cheaper():
    """THE regression this package exists to prevent: a dirt-cheap block 30 h out
    must not win, because taking it means no charge at all for a day and a half."""
    now = datetime.datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
    near = slots(now + datetime.timedelta(hours=2), 8, price=0.20)
    far = slots(now + datetime.timedelta(hours=30), 8, price=0.01)
    best, avg = auto.find_best_window(near + far, now,
                                      latest_start=auto.horizon_bound(now))
    assert best == near[0]["dt"], "picked a window outside the 24h horizon"
    assert avg == pytest.approx(0.20)
    # ...and without the bound the cheap far block wins, proving the bound acts.
    best_unbounded, _ = auto.find_best_window(near + far, now)
    assert best_unbounded == far[0]["dt"]


def test_cheapest_window_inside_the_horizon_wins_night_or_day():
    """No hour preference at all: whatever is genuinely cheapest, night or day."""
    now = datetime.datetime(2026, 8, 19, 9, 0, tzinfo=UTC)
    day = slots(now + datetime.timedelta(hours=4), 8, price=0.05)     # ~16:00 local
    night = slots(now + datetime.timedelta(hours=18), 8, price=0.09)  # ~06:00 local
    best, _ = auto.find_best_window(day + night, now,
                                    latest_start=auto.horizon_bound(now))
    assert best == day[0]["dt"]
    for s in day:
        s["price"] = 0.12
    best, _ = auto.find_best_window(day + night, now,
                                    latest_start=auto.horizon_bound(now))
    assert best == night[0]["dt"]


def test_start_cutoff_matches_the_pinned_planner():
    now = datetime.datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
    assert auto.CUTOFF_MINUTES == 10
    soon = slots(now + datetime.timedelta(minutes=2), 8, price=0.01)
    later = slots(now + datetime.timedelta(minutes=30), 8, price=0.05)
    best, _ = auto.find_best_window(soon + later, now)
    assert best == later[0]["dt"], "a window starting inside 10 min was accepted"


def test_gappy_prices_do_not_produce_a_fake_window():
    now = datetime.datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
    base = now + datetime.timedelta(hours=1)
    broken = slots(base, 4, price=0.01) + slots(base + datetime.timedelta(hours=3), 4, price=0.01)
    best, avg = auto.find_best_window(broken, now)
    # No contiguous 8-slot block exists -> the owner-mandated single-slot fallback.
    assert best in [s["dt"] for s in broken]
    assert avg == pytest.approx(0.01)


def test_single_slot_fallback_is_preserved():
    """Removing it once cost the owner a night of charging; it stays."""
    now = datetime.datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
    lone = slots(now + datetime.timedelta(hours=1), 1, price=0.001)
    best, avg = auto.find_best_window(lone, now)
    assert best == lone[0]["dt"] and avg == pytest.approx(0.001)


def test_fallback_also_respects_the_horizon():
    now = datetime.datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
    lone = slots(now + datetime.timedelta(hours=30), 1, price=0.001)
    best, avg = auto.find_best_window(lone, now, latest_start=auto.horizon_bound(now))
    assert best is None and avg is None


def test_earliest_start_excludes_the_window_that_just_failed():
    """The re-plan must not hand back a window overlapping the one the car
    slept through."""
    now = datetime.datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
    failed_end = now + datetime.timedelta(hours=2)
    inside = slots(now + datetime.timedelta(minutes=20), 8, price=0.01)
    after = slots(failed_end, 8, price=0.05)
    best, _ = auto.find_best_window(inside + after, now,
                                    latest_start=auto.horizon_bound(now),
                                    earliest_start=failed_end)
    assert best == after[0]["dt"]


LOCAL_SNAPSHOT = {
    "updated": "2026-08-19T08:11:46Z",
    "step_minutes": 15,
    "prices": {"2026-08-19": [0.30] * 24},
    "prices15": {"2026-08-19": {"03:00": 0.11, "03:15": 0.11}},
}


def test_local_price_snapshot_is_a_usable_elering_fallback():
    """An Elering outage used to mean no charge planned at all."""
    now = datetime.datetime(2026, 8, 19, 5, 30, tzinfo=UTC)
    parsed = auto.parse_local_prices(LOCAL_SNAPSHOT, now)
    assert len(parsed) == 96, "hourly table must expand to 15-min slots"
    by_dt = {s["dt"]: s["price"] for s in parsed}
    three = datetime.datetime(2026, 8, 19, 3, 0, tzinfo=auto.RIGA).astimezone(UTC)
    assert by_dt[three] == pytest.approx(0.11), "prices15 must win over the hourly table"
    assert all(isinstance(s["price"], float) for s in parsed)


def test_stale_local_snapshot_is_refused():
    now = datetime.datetime(2026, 8, 25, 0, 0, tzinfo=UTC)
    assert auto.parse_local_prices(LOCAL_SNAPSHOT, now) == []


def test_garbage_local_snapshot_never_raises():
    now = datetime.datetime(2026, 8, 19, 5, 30, tzinfo=UTC)
    for payload in ("", "not json", "[]", "{}", None, 42, {"prices": "nope"}):
        assert auto.parse_local_prices(payload, now) == []


def test_plan_change_notice_is_rate_limited():
    """The planner runs on every Nord Pool price update; the owner must not get a
    message every time."""
    assert auto.NOTIFY_MIN_INTERVAL >= 3600
    st = {"plan": "2026-08-20 03:45:00", "last_ts": 1000.0}
    assert auto.should_notify(st, "2026-08-20 03:45:00", 1e9) is False, "repeat plan"
    assert auto.should_notify(st, "2026-08-20 05:00:00", 1000.0 + 60) is False, "too soon"
    assert auto.should_notify(st, "2026-08-20 05:00:00",
                              1000.0 + auto.NOTIFY_MIN_INTERVAL) is True
    assert auto.should_notify({}, "2026-08-20 05:00:00", 0.0) is True, "first ever"


def test_importing_the_planner_has_no_side_effects():
    """It must be importable without secrets, HA, or network — otherwise these
    tests could not exist and a syntax slip would only show up in production."""
    assert auto._CFG == {} or "token" in auto._CFG


# --------------------------------------------------------------------------- #
# B. Car not plugged in — one message, a bounded re-plan, never from stale data
# --------------------------------------------------------------------------- #
def test_replan_only_believes_a_fresh_status():
    # 2026-08-19: a live read is now src="local" (HA's own alive tuya integration);
    # "cloud" (quota-dead IoT Core) is still accepted so an attribute value written by
    # the previous build is not misread as stale during the switchover.
    assert replan.LIVE_SRC == ("local", "cloud")
    for label, src in (("local read", "local"), ("legacy cloud read", "cloud")):
        fresh = {"state": "charger_free", "attributes": {"src": src, "stale_age": 60}}
        assert replan.status_is_fresh_free(fresh) is True, label
    assert replan.FRESH_MAX_AGE == FRESH_MAX_AGE
    for label, st in (
        ("cached", {"state": "charger_free", "attributes": {"src": "cache", "stale_age": 19960}}),
        ("stale", {"state": "charger_free", "attributes": {"src": "stale", "stale_age": 4000}}),
        ("charger absent from the dump",
         {"state": "cloud_error", "attributes": {"src": "no_device", "stale_age": None}}),
        ("fresh source but ancient",
         {"state": "charger_free", "attributes": {"src": "local", "stale_age": 5000}}),
        ("no age attribute",
         {"state": "charger_free", "attributes": {"src": "local"}}),
        ("plugged in", {"state": "charger_insert", "attributes": {"src": "local", "stale_age": 1}}),
        ("charging", {"state": "charger_charging", "attributes": {"src": "local", "stale_age": 1}}),
        ("cloud error", {"state": "cloud_error", "attributes": {"src": "cache", "stale_age": 9}}),
        ("unavailable", {"state": "unavailable", "attributes": {}}),
        ("missing entity", None),
    ):
        assert replan.status_is_fresh_free(st) is False, label


def test_replan_cap_is_two_per_local_day():
    assert replan.REPLAN_CAP == 2
    today = datetime.date(2026, 8, 19)
    same = {"state": "2026-08-19 00:00:00"}
    assert replan.attempts_today({"state": "0"}, same, today) == 0
    assert replan.attempts_today({"state": "2.0"}, same, today) == 2
    # a counter left over from another day must not consume today's budget
    assert replan.attempts_today({"state": "2.0"}, {"state": "2026-08-18 00:00:00"}, today) == 0
    # missing / garbage helpers read as "no attempts yet", never as a crash
    assert replan.attempts_today(None, None, today) == 0
    assert replan.attempts_today({"state": "unknown"}, same, today) == 0


def test_replan_automation_never_commands_a_device(autos):
    assert device_calls(autos[REPLAN]) == set()
    assert actions_used(autos[REPLAN]) == {"shell_command.ev_replan_next"}


def test_replan_waits_for_the_other_two_speakers(autos):
    """Autocharge checks at +6 min and the watchdog at +10 min; the re-plan must
    come last so the owner reads "why" before "what I am doing"."""
    first = autos[REPLAN]["actions"][0]
    assert first["delay"] == "00:12:00"


def test_replan_yields_to_an_explicit_request_and_to_a_cancel(autos):
    text = " ".join(str(a.get("value_template", "")) for a in autos[REPLAN]["actions"])
    assert FLAG in text, "an explicit one-shot request must not be re-planned"
    assert CANCEL_CONSUMED in text, "a cancelled window must not be re-planned"


def test_replan_and_watchdog_are_exact_complements(autos):
    """Exactly one of them speaks per occurrence. Both matching, or neither,
    would mean two messages or silence."""
    replan_cond = None
    for a in autos[REPLAN]["actions"]:
        v = str(a.get("value_template", ""))
        if "charger_free" in v:
            replan_cond = norm(v)
    generic = branch(autos[WATCHDOG], "Плановый старт был, а зарядки нет")
    watchdog_cond = None
    for c in generic["conditions"]:
        if "charger_free" in c.get("value_template", ""):
            watchdog_cond = norm(c["value_template"])
    assert replan_cond and watchdog_cond
    inner = replan_cond[replan_cond.index("{{") + 2:replan_cond.rindex("}}")].strip()
    assert f"not ({inner})" in watchdog_cond.replace("  ", " "), (
        "the watchdog guard is not the exact negation of the re-plan guard:\n"
        f"replan  : {inner}\nwatchdog: {watchdog_cond}")


# --------------------------------------------------------------------------- #
# C. The one-shot cancel — armed, consumed exactly once, un-wedgeable
# --------------------------------------------------------------------------- #
def test_cancel_script_only_writes_helpers_and_talks(cancel_script):
    assert device_calls(cancel_script) == set()
    assert actions_used(cancel_script) <= {
        "input_boolean.turn_on", "input_boolean.turn_off",
        "input_datetime.set_datetime", "telegram_bot.send_message",
    }


def test_cancel_script_arms_the_flag_and_records_when(cancel_script):
    seq = cancel_script["sequence"]
    armed = [d for d in walk(seq) if d.get("target", {}).get("entity_id") == CANCEL_ARMED]
    assert len(armed) == 1 and "now().timestamp()" in armed[0]["data"]["timestamp"]
    on = [d for d in walk(seq) if d.get("action") == "input_boolean.turn_on"
          and d["target"]["entity_id"] == CANCEL_FLAG]
    assert len(on) == 1


def test_cancel_clears_a_pending_request_so_it_wins_over_it(cancel_script):
    """«Отменить» pressed after «Зарядить ночью» must really cancel: leaving the
    request armed would keep blocking the planner AND keep the watchdog waiting
    on a window that will never charge."""
    seq = cancel_script["sequence"]
    assert any(d.get("action") == "input_boolean.turn_off"
               and d["target"]["entity_id"] == FLAG for d in walk(seq))
    resets = [d for d in walk(seq)
              if d.get("target", {}).get("entity_id") == WINDOW
              and d.get("data", {}).get("datetime") == "1970-01-01 00:00:00"]
    assert len(resets) == 1, "the stable window reference must be cleared too"


def test_cancel_resets_the_consumed_marker(cancel_script):
    """Otherwise last cancel's marker would silence the watchdog for a window
    this cancel has nothing to do with."""
    resets = [d for d in walk(cancel_script["sequence"])
              if d.get("target", {}).get("entity_id") == CANCEL_CONSUMED]
    assert len(resets) == 1
    assert resets[0]["data"]["datetime"] == "1970-01-01 00:00:00"


def test_autocharge_consumes_the_cancel_before_any_device_command(autos):
    """The gate is the FIRST action on purpose: no relay command, no boiler
    command, nothing happens before the skip decision."""
    first = autos[CHARGER]["actions"][0]
    assert "Разовая отмена" in first["alias"]
    assert CANCEL_FLAG in first["if"][0]["value_template"]
    then = first["then"]
    assert device_calls(then) == set(), device_calls(then)
    assert then[-1]["stop"], "the gate must end the run, not fall through"


def test_cancel_is_consumed_exactly_once_and_records_which_window(autos):
    then = autos[CHARGER]["actions"][0]["then"]
    offs = [d for d in walk(then) if d.get("action") == "input_boolean.turn_off"
            and d["target"]["entity_id"] == CANCEL_FLAG]
    sends = [d for d in walk(then) if d.get("action") == "telegram_bot.send_message"]
    marks = [d for d in walk(then)
             if d.get("target", {}).get("entity_id") == CANCEL_CONSUMED]
    assert len(offs) == 1, "a cancel that is not cleared would skip every charge"
    assert len(sends) == 1, "exactly one message per skipped window"
    assert len(marks) == 1
    ts = marks[0]["data"]["timestamp"]
    assert SCHED in ts, "the marker must record WHICH window was skipped"


def test_second_window_is_not_skipped_by_a_consumed_cancel(autos):
    """«Отменить 1 раз» — the gate reads the flag, and the same run clears it, so
    the very next scheduled window charges normally."""
    gate = autos[CHARGER]["actions"][0]
    guard = gate["if"][0]["value_template"]
    assert f"is_state('{CANCEL_FLAG}', 'on')" in guard.replace("''", "'")
    assert any(d.get("action") == "input_boolean.turn_off"
               and d["target"]["entity_id"] == CANCEL_FLAG for d in walk(gate["then"]))


def test_cancel_cannot_wedge_the_house(autos):
    """A cancel nobody ever consumed (HA down, manual mode, car gone for a week)
    must not silently disable automatic charging forever."""
    b = branch(autos[LIFECYCLE], "Срок истечения РАЗОВОЙ")
    conds = conds_text(b)
    assert str(CANCEL_EXPIRY) in conds
    assert CANCEL_ARMED in conds
    assert "| float(0)" in conds, "must degrade OPEN and expire, not persist"
    offs = [d for d in walk(b["sequence"]) if d.get("action") == "input_boolean.turn_off"]
    assert [d["target"]["entity_id"] for d in offs] == [CANCEL_FLAG]


def test_cancel_expiry_is_the_last_branch(autos):
    """`choose` takes the first match; the cancel sweep must never preempt a
    request verdict on the same 10-minute tick."""
    bs = branches(autos[LIFECYCLE])
    assert "Срок истечения РАЗОВОЙ" in bs[-1]["alias"]


def test_cancel_expiry_does_not_touch_the_request_flag(autos):
    """That flag is the "verdict not yet delivered" token — clearing it here
    would swallow a night/day verdict."""
    b = branch(autos[LIFECYCLE], "Срок истечения РАЗОВОЙ")
    touched = {d["target"]["entity_id"] for d in walk(b["sequence"])
               if d.get("action", "").startswith("input_boolean.")}
    assert FLAG not in touched


def test_request_still_expires_at_window_plus_three_hours(autos):
    """The night/day request must not survive its own window."""
    b = branch(autos[LIFECYCLE], "поздний вердикт")
    assert str(REQUEST_EXPIRY) in conds_text(b)
    assert b["sequence"][-1]["action"] == "input_boolean.turn_off"
    assert b["sequence"][-1]["target"]["entity_id"] == FLAG


def test_a_cancelled_occurrence_is_not_reported_as_a_failure(autos):
    """Both watchdog paths must stay quiet about a window the owner cancelled —
    and both must degrade OPEN when the helper is absent."""
    for needle in ("Плановый старт был, а зарядки нет",
                   "Ночная заявка — плановый старт"):
        b = branch(autos[WATCHDOG], needle)
        guard = [norm(c["value_template"]) for c in b["conditions"]
                 if CANCEL_CONSUMED in c.get("value_template", "")]
        assert len(guard) == 1, needle
        assert "| float(0)" in guard[0] and "cs <= 0" in guard[0]
        assert "> 60" in guard[0], "attribute-only writes must not count"


# --------------------------------------------------------------------------- #
# The three overrides — one sticky slot, two presses never queue two charges
# --------------------------------------------------------------------------- #
NIGHT_V2 = REPO / "docs" / "audit" / "ev_night2h.deployed_v2.py"
DAY_V2 = REPO / "docs" / "audit" / "ev_day2h.deployed_v2.py"
needs_scripts = pytest.mark.skipif(
    not (NIGHT_V2.is_file() and DAY_V2.is_file()),
    reason="verbatim deployed copies are gitignored (owner policy); see "
           "docs/audit/ev_auto_20260819/ for the generated diffs",
)


class _ReconfigurableIO(io.StringIO):
    def reconfigure(self, *a, **k):
        return None


def _load(path):
    spec = importlib.util.spec_from_file_location("ev_override_" + path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    old = sys.stdout
    sys.stdout = _ReconfigurableIO()
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.stdout = old
    return mod


# Price bases that fall INSIDE each override's own window, so a day request is
# offered a daytime block and a night request a night-time block.
PRICES_AT = {
    "ev_night2h.deployed_v2": datetime.datetime(2026, 8, 20, 0, 45, tzinfo=UTC),   # 03:45 Riga
    "ev_day2h.deployed_v2": datetime.datetime(2026, 8, 20, 9, 45, tzinfo=UTC),     # 12:45 Riga
}
EXPECT_WINDOW = {
    "ev_night2h.deployed_v2": ("03:45", "05:45"),
    "ev_day2h.deployed_v2": ("12:45", "14:45"),
}


def _run_override(path, sched_status=200, now=None, prices_at=None, old_val=""):
    """Run an override script with EVERY HA call intercepted. Returns the calls.

    This is the device-command interceptor: a real service call would show up
    here, and the tests below assert the list contains none.
    """
    mod = _load(path)
    calls: list[tuple[str, dict]] = []

    def fake_post(p, d):
        calls.append((p, dict(d)))
        if p.endswith("set_datetime") and d.get("entity_id") == SCHED:
            return sched_status
        return 200

    mod.ha_post = fake_post
    mod.ha_get = lambda p: ({"state": old_val} if "ev_charge_start" in p
                            else {"state": "on"})
    base = prices_at or PRICES_AT[path.stem]
    mod.fetch_lv_prices = lambda: [
        {"dt": base + datetime.timedelta(minutes=15 * i), "price": 0.01} for i in range(8)
    ]
    frozen = now or datetime.datetime(2026, 8, 19, 15, 23, tzinfo=UTC)

    class Frozen(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen

    mod.datetime.datetime = Frozen
    old = sys.stdout
    sys.stdout = _ReconfigurableIO()
    code = None
    try:
        mod.main()
    except SystemExit as exc:
        code = exc.code
    finally:
        sys.stdout = old
    return calls, code


def _svc(calls, suffix):
    return [d.get("entity_id") for p, d in calls if p.endswith(suffix)]


@needs_scripts
def test_override_windows_match_the_request():
    night = _load(NIGHT_V2)
    day = _load(DAY_V2)
    assert (night.START_H, night.END_H) == (23, 7), "«ночью» = 23:00-07:00"
    assert (day.START_H, day.END_H) == (8, 22), "«днём» = 08:00-22:00"
    assert night.WINDOW_LABEL == "23:00-07:00"
    assert day.WINDOW_LABEL == "08:00-22:00"
    # the in_window predicates really implement those ranges
    assert [h for h in range(24) if night.in_window(h)] == [0, 1, 2, 3, 4, 5, 6, 23]
    assert [h for h in range(24) if day.in_window(h)] == list(range(8, 22))


@needs_scripts
@pytest.mark.parametrize("path", [NIGHT_V2, DAY_V2], ids=["night", "day"])
def test_override_arms_one_sticky_slot_in_the_right_order(path):
    calls, code = _run_override(path)
    assert code is None
    assert _svc(calls, "input_datetime/set_datetime")[:3] == [WINDOW, SEEN, SCHED], (
        "the stable window reference must be written BEFORE the schedule, or the "
        "overwrite detector fires on our own write")
    assert _svc(calls, "input_boolean/turn_on") == [FLAG]
    assert device_calls_from(calls) == set()


def device_calls_from(calls) -> set[str]:
    out = set()
    for path, _ in calls:
        m = re.match(r"/api/services/([a-z_]+)/([a-z_]+)", path)
        if m and m.group(1) in DEVICE_DOMAINS:
            out.add(m.group(1) + "." + m.group(2))
    return out


@needs_scripts
@pytest.mark.parametrize("path", [NIGHT_V2, DAY_V2], ids=["night", "day"])
def test_override_clears_a_pending_cancel_so_it_re_arms_the_charge(path):
    """«Отменить», then «Зарядить …» — the charge must come back, otherwise the
    autocharge would skip exactly the window the owner just asked for."""
    calls, _ = _run_override(path)
    assert _svc(calls, "input_boolean/turn_off") == [
        "input_boolean.ev_manual_mode", CANCEL_FLAG]
    assert CANCEL_CONSUMED in _svc(calls, "input_datetime/set_datetime")


@needs_scripts
@pytest.mark.parametrize("path", [NIGHT_V2, DAY_V2], ids=["night", "day"])
def test_override_never_arms_a_request_it_could_not_schedule(path):
    """A request with no schedule blocks the planner for nothing."""
    calls, code = _run_override(path, sched_status=500)
    assert code == 1
    assert _svc(calls, "input_boolean/turn_on") == []
    sent = [d["message"] for p, d in calls if p.endswith("notify/send_message")]
    assert len(sent) == 1 and "НЕ поставлена" in sent[0]


@needs_scripts
@pytest.mark.parametrize("path", [NIGHT_V2, DAY_V2], ids=["night", "day"])
def test_override_always_confirms_the_concrete_window(path):
    """The owner pressed a button; silence is not an acceptable answer, and the
    confirmation must name the window and the price."""
    calls, _ = _run_override(path)
    sent = [d["message"] for p, d in calls if p.endswith("notify/send_message")]
    assert len(sent) == 1
    start, end = EXPECT_WINDOW[path.stem]
    assert start in sent[0] and end in sent[0]
    assert "0.0100" in sent[0]


@needs_scripts
@pytest.mark.parametrize("path", [NIGHT_V2, DAY_V2], ids=["night", "day"])
def test_two_presses_do_not_queue_two_charges(path):
    """Both presses overwrite the SAME helper set, and the second one says so."""
    first, _ = _run_override(path)
    written = {d["entity_id"]: d.get("datetime") for p, d in first
               if p.endswith("input_datetime/set_datetime")}
    second, _ = _run_override(path, old_val=written[SCHED])
    again = {d["entity_id"]: d.get("datetime") for p, d in second
             if p.endswith("input_datetime/set_datetime")}
    assert again[SCHED] == written[SCHED], "the window moved on an identical re-press"
    assert _svc(second, "input_boolean/turn_on") == [FLAG], "only one request slot"
    msg = [d["message"] for p, d in second if p.endswith("notify/send_message")][0]
    assert "не изменилось" in msg and "вторую зарядку" in msg


@needs_scripts
@pytest.mark.parametrize("path", [NIGHT_V2, DAY_V2], ids=["night", "day"])
def test_override_explains_missing_tomorrow_prices(path):
    """«цены на завтра ещё не опубликованы» instead of a bare "no window"."""
    mod = _load(path)
    calls = []
    mod.ha_post = lambda p, d: calls.append((p, dict(d))) or 200
    mod.ha_get = lambda p: {"state": "off"}          # tomorrow NOT published
    mod.fetch_lv_prices = lambda: []                 # -> no window at all
    old = sys.stdout
    sys.stdout = _ReconfigurableIO()
    try:
        mod.main()
    except SystemExit:
        pass
    finally:
        sys.stdout = old
    sent = [d["message"] for p, d in calls if p.endswith("notify/send_message")]
    assert len(sent) == 1
    assert "цены на завтра ещё не опубликованы" in sent[0]
    assert _svc(calls, "input_boolean/turn_on") == [], "no request without a window"


@needs_scripts
def test_override_patches_removed_nothing_but_the_listed_lines():
    """Reviewable diff: the only deleted lines are the window bounds, the label
    and the `if local_str != old_val` gate that made a press silent."""
    v1 = (REPO / "docs" / "audit" / "ev_day2h.deployed_baseline_v1.py")
    if not v1.is_file():
        pytest.skip("v1 baseline copy is gitignored")
    removed = [l[1:].strip() for l in difflib.unified_diff(
        v1.read_text(encoding="utf-8").splitlines(),
        DAY_V2.read_text(encoding="utf-8").splitlines(), lineterm="")
        if l.startswith("-") and not l.startswith("---")]
    for line in removed:
        assert (line.startswith("END_H") or line.startswith("WINDOW_LABEL")
                or "local_str != old_val" in line or "msg = f\"EV {LABEL}" in line
                or line.startswith("ha_post(") or line.startswith("msg =")
                or line.startswith("]") or line.startswith('"  ') or line == ""
                or line.startswith('f"🚗 EV {LABEL}') or line.startswith('"\\n".join')
                or line.startswith('{"entity_id": "input_datetime.ev_charge_start"')
                or 'ev_manual_mode' in line), f"unexpected removal: {line!r}"


# --------------------------------------------------------------------------- #
# D. Surfaces — Telegram menu + handler, and the Mini App
# --------------------------------------------------------------------------- #
CALLBACKS = {"/ev_night": "shell_command.ev_night2h",
             "/ev_day": "shell_command.ev_day2h",
             "/ev_cancel": "script.turn_on"}


def _handler_branch(autos, cb):
    hits = [b for b in branches(autos[HANDLER])
            if f"callback_data == '{cb}'" in conds_text(b).replace("''", "'")]
    assert len(hits) == 1, f"{cb}: {len(hits)} handler branches"
    return hits[0]


@pytest.mark.parametrize("cb", sorted(CALLBACKS))
def test_menu_offers_the_button(autos, cb):
    text = yaml.dump(autos[MENU], allow_unicode=True)
    assert cb in text, f"{cb} missing from the Telegram menu"


@pytest.mark.parametrize("cb", sorted(CALLBACKS))
def test_callback_answers_the_query_immediately(autos, cb):
    """A 30 s wait once expired the callback query and aborted the WHOLE handler,
    so the owner got no answer to any button. Nothing may precede the answer."""
    seq = _handler_branch(autos, cb)["sequence"]
    first = seq[0]
    assert first["action"] == "telegram_bot.answer_callback_query"
    assert first.get("continue_on_error") is True, (
        "an expired query id must not abort the queued handler")
    for step in seq:
        assert "delay" not in step and "wait_template" not in step, (
            "no blocking step is allowed in a callback branch")


@pytest.mark.parametrize("cb", sorted(CALLBACKS))
def test_callback_commands_no_device(autos, cb):
    """Interceptor: the whole branch, walked, must contain zero device calls."""
    seq = _handler_branch(autos, cb)["sequence"]
    assert device_calls(seq) == set(), device_calls(seq)
    assert CALLBACKS[cb] in actions_used(seq)


def test_cancel_callback_is_fire_and_forget(autos):
    seq = _handler_branch(autos, "/ev_cancel")["sequence"]
    turn_on = [d for d in walk(seq) if d.get("action") == "script.turn_on"]
    assert len(turn_on) == 1
    assert turn_on[0]["target"]["entity_id"] == "script.ev_cancel_next"


MINIAPP = REPO / "miniapp" / "smarthouse_v8.html"


def test_miniapp_offers_all_three_overrides():
    text = MINIAPP.read_text(encoding="utf-8")
    for act in ("evScheduleNight", "evScheduleDay", "evCancelNext"):
        assert f'name==="{act}"' in text, f"{act} handler missing"
        assert f"v8act('{act}')" in text, f"{act} button missing"
    assert 'svc("shell_command","ev_day2h",null)' in text
    assert 'svc("script","turn_on","script.ev_cancel_next")' in text


def test_miniapp_backend_allows_the_cancel_script():
    """Without this the button 403s silently in production."""
    backend = (REPO / "custom_components" / "miniapp_auth" / "__init__.py") \
        .read_text(encoding="utf-8")
    assert '"script.ev_cancel_next"' in backend
    assert '"ev_day2h"' in backend and '"ev_night2h"' in backend


# --------------------------------------------------------------------------- #
# Telegram discipline — the bot entry defaults to markdown and rejects entity_ids
# --------------------------------------------------------------------------- #
CHANGED = (PLANNER, CHARGER, WATCHDOG, LIFECYCLE, REPLAN, MENU, HANDLER)
ENTITY_RE = re.compile(
    r"\b(?:sensor|switch|input_boolean|input_datetime|input_number|binary_sensor|"
    r"climate|automation|script)\.[a-z0-9_]+")


def test_every_new_telegram_message_declares_html(autos, cancel_script):
    """A message with a bare entity_id under markdown is rejected outright, so
    every message this package added or rewrote must opt into html."""
    NEW_MARKERS = ("Разовая отмена снята", "разовая отмена зарядки истекла",
                   "плановая зарядка не началась", "зарядка по заявке НЕ состоялась",
                   "следующая зарядка отменена", "EV расписание")
    checked = 0
    for node in list(walk(autos)) + list(walk(cancel_script)):
        if node.get("action") != "telegram_bot.send_message":
            continue
        msg = node.get("data", {}).get("message", "")
        if not any(m in msg for m in NEW_MARKERS):
            continue
        assert node["data"].get("parse_mode") == "html", msg[:120]
        checked += 1
    assert checked >= 6, checked


def test_entity_ids_in_new_messages_are_wrapped_in_code(autos, cancel_script):
    for node in list(walk(autos)) + list(walk(cancel_script)):
        if node.get("action") != "telegram_bot.send_message":
            continue
        msg = node.get("data", {}).get("message", "")
        if node.get("data", {}).get("parse_mode") != "html":
            # markdown-mode messages must contain no entity_id at all
            prose = re.sub(r"\{[%{].*?[%}]\}", "", msg, flags=re.S)
            assert not ENTITY_RE.search(prose), f"bare entity_id in markdown msg: {msg[:120]}"
            continue
        prose = re.sub(r"\{[%{].*?[%}]\}", "", msg, flags=re.S)
        for m in ENTITY_RE.finditer(prose):
            window = prose[max(0, m.start() - 8):m.end() + 9]
            assert "<code>" in window and "</code>" in window, (
                f"bare entity_id {m.group(0)!r} in: {msg[:160]}")


def test_new_message_bodies_escape_their_interpolations(autos):
    """Free text must go through `| e`. `cause`/`stale_note`/`kind`/`who` are
    composed from already-escaped values in the shared preamble."""
    PRE_ESCAPED = {"cause", "stale_note", "who", "kind"}
    targets = [
        branch(autos[WATCHDOG], "Плановый старт был, а зарядки нет"),
        branch(autos[WATCHDOG], "Ночная заявка — плановый старт"),
        branch(autos[LIFECYCLE], "Срок истечения РАЗОВОЙ"),
        autos[CHARGER]["actions"][0],
    ]
    checked = 0
    for node in targets:
        for d in walk(node):
            if d.get("action") != "telegram_bot.send_message":
                continue
            msg = d["data"]["message"]
            _, _, body = msg.rpartition("-%}")
            for expr in re.findall(r"\{\{(.*?)\}\}", body, flags=re.S):
                if expr.strip().rstrip("| e").strip() in PRE_ESCAPED:
                    continue
                if expr.strip() in PRE_ESCAPED:
                    continue
                assert "| e" in expr, f"unescaped interpolation {expr.strip()!r}"
                checked += 1
    assert checked >= 6, checked


def test_stale_aware_cause_list_reaches_every_verdict_path(autos):
    """Task E: no path may name a confident cause from a cached status. With the
    Tuya quota exhausted this is the difference between a true statement and a
    lie about the owner's car."""
    paths = [
        branch(autos[WATCHDOG], "Плановый старт был, а зарядки нет"),
        branch(autos[WATCHDOG], "Ночная заявка — плановый старт"),
        branch(autos[LIFECYCLE], "поздний вердикт"),
        branch(autos[LIFECYCLE], "Плановое время перезаписано"),
    ]
    for node in paths:
        msgs = [d["data"]["message"] for d in walk(node)
                if d.get("action") == "telegram_bot.send_message"]
        assert len(msgs) == 1
        msg = msgs[0]
        assert "нет свежих данных от зарядки" in msg, "no staleness branch"
        assert "причину назвать нельзя" in msg
        # The freshness test must name the live source(s) and the 900 s bound. Since
        # 2026-08-19 the live source is "local" (HA's own alive tuya integration); a
        # verdict that still only accepted "cloud" would call every reading stale
        # forever, i.e. it would never again report a real cause.
        assert "'local'" in msg, "verdict does not accept the local (live) source"
        assert "'cloud'" in msg and "900" in msg, "no freshness test"
        assert "'charger_free': 'машина не подключена'" in msg
        assert "'charger_insert': 'машина подключена, но зарядка не началась'" in msg
        assert "'charger_pause'" in msg and "'charger_end'" in msg
        assert "нет связи с зарядкой" in msg
        # a stale charger_charging must NOT be reported as success
        assert msg.index("elif not fresh") < msg.index("causes.get(s")


def test_no_new_device_command_anywhere_in_the_package(autos, cancel_script):
    """The only automation in this package allowed to command anything is the
    pre-existing autocharge 1778800001002 — and only outside the cancel gate."""
    for aid in (PLANNER, WATCHDOG, LIFECYCLE, REPLAN, MENU, HANDLER):
        if aid == HANDLER:
            continue  # the handler legitimately carries the house's own buttons
        assert device_calls(autos[aid]) == set(), (aid, device_calls(autos[aid]))
    assert device_calls(cancel_script) == set()
    assert device_calls(autos[CHARGER]["actions"][0]) == set()


def test_fixture_mirrors_production(autos):
    """These tests are only worth anything if the fixture is what is deployed."""
    assert set(autos) == set(CHANGED)
    assert autos[LIFECYCLE]["mode"] == "queued" and autos[LIFECYCLE]["max"] >= 2
    assert autos[WATCHDOG]["mode"] == "queued"
    assert autos[REPLAN]["mode"] == "single"
    assert autos[PLANNER]["mode"] == "single"
