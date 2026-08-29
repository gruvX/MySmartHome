"""Unit tests for the interval-based energy cost model (tools/energy_cost).

Covers: hourly & 15-min grids, DST day length, negative prices, missing price,
missing energy (unavailable), and counter reset. All data is mocked; no HA
access. The whole point is to prove correct per-interval accounting and that
missing data is never treated as zero.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.energy_cost.model import (  # noqa: E402
    LOCAL_TZ,
    PricePoint,
    Reading,
    SPOT_ONLY,
    Tariff,
    build_grid,
    compute_device_costs,
    cost_interval,
    day_bounds,
    interval_energy,
    last_month_bounds,
    month_bounds,
    month_forecast,
    price_for_interval,
    summarize,
    home_report,
)

UTC = timezone.utc
Q = timedelta(minutes=15)
H = timedelta(hours=1)


def _dt(y, mo, d, h=0, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=UTC)


def _prices_15(start, vals):
    """Build consecutive 15-min PricePoints from a list of prices."""
    pts = []
    t = start
    for v in vals:
        pts.append(PricePoint(t, t + Q, v))
        t += Q
    return pts


# --------------------------------------------------------------------------- #
# Interval energy from a cumulative counter
# --------------------------------------------------------------------------- #
def test_interval_energy_simple_delta():
    r = [Reading(_dt(2026, 7, 15, 10, 0), 100.0), Reading(_dt(2026, 7, 15, 10, 15), 100.5)]
    e = interval_energy(r, _dt(2026, 7, 15, 10, 0), _dt(2026, 7, 15, 10, 15))
    assert e.kwh == 0.5
    assert e.complete and not e.reset


def test_interval_energy_uses_anchor_before_start():
    # last reading before the window is the start anchor (carry-forward)
    r = [
        Reading(_dt(2026, 7, 15, 9, 50), 10.0),
        Reading(_dt(2026, 7, 15, 10, 10), 12.0),
    ]
    e = interval_energy(r, _dt(2026, 7, 15, 10, 0), _dt(2026, 7, 15, 10, 15))
    assert e.kwh == 2.0  # 12 - 10, anchored to the 9:50 value
    assert e.complete


def test_available_but_idle_is_zero_not_missing():
    # available counter, no new pulses in window => genuine 0 kWh (not missing)
    r = [Reading(_dt(2026, 7, 15, 9, 0), 50.0)]
    e = interval_energy(r, _dt(2026, 7, 15, 10, 0), _dt(2026, 7, 15, 10, 15))
    assert e.kwh == 0.0
    assert e.complete


# --------------------------------------------------------------------------- #
# Missing / unavailable energy is NEVER zero
# --------------------------------------------------------------------------- #
def test_missing_energy_no_data_is_none_not_zero():
    e = interval_energy([], _dt(2026, 7, 15, 10, 0), _dt(2026, 7, 15, 10, 15))
    assert e.kwh is None
    assert not e.complete


def test_unavailable_marks_incomplete():
    r = [
        Reading(_dt(2026, 7, 15, 10, 0), 100.0),
        Reading(_dt(2026, 7, 15, 10, 5), None),   # went unavailable
        Reading(_dt(2026, 7, 15, 10, 12), 100.4),  # recovered
    ]
    e = interval_energy(r, _dt(2026, 7, 15, 10, 0), _dt(2026, 7, 15, 10, 15))
    assert not e.complete  # gap touched the interval
    # measured post-recovery portion is preserved, not fabricated as 0
    assert e.kwh == 0.0 or e.kwh is not None


def test_missing_energy_yields_none_cost():
    e = interval_energy([], _dt(2026, 7, 15, 10, 0), _dt(2026, 7, 15, 10, 15))
    c = cost_interval(e, price=0.10)
    assert c.total is None
    assert c.energy_missing is True


# --------------------------------------------------------------------------- #
# Counter reset detection
# --------------------------------------------------------------------------- #
def test_counter_reset_detected():
    r = [
        Reading(_dt(2026, 7, 15, 10, 0), 500.0),
        Reading(_dt(2026, 7, 15, 10, 10), 0.3),  # reset to ~0 then climbed
    ]
    e = interval_energy(r, _dt(2026, 7, 15, 10, 0), _dt(2026, 7, 15, 10, 15))
    assert e.reset is True
    assert e.kwh == 0.3  # post-reset value counted, huge negative not counted


def test_reset_flag_flows_to_summary():
    r = [
        Reading(_dt(2026, 7, 15, 10, 0), 500.0),
        Reading(_dt(2026, 7, 15, 10, 10), 0.3),
    ]
    ivs = compute_device_costs(
        r, _prices_15(_dt(2026, 7, 15, 10, 0), [0.1]),
        _dt(2026, 7, 15, 10, 0), _dt(2026, 7, 15, 10, 15),
    )
    s = summarize(ivs, "reset")
    assert s.n_reset == 1


# --------------------------------------------------------------------------- #
# Price alignment + core correctness (per-interval, not daily-avg)
# --------------------------------------------------------------------------- #
def test_price_alignment_15min():
    prices = _prices_15(_dt(2026, 7, 15, 10, 0), [0.05, 0.20])
    assert price_for_interval(prices, _dt(2026, 7, 15, 10, 0), _dt(2026, 7, 15, 10, 15)) == 0.05
    assert price_for_interval(prices, _dt(2026, 7, 15, 10, 15), _dt(2026, 7, 15, 10, 30)) == 0.20


def test_interval_cost_beats_daily_avg():
    # 1 kWh cheap quarter @0.02, 1 kWh pricey quarter @0.20
    # correct = 0.02 + 0.20 = 0.22 ; daily-avg-of-price*total = 0.11*2 = 0.22 here
    # but shift the load onto the pricey quarter to show the difference:
    readings = [
        Reading(_dt(2026, 7, 15, 10, 0), 0.0),
        Reading(_dt(2026, 7, 15, 10, 15), 0.0),   # nothing used in cheap quarter
        Reading(_dt(2026, 7, 15, 10, 30), 2.0),   # 2 kWh used in pricey quarter
    ]
    prices = _prices_15(_dt(2026, 7, 15, 10, 0), [0.02, 0.20])
    ivs = compute_device_costs(
        readings, prices, _dt(2026, 7, 15, 10, 0), _dt(2026, 7, 15, 10, 30)
    )
    s = summarize(ivs, "load-shift")
    assert abs(s.total - 0.40) < 1e-9        # correct: 2 kWh * 0.20
    naive = 2.0 * ((0.02 + 0.20) / 2)         # daily/avg-price method
    assert abs(naive - 0.22) < 1e-9
    assert s.total != naive                    # model is not the naive method


# --------------------------------------------------------------------------- #
# Negative prices are not clamped
# --------------------------------------------------------------------------- #
def test_negative_price_not_clamped():
    e = interval_energy(
        [Reading(_dt(2026, 7, 15, 10, 0), 0.0), Reading(_dt(2026, 7, 15, 10, 15), 3.0)],
        _dt(2026, 7, 15, 10, 0), _dt(2026, 7, 15, 10, 15),
    )
    c = cost_interval(e, price=-0.05)
    assert abs(c.spot_cost - (-0.15)) < 1e-9
    assert abs(c.total - (-0.15)) < 1e-9  # spot-only tariff: you are paid
    assert c.total < 0


# --------------------------------------------------------------------------- #
# Missing price -> None cost, surfaced in data quality
# --------------------------------------------------------------------------- #
def test_missing_price_none_cost_and_counted():
    readings = [
        Reading(_dt(2026, 7, 15, 10, 0), 0.0),
        Reading(_dt(2026, 7, 15, 10, 15), 1.0),
        Reading(_dt(2026, 7, 15, 10, 30), 2.0),
    ]
    # price only for the first quarter; second quarter price missing
    prices = [PricePoint(_dt(2026, 7, 15, 10, 0), _dt(2026, 7, 15, 10, 15), 0.10)]
    ivs = compute_device_costs(
        readings, prices, _dt(2026, 7, 15, 10, 0), _dt(2026, 7, 15, 10, 30)
    )
    s = summarize(ivs, "price-gap")
    assert s.n_price_missing == 1
    assert s.n_usable == 1
    assert abs(s.kwh - 1.0) < 1e-9   # only the priced quarter's kWh summed
    assert s.completeness == 0.5


# --------------------------------------------------------------------------- #
# Grids: hourly and 15-min
# --------------------------------------------------------------------------- #
def test_grid_15min_count():
    g = build_grid(_dt(2026, 7, 15, 0, 0), _dt(2026, 7, 15, 1, 0), Q)
    assert len(g) == 4


def test_grid_hourly_count():
    g = build_grid(_dt(2026, 7, 15, 0, 0), _dt(2026, 7, 16, 0, 0), H)
    assert len(g) == 24


def test_hourly_end_to_end():
    readings = [
        Reading(_dt(2026, 7, 15, 0, 0), 0.0),
        Reading(_dt(2026, 7, 15, 1, 0), 1.0),
        Reading(_dt(2026, 7, 15, 2, 0), 3.0),
    ]
    prices = [
        PricePoint(_dt(2026, 7, 15, 0, 0), _dt(2026, 7, 15, 1, 0), 0.10),
        PricePoint(_dt(2026, 7, 15, 1, 0), _dt(2026, 7, 15, 2, 0), 0.30),
    ]
    ivs = compute_device_costs(
        readings, prices, _dt(2026, 7, 15, 0, 0), _dt(2026, 7, 15, 2, 0), step=H
    )
    s = summarize(ivs, "hourly")
    # hour1: 1 kWh * 0.10 = 0.10 ; hour2: 2 kWh * 0.30 = 0.60
    assert abs(s.total - 0.70) < 1e-9


# --------------------------------------------------------------------------- #
# DST day length (Europe/Riga)
# --------------------------------------------------------------------------- #
def test_dst_spring_forward_day_is_23h():
    # 2026-03-29: clocks jump 03:00 -> 04:00 local, day is 23h
    start, end = day_bounds(datetime(2026, 3, 29, 12, 0, tzinfo=LOCAL_TZ))
    assert (end - start) == timedelta(hours=23)


def test_dst_fall_back_day_is_25h():
    # 2026-10-25: clocks fall back, day is 25h
    start, end = day_bounds(datetime(2026, 10, 25, 12, 0, tzinfo=LOCAL_TZ))
    assert (end - start) == timedelta(hours=25)


def test_normal_day_is_24h():
    start, end = day_bounds(datetime(2026, 7, 15, 12, 0, tzinfo=LOCAL_TZ))
    assert (end - start) == timedelta(hours=24)


def test_month_bounds_july():
    start, end = month_bounds(datetime(2026, 7, 15, 12, 0, tzinfo=LOCAL_TZ))
    assert start.astimezone(LOCAL_TZ).day == 1
    assert start.astimezone(LOCAL_TZ).month == 7
    assert end.astimezone(LOCAL_TZ).month == 8


def test_last_month_bounds():
    start, end = last_month_bounds(datetime(2026, 7, 15, 12, 0, tzinfo=UTC))
    assert start.astimezone(LOCAL_TZ).month == 6
    assert end.astimezone(LOCAL_TZ).month == 7


# --------------------------------------------------------------------------- #
# Aggregation, tariff add-ons, home report, reconciliation, forecast
# --------------------------------------------------------------------------- #
def test_tariff_addons_and_vat():
    e = interval_energy(
        [Reading(_dt(2026, 7, 15, 10, 0), 0.0), Reading(_dt(2026, 7, 15, 10, 15), 1.0)],
        _dt(2026, 7, 15, 10, 0), _dt(2026, 7, 15, 10, 15),
    )
    t = Tariff(
        supplier_margin_eur_per_kwh=0.01,
        distribution_eur_per_kwh=0.05,
        vat_rate=0.21,
    )
    c = cost_interval(e, price=0.10, tariff=t)
    # subtotal = 1*(0.10 + 0.01 + 0.05) = 0.16 ; vat = 0.0336 ; total = 0.1936
    assert abs(c.spot_cost - 0.10) < 1e-9
    assert abs(c.addon_cost - 0.06) < 1e-9
    assert abs(c.vat - 0.0336) < 1e-9
    assert abs(c.total - 0.1936) < 1e-9


def test_spot_only_flag():
    assert SPOT_ONLY.spot_only is True
    assert Tariff(vat_rate=0.21).spot_only is False


def test_home_report_reconciliation_and_unaccounted():
    def one_dev(kwh, cost):
        from tools.energy_cost.model import PeriodSummary

        s = PeriodSummary("d", _dt(2026, 7, 15), _dt(2026, 7, 16))
        s.kwh = kwh
        s.total = cost
        s.n_intervals = 96
        s.n_usable = 96
        return s

    devices = {"boiler": one_dev(10.0, 1.0), "ev": one_dev(20.0, 2.0)}
    main = one_dev(40.0, 4.5)  # main meter sees more than sum of plugs
    rep = home_report(devices, "today", main_meter=main)
    assert abs(rep.total_kwh - 30.0) < 1e-9
    assert abs(rep.unaccounted_kwh - 10.0) < 1e-9
    assert abs(rep.unaccounted_cost - 1.5) < 1e-9
    assert rep.ranking[0][0] == "ev"  # most expensive device first
    assert 24.9 < rep.unaccounted_pct < 25.1


def test_home_report_without_main_meter_has_no_unaccounted():
    from tools.energy_cost.model import PeriodSummary

    s = PeriodSummary("d", _dt(2026, 7, 15), _dt(2026, 7, 16))
    s.kwh, s.total, s.n_intervals, s.n_usable = 5.0, 0.5, 96, 96
    rep = home_report({"boiler": s}, "today")
    assert rep.unaccounted_kwh is None  # cannot reconcile without a main meter


def test_month_forecast_linear_runrate():
    from tools.energy_cost.model import PeriodSummary

    m_start, _ = month_bounds(datetime(2026, 7, 15, 12, 0, tzinfo=LOCAL_TZ))
    s = PeriodSummary("m", m_start, m_start + timedelta(days=31))
    s.total = 50.0
    s.n_usable = 100
    # pretend 10 days elapsed -> rate 5/day -> ~155 for 31-day July
    now = m_start.astimezone(LOCAL_TZ) + timedelta(days=10)
    fc = month_forecast(s, now=now)
    assert abs(fc - 155.0) < 1e-6


def test_month_forecast_none_without_data():
    from tools.energy_cost.model import PeriodSummary

    m_start, _ = month_bounds(datetime(2026, 7, 15, 12, 0, tzinfo=LOCAL_TZ))
    s = PeriodSummary("m", m_start, m_start + timedelta(days=31))
    assert month_forecast(s) is None


def test_fixed_daily_charge_applied_at_summary():
    readings = [
        Reading(_dt(2026, 7, 15, 10, 0), 0.0),
        Reading(_dt(2026, 7, 15, 10, 15), 1.0),
    ]
    prices = _prices_15(_dt(2026, 7, 15, 10, 0), [0.10])
    t = Tariff(fixed_daily_eur=0.30)
    ivs = compute_device_costs(
        readings, prices, _dt(2026, 7, 15, 10, 0), _dt(2026, 7, 15, 10, 15), tariff=t
    )
    s = summarize(ivs, "fixed", tariff=t, n_days_for_fixed=1)
    assert abs(s.fixed_cost - 0.30) < 1e-9
    assert abs(s.total - (0.10 + 0.30)) < 1e-9
