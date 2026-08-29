#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EV re-plan — the car was not plugged in, move the charge to the next window.

WHY (2026-08-19)
----------------
Owner request: charging must happen by itself, and "car not plugged in" must
never be silent. Before this, a planned window that arrived with the car
unplugged produced one warning and then nothing at all: the plan stayed on a
window that had already passed until the next Nord Pool price update happened
to re-run the planner. Effectively a skipped day.

This script is invoked by automation 1791000001001 ONLY when
sensor.ev_charger_status is FRESH (src in LIVE_SRC, stale_age < 900) and equal to
charger_free. A cached/stale status must never be used to assert "the car is not
connected" — that check lives in the automation's conditions, and this script
re-checks it so it cannot be run into a wrong claim by hand.

2026-08-19: ev_query.py stopped reading the quota-dead Tuya IoT Core project and now
reads the same DPs out of HA's own live `tuya` integration, so a live read is labelled
src="local". "cloud" stays in LIVE_SRC only so an attribute value written by the
previous build is not misread as stale during the switchover; ev_query.py can no
longer emit it.

BOUNDED: at most REPLAN_CAP re-plans per local calendar day
(input_number.ev_replan_count, reset when input_datetime.ev_replan_day is not
today). Once the cap is reached the owner is told once and the ordinary planner
takes over again at its next run — no loop, no retry storm.

NEVER commands a device. Only input_number / input_datetime writes + notify.
"""
from __future__ import annotations

import datetime
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import ev_auto2h as auto

REPLAN_CAP = 2                 # re-plans per local calendar day
FRESH_MAX_AGE = 900            # seconds; matches the watchdog's freshness rule
# Sources that mean "read live, right now". Must stay in sync with the same list in
# automations.yaml (1790100001001 / 1790500001001 / 1791000001001).
LIVE_SRC = ("local", "cloud")

SCHED = "input_datetime.ev_charge_start"
STATUS = "sensor.ev_charger_status"
COUNT = "input_number.ev_replan_count"
DAY = "input_datetime.ev_replan_day"
WINDOW_HOURS = 2

UTC = datetime.timezone.utc


def status_is_fresh_free(state):
    """True only for a FRESH charger_free. A cached/stale status returns False —
    "the car is not connected" may not be asserted from stale data."""
    if not state:
        return False
    attrs = state.get("attributes") or {}
    if state.get("state") != "charger_free":
        return False
    if attrs.get("src") not in LIVE_SRC:
        return False
    try:
        age = float(attrs.get("stale_age"))
    except (TypeError, ValueError):
        return False
    return 0 <= age < FRESH_MAX_AGE


def attempts_today(count_state, day_state, today):
    """Current re-plan count for `today`, or 0 when the stored day is not today.

    Pure — this is the cap logic and it is unit-tested directly.
    """
    stored = (day_state or {}).get("state") or ""
    if str(stored)[:10] != today.isoformat():
        return 0
    try:
        return int(float((count_state or {}).get("state") or 0))
    except (TypeError, ValueError):
        return 0


def main(argv=None):
    now_utc = datetime.datetime.now(UTC)
    now_local = now_utc.astimezone(auto.RIGA)
    today = now_local.date()

    status = auto.state_of(STATUS)
    if not status_is_fresh_free(status):
        print("SKIP: status is not a fresh charger_free "
              "(state=%s src=%s)" % ((status or {}).get("state"),
                                     ((status or {}).get("attributes") or {})
                                     .get("src")), file=sys.stderr)
        return 0

    used = attempts_today(auto.state_of(COUNT), auto.state_of(DAY), today)
    if used >= REPLAN_CAP:
        auto.notify(
            "🚗 EV: машина по-прежнему не подключена.\n"
            "  Перенос зарядки на сегодня больше не делаю — "
            "лимит %d переноса(ов) в сутки исчерпан.\n"
            "  Подключи машину; обычное расписание вернётся само." % REPLAN_CAP)
        print("SKIP: daily re-plan cap %d reached" % REPLAN_CAP)
        return 0

    sched = auto.state_of(SCHED)
    try:
        failed_ts = float(((sched or {}).get("attributes") or {})
                          .get("timestamp") or 0)
    except (TypeError, ValueError):
        failed_ts = 0.0
    if failed_ts > 0:
        earliest = (datetime.datetime.fromtimestamp(failed_ts, tz=UTC)
                    + datetime.timedelta(hours=WINDOW_HOURS))
    else:
        earliest = now_utc

    try:
        prices = auto.fetch_elering(now_utc)
        source = "elering"
    except Exception as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        prices = auto.read_local_prices(now_utc=now_utc)
        source = "local"

    best_utc, avg = (None, None)
    if prices:
        best_utc, avg = auto.find_best_window(
            prices, now_utc,
            latest_start=auto.horizon_bound(now_utc),
            earliest_start=earliest,
        )

    if best_utc is None:
        auto.notify(
            "🚗 EV: машина не подключена, а другого окна на ближайшие %d ч нет "
            "(цены на завтра ещё не опубликованы или данные недоступны).\n"
            "  Перенос не сделан, обычное расписание вернётся само."
            % auto.HORIZON_HOURS)
        print("SKIP: no alternative window (source=%s)" % source)
        return 0

    start_local = best_utc.astimezone(auto.RIGA)
    end_local = start_local + datetime.timedelta(hours=WINDOW_HOURS)
    local_str = start_local.strftime("%Y-%m-%d %H:%M:%S")

    written = auto.ha_post("/api/services/input_datetime/set_datetime",
                           {"entity_id": SCHED, "datetime": local_str})
    if not (isinstance(written, int) and 200 <= written < 300):
        auto.notify("⚠️ EV: машина не подключена, но перенести зарядку не "
                    "удалось (HTTP %s). Расписание не изменено." % written)
        print("ERROR: set_datetime -> %s" % written, file=sys.stderr)
        return 1

    # Count the attempt only after the plan really moved.
    auto.ha_post("/api/services/input_datetime/set_datetime",
                 {"entity_id": DAY, "datetime": today.isoformat() + " 00:00:00"})
    auto.ha_post("/api/services/input_number/set_value",
                 {"entity_id": COUNT, "value": used + 1})

    auto.notify("\n".join([
        "🚗 EV: машина не подключена — зарядка перенесена",
        "  Новое окно: " + start_local.strftime("%d.%m %H:%M") + " → "
        + end_local.strftime("%H:%M") + " (2 ч)",
        "  Средн. цена: %.4f EUR/кВт·ч" % avg,
        "  Перенос %d из %d за сутки." % (used + 1, REPLAN_CAP),
    ]))
    print("OK: %s, avg=%.4f, attempt=%d/%d, source=%s"
          % (local_str, avg, used + 1, REPLAN_CAP, source))
    return 0


if __name__ == "__main__":
    sys.exit(main())
