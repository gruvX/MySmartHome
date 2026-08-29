#!/usr/bin/env python3
"""EV charger status/energy for Home Assistant — read from HA's OWN Tuya integration.

WHY (2026-08-19, "the free fix")
--------------------------------
Until today this script signed its own requests against **Tuya IoT Core**
(`apigw.tuyaeu.com`, `TUYA_CLIENT_ID`/`TUYA_CLIENT_SECRET`). That project's quota is
exhausted (`code 28841004`), so both `sensor.ev_charger_status` and
`sensor.ev_charger_energy` had been serving the same cached payload for hours
(`src=cache`, `stale_age` ≈ 3·10⁴ s) — frozen at `charger_insert` / `1040.23` kWh while
the car was in fact charging. Every EV verdict path then honestly reported
«нет свежих данных» instead of a real cause, and the owner had no way to see a charge
start. Buying quota would not have fixed the design: the same 26 000-calls/month tier
also carries the water-leak backup (`tuya_leak_query.py`), which is life-safety.

HA's own `tuya` integration (config entry, `tuya_sharing` SDK, app-account based) is a
SEPARATE credential path and is demonstrably alive: `mqtt_connected: True`, device DPs
pushed over MQTT in real time. It already holds the identical data for this charger in
memory — HA simply does not map Tuya category `qccdz` beyond the switch entity. So this
script now reads those in-memory DPs through HA's local integration-diagnostics endpoint:

    GET /api/diagnostics/config_entry/<tuya entry_id>   ->  data.devices[].status

MEASURED on this box: ~378 KB, 0.007-0.033 s, served entirely from
`manager.device_map` — no outbound Tuya request is possible in that time, and the
IoT Core quota was refusing every call while these reads succeeded. `charge_energy_once`
was observed incrementing every 20 s (1095 -> 1102 -> 1108 -> 1114 -> 1120), i.e. live.

Cost: **zero Tuya IoT Core calls.** The whole IoT Core path (token, HMAC signing,
`apigw.tuyaeu.com`) has been REMOVED from this file rather than kept as a fallback, so
it cannot re-burn quota that the leak backup needs. Restore it from git history if a
paid plan is ever bought — but then re-do the free-tier arithmetic locked by
`tests/test_leak_truth.py::test_leak_cloud_worst_case_fits_the_free_tier` first.

Freshness envelope (kept, extended)
-----------------------------------
Every emitted payload carries:
  src       — where this answer came from:
              local          fresh in-memory read via HA's tuya diagnostics (age 0)
              cache          our own result, younger than RESULT_TTL
              stale          local read failed; serving cache up to STALE_TTL
              error          local read failed (transport/auth/entry) AND no cache
              no_device      diagnostics fine, but the charger / its DPs are absent
                             AND no cache
              missing_config no HA token or base URL available
  stale_age — seconds since the data really came off the device (0 for a live read,
              None when there is no data at all).
A stale value must NEVER be presented as fresh: only `src == "local"` (and, for
historic records, `"cloud"`) counts as live in the consuming templates
(`automations.yaml` 1790100001001 / 1790500001001 / 1791000001001, `ev_replan_next.py`).

Value contract — DO NOT CHANGE
------------------------------
`sensor.ev_charger_energy` is a `total_increasing` kWh counter and feeds the daily /
monthly € accounting via `input_number.midnight_ev_energy`. Tuya reports
`forward_energy_total` and `charge_energy_once` with `scale: 2`, so both are divided by
100 exactly as the old cloud path did (104023 -> 1040.23). A partial read that lacks
`forward_energy_total` is treated as a FAILURE (serve cache), never as `0` — a phantom
0 followed by 1040.23 would be booked by HA statistics as 1040 kWh of consumption.
"""
import json
import os
import sys
import tempfile
import time
import urllib.request

try:
    import fcntl  # POSIX file locking (available on HA/Linux)
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None

sys.stdout.reconfigure(encoding="utf-8")

from project_secrets import secret

DEVICE_ID = secret("TUYA_EV_DEVICE_ID")
HA_TOKEN = secret("HA_TOKEN")
# The command_line sensor runs INSIDE the homeassistant container, where 127.0.0.1 is
# HA itself; HA_BASE_URL is the fallback that also works from the SSH add-on container
# and from a dev box on the LAN.
HA_BASES = [b for b in ("http://127.0.0.1:8123", secret("HA_BASE_URL")) if b]
EV_CATEGORY = "qccdz"

