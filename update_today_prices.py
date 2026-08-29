#!/usr/bin/env python3
"""Write Elering/Nord Pool LV prices grouped by Europe/Riga LOCAL time.

Deployed to the HA box as ``/config/update_today_prices.py`` and invoked by
``shell_command.update_today_prices`` from automation ``1748100001001``
(«⚡ Цены дня — Elering»). Data-only job: it fetches, it writes one JSON file,
it switches nothing.

Output shape — ``prices`` is unchanged from the 2026-05 version, so every
already-deployed UI build keeps working byte-for-byte::

    {
      "updated": "2026-08-16T11:15:00Z",
      "step_minutes": 15,
      "prices":   {"YYYY-MM-DD": {"0": 0.0077, ..., "23": 0.0584}},
      "prices15": {"YYYY-MM-DD": {"00:00": 0.00999, ..., "23:45": 0.0601}}
    }

``prices``   — hourly mean, EUR/kWh, 5 decimals. Legacy key, never removed.
``prices15`` — the market's NATIVE resolution (Elering returns 15-minute data
               since the LV day-ahead market moved to quarter-hourly products;
               ``sensor.nord_pool_lv_current_price`` steps every 15 min too).
               Additive: an old build simply ignores it.

Rules that must not be relaxed
------------------------------
* A FUTURE day (tomorrow, day-after) is written only when that local day is
  COMPLETE. Elering's response bleeds a handful of next-day slots across the
  UTC->local boundary hours before the day-ahead auction publishes (~14:00
  local); writing those made the UIs claim they "had tomorrow" and then draw 23
  empty hours next to one real bar.
* Nothing is ever fabricated. No zero-fill, no interpolation, no carrying the
  last price forward. A slot we do not have is simply absent.
* Negative prices are legitimate on the day-ahead market and are kept verbatim.
* The previous file is merged in, and a day is replaced only by data with at
  least as many slots, so a partial or late response can never destroy a good
  day that was already known.
* Days older than yesterday are pruned, so the file cannot grow forever.
* On ANY fetch/parse failure the existing file is left untouched (and the job
  exits non-zero so HA logs it).
* The write is atomic (temp file in the same directory + ``os.replace``), the
  published file is always mode 0644 (it is served from ``/config/www``), and
  the directory entry is fsynced so the rename survives a power cut. No failure
  path — including an interrupt mid-write — can leave a partial file at the
  target path or a stray temp file in the web root.
"""
from __future__ import annotations

import datetime
import json
import os
import sys
import tempfile
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

try:
    from zoneinfo import ZoneInfo

    RIGA = ZoneInfo("Europe/Riga")
except Exception:  # pragma: no cover - zoneinfo missing is not expected on HA OS
    RIGA = datetime.timezone(datetime.timedelta(hours=3))

UTC = datetime.timezone.utc

API = "https://dashboard.elering.ee/api/nps/price"
AREA = "lv"
OUT_PATH = "/config/www/today_prices.json"
HORIZON_DAYS = 3          # today + tomorrow + day-after; Elering serves what exists
HTTP_TIMEOUT = 15
HOUR = 3600


# --------------------------------------------------------------------------- fetch

