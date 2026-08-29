#!/usr/bin/env python3
"""Independent Tuya-cloud leak truth source for Home Assistant.

Queries the 4 Tuya water-leak sensors (category sj, DP watersensor_state) in ONE
batch cloud call and prints a single JSON line on stdout.

Design rules (life-safety component):
  * ALWAYS print exactly one valid JSON line, even on failure/timeout.
  * Print BEFORE touching the cache file (HA must get output even if disk write fails).
  * Never raise, never print a traceback on stdout, never print any secret.
  * FAIL-SAFE POLARITY: only explicit alarm markers count as alarm. Anything
    unrecognised is "unknown", never "alarm". Raw DP values are always exposed so
    the real polarity can be proven by a real wetting.

Output:
  {"state": "alarm|normal|unknown",
   "alarm_entities": [...], "raw": {...}, "online": {...},
   "ts": <unix>, "src": "cloud|cache|error"}
"""
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://apigw.tuyaeu.com"
SECRETS_FILES = ("/config/local_secrets.json",
                 os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_secrets.json"))
CACHE_DIR = "/config/.tuya_leak_cache" if os.path.isdir("/config") else os.path.join(os.getcwd(), ".tuya_leak_cache")
TOKEN_CACHE = os.path.join(CACHE_DIR, "token.json")
RESULT_CACHE = os.path.join(CACHE_DIR, "result.json")

HTTP_TIMEOUT = 8          # per-request
TOTAL_BUDGET = 15         # hard wall-clock budget for all network work
FRESH_TTL = 20            # re-serve our own very recent result instead of re-calling
STALE_TTL = 86400         # how long a cached result may still be reported
QUOTA_BACKOFF = 300       # on Tuya quota error, serve cache for this long
FAIL_BACKOFF = 120        # on ANY other cloud failure, serve cache for this long

# device_id -> HA entity_id
DEVICES = {
    "bf9b5a67b2b694d774w7lr": "binary_sensor.water_sensor_4_moisture",  # Душевая 1ый этаж
    "bf2570eaf64eca1be2tl9r": "binary_sensor.vannaia_moisture",         # Ванная
    "bf9e795fd700f3434elayn": "binary_sensor.garazh_moisture",          # Гараж
    "bf834d89471750b004ukco": "binary_sensor.kukhnia_moisture",         # Кухня
}
DP = "watersensor_state"

# FAIL-SAFE: alarm only on these explicit markers.
ALARM_MARKERS = {"1", "alarm", "true"}
NORMAL_MARKERS = {"2", "normal", "false"}

START = time.time()
_PRINTED = False   # guarantees exactly ONE stdout line, ever


def budget_left(need=0.0):
    return (time.time() - START) < (TOTAL_BUDGET - need)


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_json(path, data):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o644)
        except Exception:
            pass
    except Exception:
        pass


def creds():
    for path in SECRETS_FILES:
        data = load_json(path)
        if isinstance(data, dict) and data.get("TUYA_CLIENT_ID") and data.get("TUYA_CLIENT_SECRET"):
            return str(data["TUYA_CLIENT_ID"]), str(data["TUYA_CLIENT_SECRET"])
    cid = os.environ.get("TUYA_CLIENT_ID")
    csec = os.environ.get("TUYA_CLIENT_SECRET")
    if cid and csec:
        return cid, csec
    return None, None


CLIENT_ID, CLIENT_SECRET = creds()


