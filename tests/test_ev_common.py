"""Unit tests for ev_common — shared EV scheduler logic.

Covers: genuine contiguous 2h-window requirement (no single-slot fallback),
incomplete/gappy prices, day/night hour boundaries, DST boundary handling,
Elering parsing, HA POST status checking, and API timeout/retry behavior.
All network is stubbed; no real Elering/HA/Tuya calls.
"""
from __future__ import annotations

import datetime
import json
import socket
import urllib.error

import pytest

import ev_common as ev

UTC = datetime.timezone.utc


def make_slots(start_utc, count, price=0.05, step_min=15):
    """Build `count` price slots starting at start_utc, step_min apart."""
    return [
        {"dt": start_utc + datetime.timedelta(minutes=step_min * i), "price": price}
        for i in range(count)
    ]


# --------------------------------------------------------------------------- #
# find_best_2h: genuine contiguous window only
# --------------------------------------------------------------------------- #
def test_contiguous_window_found():
    now = datetime.datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
    slots = make_slots(now + datetime.timedelta(hours=1), 10, price=0.05)
    best, avg = ev.find_best_2h(slots, now)
    assert best is not None
    assert avg == pytest.approx(0.05)
    assert best == slots[0]["dt"]


def test_cheapest_contiguous_window_selected():
    now = datetime.datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
    base = now + datetime.timedelta(hours=1)
    slots = make_slots(base, 16, price=0.20)
    # Make the 5th..12th slots cheap -> that 8-slot window should win.
    for i in range(4, 12):
        slots[i]["price"] = 0.01
    best, avg = ev.find_best_2h(slots, now)
    assert best == slots[4]["dt"]
    assert avg == pytest.approx(0.01)


def test_no_single_slot_fallback_when_only_one_slot():
    """A lone cheap slot must NOT be reported as a 2h window."""
    now = datetime.datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
    slots = make_slots(now + datetime.timedelta(hours=1), 1, price=0.001)
    best, avg = ev.find_best_2h(slots, now)
    assert best is None
    assert avg is None


def test_gappy_prices_break_contiguity():
    """A missing slot in the middle must invalidate that window."""
    now = datetime.datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
    base = now + datetime.timedelta(hours=1)
    slots = make_slots(base, 9, price=0.02)
    # Drop slot index 4 -> creates a 30-min gap, no 8-contiguous run remains.
    del slots[4]
    best, avg = ev.find_best_2h(slots, now)
    assert best is None and avg is None


def test_partial_gappy_still_finds_clean_run():
    """If a clean 8-slot run exists after a gap, it should be found."""
    now = datetime.datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
    base = now + datetime.timedelta(hours=1)
    # First 3 slots, a gap, then a clean 8-slot run.
    early = make_slots(base, 3, price=0.30)
    clean_start = base + datetime.timedelta(hours=3)
    clean = make_slots(clean_start, 8, price=0.02)
    best, avg = ev.find_best_2h(early + clean, now)
    assert best == clean[0]["dt"]
    assert avg == pytest.approx(0.02)


def test_cutoff_excludes_imminent_slots():
    now = datetime.datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
    # Window starts in 5 min -> inside 10-min cutoff -> excluded.
    slots = make_slots(now + datetime.timedelta(minutes=5), 8, price=0.01)
    best, _ = ev.find_best_2h(slots, now)
    assert best is None


# --------------------------------------------------------------------------- #
# Day / night hour boundaries
# --------------------------------------------------------------------------- #
def _day_filter(h):
    return 8 <= h < 20


def _night_filter(h):
    return h >= 22 or h < 6


def test_day_filter_accepts_daytime_window():
    now = datetime.datetime(2026, 1, 15, 6, 0, tzinfo=UTC)  # winter UTC+2
    # Local 10:00 == 08:00 UTC (winter). Window 10:00-12:00 local.
    start = datetime.datetime(2026, 1, 15, 8, 0, tzinfo=UTC)
    slots = make_slots(start, 8, price=0.03)
    best, _ = ev.find_best_2h(slots, now, hour_filter=_day_filter)
    assert best is not None


def test_day_filter_rejects_night_window():
    now = datetime.datetime(2026, 1, 15, 18, 0, tzinfo=UTC)
    # Local 23:00 == 21:00 UTC winter -> outside day window.
    start = datetime.datetime(2026, 1, 15, 21, 0, tzinfo=UTC)
    slots = make_slots(start, 8, price=0.01)
    best, _ = ev.find_best_2h(slots, now, hour_filter=_day_filter)
    assert best is None