def build_url(start: datetime.datetime, end: datetime.datetime) -> str:
    return (
        API
        + "?start=" + start.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        + "&end=" + end.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def fetch(url: str, timeout: int = HTTP_TIMEOUT) -> dict:
    """GET + parse. Raises on transport error, HTTP error or malformed JSON."""
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "HA/1.0"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# --------------------------------------------------------------------------- parse

def slots(data, area: str = AREA):
    """-> sorted [(aware local datetime, EUR/kWh)]. Unusable rows are dropped.

    Deduplicates by exact instant. The two local 03:00 readings of the autumn
    DST fall-back day are DIFFERENT instants, so both survive and the day still
    counts as complete.
    """
    rows = ((data or {}).get("data") or {}).get(area) if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    found: dict[datetime.datetime, float] = {}
    for x in rows:
        if not isinstance(x, dict):
            continue
        try:
            ts = int(x["timestamp"])
            eur_mwh = float(x["price"])
        except (KeyError, TypeError, ValueError):
            continue
        if eur_mwh != eur_mwh or eur_mwh in (float("inf"), float("-inf")):
            continue  # NaN / +-inf are not prices
        try:
            dt = datetime.datetime.fromtimestamp(ts, tz=UTC).astimezone(RIGA)
        except (OverflowError, OSError, ValueError):
            continue
        found[dt] = eur_mwh / 1000.0  # EUR/MWh -> EUR/kWh
    return sorted(found.items())


def step_seconds(times) -> int:
    """Native resolution = the smallest positive gap between consecutive slots.

    Robust to holes in the series and to the DST day's odd gap. Falls back to
    hourly when there is only one slot (nothing to measure).
    """
    deltas = [int((b - a).total_seconds()) for a, b in zip(times, times[1:])]
    deltas = [d for d in deltas if d > 0]
    return min(deltas) if deltas else HOUR


def day_span_seconds(day: datetime.date) -> int:
    """Real length of that LOCAL calendar day: 23 h / 24 h / 25 h around DST."""
    a = datetime.datetime.combine(day, datetime.time(0, 0), tzinfo=RIGA)
    b = datetime.datetime.combine(day + datetime.timedelta(days=1), datetime.time(0, 0), tzinfo=RIGA)
    return int((b.astimezone(UTC) - a.astimezone(UTC)).total_seconds())


def expected_hours(day: datetime.date) -> int:
    """Distinct local hour labels that day has: 23 spring-forward, 24 otherwise.

    The autumn fall-back day is 25 h long but repeats hour 3, so the hourly map
    still holds 24 keys.
    """
    return min(24, day_span_seconds(day) // HOUR)


def group(items):
    """-> (hourly {day:{'H':price}}, quarter {day:{'HH:MM':price}}, {day: slot count})."""
    b_hour: dict[str, dict[str, list]] = {}
    b_step: dict[str, dict[str, list]] = {}
    counts: dict[str, int] = {}
    for dt, price in items:
        day = dt.strftime("%Y-%m-%d")
        counts[day] = counts.get(day, 0) + 1
        b_hour.setdefault(day, {}).setdefault(str(dt.hour), []).append(price)
        b_step.setdefault(day, {}).setdefault(dt.strftime("%H:%M"), []).append(price)

    def flatten(buckets, key):
        return {
            day: {
                k: round(sum(v) / len(v), 5)
                for k, v in sorted(slots_.items(), key=key)
            }
            for day, slots_ in buckets.items()
        }

    hourly = flatten(b_hour, lambda kv: int(kv[0]))
    quarter = flatten(b_step, lambda kv: kv[0])
    return hourly, quarter, counts


# --------------------------------------------------------------------------- merge

def load_previous(path: str) -> dict:
    """Previous file, or an empty skeleton. Never raises: a corrupt file simply
    means we have nothing to carry forward."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _clean_day_map(value) -> dict:
    """Keep only ``{'YYYY-MM-DD': {str: number}}`` entries from a previous file."""
    out: dict[str, dict[str, float]] = {}
    if not isinstance(value, dict):
        return out
    for day, slots_ in value.items():
        if not isinstance(day, str) or not isinstance(slots_, dict):
            continue
        try:
            datetime.date.fromisoformat(day)
        except ValueError:
            continue
        kept = {}
        for k, v in slots_.items():
            if not isinstance(k, str) or isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            if v != v or v in (float("inf"), float("-inf")):
                continue
            kept[k] = float(v)
        if kept:
            out[day] = kept
    return out


def build_payload(data, now_local: datetime.datetime, previous: dict) -> dict:
    """Pure: raw Elering JSON + clock + previous file -> the file to write.

    Raises ValueError when the result would not contain today, which is the one
    situation where writing is worse than keeping what is already on disk.
    """
    items = slots(data)
    step = step_seconds([dt for dt, _ in items])
    hourly, quarter, counts = group(items)

    today = now_local.date()
    yesterday = today - datetime.timedelta(days=1)

    accepted: list[str] = []
    for day_key, count in sorted(counts.items()):
        day = datetime.date.fromisoformat(day_key)
        if day < today:
            continue                       # never in range, but be explicit
        if day == today:
            accepted.append(day_key)       # today is authoritative even if short
            continue
        # FUTURE day: complete or nothing. This is the gate that stops the
        # cross-midnight bleed from masquerading as "tomorrow's prices".
        if count >= day_span_seconds(day) // step:
            accepted.append(day_key)

    if not accepted:
        # Well-formed JSON that carries no usable day (wrong shape, empty area,
        # every row rejected). Rewriting would only restamp `updated` on data we
        # did not refresh, so treat it exactly like a failed fetch.
        raise ValueError("response contained no usable day")

    merged_hour = _clean_day_map(previous.get("prices"))
    merged_step = _clean_day_map(previous.get("prices15"))
    written = []
    for day_key in accepted:
        # A day is replaced only by data that is at least as complete, so a
        # short/late response can never eat a good day we already had.
        if len(hourly[day_key]) >= len(merged_hour.get(day_key, {})):
            merged_hour[day_key] = hourly[day_key]
            merged_step[day_key] = quarter[day_key]
            written.append(day_key)

    # Prune: nothing older than yesterday, and no INCOMPLETE future day. The second
    # half also cleans a partial tomorrow written by an older version of this script
    # (or carried over from the previous file) — a future day is all-or-nothing.
    def keep(day_key: str) -> bool:
        if day_key < yesterday.isoformat():
            return False
        day = datetime.date.fromisoformat(day_key)
        if day <= today:
            return True
        return len(merged_hour.get(day_key, {})) >= expected_hours(day)

    merged_hour = {d: v for d, v in sorted(merged_hour.items()) if keep(d)}
    merged_step = {d: v for d, v in sorted(merged_step.items()) if d in merged_hour}

    if today.isoformat() not in merged_hour:
        raise ValueError("no prices for today after merge")

    # Only claim a fresh timestamp when this run actually contributed data.
    updated = (
        datetime.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        if written
        else previous.get("updated") or datetime.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    payload = {"updated": updated, "step_minutes": max(1, step // 60),
               "prices": merged_hour}
    if merged_step:
        payload["prices15"] = merged_step
    return payload


# --------------------------------------------------------------------------- write

def _fsync_dir(directory: str) -> None:
    """Flush the directory entry so the rename survives a power cut.

    ``os.replace`` is atomic with respect to readers, but on most filesystems
    the new directory entry only reaches the platter on the next metadata
    flush.  The HA box is a VM that can lose power, and the failure mode is
    exactly the one this whole module exists to prevent: after the reboot the
    consumers find a zero-length or half-old ``today_prices.json``.

    Best-effort on purpose: some filesystems refuse ``O_RDONLY`` fsync on a
    directory.  Durability is a bonus, never a reason to report a successful
    write as failed — by the time we get here the file is already correct.
    """
    try:
        dir_fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    except OSError:
        pass
    finally:
        os.close(dir_fd)


def write_atomic(path: str, payload: dict) -> None:
    directory = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".today_prices.", suffix=".tmp")
    try:
        try:
            handle = os.fdopen(fd, "w", encoding="utf-8")
        except BaseException:
            os.close(fd)   # fdopen did not take ownership; don't leak the fd
            raise
        with handle as f:
            json.dump(payload, f)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o644)          # served from /config/www, must stay readable
        os.replace(tmp, path)
    except BaseException:
        # BaseException, not Exception: a KeyboardInterrupt/SystemExit between
        # mkstemp and replace must not leave a 0600 temp file behind in the
        # web root either.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    _fsync_dir(directory)


def main() -> int:
    now_local = datetime.datetime.now(RIGA)
    start = datetime.datetime.combine(now_local.date(), datetime.time(0, 0), tzinfo=RIGA)
    end = start + datetime.timedelta(days=HORIZON_DAYS)
    try:
        data = fetch(build_url(start, end))
    except Exception as exc:
        print("SKIP: Elering fetch failed, file untouched:", type(exc).__name__, exc)
        return 1

    previous = load_previous(OUT_PATH)
    try:
        payload = build_payload(data, now_local, previous)
    except Exception as exc:
        print("SKIP: unusable response, file untouched:", type(exc).__name__, exc)
        return 1

    try:
        write_atomic(OUT_PATH, payload)
    except Exception as exc:
        print("FAIL: could not write", OUT_PATH, type(exc).__name__, exc)
        return 1

    print("OK:", {
        "step_minutes": payload["step_minutes"],
        "days": {d: len(h) for d, h in payload["prices"].items()},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