def sign_headers(method, path, token=""):
    t = str(int(time.time() * 1000))
    string_to_sign = f"{method}\n{hashlib.sha256(b'').hexdigest()}\n\n{path}"
    message = f"{CLIENT_ID}{token}{t}{string_to_sign}"
    sig = hmac.new(CLIENT_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest().upper()
    headers = {"client_id": CLIENT_ID, "t": t, "sign": sig, "sign_method": "HMAC-SHA256"}
    if token:
        headers["access_token"] = token
    return headers


def api(path, token=""):
    """GET a signed Tuya path. Returns {} on any transport error."""
    try:
        req = urllib.request.Request(BASE + path, headers=sign_headers("GET", path, token))
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return {}


def get_token(force=False):
    if not force:
        cached = load_json(TOKEN_CACHE)
        if isinstance(cached, dict) and cached.get("exp", 0) > time.time() + 60:
            tok = cached.get("tok")
            if tok:
                return str(tok)
    res = api("/v1.0/token?grant_type=1")
    if not res.get("success"):
        return None
    result = res.get("result") or {}
    tok = result.get("access_token")
    try:
        expire = int(result.get("expire_time") or 0)
    except Exception:
        expire = 0
    if not tok or expire <= 0:
        return None
    save_json(TOKEN_CACHE, {"tok": tok, "exp": time.time() + expire - 120})
    return str(tok)


def norm(value):
    """Normalise a DP value to a lowercase comparison key."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip().lower()


def classify(raw_map):
    """Fail-safe classification. Returns (state, alarm_entities)."""
    alarm = []
    saw_normal = False
    for entity, value in raw_map.items():
        key = norm(value)
        if key in ALARM_MARKERS:
            alarm.append(entity)
        elif key in NORMAL_MARKERS:
            saw_normal = True
        # anything else contributes nothing -> cannot create an alarm
    if alarm:
        return "alarm", sorted(alarm)
    if saw_normal:
        return "normal", []
    return "unknown", []


def emit(payload, cache=False, serve_until=None):
    """Print the single JSON line FIRST, then optionally persist the cache."""
    global _PRINTED
    if _PRINTED:
        return
    _PRINTED = True
    try:
        line = json.dumps(payload, ensure_ascii=False)
    except Exception:
        line = '{"state": "unknown", "alarm_entities": [], "raw": {}, "online": {}, "ts": 0, "src": "error"}'
    print(line)
    sys.stdout.flush()
    if cache:
        entry = {"ts": payload.get("ts", int(time.time())), "data": payload}
        if serve_until:
            entry["serve_until"] = serve_until
        save_json(RESULT_CACHE, entry)


def cached(max_age):
    entry = load_json(RESULT_CACHE)
    if not isinstance(entry, dict):
        return None, 0
    data = entry.get("data")
    ts = entry.get("ts") or 0
    if not isinstance(data, dict):
        return None, 0
    try:
        ts = float(ts)
    except Exception:
        return None, 0
    if ts > time.time() - max_age:
        return data, entry.get("serve_until") or 0
    return None, entry.get("serve_until") or 0


def as_cache(data):
    out = dict(data)
    out["src"] = "cache"
    return out


def unknown_payload(src="error"):
    return {"state": "unknown", "alarm_entities": [], "raw": {}, "online": {},
            "ts": int(time.time()), "src": src}


def fallback():
    """Best available answer when the cloud path failed."""
    data, _ = cached(STALE_TTL)
    if data:
        emit(as_cache(data))
    else:
        emit(unknown_payload())


def parse_devices_payload(result):
    """/v1.0/devices?device_ids= -> (raw_map, online_map). Empty if unusable."""
    if isinstance(result, dict):
        result = result.get("devices") or result.get("list") or []
    if not isinstance(result, list):
        return {}, {}
    raw_map, online_map = {}, {}
    for dev in result:
        if not isinstance(dev, dict):
            continue
        entity = DEVICES.get(dev.get("id"))
        if not entity:
            continue
        online_map[entity] = bool(dev.get("online"))
        for st in dev.get("status") or []:
            if isinstance(st, dict) and st.get("code") == DP:
                raw_map[entity] = st.get("value")
    return raw_map, online_map


def parse_status_payload(result):
    """/v1.0/devices/status?device_ids= -> (raw_map, online_map). No online info."""
    raw_map, online_map = {}, {}
    items = []
    if isinstance(result, dict):
        # EU gateway returns {device_id: [ {code,value}, ... ]}
        for dev_id, dps in result.items():
            items.append((dev_id, dps))
    elif isinstance(result, list):
        for dev in result:
            if isinstance(dev, dict):
                items.append((dev.get("id"), dev.get("status")))
    for dev_id, dps in items:
        entity = DEVICES.get(dev_id)
        if not entity or not isinstance(dps, list):
            continue
        for st in dps:
            if isinstance(st, dict) and st.get("code") == DP:
                raw_map[entity] = st.get("value")
                online_map.setdefault(entity, None)
    return raw_map, online_map


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        data, _ = cached(STALE_TTL)
        emit(as_cache(data) if data else unknown_payload())
        return

    # Serve our own very recent answer (protects the Tuya API quota).
    data, serve_until = cached(FRESH_TTL)
    if data:
        emit(as_cache(data))
        return
    if serve_until and time.time() < serve_until:
        data, _ = cached(STALE_TTL)
        if data:
            emit(as_cache(data))
            return

    token = get_token()
    if not token or not budget_left(HTTP_TIMEOUT):
        fallback()
        return

    ids = ",".join(sorted(DEVICES))
    # ONE batch call: returns both `status` (watersensor_state) and real `online`.
    res = api(f"/v1.0/devices?device_ids={ids}", token)

    # Token might have been revoked -> refresh once if we still have budget.
    if not res.get("success") and str(res.get("code")) in ("1010", "1011", "1004", "1000") \
            and budget_left(2 * HTTP_TIMEOUT):
        token = get_token(force=True)
        if token:
            res = api(f"/v1.0/devices?device_ids={ids}", token)

    raw_map, online_map = ({}, {})
    if res.get("success"):
        raw_map, online_map = parse_devices_payload(res.get("result"))

    # Fallback to the leaner status endpoint if the rich one gave us nothing.
    if not raw_map and budget_left(HTTP_TIMEOUT):
        res2 = api(f"/v1.0/devices/status?device_ids={ids}", token)
        if res2.get("success"):
            raw_map, online_map = parse_status_payload(res2.get("result"))
        elif not res.get("success") and res2:
            # Keep a KNOWN error code (e.g. 28841004 "IoT Core trial quota is
            # exhausted") instead of overwriting it with an empty transport failure:
            # the code decides which backoff we take below, and a quota error must
            # get the long one. MEASURED 2026-08-19: the /devices call returned
            # 28841004 while the leaner /devices/status call timed out and returned
            # {}, so the quota backoff was silently downgraded to the generic one.
            res = res2

    if not raw_map:
        # Cloud unusable. BACK OFF on EVERY failure, not just on the quota code
        # (fix 2026-08-19): a failing run costs 1-3 cloud calls (token + /devices +
        # /devices/status), so an unthrottled failure storm was itself a quota
        # problem - exactly how we reached API_QPS_LIMIT_OR_DEGRADE. The backoff is
        # deliberately shorter than the 180 s poll interval, so it never throttles
        # the healthy steady state; it only caps the forced 30 s polling burst that
        # automation 1790400001001 drives while the moisture sensors are blind.
        # The cache keeps its ORIGINAL cloud `ts` (as_cache never re-stamps), so a
        # served-from-cache answer can never look fresher than it is.
        quota = str(res.get("code")) == "28841004"
        data, _ = cached(STALE_TTL)
        if data:
            emit(as_cache(data), cache=True,
                 serve_until=time.time() + (QUOTA_BACKOFF if quota else FAIL_BACKOFF))
        elif quota:
            # No cache at all: nothing to serve, so do NOT go quiet - keep the
            # honest "unknown" and let the next poll try again.
            emit(unknown_payload("cache"))
        else:
            fallback()
        return

    for entity in DEVICES.values():
        online_map.setdefault(entity, False)

    state, alarm_entities = classify(raw_map)
    payload = {
        "state": state,
        "alarm_entities": alarm_entities,
        "raw": {e: raw_map[e] for e in sorted(raw_map)},
        "online": {e: online_map.get(e) for e in sorted(online_map)},
        "ts": int(time.time()),
        "src": "cloud",
    }
    emit(payload, cache=True)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        # Absolutely never let HA see a traceback on stdout / an empty state.
        try:
            fallback()
        except BaseException:
            if not _PRINTED:
                print('{"state": "unknown", "alarm_entities": [], "raw": {}, "online": {}, "ts": 0, "src": "error"}')