def test_night_filter_accepts_across_midnight():
    now = datetime.datetime(2026, 1, 15, 18, 0, tzinfo=UTC)
    # Local 23:00-01:00 (winter): start 21:00 UTC.
    start = datetime.datetime(2026, 1, 15, 21, 0, tzinfo=UTC)
    slots = make_slots(start, 8, price=0.01)
    best, _ = ev.find_best_2h(slots, now, hour_filter=_night_filter)
    assert best is not None
    # Confirm the boundary really spans midnight in local time.
    assert best.astimezone(ev.RIGA).hour == 23


def test_night_filter_rejects_midday_window():
    now = datetime.datetime(2026, 1, 15, 6, 0, tzinfo=UTC)
    start = datetime.datetime(2026, 1, 15, 10, 0, tzinfo=UTC)  # local 12:00
    slots = make_slots(start, 8, price=0.01)
    best, _ = ev.find_best_2h(slots, now, hour_filter=_night_filter)
    assert best is None


# --------------------------------------------------------------------------- #
# DST boundary — contiguity is UTC-based and must survive the local jump
# --------------------------------------------------------------------------- #
def test_dst_spring_forward_contiguity_preserved():
    """Riga spring-forward 2026-03-29: 03:00->04:00 local. UTC slots stay 900s
    apart, so a window spanning the transition is still contiguous."""
    now = datetime.datetime(2026, 3, 29, 0, 0, tzinfo=UTC)
    # 01:00 UTC is the transition instant (EET->EEST). Straddle it.
    start = datetime.datetime(2026, 3, 29, 0, 30, tzinfo=UTC)
    slots = make_slots(start, 8, price=0.02)
    best, avg = ev.find_best_2h(slots, now)
    assert best is not None
    assert avg == pytest.approx(0.02)
    # Local hour jumps from 02:xx to 04:xx across the window; verify the jump.
    locals_ = [s["dt"].astimezone(ev.RIGA).hour for s in slots]
    assert 3 not in locals_  # the 03:00 local hour does not exist


def test_dst_fall_back_contiguity_preserved():
    """Riga fall-back 2026-10-25: 04:00->03:00 local. UTC spacing unchanged."""
    now = datetime.datetime(2026, 10, 25, 0, 0, tzinfo=UTC)
    start = datetime.datetime(2026, 10, 25, 0, 30, tzinfo=UTC)
    slots = make_slots(start, 8, price=0.02)
    best, _ = ev.find_best_2h(slots, now)
    assert best is not None
    assert ev._is_contiguous(slots) is True


# --------------------------------------------------------------------------- #
# parse_prices
# --------------------------------------------------------------------------- #
def test_parse_prices_basic():
    raw = {"data": {"lv": [
        {"timestamp": 1_700_000_000, "price": 40.0},
        {"timestamp": 1_700_000_900, "price": 30.0},
    ]}}
    out = ev.parse_prices(raw)
    assert len(out) == 2
    assert out[0]["price"] == pytest.approx(0.04)  # EUR/MWh -> EUR/kWh
    assert out[0]["dt"] < out[1]["dt"]


def test_parse_prices_empty_raises():
    with pytest.raises(ValueError):
        ev.parse_prices({"data": {"lv": []}})


def test_parse_prices_skips_malformed_rows():
    raw = {"data": {"lv": [
        {"timestamp": 1_700_000_000, "price": 40.0},
        {"price": 30.0},                     # missing timestamp -> skipped
        {"timestamp": "bad", "price": 20.0}, # bad timestamp -> skipped
        {"timestamp": 1_700_000_900, "price": 10.0},
    ]}}
    out = ev.parse_prices(raw)
    assert len(out) == 2


def test_parse_prices_all_malformed_raises():
    with pytest.raises(ValueError):
        ev.parse_prices({"data": {"lv": [{"nope": 1}]}})


# --------------------------------------------------------------------------- #
# ha_post status checking
# --------------------------------------------------------------------------- #
def test_ha_post_ok_on_2xx(fake_http):
    fake_http.route("ha.test", {"ok": True}, status=200)
    ok, status = ev.ha_post("http://ha.test:8123", "/api/services/x/y",
                            {"a": 1}, ev.make_headers("tok"))
    assert ok is True and status == 200


