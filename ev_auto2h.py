#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EV automatic planner — cheapest genuine 2 h window in the NEXT 24 HOURS.

WHY THIS FILE EXISTS (2026-08-19)
---------------------------------
The owner asked for charging that "just happens" every day at the cheapest
hours, night or day, without planning anything by hand.

/config/ev_best2h.py already picks the cheapest contiguous 2 h block, but it
searches the WHOLE fetched horizon: Elering is queried from UTC midnight of the
current day to +2 days, so at 14:05 the search can reach ~34 h ahead. Two
consequences the owner felt:

  * the plan can be parked on the far side of tomorrow, leaving a gap of up to
    ~37 h between two consecutive charges — i.e. a day with no charge at all;
  * nothing re-plans when the plan silently rots (HA down over the planned
    time, a window that has already passed): the planner only runs on
    sensor.nord_pool_lv_lowest_price changes (gated 08-22), on HA start and at
    14:05.

ev_best2h.py is PINNED by tests/test_ev_notify_surgical.py to
notification-only changes against a byte-exact baseline — an owner-mandated
contract. So the 24 h bound lives HERE, outside that file, and this script is
what automation 1778800001001 ("EV зарядка — планировщик") now runs. The pinned
file is unchanged and still reachable manually via shell_command.ev_find_best2h.

WHAT IT DOES
------------
  1. Refuses to touch the plan while an explicit one-shot request is pending
     (input_boolean.ev_night_requested + input_datetime.ev_night_window_start).
     Defence in depth: the same guard is condition #1 of automation
     1778800001001. Degrades OPEN — a missing helper must never stop planning.
  2. Prices: Elering 15-min LV (retries), falling back to the locally produced
     snapshot /config/www/today_prices.json when Elering is down, so an Elering
     outage no longer means "no charge today".
  3. Picks the cheapest genuine contiguous 2 h window whose START lies in
     now+10min .. now+24h. The +10 min cutoff and the contiguity rule are the
     same as the pinned planner; the single-slot fallback the owner insisted on
     keeping is preserved too (see find_best_window).
  4. Writes input_datetime.ev_charge_start, CHECKING the HTTP status, and tells
     the owner about the new window — at most one "plan changed" message per
     NOTIFY_MIN_INTERVAL, because the planner runs on every Nord Pool price
     update.

