"""Surgical-patch tests for the DEPLOYED ev_best2h.py Elering-notify fix.

Scope of the change under test
------------------------------
The DEPLOYED /config/ev_best2h.py is a STANDALONE script (it does NOT import
ev_common — ev_common.py is not present on the box). The surgical fix adds an
INLINE Elering-outage notification dedup + 6h cooldown + one-shot recovery, and
swaps ONLY the two notify call-sites. It must NOT change any charging / window /
schedule / trigger / exit-code behaviour.

These tests therefore assert two things:

1. Behaviour of the new notification helpers (dedup / cooldown / recovery,
   atomic+safe state file).
2. That the charging logic is byte-for-byte preserved vs the deployed baseline
   — in particular the single-slot fallback in find_best_2h (the fallback a
   prior-session ev_common refactor removed, which the owner forbade) and the
   input_datetime.ev_charge_start set_datetime + exit codes.

The patched deployed file lives at docs/audit/ev_best2h.deployed_patched.py and
the byte-exact deployed baseline (md5 0600cbd7c036cde2e3febbef0780b5cd) at
docs/audit/ev_best2h.deployed_baseline.py. All network is stubbed; no real
Elering/HA/Tuya calls.
"""
from __future__ import annotations

import datetime
import difflib
import hashlib
import importlib.util
import io
import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
BASELINE = REPO / "docs" / "audit" / "ev_best2h.deployed_baseline.py"
PATCHED = REPO / "docs" / "audit" / "ev_best2h.deployed_patched.py"

# The exact md5 of the file currently deployed at /config/ev_best2h.py. The
# deploy guard must refuse to deploy unless the live file matches this.
DEPLOYED_BASELINE_MD5 = "0600cbd7c036cde2e3febbef0780b5cd"

UTC = datetime.timezone.utc


# --------------------------------------------------------------------------- #
# Module loader — import the patched deployed script by path.
# The script calls sys.stdout.reconfigure() at import; pytest's captured stdout
# may lack reconfigure, so give it a stand-in for the duration of the import.
# --------------------------------------------------------------------------- #
class _ReconfigurableIO(io.StringIO):
    def reconfigure(self, *args, **kwargs):
        return None


def _load_patched():
    spec = importlib.util.spec_from_file_location("ev_best2h_patched", PATCHED)
    mod = importlib.util.module_from_spec(spec)
    real_stdout = sys.stdout
    sys.stdout = _ReconfigurableIO()
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.stdout = real_stdout
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_patched()


def _statefile(tmp_path):
    return str(tmp_path / "elering_notify_state.json")


class _Sender:
    """Collects messages passed to a send_fn; returns configurable success."""

    def __init__(self, ok=True):
        self.msgs = []
        self.ok = ok

    def __call__(self, message):
        self.msgs.append(message)
        return self.ok


# --------------------------------------------------------------------------- #
# 1. Deploy-guard baseline integrity
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_deployed_baseline_md5_matches_guard():
    data = BASELINE.read_bytes()
    assert hashlib.md5(data).hexdigest() == DEPLOYED_BASELINE_MD5


# --------------------------------------------------------------------------- #
# 2. Charging / window / schedule / exit-code path unchanged vs deployed
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_diff_is_notification_only():
    """The ONLY deployed lines that disappear are the two non-charging lines:
    the old import line (extended with os/tempfile) and the unconditional
    failure-notify ha_post. Everything the patch does is ADD lines."""
    base = BASELINE.read_text(encoding="utf-8").splitlines()
    patched = PATCHED.read_text(encoding="utf-8").splitlines()

    removed = []  # lines present in deployed baseline but not in patched
    for line in difflib.unified_diff(base, patched, lineterm=""):
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("-"):
            removed.append(line[1:])

    expected_removed = {
        "import sys, json, urllib.request, urllib.error, datetime, time",
        '        ha_post("/api/services/notify/send_message", '
        '{"entity_id": TG, "message": msg})',
    }
    assert set(removed) == expected_removed, (
        "patch removed/altered unexpected deployed lines: "
        f"{set(removed) - expected_removed}"
    )
    # Neither removed line is charging/window/schedule/exit-code logic.
    joined = "\n".join(removed)
    for forbidden in ("find_best_2h", "set_datetime", "sys.exit",
                      "ev_charge_start", "best_start", "cheapest",
                      "Fallback", "cutoff"):
        assert forbidden not in joined


