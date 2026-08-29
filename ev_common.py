#!/usr/bin/env python3
"""Shared EV charging-scheduler logic.

Imported by ev_best2h.py / ev_day2h.py / ev_night2h.py so they share one
implementation of price fetching, contiguous 2h-window selection and HA calls.
The three scripts stay runnable standalone (HA invokes them directly, e.g.
`python3 /config/ev_best2h.py`); this module carries no side effects on import.

Design notes:
  * A window is only valid if it is a GENUINE contiguous 2h block (8 × 15min
    slots, each ~900s apart). There is NO single-slot fallback — if no real
    window exists we return (None, None) and the caller emits a clear no-op.
  * Every HA POST is checked: ha_post returns (ok, status) and callers must
    never report success on a non-2xx response.
  * stderr logging goes through log()/log_err() which never emit secret values.
"""
from __future__ import annotations

import datetime
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request

try:
    import fcntl  # POSIX advisory locking (available on HA/Linux)
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None

SLOTS = 8            # 8 × 15min = 2 hours
SLOT_SECONDS = 900   # nominal spacing between 15-min slots
SLOT_TOLERANCE = 30  # allowed drift (seconds) around SLOT_SECONDS
CUTOFF_MINUTES = 10  # ignore slots starting within this many minutes of now

# Unified error/status vocabulary shared across scripts.
STATUS_OK = "ok"
STATUS_NO_WINDOW = "no_window"
STATUS_API_ERROR = "api_error"
STATUS_HA_ERROR = "ha_error"
STATUS_CONFIG_ERROR = "config_error"

# --- Elering-outage notification dedup/cooldown/recovery --------------------- #
# One Telegram message per Elering incident, a cooldown ceiling while it stays
# down, and exactly one recovery message when it returns. This changes ONLY the
# notification cadence — never the EV schedule (ev_charge_start is untouched
# here; callers preserve it exactly as before on failure).
ELERING_NOTIFY_COOLDOWN = 6 * 3600  # seconds — max one "недоступен" per 6h
ELERING_FAILURE_MSG = (
    "⚠️ EV планировщик: Elering API временно недоступен. Расписание не изменено."
)
ELERING_RECOVERY_MSG = (
    "✅ Elering снова доступен, расписание обновляется."
)

try:
    from zoneinfo import ZoneInfo
    RIGA = ZoneInfo("Europe/Riga")
except Exception:  # pragma: no cover - fallback for stripped runtimes
    RIGA = datetime.timezone(datetime.timedelta(hours=3))  # EEST fallback


# --------------------------------------------------------------------------- #
# Logging (safe — never print tokens/secrets)
# --------------------------------------------------------------------------- #
def log(msg: str) -> None:
    """Write an informational line to stderr."""
    print(msg, file=sys.stderr)


def log_err(msg: str) -> None:
    """Write an error line to stderr. Callers must pass non-secret text only."""
    print("ERROR: " + msg, file=sys.stderr)