NEVER commands a device. Only input_datetime writes + notify.
"""
from __future__ import annotations

import datetime
import json
import os
import tempfile
import time
import urllib.error
import urllib.request

import sys

if hasattr(sys.stdout, "reconfigure"):  # pytest's captured stdout may not have it
    sys.stdout.reconfigure(encoding="utf-8")

SLOTS = 8                        # 8 × 15 min = 2 h
CUTOFF_MINUTES = 10              # a window may not start sooner than this
HORIZON_HOURS = 24               # window START must fall inside now .. now+24h
STICKY_EXPIRY = 10800            # request window start + 3 h — mirrors 1790500001001
NOTIFY_MIN_INTERVAL = 3 * 3600   # at most one "plan changed" notice per 3 h
SLOT_SECONDS = 900

SCHED = "input_datetime.ev_charge_start"
REQ_FLAG = "input_boolean.ev_night_requested"
REQ_WINDOW = "input_datetime.ev_night_window_start"

LOCAL_PRICES = "/config/www/today_prices.json"
LOCAL_PRICES_MAX_AGE = 36 * 3600  # snapshot older than this is not trusted

_CACHE_DIR = "/config/.ev_cache" if os.path.isdir("/config") \
    else os.path.join(os.getcwd(), ".ev_cache")
NOTIFY_STATE = os.path.join(_CACHE_DIR, "auto_plan_notify.json")

try:
    from zoneinfo import ZoneInfo
    RIGA = ZoneInfo("Europe/Riga")
except Exception:  # pragma: no cover - zoneinfo is present on HA
    RIGA = datetime.timezone(datetime.timedelta(hours=3))

UTC = datetime.timezone.utc


# --------------------------------------------------------------------------- #
# Home Assistant access. Lazy on purpose: importing this module must have no
# side effects, so the unit tests can import it without any secrets present.
# --------------------------------------------------------------------------- #
_CFG: dict = {}


def _cfg() -> dict:
    if not _CFG:
        from project_secrets import secret
        _CFG["token"] = secret("HA_TOKEN", required=True)
        _CFG["base"] = secret("HA_BASE_URL", "http://127.0.0.1:8123")
        _CFG["tg"] = secret("HA_NOTIFY_ENTITY",
                            "notify.telegram_owner")
    return _CFG


def _hdr() -> dict:
    return {"Authorization": "Bearer " + _cfg()["token"],
            "Content-Type": "application/json"}


def ha_get(path: str):
    req = urllib.request.Request(_cfg()["base"] + path, headers=_hdr())
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def ha_post(path: str, data: dict) -> int:
    req = urllib.request.Request(
        _cfg()["base"] + path,
        data=json.dumps(data, ensure_ascii=False).encode("utf-8"),
        method="POST", headers=_hdr(),
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception:
        return 0


def notify(message: str) -> bool:
    """Telegram via the notify entity. The bot entry defaults to markdown, so
    these messages must stay free of entity_ids and markdown metacharacters."""
    status = ha_post("/api/services/notify/send_message",
                     {"entity_id": _cfg()["tg"], "message": message})
    return isinstance(status, int) and 200 <= status < 300


def state_of(entity_id: str):
    try:
        return ha_get("/api/states/" + entity_id)
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Window selection — the pinned planner's rule plus a hard horizon bound.
# --------------------------------------------------------------------------- #
def find_best_window(slots, now_utc, latest_start=None, earliest_start=None,
                     cutoff_minutes=CUTOFF_MINUTES):
    """Cheapest genuine contiguous 2 h window, bounded on both sides.

    Identical to /config/ev_best2h.py:find_best_2h — 8 slots, gaps within 30 s
    of 900 s, cheapest mean, and the single-slot fallback the owner explicitly
    refused to give up — except that a candidate's START must also satisfy
    ``earliest_start <= start <= latest_start`` when those are given.
    """
    cutoff = now_utc + datetime.timedelta(minutes=cutoff_minutes)
    if earliest_start is not None and earliest_start > cutoff:
        cutoff = earliest_start

    def startable(dt):
        if dt < cutoff:
            return False
        if latest_start is not None and dt > latest_start:
            return False
        return True

    future = [s for s in slots if s["dt"] >= cutoff]
    best_start, best_avg = None, float("inf")
    for i in range(len(future) - SLOTS + 1):
        window = future[i:i + SLOTS]
        if not startable(window[0]["dt"]):
            continue
        gaps = [(window[j + 1]["dt"] - window[j]["dt"]).total_seconds()
                for j in range(SLOTS - 1)]
        if not all(abs(g - SLOT_SECONDS) < 30 for g in gaps):
            continue
        avg = sum(s["price"] for s in window) / SLOTS
        if avg < best_avg:
            best_avg, best_start = avg, window[0]["dt"]

    # Fallback: cheapest single slot inside the same bounds. Kept deliberately —
    # removing it once cost the owner a night of charging.
    if best_start is None:
        candidates = [s for s in future if startable(s["dt"])]
        if candidates:
            cheapest = min(candidates, key=lambda x: x["price"])
            best_start, best_avg = cheapest["dt"], cheapest["price"]

    if best_start is None:
        return None, None
    return best_start, best_avg


def horizon_bound(now_utc, hours=HORIZON_HOURS):
    """Latest permitted window START. This IS the 24 h horizon."""
    return now_utc + datetime.timedelta(hours=hours)


# --------------------------------------------------------------------------- #
# Prices
# --------------------------------------------------------------------------- #
def fetch_elering(now_utc=None, delays=(0, 3, 8, 15)):
    """15-min LV prices, today 00:00 UTC .. +2 days. Same call as the pinned
    planner (same retry ladder), duplicated rather than imported so this script
    never depends on the pinned file's internals."""
    now_utc = now_utc or datetime.datetime.now(UTC)
    start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + datetime.timedelta(days=2)
    url = ("https://dashboard.elering.ee/api/nps/price"
           "?start=" + start.strftime("%Y-%m-%dT%H:%M:%SZ") +
           "&end=" + end.strftime("%Y-%m-%dT%H:%M:%SZ"))
    headers = {"Accept": "application/json",
               "User-Agent": "HomeAssistant-EV-AutoPlanner/1.0"}
    last = None
    for attempt, delay in enumerate(delays):
        if delay:
            time.sleep(delay)
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode())
            lv = data.get("data", {}).get("lv", [])
            if not lv:
                raise ValueError("Elering returned empty LV price list")
            return [
                {"dt": datetime.datetime.fromtimestamp(x["timestamp"], tz=UTC),
                 "price": x["price"] / 1000.0}
                for x in sorted(lv, key=lambda i: i["timestamp"])
            ]
        except Exception as exc:  # noqa: BLE001 - retried, then reported
            last = exc
            print("Elering attempt %d/%d failed: %s"
                  % (attempt + 1, len(delays), exc), file=sys.stderr)
    raise RuntimeError("Elering unavailable after %d attempts: %s"
                       % (len(delays), last))


