"""Contract tests for the Nord Pool / Elering price pipeline.

Two scripts, deployed to the HA box as ``/config/update_today_prices.py`` and
``/config/price_forecast.py``:

    Elering  ->  update_today_prices.py  ->  /config/www/today_prices.json
                                                   |
                        +--------------------------+--------------------+
                        |                                               |
                 price_forecast.py                              Mini App / tablet
                 (shell_command, response_variable)              (HTTP /local/...)

The whole point of the file is that four consumers read it, so the invariants
worth locking are about what may EVER appear at that path:

* it is only ever replaced atomically and with mode 0644 (the tablet and the
  Mini App fetch it over HTTP from the web root — a 0600 file is a silent
  outage for both);
* every failure path leaves the previous good file byte-identical, because
  stale-but-real prices beat no prices;
* nothing is ever fabricated — a slot we do not have is absent, never zero;
* ``price_forecast.py`` never exits non-zero and never raises, because its
  caller is a Jinja template with no ``try``: it must degrade to ``ok=0`` so
  the automation prints «нет данных» instead of dying mid-notification.

Hermetic: no network, no HA, no real ``/config``. Every test writes into tmp_path.
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import os
import stat
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _load(name: str):
    """Import a repo-root script by path (they are scripts, not a package)."""
    spec = importlib.util.spec_from_file_location(name, REPO / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


updater = _load("update_today_prices")
forecast = _load("price_forecast")

RIGA = updater.RIGA


# --------------------------------------------------------------------------- helpers
def elering(day: datetime.date, *, step_min: int = 15, price=lambda i: 10.0,
            days: int = 1, area: str = "lv") -> dict:
    """Elering-shaped response: `days` complete local days at `step_min` resolution."""
    rows = []
    per_day = 24 * 60 // step_min
    for d in range(days):
        start = datetime.datetime.combine(
            day + datetime.timedelta(days=d), datetime.time(0, 0), tzinfo=RIGA
        )
        for i in range(per_day):
            when = start + datetime.timedelta(minutes=step_min * i)
            rows.append({"timestamp": int(when.timestamp()), "price": price(d * per_day + i)})
    return {"success": True, "data": {area: rows}}


def good_payload(day: datetime.date) -> dict:
    return updater.build_payload(
        elering(day), datetime.datetime.combine(day, datetime.time(12, 0), tzinfo=RIGA), {}
    )


@pytest.fixture
def forecast_runner(monkeypatch, capsys):
    def _run(path: Path) -> dict:
        monkeypatch.setattr(forecast, "PATH", str(path))
        code = 0
        try:
            forecast.main()
        except SystemExit as exc:
            code = exc.code or 0
        assert code == 0, f"price_forecast must always exit 0, got {code}"
        fields = {}
        for line in capsys.readouterr().out.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                fields[k] = v
        return fields

    return _run


# =========================================================================== #
# update_today_prices.py — what may appear at the published path
# =========================================================================== #
@pytest.mark.unit
def test_published_file_is_world_readable(tmp_path):
    """Mode 0644. The tablet and Mini App fetch this over HTTP from /config/www;
    mkstemp creates 0600, so forgetting the chmod is a silent outage for both."""
    target = tmp_path / "today_prices.json"
    updater.write_atomic(str(target), {"updated": "x", "prices": {}})
    assert stat.S_IMODE(target.stat().st_mode) == 0o644


@pytest.mark.unit
def test_write_leaves_no_temp_file_behind(tmp_path):
    target = tmp_path / "today_prices.json"
    updater.write_atomic(str(target), {"updated": "x", "prices": {}})
    assert [p.name for p in tmp_path.iterdir()] == ["today_prices.json"]


@pytest.mark.unit
def test_failed_write_keeps_previous_file_and_drops_the_temp(tmp_path):
    """A payload that cannot be serialised must not truncate the good file."""
    target = tmp_path / "today_prices.json"
    original = json.dumps({"updated": "old", "prices": {"2026-08-16": {"0": 0.01}}})
    target.write_text(original, encoding="utf-8")

    class Unserialisable:
        pass

    with pytest.raises(TypeError):
        updater.write_atomic(str(target), {"prices": Unserialisable()})

    assert target.read_text(encoding="utf-8") == original
    assert sorted(p.name for p in tmp_path.iterdir()) == ["today_prices.json"]


@pytest.mark.unit
def test_interrupt_mid_write_leaves_no_stray_temp_in_web_root(tmp_path, monkeypatch):
    """KeyboardInterrupt is a BaseException — the cleanup must still fire, or a
    0600 temp file is left sitting in the web root."""
    target = tmp_path / "today_prices.json"

    def boom(*a, **k):
        raise KeyboardInterrupt

    monkeypatch.setattr(updater.json, "dump", boom)
    with pytest.raises(KeyboardInterrupt):
        updater.write_atomic(str(target), {"prices": {}})
    assert list(tmp_path.iterdir()) == []


@pytest.mark.unit
def test_replace_is_durable(tmp_path, monkeypatch):
    """The directory entry is fsynced, otherwise a power cut can resurrect the
    old file (or a zero-length one) after reboot."""
    seen = []
    real_fsync = os.fsync
    monkeypatch.setattr(updater.os, "fsync", lambda fd: (seen.append(fd), real_fsync(fd))[1])
    updater.write_atomic(str(tmp_path / "today_prices.json"), {"prices": {}})
    # one fsync for the file, one for the containing directory
    assert len(seen) >= 2, "directory entry was not fsynced after os.replace"


@pytest.mark.unit
def test_directory_fsync_failure_does_not_fail_a_good_write(tmp_path, monkeypatch):
    """Durability is a bonus. If the filesystem refuses to fsync a directory the
    file is already correct, so the run must still report success."""
    target = tmp_path / "today_prices.json"
    real_open = os.open

    def refuse_directories(path, flags, *a, **k):
        if os.path.isdir(path):
            raise OSError("this filesystem will not fsync a directory")
        return real_open(path, flags, *a, **k)

    monkeypatch.setattr(updater.os, "open", refuse_directories)
    updater.write_atomic(str(target), {"updated": "x", "prices": {}})
    assert json.loads(target.read_text(encoding="utf-8"))["updated"] == "x"


# =========================================================================== #
# update_today_prices.py — main(): every failure path keeps the good file
# =========================================================================== #
@pytest.mark.parametrize(
    "fetch_result, why",
    [
        (ConnectionError("Elering unreachable"), "transport failure"),
        (ValueError("Expecting value"), "malformed JSON"),
        ({"data": {"ee": []}}, "valid JSON, wrong area"),
        ({"nonsense": True}, "valid JSON, wrong shape"),
        ({"data": {"lv": []}}, "valid JSON, no rows"),
    ],
)
@pytest.mark.unit
def test_every_failure_path_leaves_the_previous_good_file_intact(
    tmp_path, monkeypatch, fetch_result, why
):
    target = tmp_path / "today_prices.json"
    today = datetime.datetime.now(RIGA).date()
    updater.write_atomic(str(target), good_payload(today))
    before = target.read_bytes()

    def fetch(*a, **k):
        if isinstance(fetch_result, Exception):
            raise fetch_result
        return fetch_result

    monkeypatch.setattr(updater, "fetch", fetch)
    monkeypatch.setattr(updater, "OUT_PATH", str(target))

    assert updater.main() == 1, f"{why}: must exit non-zero so HA logs it"
    assert target.read_bytes() == before, f"{why}: clobbered a good price file"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["today_prices.json"]


@pytest.mark.unit
def test_successful_run_publishes_today_at_native_resolution(tmp_path, monkeypatch):
    target = tmp_path / "today_prices.json"
    today = datetime.datetime.now(RIGA).date()
    monkeypatch.setattr(updater, "fetch", lambda *a, **k: elering(today))
    monkeypatch.setattr(updater, "OUT_PATH", str(target))

    assert updater.main() == 0
    data = json.loads(target.read_text(encoding="utf-8"))
    key = today.isoformat()
    assert data["step_minutes"] == 15
    assert len(data["prices"][key]) == 24, "24 hourly means"
    assert len(data["prices15"][key]) == 96, "96 quarter-hour slots"
    assert stat.S_IMODE(target.stat().st_mode) == 0o644


@pytest.mark.unit
def test_incomplete_tomorrow_is_not_published(tmp_path):
    """Elering bleeds a few next-day slots across the UTC->local boundary long
    before the day-ahead auction publishes. Writing them made the UIs claim they
    "had tomorrow" and then draw 23 empty bars next to one real one."""
    today = datetime.datetime.now(RIGA).date()
    tomorrow = today + datetime.timedelta(days=1)
    data = elering(today)
    bleed = datetime.datetime.combine(tomorrow, datetime.time(0, 0), tzinfo=RIGA)
    data["data"]["lv"].append({"timestamp": int(bleed.timestamp()), "price": 42.0})

    payload = updater.build_payload(
        data, datetime.datetime.combine(today, datetime.time(12, 0), tzinfo=RIGA), {}
    )
    assert tomorrow.isoformat() not in payload["prices"]


@pytest.mark.unit
def test_complete_tomorrow_is_published(tmp_path):
    today = datetime.datetime.now(RIGA).date()
    tomorrow = today + datetime.timedelta(days=1)
    payload = updater.build_payload(
        elering(today, days=2),
        datetime.datetime.combine(today, datetime.time(15, 0), tzinfo=RIGA),
        {},
    )
    assert len(payload["prices"][tomorrow.isoformat()]) == 24
    assert len(payload["prices15"][tomorrow.isoformat()]) == 96


@pytest.mark.unit
def test_a_known_good_day_is_never_replaced_by_a_shorter_one():
    """A late/partial response must not eat a complete day already on disk."""
    today = datetime.datetime.now(RIGA).date()
    now = datetime.datetime.combine(today, datetime.time(20, 0), tzinfo=RIGA)
    full = updater.build_payload(elering(today, days=2), now, {})

    partial = elering(today)
    partial["data"]["lv"] = partial["data"]["lv"][:8]
    merged = updater.build_payload(partial, now, full)

    tomorrow = (today + datetime.timedelta(days=1)).isoformat()
    assert len(merged["prices"][today.isoformat()]) == 24, "today was truncated"
    assert len(merged["prices"][tomorrow]) == 24, "tomorrow was lost"


# =========================================================================== #
# price_forecast.py — the reader the two Telegram automations depend on
# =========================================================================== #
@pytest.mark.unit
def test_forecast_reads_today(tmp_path, forecast_runner):
    now = datetime.datetime.now(RIGA)
    today = now.date().isoformat()
    # cheap all day except a spike at 23:00, so both thresholds resolve
    quarter = {f"{h:02d}:{m:02d}": (0.20 if h == 23 else 0.01)
               for h in range(24) for m in (0, 15, 30, 45)}
    path = tmp_path / "p.json"
    path.write_text(json.dumps({
        "updated": "2026-08-16T09:42:18Z", "step_minutes": 15,
        "prices": {today: {str(h): (0.20 if h == 23 else 0.01) for h in range(24)}},
        "prices15": {today: quarter},
    }), encoding="utf-8")

    f = forecast_runner(path)
    assert f["ok"] == "1"
    assert f["today"] == today
    assert f["updated"] == "2026-08-16T09:42:18Z"
    assert f["has_tomorrow"] == "0"
    assert float(f["slot_price"]) == 0.01
    assert f["rest_max"] == "0.2" and f["rest_max_at"] == "23:00"
    assert f["boiler_cheap"] == "1" and f["boiler_cross_at"] == "23:00"
    assert f["towel_cheap"] == "1" and f["towel_cross_at"] == "23:00"


@pytest.mark.unit
def test_forecast_reports_tomorrow_when_present(tmp_path, forecast_runner):
    now = datetime.datetime.now(RIGA)
    today = now.date().isoformat()
    tomorrow = (now + datetime.timedelta(days=1)).date().isoformat()
    path = tmp_path / "p.json"
    path.write_text(json.dumps({
        "updated": "u", "step_minutes": 60,
        "prices": {today: {str(h): 0.01 for h in range(24)},
                   tomorrow: {str(h): 0.05 + h * 0.01 for h in range(24)}},
    }), encoding="utf-8")

    f = forecast_runner(path)
    assert f["ok"] == "1"
    assert f["has_tomorrow"] == "1"
    assert float(f["tomorrow_min"]) == pytest.approx(0.05)
    assert f["tomorrow_min_at"] == "00:00"
    assert float(f["tomorrow_max"]) == pytest.approx(0.28)
    assert f["tomorrow_max_at"] == "23:00"
    # cheap now, tomorrow crosses 0.04 -> the crossing is reported as "завтра"
    assert f["towel_cheap"] == "1"
    assert "завтра" in f["towel_txt"]


@pytest.mark.parametrize(
    "content, expected_error",
    [
        (None, "file_missing"),
        ("{not json", "file_unreadable:JSONDecodeError"),
        ("[]", "file_not_object"),
        ('{"updated": "u", "prices": {}}', "no_today"),
        ('{"updated": "u", "prices": {"1999-01-01": {"0": 0.1}}}', "no_today"),
    ],
)
@pytest.mark.unit
def test_forecast_degrades_to_ok0_instead_of_raising(tmp_path, forecast_runner,
                                                     content, expected_error):
    """The caller is a Jinja template with no `try`. A raise or a non-zero exit
    would abort the whole Telegram notification; ok=0 makes it print «нет данных»."""
    path = tmp_path / "p.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")

    f = forecast_runner(path)
    assert f["ok"] == "0"
    assert f["error"] == expected_error
    # must not invent numbers to fill the gap
    assert "slot_price" not in f and "rest_min" not in f


@pytest.mark.unit
def test_forecast_output_is_parseable_by_the_jinja_regex(tmp_path, forecast_runner):
    """The automations parse with regex_findall('(?m)^key=(.*)$'), so no key may
    contain '=' and no value may contain a newline."""
    now = datetime.datetime.now(RIGA)
    path = tmp_path / "p.json"
    path.write_text(json.dumps({
        "updated": "u", "step_minutes": 60,
        "prices": {now.date().isoformat(): {str(h): 0.01 for h in range(24)}},
    }), encoding="utf-8")

    fields = forecast_runner(path)
    assert fields["ok"] == "1"
    for key, value in fields.items():
        assert "=" not in key and key == key.strip()
        assert "\n" not in value and "\r" not in value


@pytest.mark.unit
def test_forecast_never_zero_fills_a_sparse_day(tmp_path, forecast_runner):
    """Only one hour is known for today. The extremes must describe THAT slot —
    a zero-filled 0.0 minimum would send the digest's «дёшево до …» line lying."""
    today = datetime.datetime.now(RIGA).date().isoformat()
    path = tmp_path / "p.json"
    path.write_text(json.dumps({
        "updated": "u", "step_minutes": 60,
        "prices": {today: {"23": 0.077}},
    }), encoding="utf-8")

    f = forecast_runner(path)
    assert f["ok"] == "1"
    assert float(f["rest_min"]) == 0.077
    assert float(f["rest_max"]) == 0.077
    assert f["rest_min_at"] == "23:00"
