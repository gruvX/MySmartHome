#!/usr/bin/env python3
"""Read /config/www/today_prices.json and answer "how long will this hold?".

Deployed to the HA box as ``/config/price_forecast.py`` and invoked by
``shell_command.price_forecast`` with ``response_variable``.  Read-only: it
opens one JSON file and prints flat text on stdout.  It commands nothing,
writes nothing, and never exits non-zero — every failure path still prints
``ok=0`` plus a machine-readable ``error`` so the calling template can say
«нет данных» instead of inventing a number.

Input shape (written by update_today_prices.py, Europe/Riga LOCAL labels)::

    {"updated": "...Z", "step_minutes": 15,
     "prices":   {"YYYY-MM-DD": {"0": 0.0077, ..., "23": 0.0584}},
     "prices15": {"YYYY-MM-DD": {"00:00": 0.00999, ..., "23:45": 0.0601}}}

Output shape — deliberately NOT JSON but flat ``key=value`` lines, one per
line, no ``=`` in any key, no newline inside any value::

    ok=1
    updated=2026-08-16T06:43:46Z
    now=11:20
    slot_price=0.00638
    slot_at=11:15
    has_tomorrow=0
    horizon_end=16.08 23:45
    rest_min=0.00597
    rest_min_at=12:00
    rest_max=0.08357
    rest_max_at=21:00
    boiler_cheap=1
    boiler_cross_at=20:45
    boiler_txt=дёшево примерно до 20:45
    towel_cheap=1
    towel_cross_at=19:45
    towel_txt=дёшево примерно до 19:45

Why not JSON: the consumer is a Home Assistant Jinja template, which has no
``try``.  ``| from_json`` on an unexpected byte RAISES and aborts the calling
automation — one bad price file would silently swallow the whole notification.
``| regex_findall('^key=(.*)$')`` cannot raise, so every field degrades to
«нет данных» on its own without taking the message down with it.  A key whose
value is unknown is simply not printed.

``*_cheap`` is ``price <= threshold`` for the slot that contains *now*, i.e.
the same comparison the Nord Pool automations make.  ``*_cross_at`` is the
first future slot whose side differs.  When no crossing exists inside the data
we have, ``*_cross_at`` is absent and ``*_txt`` says so honestly rather than
implying the price holds forever.

Never fabricates: a missing slot is absent, not zero.  A negative price is
legitimate on the day-ahead market and is kept verbatim.
"""
from __future__ import annotations

import datetime
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

try:
    from zoneinfo import ZoneInfo

    RIGA = ZoneInfo("Europe/Riga")
except Exception:  # pragma: no cover - zoneinfo is present on HA OS
    RIGA = datetime.timezone(datetime.timedelta(hours=3))

PATH = "/config/www/today_prices.json"
BOILER_THRESHOLD = 0.10
TOWEL_THRESHOLD = 0.04


def emit(fields: dict) -> None:
    """Print flat key=value lines, skipping anything we do not actually know."""
    out = []
    for key, value in fields.items():
        if value is None or value == "":
            continue          # a slot we do not have is absent, never zero
        if isinstance(value, bool):
            value = 1 if value else 0
        out.append(f"{key}={value}".replace("\n", " ").replace("\r", " "))
    print("\n".join(out))


def fail(error: str) -> None:
    """Print a well-formed 'no data' answer and exit 0.

    Exit 0 on purpose: a non-zero exit makes HA log a shell_command error and
    (without continue_on_error) abort the caller.  The caller must instead read
    ok=false and print «нет данных».
    """
    emit({"ok": 0, "error": error})
    sys.exit(0)


def slots_for_day(payload: dict, day: str) -> list[tuple[str, float]]:
    """-> sorted [("HH:MM", price)] for one local day, 15-min if we have it."""
    step = (payload.get("prices15") or {}).get(day)
    if isinstance(step, dict) and step:
        out = []
        for label, price in step.items():
            try:
                hh, mm = label.split(":")
                out.append((f"{int(hh):02d}:{int(mm):02d}", float(price)))
            except (ValueError, TypeError, AttributeError):
                continue
        if out:
            return sorted(out)
    hourly = (payload.get("prices") or {}).get(day)
    if isinstance(hourly, dict) and hourly:
        out = []
        for label, price in hourly.items():
            try:
                out.append((f"{int(label):02d}:00", float(price)))
            except (ValueError, TypeError):
                continue
        if out:
            return sorted(out)
    return []


