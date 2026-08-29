"""Interval-based electricity cost model for MySmartHome.

Pure-Python cost accounting that prices each energy interval at the Nord Pool
price in force during that interval. No Home Assistant writes, no deploys.

See ``model`` for the algorithm and ``ha_source`` for a READ-ONLY adapter that
pulls interval energy + interval prices out of the HA recorder.
"""
from .model import (  # noqa: F401
    CostInterval,
    EnergyInterval,
    HomeReport,
    LOCAL_TZ,
    PeriodSummary,
    PricePoint,
    Reading,
    SPOT_ONLY,
    Tariff,
    UTC,
    build_grid,
    compute_device_costs,
    cost_interval,
    cost_series,
    day_bounds,
    energy_series,
    home_report,
    interval_energy,
    last_month_bounds,
    month_bounds,
    month_forecast,
    price_for_interval,
    summarize,
    this_month_bounds,
    today_bounds,
    yesterday_bounds,
)

__all__ = [
    "CostInterval",
    "EnergyInterval",
    "HomeReport",
    "LOCAL_TZ",
    "PeriodSummary",
    "PricePoint",
    "Reading",
    "SPOT_ONLY",
    "Tariff",
    "UTC",
    "build_grid",
    "compute_device_costs",
    "cost_interval",
    "cost_series",
    "day_bounds",
    "energy_series",
    "home_report",
    "interval_energy",
    "last_month_bounds",
    "month_bounds",
    "month_forecast",
    "price_for_interval",
    "summarize",
    "this_month_bounds",
    "today_bounds",
    "yesterday_bounds",
]