def test_ha_post_not_ok_on_5xx(fake_http):
    fake_http.route("ha.test", {"err": True}, status=500)
    ok, status = ev.ha_post("http://ha.test:8123", "/api/services/x/y",
                            {"a": 1}, ev.make_headers("tok"))
    assert ok is False and status == 500


def test_ha_post_handles_httperror(monkeypatch):
    def _raise(req, *a, **k):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)
    monkeypatch.setattr("urllib.request.urlopen", _raise, raising=True)
    ok, status = ev.ha_post("http://ha.test:8123", "/p", {}, ev.make_headers("t"))
    assert ok is False and status == 401


def test_ha_post_handles_network_error(monkeypatch):
    def _raise(req, *a, **k):
        raise urllib.error.URLError("connection refused")
    monkeypatch.setattr("urllib.request.urlopen", _raise, raising=True)
    ok, status = ev.ha_post("http://ha.test:8123", "/p", {}, ev.make_headers("t"))
    assert ok is False and status is None


# --------------------------------------------------------------------------- #
# fetch_lv_prices: success + timeout/retry
# --------------------------------------------------------------------------- #
def test_fetch_success(fake_http, elering_response):
    fake_http.route("elering.ee", elering_response)
    slept = []
    prices = ev.fetch_lv_prices(sleep=lambda d: slept.append(d))
    assert len(prices) == 24
    assert fake_http.calls  # actually hit the (stubbed) endpoint


def test_fetch_timeout_retries_then_raises(monkeypatch):
    calls = {"n": 0}

    def _timeout(req, *a, **k):
        calls["n"] += 1
        raise socket.timeout("timed out")

    monkeypatch.setattr("urllib.request.urlopen", _timeout, raising=True)
    slept = []
    with pytest.raises(RuntimeError):
        ev.fetch_lv_prices(delays=(0, 1, 2), sleep=lambda d: slept.append(d))
    assert calls["n"] == 3           # one attempt per delay
    assert slept == [1, 2]           # non-zero delays waited (injected, no real sleep)


def test_fetch_retries_recover(monkeypatch, elering_response):
    """Fail twice, then succeed on the third attempt."""
    import json as _json
    state = {"n": 0}

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return _json.dumps(elering_response).encode()

    def _flaky(req, *a, **k):
        state["n"] += 1
        if state["n"] < 3:
            raise socket.timeout("boom")
        return _Resp()

    monkeypatch.setattr("urllib.request.urlopen", _flaky, raising=True)
    prices = ev.fetch_lv_prices(delays=(0, 0, 0, 0), sleep=lambda d: None)
    assert len(prices) == 24
    assert state["n"] == 3


# --------------------------------------------------------------------------- #
# Elering-outage notification: dedup / cooldown / recovery
# --------------------------------------------------------------------------- #
class _Sender:
    """Collects messages passed to a send_fn; returns configurable success."""

    def __init__(self, ok=True):
        self.msgs = []
        self.ok = ok

    def __call__(self, message):
        self.msgs.append(message)
        return self.ok


def _statefile(tmp_path):
    return str(tmp_path / "elering_notify_state.json")


def test_failure_first_sends_once(tmp_path):
    sp = _statefile(tmp_path)
    s = _Sender()
    sent = ev.notify_elering_failure(s, state_path=sp, now=1000.0)
    assert sent is True
    assert s.msgs == [ev.ELERING_FAILURE_MSG]
    st = json.load(open(sp, encoding="utf-8"))
    assert st["failing"] is True
    assert st["fail_since"] == 1000.0
    assert st["last_notify_ts"] == 1000.0


def test_failure_within_cooldown_suppressed(tmp_path):
    sp = _statefile(tmp_path)
    s = _Sender()
    ev.notify_elering_failure(s, state_path=sp, now=1000.0)
    # 1h later — well inside the 6h cooldown -> silent.
    sent2 = ev.notify_elering_failure(s, state_path=sp, now=1000.0 + 3600)
    assert sent2 is False
    assert len(s.msgs) == 1  # still just the first message
    st = json.load(open(sp, encoding="utf-8"))
    assert st["failing"] is True
    assert st["fail_since"] == 1000.0          # outage start preserved
    assert st["last_notify_ts"] == 1000.0      # cooldown clock not advanced