CACHE_DIR = "/config/.ev_cache" if os.path.isdir("/config") else os.path.join(os.getcwd(), ".ev_cache")
RESULT_CACHE = os.path.join(CACHE_DIR, "tuya_result.json")
LINK_CACHE = os.path.join(CACHE_DIR, "ha_link.json")
# Local reads are free (8 ms, no cloud), so the shared-result TTL only has to de-duplicate
# the two command_line sensors polling in the same instant and to blunt a forced
# `homeassistant.update_entity` storm. It used to be 290 s because every read cost a
# Tuya API call; keeping that value now would make a forced refresh useless.
RESULT_TTL = 10
STALE_TTL = 86400
# Tolerated clock jitter when judging a cache timestamp. Anything further in the future
# is a POISONED record: the removed quota branch used to stamp `ts` deliberately forward
# (now - RESULT_TTL + 1800) so HA would back off for ~30 min. Such a stamp must never be
# able to masquerade as fresh — measured 2026-08-19, a leftover forward stamp made a
# 31 279 s old payload pass a 10 s TTL check.
CLOCK_SKEW = 5
HTTP_TIMEOUT = 4          # per request
TOTAL_BUDGET = 10         # hard wall-clock budget; command_timeout defaults to 15 s

START = time.time()

# `cloud_error` is kept as the failure STATUS string (not `src`) purely for
# compatibility: the tablet panel, the Mini App graph and four automation templates
# already branch on it, and several of those files are out of scope for this change.
ERROR = {"energy": -1, "status": "cloud_error", "mode": "unknown", "switch": False, "session_kwh": 0}

LOCK_PATH = os.path.join(CACHE_DIR, ".lock")


def budget_left(need=0.0):
    return (time.time() - START) < (TOTAL_BUDGET - need)


def _ensure_cache_dir():
    """Create the cache dir with restrictive perms (700)."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        os.chmod(CACHE_DIR, 0o700)
    except OSError:
        pass


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            if fcntl is not None:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                except OSError:
                    pass
            return json.load(f)
    except Exception:
        return None


def save_json(path, data):
    """Atomically write JSON: temp file in the cache dir + os.replace.

    Serialized with an advisory exclusive lock so concurrent runs don't interleave.
    The result file is created with 0600 perms.
    """
    lock_fh = None
    try:
        _ensure_cache_dir()
        if fcntl is not None:
            try:
                lock_fh = open(LOCK_PATH, "w")
                os.chmod(LOCK_PATH, 0o600)
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
            except OSError:
                lock_fh = None
        fd, tmp = tempfile.mkstemp(dir=CACHE_DIR, prefix=".tmp-", suffix=".json")
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)  # atomic on POSIX
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception:
        pass
    finally:
        if lock_fh is not None:
            try:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            lock_fh.close()


_META_KEYS = ("src", "stale_age")
_LIVE_SRC = ("local",)
_PRINTED = False   # guarantees exactly ONE stdout line, ever


def _strip_meta(data):
    """Cache the device payload only; freshness labels are recomputed on every emit."""
    return {k: v for k, v in data.items() if k not in _META_KEYS}


def emit(data, cache_ts=None, src="local", origin_ts=None):
    global _PRINTED
    if _PRINTED:
        return
    _PRINTED = True
    payload = _strip_meta(data)
    if origin_ts is None and src in _LIVE_SRC:
        origin_ts = time.time()
    payload["src"] = src
    payload["stale_age"] = max(0, int(time.time() - origin_ts)) if origin_ts is not None else None
    print(json.dumps(payload))
    if cache_ts is not None:
        save_json(
            RESULT_CACHE,
            {"ts": cache_ts, "origin_ts": origin_ts, "data": _strip_meta(data)},
        )


def cached_result(max_age):
    """Return (payload, origin_ts) from the cache, or (None, None).

    `origin_ts` records when the data really came off the device, so a cache record can
    never be served as if it were fresh. Records written by the older format have no
    `origin_ts` and fall back to `ts`. A `ts` stamped in the future (see CLOCK_SKEW) is
    not trusted for the freshness decision — the honest `origin_ts` decides instead.
    """
    rc = load_json(RESULT_CACHE)
    if not isinstance(rc, dict):
        return None, None
    data = rc.get("data")
    if not isinstance(data, dict):
        return None, None
    now = time.time()
    origin = rc.get("origin_ts")
    if not isinstance(origin, (int, float)) or origin > now + CLOCK_SKEW:
        origin = None
    ts = rc.get("ts")
    if not isinstance(ts, (int, float)) or ts > now + CLOCK_SKEW:
        ts = origin
    if ts is None or ts <= now - max_age:
        return None, None
    return _strip_meta(data), (origin if origin is not None else ts)


# --------------------------------------------------------------------------- #
# Local Home Assistant access. The ONLY network destination in this file.
# --------------------------------------------------------------------------- #

def ha_get(base, path):
    """GET a JSON document from the local HA instance. Returns None on any failure."""
    try:
        req = urllib.request.Request(
            base + path,
            headers={"Authorization": "Bearer " + HA_TOKEN, "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None


def cached_link():
    link = load_json(LINK_CACHE)
    if isinstance(link, dict):
        base = link.get("base")
        entry = link.get("entry_id")
        if isinstance(base, str) and isinstance(entry, str) and base and entry:
            return base, entry
    return None, None


def discover_link():
    """Find (base_url, tuya entry_id) by asking HA. Cached afterwards.

    Deliberately NOT hardcoded: the entry_id changes if the integration is ever
    re-added, and a hardcoded one would silently freeze the sensors again.
    """
    for base in HA_BASES:
        if not budget_left(HTTP_TIMEOUT):
            return None, None
        entries = ha_get(base, "/api/config/config_entries/entry")
        if not isinstance(entries, list):
            continue
        for e in entries:
            if isinstance(e, dict) and e.get("domain") == "tuya" and not e.get("disabled_by"):
                entry_id = e.get("entry_id")
                if isinstance(entry_id, str) and entry_id:
                    save_json(LINK_CACHE, {"base": base, "entry_id": entry_id})
                    return base, entry_id
    return None, None


def iter_devices(devices):
    if isinstance(devices, list):
        for d in devices:
            if isinstance(d, dict):
                yield d
    elif isinstance(devices, dict):
        for d in devices.values():
            if isinstance(d, dict):
                yield d


def pick_device(diag):
    """Return the EV charger's device dict from a tuya diagnostics dump, or None.

    Matches on the configured device id first, then on Tuya category `qccdz`, so a
    replaced/re-paired charger keeps working without editing secrets.
    """
    if not isinstance(diag, dict):
        return None
    devices = (diag.get("data") or {}).get("devices")
    by_category = None
    for dev in iter_devices(devices):
        if DEVICE_ID and dev.get("id") == DEVICE_ID:
            return dev
        if dev.get("category") == EV_CATEGORY and by_category is None:
            by_category = dev
    return by_category


def scale2(value):
    """Tuya `scale: 2` integer -> kWh. Returns None when the DP is unusable."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(value * 0.01, 2)