def parse_local_prices(payload, now_utc=None, max_age=LOCAL_PRICES_MAX_AGE):
    """Slots from the locally produced /local/today_prices.json snapshot.

    Shape (written by update_today_prices.py):
        {"updated": "...Z", "step_minutes": 15,
         "prices":   {"YYYY-MM-DD": [24 hourly floats]},
         "prices15": {"YYYY-MM-DD": {"HH:MM": float}}}
    Dates and times are LOCAL (Europe/Riga). prices15 wins; the hourly table is
    expanded to four identical 15-min slots when prices15 is absent for a day.
    Returns [] when the snapshot is missing, unparseable or too old to trust.
    """
    if isinstance(payload, (str, bytes)):
        try:
            payload = json.loads(payload)
        except Exception:
            return []
    if not isinstance(payload, dict):
        return []
    now_utc = now_utc or datetime.datetime.now(UTC)
    updated = payload.get("updated")
    if isinstance(updated, str) and updated:
        try:
            stamp = datetime.datetime.strptime(updated, "%Y-%m-%dT%H:%M:%SZ") \
                .replace(tzinfo=UTC)
            if (now_utc - stamp).total_seconds() > max_age:
                return []
        except Exception:
            return []
    slots = {}
    hourly = payload.get("prices") or {}
    if isinstance(hourly, dict):
        for day, values in hourly.items():
            if not isinstance(values, list):
                continue
            for hour, price in enumerate(values):
                for quarter in range(4):
                    dt = _local_dt(day, hour, quarter * 15)
                    if dt is not None and isinstance(price, (int, float)):
                        slots[dt] = float(price)
    quarters = payload.get("prices15") or {}
    if isinstance(quarters, dict):
        for day, table in quarters.items():
            if not isinstance(table, dict):
                continue
            for hhmm, price in table.items():
                try:
                    hour, minute = (int(p) for p in str(hhmm).split(":")[:2])
                except Exception:
                    continue
                dt = _local_dt(day, hour, minute)
                if dt is not None and isinstance(price, (int, float)):
                    slots[dt] = float(price)
    return [{"dt": dt, "price": slots[dt]} for dt in sorted(slots)]


def _local_dt(day, hour, minute):
    try:
        date = datetime.datetime.strptime(str(day), "%Y-%m-%d").date()
    except Exception:
        return None
    try:
        naive = datetime.datetime(date.year, date.month, date.day, hour, minute)
        return naive.replace(tzinfo=RIGA).astimezone(UTC)
    except Exception:
        return None