def to_dt(day: str, label: str) -> datetime.datetime:
    y, m, d = (int(x) for x in day.split("-"))
    hh, mm = (int(x) for x in label.split(":"))
    return datetime.datetime(y, m, d, hh, mm, tzinfo=RIGA)


def extreme(slots: list[tuple[str, float]], pick):
    if not slots:
        return None, None
    label, price = pick(slots, key=lambda sp: sp[1])
    return price, label


def analyse(series: list[tuple[datetime.datetime, float]],
            now: datetime.datetime, threshold: float) -> dict:
    """Side of `threshold` we are on now + first future slot on the other side."""
    current = None
    for when, price in series:
        if when <= now:
            current = (when, price)
        else:
            break
    if current is None:
        return {"threshold": threshold, "cheap": None, "cross_at": None,
                "cross_day": None, "txt": "нет данных о цене на сейчас"}

    cheap = current[1] <= threshold
    for when, price in series:
        if when <= current[0]:
            continue
        if (price <= threshold) != cheap:
            same_day = when.date() == now.date()
            at = when.strftime("%H:%M")
            when_txt = at if same_day else f"завтра {at}"
            txt = ("дёшево примерно до " if cheap else "дорого примерно до ") + when_txt
            return {"threshold": threshold, "cheap": cheap, "cross_at": at,
                    "cross_day": "today" if same_day else "tomorrow", "txt": txt}

    end = series[-1][0] if series else None
    horizon = end.strftime("%H:%M") if end else "?"
    same_day = bool(end) and end.date() == now.date()
    tail = horizon if same_day else f"завтра {horizon}"
    state = "дёшево" if cheap else "дорого"
    return {"threshold": threshold, "cheap": cheap, "cross_at": None,
            "cross_day": None,
            "txt": f"{state} до конца известных цен ({tail}), перелома в данных нет"}


def main() -> None:
    try:
        with open(PATH, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except FileNotFoundError:
        fail("file_missing")
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        fail(f"file_unreadable:{type(exc).__name__}")
    if not isinstance(payload, dict):
        fail("file_not_object")

    now = datetime.datetime.now(RIGA)
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    today_slots = slots_for_day(payload, today)
    tomorrow_slots = slots_for_day(payload, tomorrow)
    if not today_slots:
        fail("no_today")

    series = [(to_dt(today, lb), p) for lb, p in today_slots]
    series += [(to_dt(tomorrow, lb), p) for lb, p in tomorrow_slots]
    series.sort()

    current = None
    for when, price in series:
        if when <= now:
            current = (when, price)
        else:
            break

    rest = [(lb, p) for lb, p in today_slots if to_dt(today, lb) >= now]
    rest_min, rest_min_at = extreme(rest, min)
    rest_max, rest_max_at = extreme(rest, max)
    tmr_min, tmr_min_at = extreme(tomorrow_slots, min)
    tmr_max, tmr_max_at = extreme(tomorrow_slots, max)

    boiler = analyse(series, now, BOILER_THRESHOLD)
    towel = analyse(series, now, TOWEL_THRESHOLD)
    emit({
        "ok": 1,
        "updated": payload.get("updated"),
        "now": now.strftime("%H:%M"),
        "today": today,
        "step_minutes": payload.get("step_minutes"),
        "slot_price": current[1] if current else None,
        "slot_at": current[0].strftime("%H:%M") if current else None,
        "has_tomorrow": 1 if tomorrow_slots else 0,
        "horizon_end": series[-1][0].strftime("%d.%m %H:%M") if series else None,
        "rest_min": rest_min, "rest_min_at": rest_min_at,
        "rest_max": rest_max, "rest_max_at": rest_max_at,
        "tomorrow_min": tmr_min, "tomorrow_min_at": tmr_min_at,
        "tomorrow_max": tmr_max, "tomorrow_max_at": tmr_max_at,
        "boiler_cheap": boiler["cheap"],
        "boiler_cross_at": boiler["cross_at"],
        "boiler_txt": boiler["txt"],
        "towel_cheap": towel["cheap"],
        "towel_cross_at": towel["cross_at"],
        "towel_txt": towel["txt"],
    })


if __name__ == "__main__":
    main()