def build_result(dev):
    """DPs -> the payload shape HA has always consumed, or None if unusable."""
    status = dev.get("status")
    if isinstance(status, list):  # tolerate the [{code,value}] shape too
        status = {s.get("code"): s.get("value") for s in status if isinstance(s, dict)}
    if not isinstance(status, dict):
        return None
    energy = scale2(status.get("forward_energy_total"))
    work_state = status.get("work_state")
    if energy is None or not isinstance(work_state, str) or not work_state:
        # Partial read. Emitting energy 0 here would be booked by HA statistics as a
        # counter reset and then ~1040 kWh of phantom consumption.
        return None
    session = scale2(status.get("charge_energy_once"))
    return {
        "energy": energy,
        "status": work_state,
        "mode": str(status.get("work_mode", "unknown")),
        "switch": bool(status.get("switch", False)),
        "session_kwh": session if session is not None else 0,
    }


def read_local():
    """(payload, failure_src). failure_src is None on success."""
    base, entry_id = cached_link()
    diag = None
    if base and entry_id and budget_left(HTTP_TIMEOUT):
        diag = ha_get(base, "/api/diagnostics/config_entry/" + entry_id)
    if diag is None:
        base, entry_id = discover_link()
        if base and entry_id and budget_left(HTTP_TIMEOUT):
            diag = ha_get(base, "/api/diagnostics/config_entry/" + entry_id)
    if diag is None:
        # No answer: HA busy, token rejected, entry unloaded/reloading, or no route.
        return None, "error"
    dev = pick_device(diag)
    if dev is None:
        return None, "no_device"
    result = build_result(dev)
    if result is None:
        return None, "no_device"
    return result, None


def main():
    if not HA_TOKEN or not HA_BASES:
        emit({**ERROR, "status": "missing_config"}, src="missing_config")
        return

    fresh, fresh_origin = cached_result(RESULT_TTL)
    if fresh:
        emit(fresh, src="cache", origin_ts=fresh_origin)
        return

    result, failure = read_local()
    if result is not None:
        emit(result, cache_ts=time.time())
        return

    stale, stale_origin = cached_result(STALE_TTL)
    if stale:
        emit(stale, src="stale", origin_ts=stale_origin)
    else:
        emit(ERROR, src=failure or "error")


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        # HA must always get exactly one parseable line, never a traceback on stdout.
        if not _PRINTED:
            print(json.dumps({**ERROR, "src": "error", "stale_age": None}))
