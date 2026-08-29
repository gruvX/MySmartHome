"""Unit tests for ev_query: cache hardening + the local-source freshness envelope.

Covers: atomic write (temp file + os.replace), 0600 file perms, 0700 dir
perms, load/save roundtrip, atomicity under a mid-write failure (existing
cache preserved, no stray temp files), and the `src` / `stale_age` labels for
every source and failure mode. No network is touched.
"""
from __future__ import annotations

import json
import os
import stat

import pytest

import ev_query


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    """Redirect ev_query's cache globals into a temp dir."""
    d = tmp_path / "cache"
    monkeypatch.setattr(ev_query, "CACHE_DIR", str(d), raising=True)
    monkeypatch.setattr(ev_query, "LOCK_PATH", str(d / ".lock"), raising=True)
    monkeypatch.setattr(ev_query, "RESULT_CACHE", str(d / "tuya_result.json"), raising=True)
    monkeypatch.setattr(ev_query, "LINK_CACHE", str(d / "ha_link.json"), raising=True)
    return d


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


def test_save_creates_file_and_roundtrips(cache_dir):
    target = str(cache_dir / "tuya_result.json")
    payload = {"ts": 123, "data": {"energy": 1.5, "status": "charger_charging"}}
    ev_query.save_json(target, payload)
    assert os.path.exists(target)
    assert ev_query.load_json(target) == payload


def test_cache_dir_perms_700(cache_dir):
    ev_query.save_json(str(cache_dir / "tuya_result.json"), {"a": 1})
    assert _mode(str(cache_dir)) == 0o700


def test_cache_file_perms_600(cache_dir):
    target = str(cache_dir / "tuya_result.json")
    ev_query.save_json(target, {"a": 1})
    assert _mode(target) == 0o600


def test_write_is_atomic_via_replace(cache_dir, monkeypatch):
    """os.replace must be the mechanism that publishes the file."""
    calls = {"replace": 0}
    real_replace = os.replace

    def _spy(src, dst):
        calls["replace"] += 1
        return real_replace(src, dst)

    monkeypatch.setattr(ev_query.os, "replace", _spy, raising=True)
    ev_query.save_json(str(cache_dir / "tuya_result.json"), {"x": 1})
    assert calls["replace"] == 1