# --------------------------------------------------------------------------- #
# Home Assistant HTTP helpers
# --------------------------------------------------------------------------- #
def make_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def ha_get(base: str, path: str, headers: dict, timeout: int = 10):
    req = urllib.request.Request(f"{base}{path}", headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def ha_post(base: str, path: str, data: dict, headers: dict, timeout: int = 10):
    """POST to HA. Returns (ok, status).

    ok is True only for a 2xx status. Network/HTTP errors yield (False, code)
    so callers can decide what to report — never assume success.
    """
    req = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(data, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status = getattr(r, "status", None) or r.getcode()
            return (200 <= status < 300, status)
    except urllib.error.HTTPError as e:
        return (False, e.code)
    except Exception as exc:  # URLError, timeout, etc.
        log_err(f"HA POST {path} failed: {type(exc).__name__}")
        return (False, None)


def notify(base: str, path_data, headers: dict) -> bool:
    """Convenience wrapper; returns whether the notify POST succeeded."""
    path, data = path_data
    ok, _status = ha_post(base, path, data, headers)
    return ok


# --------------------------------------------------------------------------- #
# Elering price fetching
# --------------------------------------------------------------------------- #
def build_elering_url(now_utc: datetime.datetime) -> str:
    start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + datetime.timedelta(days=2)
    return (
        "https://dashboard.elering.ee/api/nps/price"
        f"?start={start.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        f"&end={end.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    )


def parse_prices(raw: dict) -> list:
    """Parse Elering JSON into a sorted list of {dt, price} dicts.

    Skips malformed rows (missing timestamp/price) rather than crashing.
    Raises ValueError if no usable LV prices are present.
    """
    lv = (raw or {}).get("data", {}).get("lv", [])
    if not lv:
        raise ValueError("Elering returned empty LV price list")
    out = []
    for x in lv:
        try:
            ts = x["timestamp"]
            price = x["price"]
        except (KeyError, TypeError):
            continue
        try:
            dt = datetime.datetime.fromtimestamp(int(ts), tz=datetime.timezone.utc)
            out.append({"dt": dt, "price": float(price) / 1000.0})
        except (ValueError, TypeError, OverflowError, OSError):
            continue
    if not out:
        raise ValueError("Elering LV list had no usable rows")
    out.sort(key=lambda item: item["dt"])
    return out


def fetch_lv_prices(now_utc: datetime.datetime | None = None,
                    delays=(0, 3, 8, 15), timeout: int = 20,
                    sleep=time.sleep) -> list:
    """Fetch 15-min LV prices from Elering with retries (transient 5xx/timeouts).

    `sleep` is injectable so tests don't actually wait.
    """
    if now_utc is None:
        now_utc = datetime.datetime.now(datetime.timezone.utc)
    url = build_elering_url(now_utc)
    headers = {"Accept": "application/json",
               "User-Agent": "HomeAssistant-EV-Scheduler/2.2"}
    last_err = None
    for attempt, delay in enumerate(delays):
        if delay:
            sleep(delay)
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode())
            return parse_prices(data)
        except Exception as exc:
            last_err = exc
            log(f"Elering attempt {attempt + 1}/{len(delays)} failed: "
                f"{type(exc).__name__}")
    raise RuntimeError(
        f"Elering unavailable after {len(delays)} attempts: "
        f"{type(last_err).__name__ if last_err else 'unknown'}"
    )


# --------------------------------------------------------------------------- #
# Window selection — genuine contiguous 2h windows only
# --------------------------------------------------------------------------- #
def _is_contiguous(window: list) -> bool:
    """True only if the window has exactly SLOTS slots, each ~900s apart."""
    if len(window) != SLOTS:
        return False
    for j in range(SLOTS - 1):
        gap = (window[j + 1]["dt"] - window[j]["dt"]).total_seconds()
        if abs(gap - SLOT_SECONDS) >= SLOT_TOLERANCE:
            return False
    return True


def find_best_2h(slots: list, now_utc: datetime.datetime, hour_filter=None):
    """Return (best_start_utc, best_avg) for the cheapest genuine 2h window.

    A window must be a contiguous block of SLOTS 15-min slots. If hour_filter
    is given, every slot's local (Riga) hour must satisfy it. If no genuine
    window qualifies, returns (None, None) — never a fabricated single slot.
    """
    cutoff = now_utc + datetime.timedelta(minutes=CUTOFF_MINUTES)
    best_start = None
    best_avg = float("inf")
    for i in range(len(slots) - SLOTS + 1):
        window = slots[i: i + SLOTS]
        if window[0]["dt"] < cutoff:
            continue
        if not _is_contiguous(window):
            continue
        if hour_filter is not None and not all(
            hour_filter(s["dt"].astimezone(RIGA).hour) for s in window
        ):
            continue
        avg = sum(s["price"] for s in window) / SLOTS
        if avg < best_avg:
            best_avg = avg
            best_start = window[0]["dt"]
    if best_start is None:
        return None, None
    return best_start, best_avg


# --------------------------------------------------------------------------- #
# Persistent notification state (atomic write + advisory lock, ev_query style)
# --------------------------------------------------------------------------- #
def _cache_dir() -> str:
    """Same cache dir as ev_query.py: /config/.ev_cache on the box, else cwd."""
    return "/config/.ev_cache" if os.path.isdir("/config") \
        else os.path.join(os.getcwd(), ".ev_cache")


def elering_state_path() -> str:
    """Path of the shared Elering-notify state file."""
    return os.path.join(_cache_dir(), "elering_notify_state.json")


# last_notify_ts is None until a failure notice has actually been SENT for the
# current incident; a float once one has. This lets a failed send retry on the
# next run (None) while a successful send starts the cooldown clock (float).
_DEFAULT_NOTIFY_STATE = {"failing": False, "fail_since": None, "last_notify_ts": None}


def _load_notify_state(path: str) -> dict:
    """Read the notify-state JSON (shared lock); return defaults if absent/bad."""
    try:
        with open(path, encoding="utf-8") as f:
            if fcntl is not None:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                except OSError:
                    pass
            data = json.load(f)
    except Exception:
        data = None
    if not isinstance(data, dict):
        return dict(_DEFAULT_NOTIFY_STATE)
    raw = data.get("last_notify_ts", None)
    try:
        last = None if raw is None else float(raw)
    except (TypeError, ValueError):
        last = None
    return {
        "failing": bool(data.get("failing", False)),
        "fail_since": data.get("fail_since"),
        "last_notify_ts": last,
    }


def _save_notify_state(path: str, data: dict) -> None:
    """Atomically write JSON under an exclusive advisory lock (0600).

    Never raises — a notify-state write failure must not break scheduling.
    """
    lock_fh = None
    try:
        cache_dir = os.path.dirname(path) or "."
        os.makedirs(cache_dir, exist_ok=True)
        try:
            os.chmod(cache_dir, 0o700)
        except OSError:
            pass
        if fcntl is not None:
            try:
                lock_path = os.path.join(cache_dir, ".lock")
                lock_fh = open(lock_path, "w")
                os.chmod(lock_path, 0o600)
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
            except OSError:
                lock_fh = None
        fd, tmp = tempfile.mkstemp(dir=cache_dir, prefix=".tmp-", suffix=".json")
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


def notify_elering_failure(send_fn, message: str = ELERING_FAILURE_MSG,
                           state_path: str | None = None,
                           now: float | None = None,
                           cooldown: float = ELERING_NOTIFY_COOLDOWN) -> bool:
    """Send at most one Elering-failure notice per incident / cooldown.

    Sends via `send_fn(message)` (which returns truthy on success) only when we
    are NOT already in a failing state, OR when `cooldown` seconds have elapsed
    since the last notice. Always records state=failing (with `fail_since` set on
    the first failure of an incident). Returns True iff a message was sent.

    Does NOT touch the EV schedule — the caller preserves ev_charge_start.
    """
    if now is None:
        now = time.time()
    path = state_path or elering_state_path()
    st = _load_notify_state(path)

    should_send = (
        not st["failing"]                         # new incident
        or st["last_notify_ts"] is None           # failing but never sent yet
        or (now - st["last_notify_ts"] >= cooldown)  # cooldown elapsed
    )
    sent = bool(send_fn(message)) if should_send else False

    fail_since = st["fail_since"] if st["failing"] else now
    if fail_since is None:
        fail_since = now
    # Only advance the cooldown clock when a message actually went out, so a
    # failed send is retried on the next run rather than being silenced.
    last_notify_ts = now if sent else st["last_notify_ts"]
    _save_notify_state(path, {
        "failing": True,
        "fail_since": fail_since,
        "last_notify_ts": last_notify_ts,
    })
    return sent


def notify_elering_recovery(send_fn, message: str = ELERING_RECOVERY_MSG,
                            state_path: str | None = None) -> bool:
    """Send exactly one recovery notice on the first success after a failure.

    If we were not in a failing state, sends nothing (returns False). On a
    successful `send_fn(message)` the failing flag is cleared. If the send
    fails, the failing state is kept so the next success retries the recovery.
    """
    path = state_path or elering_state_path()
    st = _load_notify_state(path)
    if not st["failing"]:
        return False
    sent = bool(send_fn(message))
    if sent:
        _save_notify_state(path, dict(_DEFAULT_NOTIFY_STATE))
    return sent