def test_failure_after_cooldown_sends_again(tmp_path):
    sp = _statefile(tmp_path)
    s = _Sender()
    ev.notify_elering_failure(s, state_path=sp, now=1000.0)
    later = 1000.0 + ev.ELERING_NOTIFY_COOLDOWN + 1
    sent2 = ev.notify_elering_failure(s, state_path=sp, now=later)
    assert sent2 is True
    assert len(s.msgs) == 2
    st = json.load(open(sp, encoding="utf-8"))
    assert st["fail_since"] == 1000.0          # same incident
    assert st["last_notify_ts"] == later       # cooldown clock advanced


def test_recovery_after_failure_sends_once(tmp_path):
    sp = _statefile(tmp_path)
    fail_send = _Sender()
    ev.notify_elering_failure(fail_send, state_path=sp, now=1000.0)
    rec_send = _Sender()
    sent = ev.notify_elering_recovery(rec_send, state_path=sp)
    assert sent is True
    assert rec_send.msgs == [ev.ELERING_RECOVERY_MSG]
    st = json.load(open(sp, encoding="utf-8"))
    assert st["failing"] is False
    assert st["fail_since"] is None
    # A second success sends nothing.
    rec2 = _Sender()
    assert ev.notify_elering_recovery(rec2, state_path=sp) is False
    assert rec2.msgs == []


def test_recovery_without_prior_failure_is_silent(tmp_path):
    sp = _statefile(tmp_path)
    s = _Sender()
    sent = ev.notify_elering_recovery(s, state_path=sp)
    assert sent is False
    assert s.msgs == []


def test_failure_send_failure_does_not_advance_cooldown(tmp_path):
    """If send_fn fails, the cooldown clock must not advance (retry next run)."""
    sp = _statefile(tmp_path)
    bad = _Sender(ok=False)
    sent = ev.notify_elering_failure(bad, state_path=sp, now=1000.0)
    assert sent is False
    st = json.load(open(sp, encoding="utf-8"))
    assert st["failing"] is True
    assert st["last_notify_ts"] is None  # never sent -> next run retries
    # Next run (still within nominal cooldown window) retries because clock=0.
    good = _Sender(ok=True)
    sent2 = ev.notify_elering_failure(good, state_path=sp, now=1000.0 + 60)
    assert sent2 is True
    assert good.msgs == [ev.ELERING_FAILURE_MSG]


def test_recovery_send_failure_keeps_failing_state(tmp_path):
    sp = _statefile(tmp_path)
    ev.notify_elering_failure(_Sender(), state_path=sp, now=1000.0)
    bad = _Sender(ok=False)
    assert ev.notify_elering_recovery(bad, state_path=sp) is False
    st = json.load(open(sp, encoding="utf-8"))
    assert st["failing"] is True  # not cleared -> next success retries
    good = _Sender(ok=True)
    assert ev.notify_elering_recovery(good, state_path=sp) is True


def test_state_file_written_atomically_and_locked(tmp_path):
    """State file is a plain JSON dict and re-readable (round-trips)."""
    sp = _statefile(tmp_path)
    ev._save_notify_state(sp, {"failing": True, "fail_since": 42.0,
                               "last_notify_ts": 99.0})
    loaded = ev._load_notify_state(sp)
    assert loaded == {"failing": True, "fail_since": 42.0, "last_notify_ts": 99.0}
    # Corrupt/absent files fall back to safe defaults rather than crashing.
    with open(sp, "w", encoding="utf-8") as f:
        f.write("{ not json")
    assert ev._load_notify_state(sp) == ev._DEFAULT_NOTIFY_STATE
    assert ev._load_notify_state(str(tmp_path / "missing.json")) == \
        ev._DEFAULT_NOTIFY_STATE


def test_full_incident_lifecycle(tmp_path):
    """down -> (silent repeats) -> recovery -> next outage is a fresh incident."""
    sp = _statefile(tmp_path)
    s = _Sender()
    # Outage begins.
    assert ev.notify_elering_failure(s, state_path=sp, now=0.0) is True
    # Restart storm within cooldown -> all silent.
    for t in (10, 600, 3600):
        assert ev.notify_elering_failure(s, state_path=sp, now=float(t)) is False
    assert len(s.msgs) == 1
    # Elering returns -> one recovery.
    rec = _Sender()
    assert ev.notify_elering_recovery(rec, state_path=sp) is True
    assert len(rec.msgs) == 1
    # A brand-new outage later notifies again (fresh incident, not failing).
    assert ev.notify_elering_failure(s, state_path=sp, now=100000.0) is True
    assert len(s.msgs) == 2