def test_failed_write_preserves_existing_and_leaves_no_temp(cache_dir, monkeypatch):
    target = str(cache_dir / "tuya_result.json")
    good = {"ts": 1, "data": {"ok": True}}
    ev_query.save_json(target, good)
    assert ev_query.load_json(target) == good

    # Force json.dump to blow up mid-write.
    def _boom(*a, **k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(ev_query.json, "dump", _boom, raising=True)
    # save_json swallows the error (best-effort cache), but the old file
    # must remain intact and no .tmp-* file should be left behind.
    ev_query.save_json(target, {"ts": 2, "data": {"ok": False}})

    assert ev_query.load_json(target) == good  # unchanged
    leftovers = [n for n in os.listdir(str(cache_dir)) if n.startswith(".tmp-")]
    assert leftovers == []


def test_load_missing_returns_none(cache_dir):
    assert ev_query.load_json(str(cache_dir / "nope.json")) is None


def test_concurrent_saves_do_not_corrupt(cache_dir):
    """Sequential saves via the locked path keep the file always parseable."""
    target = str(cache_dir / "tuya_result.json")
    for i in range(20):
        ev_query.save_json(target, {"ts": i, "data": {"n": i}})
        # File must always be complete/parseable JSON after each replace.
        with open(target, encoding="utf-8") as f:
            assert json.load(f)["ts"] == i


# --------------------------------------------------------------------------- #
# Source + freshness envelope
#
# 2026-08-16: ev_query may serve a cached payload for up to STALE_TTL (24 h) after a
# failure. Before that envelope a cached serve looked exactly like a live read, so
# `sensor.ev_charger_status` could lag a whole day invisibly. Every emit carries
# `src` + `stale_age`, and `stale_age` is measured from `origin_ts` — the moment the
# data really came off the device — so re-serving cannot hide age.
#
# 2026-08-19 ("the free fix"): the data source moved from Tuya IoT Core (quota
# exhausted, `code 28841004`) to HA's OWN alive `tuya` integration, read locally
# through /api/diagnostics/config_entry/<entry>. A live read is now labelled
# `src="local"`. The IoT Core path was REMOVED, not kept as a fallback, so it can
# never re-burn the 26 000-calls/month tier that the water-leak backup needs.
# --------------------------------------------------------------------------- #
import contextlib
import io
import time


DEVICE_PAYLOAD = {
    "energy": 10.0,
    "status": "charger_charging",
    "mode": "m",
    "switch": True,
    "session_kwh": 1.0,
}

# Shape of one device inside data.devices[] of the tuya diagnostics dump.
# Values are the real ones measured on the box (scale 2 -> divide by 100).
EV_DEVICE = {
    "id": "dev",
    "name": "EV Charger",
    "category": "qccdz",
    "online": True,
    "status": {
        "forward_energy_total": 104023,
        "work_state": "charger_charging",
        "work_mode": "charge_now",
        "switch": False,
        "charge_energy_once": 1057,
    },
}


def _diag(devices):
    return {"data": {"mqtt_connected": True, "devices": devices}}


def _emitted(fn):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn()
    return json.loads(buf.getvalue().strip())


@pytest.fixture
def ev(cache_dir, monkeypatch):
    """ev_query with local HA access configured and the network unreachable by default."""
    monkeypatch.setattr(ev_query, "HA_TOKEN", "tok", raising=True)
    monkeypatch.setattr(ev_query, "HA_BASES", ["http://ha.invalid:8123"], raising=True)
    monkeypatch.setattr(ev_query, "DEVICE_ID", "dev", raising=True)
    monkeypatch.setattr(ev_query, "START", time.time(), raising=True)
    monkeypatch.setattr(ev_query, "_PRINTED", False, raising=True)
    monkeypatch.setattr(ev_query, "ha_get", lambda base, path: None, raising=True)
    return ev_query


def _serve(monkeypatch, entries, diag):
    """Stub the only network function with a fake local HA."""

    def _ha_get(base, path):
        if path.startswith("/api/config/config_entries/entry"):
            return entries
        if path.startswith("/api/diagnostics/config_entry/"):
            return diag
        return None

    monkeypatch.setattr(ev_query, "ha_get", _ha_get, raising=True)


ENTRIES = [{"domain": "tuya", "entry_id": "01ENTRY", "disabled_by": None}]


# --- the four cases the deployment had to prove --------------------------------- #

def test_fresh_local_read_is_labelled_local_with_zero_age(ev, monkeypatch):
    """Case 1: fresh local read."""
    _serve(monkeypatch, ENTRIES, _diag([EV_DEVICE]))
    out = _emitted(ev.main)
    assert out["src"] == "local"
    assert out["stale_age"] == 0
    assert out["status"] == "charger_charging"
    # scale 2: 104023 -> 1040.23 kWh, 1057 -> 10.57 kWh. A scale slip here would
    # corrupt the owner's daily/monthly cost history.
    assert out["energy"] == 1040.23
    assert out["session_kwh"] == 10.57


def test_local_read_unavailable_serves_cache_as_stale(ev):
    """Case 2: local read unavailable (HA busy / no route / token rejected)."""
    old = time.time() - 7200
    ev.save_json(ev.RESULT_CACHE, {"ts": old, "origin_ts": old, "data": dict(DEVICE_PAYLOAD)})
    out = _emitted(ev.main)
    assert out["src"] == "stale"
    assert 7100 <= out["stale_age"] <= 7300
    assert out["status"] == "charger_charging", "stale value is preserved, but labelled stale"


def test_integration_reloading_reports_error_when_there_is_no_cache(ev, monkeypatch):
    """Case 3: entry present but diagnostics unavailable (integration reloading)."""
    _serve(monkeypatch, ENTRIES, None)
    out = _emitted(ev.main)
    assert out["src"] == "error"
    assert out["stale_age"] is None
    assert out["status"] == "cloud_error"


def test_device_missing_from_dump_is_labelled_no_device(ev, monkeypatch):
    """Case 4: diagnostics fine, charger absent (device removed / re-pairing)."""
    _serve(monkeypatch, ENTRIES, _diag([{"id": "other", "category": "cz", "status": {}}]))
    out = _emitted(ev.main)
    assert out["src"] == "no_device"
    assert out["stale_age"] is None


def test_device_missing_but_cache_present_stays_honest(ev, monkeypatch):
    _serve(monkeypatch, ENTRIES, _diag([]))
    old = time.time() - 300
    ev.save_json(ev.RESULT_CACHE, {"ts": old, "origin_ts": old, "data": dict(DEVICE_PAYLOAD)})
    out = _emitted(ev.main)
    assert out["src"] == "stale"
    assert 290 <= out["stale_age"] <= 320


# --- value integrity ----------------------------------------------------------- #

def test_partial_read_never_emits_zero_energy(ev, monkeypatch):
    """A dump without forward_energy_total must NOT be published as 0 kWh.

    `sensor.ev_charger_energy` is `total_increasing`: a 0 followed by 1040.23 would be
    booked by HA statistics as ~1040 kWh of phantom consumption and would corrupt the
    monthly € accounting that reads it via input_number.midnight_ev_energy.
    """
    broken = dict(EV_DEVICE, status={"work_state": "charger_charging"})
    _serve(monkeypatch, ENTRIES, _diag([broken]))
    old = time.time() - 60
    ev.save_json(ev.RESULT_CACHE, {"ts": old, "origin_ts": old, "data": dict(DEVICE_PAYLOAD)})
    out = _emitted(ev.main)
    assert out["src"] == "stale"
    assert out["energy"] == 10.0, "cached value kept; a phantom 0 must never be emitted"


def test_device_matched_by_category_when_id_changed(ev, monkeypatch):
    """A re-paired charger keeps working without editing secrets."""
    monkeypatch.setattr(ev, "DEVICE_ID", "some-old-id", raising=True)
    _serve(monkeypatch, ENTRIES, _diag([EV_DEVICE]))
    out = _emitted(ev.main)
    assert out["src"] == "local" and out["energy"] == 1040.23


def test_status_list_shape_is_tolerated(ev, monkeypatch):
    listed = dict(EV_DEVICE, status=[{"code": k, "value": v}
                                     for k, v in EV_DEVICE["status"].items()])
    _serve(monkeypatch, ENTRIES, _diag([listed]))
    out = _emitted(ev.main)
    assert out["src"] == "local" and out["energy"] == 1040.23


# --- cache/labelling invariants ------------------------------------------------ #

def test_meta_is_never_written_into_the_cache(ev):
    _emitted(lambda: ev.emit(dict(DEVICE_PAYLOAD), cache_ts=time.time()))
    rec = ev.load_json(ev.RESULT_CACHE)
    assert "src" not in rec["data"] and "stale_age" not in rec["data"], (
        "freshness labels must be recomputed on every emit, never cached"
    )
    assert isinstance(rec["origin_ts"], (int, float))


def test_recent_cache_is_labelled_cache_not_local(ev):
    """The shared-result TTL must never masquerade as a live read."""
    old = time.time() - 5
    ev.save_json(ev.RESULT_CACHE, {"ts": old, "origin_ts": old, "data": dict(DEVICE_PAYLOAD)})
    out = _emitted(ev.main)
    assert out["src"] == "cache"
    assert 4 <= out["stale_age"] <= 8


def test_no_data_at_all_reports_error_and_null_age(ev):
    out = _emitted(ev.main)
    assert out["src"] == "error"
    assert out["stale_age"] is None


def test_missing_config_is_labelled(ev, monkeypatch):
    monkeypatch.setattr(ev, "HA_TOKEN", "", raising=True)
    out = _emitted(ev.main)
    assert out["src"] == "missing_config"
    assert out["stale_age"] is None


def test_future_stamped_record_is_never_served_as_fresh(ev):
    """The removed quota branch stamped `ts` deliberately forward (now + ~1510 s) so HA
    would back off. MEASURED 2026-08-19: such a leftover record passed the TTL check and
    kept a 31 279 s old `charger_insert` on screen while the car was charging. The honest
    `origin_ts` must decide, and the payload must be labelled `stale`.
    """
    origin = time.time() - 31279
    ev.save_json(ev.RESULT_CACHE,
                 {"ts": time.time() + 1510, "origin_ts": origin, "data": dict(DEVICE_PAYLOAD)})
    fresh, _ = ev.cached_result(ev.RESULT_TTL)
    assert fresh is None, "a forward-stamped record must not satisfy the fresh TTL"
    out = _emitted(ev.main)
    assert out["src"] == "stale"
    assert 31200 <= out["stale_age"] <= 31400


def test_future_stamped_record_without_origin_is_rejected(ev):
    """No honest timestamp at all -> the record cannot be aged, so it is not used."""
    ev.save_json(ev.RESULT_CACHE, {"ts": time.time() + 3600, "data": dict(DEVICE_PAYLOAD)})
    assert ev.cached_result(ev.RESULT_TTL) == (None, None)
    assert ev.cached_result(ev.STALE_TTL) == (None, None)
    out = _emitted(ev.main)
    assert out["src"] == "error" and out["stale_age"] is None


def test_legacy_cache_record_without_origin_ts_still_ages(ev):
    """Records written by the pre-2026-08-16 format fall back to `ts`."""
    ev.save_json(ev.RESULT_CACHE, {"ts": time.time() - 3600, "data": dict(DEVICE_PAYLOAD)})
    out = _emitted(ev.main)
    assert out["src"] == "stale"
    assert 3500 <= out["stale_age"] <= 3700


def test_exactly_one_line_is_ever_printed(ev, monkeypatch):
    _serve(monkeypatch, ENTRIES, _diag([EV_DEVICE]))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ev.main()
        ev.main()  # a second call must not add a second line
    assert len([ln for ln in buf.getvalue().splitlines() if ln.strip()]) == 1


def test_cache_paths_and_ttls():
    assert ev_query.STALE_TTL == 86400
    assert ev_query.RESULT_CACHE.endswith("tuya_result.json")
    assert ev_query.LINK_CACHE.endswith("ha_link.json")
    # Local reads cost nothing, so the shared TTL is short enough that a forced
    # homeassistant.update_entity actually fetches live data.
    assert 0 < ev_query.RESULT_TTL <= 30
    assert 0 < ev_query.CLOCK_SKEW <= 60
    assert ev_query.TOTAL_BUDGET < 15, "command_timeout for these sensors defaults to 15 s"


# --- the whole point: zero Tuya IoT Core calls --------------------------------- #

IOT_CORE_MARKERS = (
    "apigw.tuya",
    "openapi.tuya",
    "hmac",
    "sign_method",
    "HMAC-SHA256",
    "TUYA_CLIENT_ID",
    "TUYA_CLIENT_SECRET",
    "grant_type=1",
    "access_token",
)


def test_source_contains_no_tuya_iot_core_call_site():
    """Structural proof that steady state costs 0 Tuya IoT Core calls.

    The quota-limited path is not throttled, it is absent: there is no signing code
    and no tuya endpoint left in this module, so no failure mode can revive it and
    eat the free tier that tuya_leak_query.py (water-leak backup) depends on.
    """
    src = open(ev_query.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    code = "\n".join(
        line for line in src.splitlines()
        if not line.lstrip().startswith("#")
    )
    # Strip the module docstring, which legitimately explains the removed path.
    body = code.split('"""', 2)[-1]
    for marker in IOT_CORE_MARKERS:
        assert marker not in body, f"Tuya IoT Core call site re-appeared: {marker}"


def test_only_network_destination_is_the_local_ha_instance():
    assert ev_query.HA_BASES, "no HA base URL configured"
    for base in ev_query.HA_BASES:
        assert base.startswith("http://") or base.startswith("https://")
        assert "tuya" not in base