@pytest.mark.unit
def test_charging_landmarks_preserved_in_source():
    """The exact deployed charging/window/schedule/exit lines must survive."""
    patched = PATCHED.read_text(encoding="utf-8")
    for landmark in (
        "    # Fallback: cheapest single slot",
        '        cheapest   = min(future, key=lambda x: x["price"])',
        '        best_start = cheapest["dt"]',
        '        best_avg   = cheapest["price"]',
        'ha_post("/api/services/input_datetime/set_datetime", {',
        '        "entity_id": "input_datetime.ev_charge_start",',
        "    cutoff = now_utc + datetime.timedelta(minutes=10)",
        "        sys.exit(2)",
        "        sys.exit(1)",
        "        sys.exit(0)",
    ):
        assert landmark in patched, f"missing charging landmark: {landmark!r}"


@pytest.mark.unit
def test_find_best_2h_single_slot_fallback_intact(mod):
    """The DEPLOYED single-slot fallback (removed by the forbidden ev_common
    refactor) must still be present: a lone future slot yields a window."""
    now = datetime.datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
    lone = [{"dt": now + datetime.timedelta(hours=1), "price": 0.001}]
    best, avg = mod.find_best_2h(lone, now)
    assert best == lone[0]["dt"]
    assert avg == pytest.approx(0.001)


@pytest.mark.unit
def test_find_best_2h_prefers_contiguous_over_fallback(mod):
    """When a genuine contiguous 2h window exists it is chosen (unchanged)."""
    now = datetime.datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
    base = now + datetime.timedelta(hours=1)
    slots = [
        {"dt": base + datetime.timedelta(minutes=15 * i), "price": 0.05}
        for i in range(8)
    ]
    best, avg = mod.find_best_2h(slots, now)
    assert best == slots[0]["dt"]
    assert avg == pytest.approx(0.05)


# --------------------------------------------------------------------------- #
# 3. Notification behaviour: dedup / cooldown / recovery
# --------------------------------------------------------------------------- #
FAIL_MSG = "⚠️ EV планировщик: Elering API временно недоступен. Расписание не изменено."


@pytest.mark.unit
def test_failure_first_sends_once(mod, tmp_path):
    sp = _statefile(tmp_path)
    s = _Sender()
    assert mod.notify_elering_failure(s, FAIL_MSG, state_path=sp, now=1000.0) is True
    assert s.msgs == [FAIL_MSG]
    st = json.load(open(sp, encoding="utf-8"))
    assert st == {"failing": True, "fail_since": 1000.0, "last_notify_ts": 1000.0}


@pytest.mark.unit
def test_failure_within_cooldown_suppressed(mod, tmp_path):
    sp = _statefile(tmp_path)
    s = _Sender()
    mod.notify_elering_failure(s, FAIL_MSG, state_path=sp, now=1000.0)
    # 1h later, well inside the 6h cooldown -> silent.
    assert mod.notify_elering_failure(s, FAIL_MSG, state_path=sp,
                                      now=1000.0 + 3600) is False
    assert len(s.msgs) == 1
    st = json.load(open(sp, encoding="utf-8"))
    assert st["fail_since"] == 1000.0        # outage start preserved
    assert st["last_notify_ts"] == 1000.0    # cooldown clock not advanced


@pytest.mark.unit
def test_failure_after_cooldown_sends_again(mod, tmp_path):
    sp = _statefile(tmp_path)
    s = _Sender()
    mod.notify_elering_failure(s, FAIL_MSG, state_path=sp, now=1000.0)
    later = 1000.0 + mod.ELERING_NOTIFY_COOLDOWN + 1
    assert mod.notify_elering_failure(s, FAIL_MSG, state_path=sp, now=later) is True
    assert len(s.msgs) == 2
    st = json.load(open(sp, encoding="utf-8"))
    assert st["fail_since"] == 1000.0        # same incident
    assert st["last_notify_ts"] == later     # cooldown clock advanced


@pytest.mark.unit
def test_cooldown_is_six_hours(mod):
    assert mod.ELERING_NOTIFY_COOLDOWN == 6 * 3600


@pytest.mark.unit
def test_recovery_after_failure_sends_once(mod, tmp_path):
    sp = _statefile(tmp_path)
    mod.notify_elering_failure(_Sender(), FAIL_MSG, state_path=sp, now=1000.0)
    rec = _Sender()
    assert mod.notify_elering_recovery(rec, state_path=sp) is True
    assert rec.msgs == [mod.ELERING_RECOVERY_MSG]
    st = json.load(open(sp, encoding="utf-8"))
    assert st == mod._DEFAULT_NOTIFY_STATE
    # A second success sends nothing.
    rec2 = _Sender()
    assert mod.notify_elering_recovery(rec2, state_path=sp) is False
    assert rec2.msgs == []