def read_local_prices(path=LOCAL_PRICES, now_utc=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return parse_local_prices(fh.read(), now_utc)
    except Exception:
        return []


# --------------------------------------------------------------------------- #
# "plan changed" notification cooldown (the planner runs on every price update)
# --------------------------------------------------------------------------- #
def _load_state(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_state(path, data):
    try:
        directory = os.path.dirname(path) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".json")
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    except Exception:
        pass


def should_notify(state, plan, now_ts, min_interval=NOTIFY_MIN_INTERVAL):
    """True when this plan deserves a message. Pure, so it is unit-tested.

    Rules: a plan the owner has already been told about is never repeated; a
    different plan is announced at most once per ``min_interval``.
    """
    if state.get("plan") == plan:
        return False
    raw = state.get("last_ts")
    if raw is None:
        return True          # nothing was ever announced -> announce
    try:
        last = float(raw)
    except (TypeError, ValueError):
        return True          # unreadable state must not silence the owner
    return (now_ts - last) >= min_interval


# --------------------------------------------------------------------------- #
# Sticky one-shot request guard
# --------------------------------------------------------------------------- #
def request_pending(flag_state, window_state, now_ts, expiry=STICKY_EXPIRY):
    """Mirror of condition #1 of automation 1778800001001. Degrades OPEN."""
    flag = (flag_state or {}).get("state")
    try:
        ws = float(((window_state or {}).get("attributes") or {})
                   .get("timestamp") or 0)
    except (TypeError, ValueError):
        ws = 0.0
    return flag == "on" and ws > 0 and now_ts < (ws + expiry)


# --------------------------------------------------------------------------- #
def main(argv=None):
    now_utc = datetime.datetime.now(UTC)
    now_ts = now_utc.timestamp()

    if request_pending(state_of(REQ_FLAG), state_of(REQ_WINDOW), now_ts):
        print("SKIP: explicit one-shot request pending")
        return 0

    source = "elering"
    try:
        prices = fetch_elering(now_utc)
    except Exception as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        prices = read_local_prices(now_utc=now_utc)
        source = "local"
        if not prices:
            st = _load_state(NOTIFY_STATE)
            if (now_ts - float(st.get("outage_ts", 0) or 0)) >= 6 * 3600:
                notify("⚠️ EV: цены недоступны (Elering не отвечает и локальный "
                       "снимок цен устарел). Расписание не изменено.")
                st["outage_ts"] = now_ts
                _save_state(NOTIFY_STATE, st)
            return 1

    best_utc, avg = find_best_window(prices, now_utc,
                                     latest_start=horizon_bound(now_utc))
    if best_utc is None:
        print("No window in the next %dh (source=%s)" % (HORIZON_HOURS, source),
              file=sys.stderr)
        return 0

    start_local = best_utc.astimezone(RIGA)
    end_local = start_local + datetime.timedelta(hours=2)
    local_str = start_local.strftime("%Y-%m-%d %H:%M:%S")

    old = state_of(SCHED)
    old_val = (old or {}).get("state") or ""

    status = ha_post("/api/services/input_datetime/set_datetime",
                     {"entity_id": SCHED, "datetime": local_str})
    if not (isinstance(status, int) and 200 <= status < 300):
        print("ERROR: set_datetime %s -> %s" % (SCHED, status), file=sys.stderr)
        notify("⚠️ EV: не удалось записать плановое время зарядки (HTTP %s). "
               "Автоматическое расписание не обновлено." % status)
        return 1

    st = _load_state(NOTIFY_STATE)
    if local_str != old_val and should_notify(st, local_str, now_ts):
        notify("\n".join([
            "🚗 EV: автоматическая зарядка запланирована",
            "  " + start_local.strftime("%d.%m %H:%M") + " → "
            + end_local.strftime("%H:%M") + " (2 ч)",
            "  Средн. цена: %.4f EUR/кВт·ч" % avg,
            "  Выбрано как самое дешёвое окно на ближайшие %d ч." % HORIZON_HOURS,
            "  Отменить один раз: кнопка «Отменить зарядку».",
        ]))
        st["plan"] = local_str
        st["last_ts"] = now_ts
        _save_state(NOTIFY_STATE, st)

    print("OK: %s, avg=%.4f EUR/kWh, source=%s, horizon=%dh"
          % (local_str, avg, source, HORIZON_HOURS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