@pytest.mark.unit
def test_recovery_without_prior_failure_is_silent(mod, tmp_path):
    sp = _statefile(tmp_path)
    s = _Sender()
    assert mod.notify_elering_recovery(s, state_path=sp) is False
    assert s.msgs == []
    # No state file need exist for a silent no-op recovery.
    assert not os.path.exists(sp)


@pytest.mark.unit
def test_failed_send_does_not_advance_cooldown(mod, tmp_path):
    sp = _statefile(tmp_path)
    bad = _Sender(ok=False)
    assert mod.notify_elering_failure(bad, FAIL_MSG, state_path=sp, now=1000.0) is False
    st = json.load(open(sp, encoding="utf-8"))
    assert st["failing"] is True
    assert st["last_notify_ts"] is None      # never sent -> retry next run
    # Next run within the nominal cooldown still retries because clock is unset.
    good = _Sender(ok=True)
    assert mod.notify_elering_failure(good, FAIL_MSG, state_path=sp,
                                      now=1000.0 + 60) is True
    assert good.msgs == [FAIL_MSG]


@pytest.mark.unit
def test_recovery_send_failure_keeps_failing_state(mod, tmp_path):
    sp = _statefile(tmp_path)
    mod.notify_elering_failure(_Sender(), FAIL_MSG, state_path=sp, now=1000.0)
    assert mod.notify_elering_recovery(_Sender(ok=False), state_path=sp) is False
    st = json.load(open(sp, encoding="utf-8"))
    assert st["failing"] is True             # not cleared -> next success retries
    assert mod.notify_elering_recovery(_Sender(ok=True), state_path=sp) is True


@pytest.mark.unit
def test_full_incident_lifecycle(mod, tmp_path):
    """down -> silent repeats -> recovery -> a later outage is a fresh incident."""
    sp = _statefile(tmp_path)
    s = _Sender()
    assert mod.notify_elering_failure(s, FAIL_MSG, state_path=sp, now=0.0) is True
    for t in (10, 600, 3600):
        assert mod.notify_elering_failure(s, FAIL_MSG, state_path=sp,
                                          now=float(t)) is False
    assert len(s.msgs) == 1
    rec = _Sender()
    assert mod.notify_elering_recovery(rec, state_path=sp) is True
    assert len(rec.msgs) == 1
    assert mod.notify_elering_failure(s, FAIL_MSG, state_path=sp,
                                      now=100000.0) is True
    assert len(s.msgs) == 2


# --------------------------------------------------------------------------- #
# 4. State file: atomic, safe defaults, 0600, never raises
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_state_round_trips(mod, tmp_path):
    sp = _statefile(tmp_path)
    mod._save_notify_state(sp, {"failing": True, "fail_since": 42.0,
                                "last_notify_ts": 99.0})
    assert mod._load_notify_state(sp) == {
        "failing": True, "fail_since": 42.0, "last_notify_ts": 99.0
    }


@pytest.mark.unit
def test_state_corrupt_and_missing_fall_back_to_defaults(mod, tmp_path):
    sp = _statefile(tmp_path)
    with open(sp, "w", encoding="utf-8") as f:
        f.write("{ not json")
    assert mod._load_notify_state(sp) == mod._DEFAULT_NOTIFY_STATE
    assert mod._load_notify_state(str(tmp_path / "missing.json")) == \
        mod._DEFAULT_NOTIFY_STATE


@pytest.mark.unit
def test_state_file_permissions_are_0600(mod, tmp_path):
    sp = _statefile(tmp_path)
    mod._save_notify_state(sp, dict(mod._DEFAULT_NOTIFY_STATE))
    assert (os.stat(sp).st_mode & 0o777) == 0o600


@pytest.mark.unit
def test_save_never_raises_on_bad_path(mod):
    # A path whose parent cannot be created must not raise.
    mod._save_notify_state("/proc/nonexistent_dir/state.json",
                           dict(mod._DEFAULT_NOTIFY_STATE))


# --------------------------------------------------------------------------- #
# 5. _send_notify wrapper: 2xx -> True, non-2xx/raise -> False (never raises)
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_send_notify_true_on_2xx(mod, monkeypatch):
    monkeypatch.setattr(mod, "ha_post", lambda path, data: 200)
    assert mod._send_notify("hi") is True


@pytest.mark.unit
def test_send_notify_false_on_non_2xx(mod, monkeypatch):
    monkeypatch.setattr(mod, "ha_post", lambda path, data: 500)
    assert mod._send_notify("hi") is False


@pytest.mark.unit
def test_send_notify_false_when_ha_post_raises(mod, monkeypatch):
    def _boom(path, data):
        raise RuntimeError("network down")
    monkeypatch.setattr(mod, "ha_post", _boom)
    assert mod._send_notify("hi") is False
