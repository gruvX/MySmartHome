"""Interval-based electricity cost model (pure Python, no Home Assistant writes).

Correct cost accounting rule enforced here:

    interval_cost = interval_kWh * NordPool_price_of_that_interval

We NEVER use ``daily_kWh * daily_avg_price`` (the current HA automation even uses
``(lowest+highest)/2`` which is worse). Cost is always the sum of per-interval
products so that consumption is priced at the price that was actually in force
while it happened.

Design constraints (see docs/audit/ENERGY_COST_MODEL.md for the full rationale):

* Prices come from Nord Pool as **EUR/kWh** on a **15-minute** grid (LV market,
  verified live 2026-07-15). Hourly is supported too; the grid size is a
  parameter, not an assumption.
* Energy comes from ``total_increasing`` cumulative counters (kWh). Per-interval
  energy is a counter *delta*, computed with reset detection.
* Missing data is NEVER silently treated as zero. A missing price or missing
  energy reading yields ``None`` cost for that interval and is surfaced in a
  data-quality report. Only genuinely-observed "no change on an available
  counter" is treated as 0 kWh.
* All interval math is done in UTC. Calendar bucketing (day / month) is done in
  the local timezone (Europe/Riga) so DST-length days (23h / 25h) are handled
  correctly.
* Negative prices are legitimate and are NOT clamped.
* Retail add-ons (VAT, supplier margin, distribution/transmission, fixed daily
  charges, day/night tariff) are OWNER-PROVIDED configurable parameters. This
  module invents no values: unset add-ons default to "not applied" and results
  are then explicitly the spot-energy component only.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional, Sequence

try:  # local tz for calendar bucketing; falls back to fixed offset if tzdata missing
    from zoneinfo import ZoneInfo

    LOCAL_TZ = ZoneInfo("Europe/Riga")
except Exception:  # pragma: no cover - only on systems without tzdata
    LOCAL_TZ = timezone(timedelta(hours=2))  # EET, no DST (degraded fallback)

UTC = timezone.utc


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Reading:
    """A single cumulative-energy counter observation (kWh).

    ``value is None`` represents an ``unavailable`` / ``unknown`` state: the
    counter value is *not known* at that time. It is a gap marker, never 0.
    """

    ts: datetime
    value: Optional[float]

    def __post_init__(self) -> None:
        if self.ts.tzinfo is None:
            raise ValueError("Reading.ts must be timezone-aware")


@dataclass(frozen=True)
class PricePoint:
    """Nord Pool price valid over the half-open interval [start, end)."""

    start: datetime
    end: datetime
    price: Optional[float]  # EUR/kWh; None => price unknown for this slot

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("PricePoint start/end must be timezone-aware")
        if self.end <= self.start:
            raise ValueError("PricePoint end must be after start")


# --------------------------------------------------------------------------- #
# Tariff (owner-provided add-ons). Nothing here is invented.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Tariff:
    """Retail cost model on top of the Nord Pool spot price.

    Every field defaults to None ("not configured"). With an all-default tariff
    the computed cost is the SPOT ENERGY COMPONENT ONLY and results are flagged
    ``spot_only=True``. Fill these in from the owner's actual electricity
    contract + Sadales tikls distribution tariff. DO NOT guess values.
    """

    # Per-kWh variable add-ons (EUR/kWh). Typical LV components, all owner-provided:
    supplier_margin_eur_per_kwh: Optional[float] = None      # trader markup on spot
    distribution_eur_per_kwh: Optional[float] = None          # Sadales tikls per-kWh
    transmission_eur_per_kwh: Optional[float] = None          # AST / included in distr.
    excise_eur_per_kwh: Optional[float] = None                # electricity excise duty
    renewables_oik_eur_per_kwh: Optional[float] = None        # mandatory procurement (OIK)

    # Optional day/night split for the per-kWh distribution component. If set,
    # ``distribution_eur_per_kwh`` is ignored and these are used based on the
    # local-time hour of the interval.
    distribution_day_eur_per_kwh: Optional[float] = None
    distribution_night_eur_per_kwh: Optional[float] = None
    night_start_hour: int = 23   # local hour night tariff begins (owner-provided)
    night_end_hour: int = 7      # local hour night tariff ends

    # VAT applied to the whole variable subtotal (spot + add-ons). LV standard 21%.
    vat_rate: Optional[float] = None  # e.g. 0.21 — OWNER PROVIDED

    # Fixed charges (applied at day aggregation, not per interval).
    fixed_daily_eur: Optional[float] = None   # standing/connection charge per day

    @property
    def spot_only(self) -> bool:
        """True when no retail add-ons are configured => spot component only."""
        return all(
            getattr(self, f) is None
            for f in (
                "supplier_margin_eur_per_kwh",
                "distribution_eur_per_kwh",
                "transmission_eur_per_kwh",
                "excise_eur_per_kwh",
                "renewables_oik_eur_per_kwh",
                "distribution_day_eur_per_kwh",
                "distribution_night_eur_per_kwh",
                "vat_rate",
                "fixed_daily_eur",
            )
        )

    def _is_night(self, when_local: datetime) -> bool:
        h = when_local.hour
        if self.night_start_hour <= self.night_end_hour:
            return self.night_start_hour <= h < self.night_end_hour
        # wraps past midnight (e.g. 23 -> 7)
        return h >= self.night_start_hour or h < self.night_end_hour

    def variable_addon_per_kwh(self, interval_start_utc: datetime) -> float:
        """Sum of configured per-kWh add-ons (EUR/kWh), excluding spot & VAT."""
        total = 0.0
        for f in (
            "supplier_margin_eur_per_kwh",
            "transmission_eur_per_kwh",
            "excise_eur_per_kwh",
            "renewables_oik_eur_per_kwh",
        ):
            v = getattr(self, f)
            if v is not None:
                total += v
        if self.distribution_day_eur_per_kwh is not None or self.distribution_night_eur_per_kwh is not None:
            local = interval_start_utc.astimezone(LOCAL_TZ)
            night = self._is_night(local)
            v = self.distribution_night_eur_per_kwh if night else self.distribution_day_eur_per_kwh
            if v is not None:
                total += v
        elif self.distribution_eur_per_kwh is not None:
            total += self.distribution_eur_per_kwh
        return total


SPOT_ONLY = Tariff()  # convenience: pure spot-energy accounting


# --------------------------------------------------------------------------- #
# Per-interval results
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class EnergyInterval:
    start: datetime
    end: datetime
    kwh: Optional[float]      # None => energy unknown (NOT zero)
    complete: bool            # False => a gap/unavailable touched this interval
    reset: bool               # True => counter reset detected inside interval


@dataclass(frozen=True)
class CostInterval:
    start: datetime
    end: datetime
    kwh: Optional[float]
    price: Optional[float]        # EUR/kWh spot
    spot_cost: Optional[float]    # kwh * price (may be negative)
    addon_cost: Optional[float]   # variable per-kWh add-ons * kwh
    vat: Optional[float]
    total: Optional[float]        # None when kwh or price missing
    energy_complete: bool
    reset: bool
    price_missing: bool
    energy_missing: bool

    @property
    def usable(self) -> bool:
        return self.total is not None


@dataclass
class PeriodSummary:
    label: str
    start: datetime
    end: datetime
    kwh: float = 0.0
    spot_cost: float = 0.0
    addon_cost: float = 0.0
    vat: float = 0.0
    fixed_cost: float = 0.0
    total: float = 0.0
    n_intervals: int = 0
    n_usable: int = 0
    n_price_missing: int = 0
    n_energy_missing: int = 0
    n_incomplete: int = 0
    n_reset: int = 0

    @property
    def completeness(self) -> float:
        """Fraction of intervals with a usable (priced) cost. 1.0 == perfect."""
        return (self.n_usable / self.n_intervals) if self.n_intervals else 0.0

    @property
    def has_gaps(self) -> bool:
        return self.n_usable < self.n_intervals


# --------------------------------------------------------------------------- #
# Grid + interval energy from a cumulative counter
# --------------------------------------------------------------------------- #
def build_grid(start: datetime, end: datetime, step: timedelta) -> list[tuple[datetime, datetime]]:
    """Half-open [start,end) cells of width ``step``, computed in UTC."""
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("grid bounds must be tz-aware")
    start = start.astimezone(UTC)
    end = end.astimezone(UTC)
    cells: list[tuple[datetime, datetime]] = []
    t = start
    while t < end:
        nt = min(t + step, end)
        cells.append((t, nt))
        t = nt
    return cells


def interval_energy(readings: Sequence[Reading], start: datetime, end: datetime) -> EnergyInterval:
    """Counter delta over [start, end) from ``total_increasing`` readings.

    Rules:
      * Anchor = last reading at or before ``start`` (carry-forward). Combined
        with readings inside the interval it defines the delta.
      * ``value is None`` (unavailable) breaks continuity: the interval is marked
        incomplete and the known value is dropped. We never bridge a gap with 0.
      * A drop in value is a counter reset: the post-reset value is added and the
        interval is flagged ``reset``.
      * If no known value applies to the interval at all -> kwh is None (missing),
        NOT zero.
    """
    start = start.astimezone(UTC)
    end = end.astimezone(UTC)
    rs = sorted(readings, key=lambda r: r.ts)

    anchor: Optional[Reading] = None
    for r in rs:
        if r.ts <= start:
            anchor = r
        else:
            break
    window = [r for r in rs if start < r.ts <= end]

    seq: list[Reading] = []
    if anchor is not None:
        seq.append(anchor)
    seq.extend(window)
    if not seq:
        return EnergyInterval(start, end, None, complete=False, reset=False)

    complete = True
    reset = False
    kwh = 0.0
    prev: Optional[float] = None
    have_any = False
    for r in seq:
        if r.value is None:  # unavailable => gap
            complete = False
            prev = None
            continue
        if prev is None:
            prev = r.value
            have_any = True
            continue
        diff = r.value - prev
        if diff < 0:  # reset
            reset = True
            kwh += r.value  # counter assumed restarted from 0
        else:
            kwh += diff
        prev = r.value

    if not have_any:
        return EnergyInterval(start, end, None, complete=False, reset=reset)
    return EnergyInterval(start, end, kwh, complete, reset)


def energy_series(
    readings: Sequence[Reading], grid: Sequence[tuple[datetime, datetime]]
) -> list[EnergyInterval]:
    return [interval_energy(readings, s, e) for (s, e) in grid]


# --------------------------------------------------------------------------- #
# Price alignment
# --------------------------------------------------------------------------- #
def price_for_interval(prices: Sequence[PricePoint], start: datetime, end: datetime) -> Optional[float]:
    """Price whose [start,end) window contains the interval's start instant."""
    start = start.astimezone(UTC)
    for p in prices:
        if p.start.astimezone(UTC) <= start < p.end.astimezone(UTC):
            return p.price
    return None


# --------------------------------------------------------------------------- #
# Cost per interval
# --------------------------------------------------------------------------- #
def cost_interval(
    energy: EnergyInterval, price: Optional[float], tariff: Tariff = SPOT_ONLY
) -> CostInterval:
    price_missing = price is None
    energy_missing = energy.kwh is None

    if price_missing or energy_missing:
        return CostInterval(
            start=energy.start,
            end=energy.end,
            kwh=energy.kwh,
            price=price,
            spot_cost=None,
            addon_cost=None,
            vat=None,
            total=None,  # NEVER substitute missing with 0
            energy_complete=energy.complete,
            reset=energy.reset,
            price_missing=price_missing,
            energy_missing=energy_missing,
        )

    kwh = float(energy.kwh)  # type: ignore[arg-type]
    spot = kwh * float(price)  # may be negative on negative prices
    addon = kwh * tariff.variable_addon_per_kwh(energy.start)
    subtotal = spot + addon
    vat = subtotal * tariff.vat_rate if tariff.vat_rate is not None else 0.0
    total = subtotal + vat
    return CostInterval(
        start=energy.start,
        end=energy.end,
        kwh=kwh,
        price=price,
        spot_cost=spot,
        addon_cost=addon,
        vat=vat,
        total=total,
        energy_complete=energy.complete,
        reset=energy.reset,
        price_missing=False,
        energy_missing=False,
    )


def cost_series(
    energies: Sequence[EnergyInterval],
    prices: Sequence[PricePoint],
    tariff: Tariff = SPOT_ONLY,
) -> list[CostInterval]:
    out: list[CostInterval] = []
    for e in energies:
        p = price_for_interval(prices, e.start, e.end)
        out.append(cost_interval(e, p, tariff))
    return out


def compute_device_costs(
    readings: Sequence[Reading],
    prices: Sequence[PricePoint],
    start: datetime,
    end: datetime,
    step: timedelta = timedelta(minutes=15),
    tariff: Tariff = SPOT_ONLY,
) -> list[CostInterval]:
    """End-to-end: cumulative readings + prices -> per-interval cost."""
    grid = build_grid(start, end, step)
    energies = energy_series(readings, grid)
    return cost_series(energies, prices, tariff)


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #
def summarize(
    intervals: Sequence[CostInterval],
    label: str,
    tariff: Tariff = SPOT_ONLY,
    n_days_for_fixed: Optional[float] = None,
) -> PeriodSummary:
    """Aggregate cost intervals. Missing intervals are excluded from the sums but
    counted in the data-quality fields (never summed as zero)."""
    if not intervals:
        now = datetime.now(UTC)
        return PeriodSummary(label, now, now)

    s = PeriodSummary(label, intervals[0].start, intervals[-1].end)
    for iv in intervals:
        s.n_intervals += 1
        if iv.price_missing:
            s.n_price_missing += 1
        if iv.energy_missing:
            s.n_energy_missing += 1
        if not iv.energy_complete:
            s.n_incomplete += 1
        if iv.reset:
            s.n_reset += 1
        if iv.usable:
            s.n_usable += 1
            s.kwh += iv.kwh or 0.0
            s.spot_cost += iv.spot_cost or 0.0
            s.addon_cost += iv.addon_cost or 0.0
            s.vat += iv.vat or 0.0

    if tariff.fixed_daily_eur is not None and n_days_for_fixed:
        s.fixed_cost = tariff.fixed_daily_eur * n_days_for_fixed

    s.total = s.spot_cost + s.addon_cost + s.vat + s.fixed_cost
    return s


# --------------------------------------------------------------------------- #
# Whole-home, comparison, reconciliation, unaccounted
# --------------------------------------------------------------------------- #
@dataclass
class HomeReport:
    label: str
    per_device: dict[str, PeriodSummary]
    total_kwh: float
    total_cost: float
    ranking: list[tuple[str, float]]                 # (device, cost) desc
    min_completeness: float
    # reconciliation vs a main/grid meter (None when no meter is available)
    main_meter_kwh: Optional[float] = None
    main_meter_cost: Optional[float] = None
    unaccounted_kwh: Optional[float] = None
    unaccounted_cost: Optional[float] = None
    unaccounted_pct: Optional[float] = None


def home_report(
    device_summaries: dict[str, PeriodSummary],
    label: str,
    main_meter: Optional[PeriodSummary] = None,
) -> HomeReport:
    total_kwh = sum(s.kwh for s in device_summaries.values())
    total_cost = sum(s.total for s in device_summaries.values())
    ranking = sorted(
        ((d, s.total) for d, s in device_summaries.items()),
        key=lambda kv: kv[1],
        reverse=True,
    )
    min_comp = min((s.completeness for s in device_summaries.values()), default=0.0)

    rep = HomeReport(
        label=label,
        per_device=device_summaries,
        total_kwh=total_kwh,
        total_cost=total_cost,
        ranking=ranking,
        min_completeness=min_comp,
    )
    if main_meter is not None:
        rep.main_meter_kwh = main_meter.kwh
        rep.main_meter_cost = main_meter.total
        rep.unaccounted_kwh = main_meter.kwh - total_kwh
        rep.unaccounted_cost = main_meter.total - total_cost
        rep.unaccounted_pct = (
            (rep.unaccounted_kwh / main_meter.kwh * 100.0) if main_meter.kwh else None
        )
    return rep


# --------------------------------------------------------------------------- #
# Calendar bucketing (DST-aware, local timezone)
# --------------------------------------------------------------------------- #
def _local_midnight(d: datetime) -> datetime:
    local = d.astimezone(LOCAL_TZ)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def day_bounds(day_local: datetime) -> tuple[datetime, datetime]:
    """UTC [start,end) spanning the given local calendar day. On DST days this is
    23h or 25h wide, computed by advancing one *calendar* day in local time."""
    start_local = _local_midnight(day_local)
    # add 1 day then re-normalise to local midnight to absorb DST shifts
    next_local = (start_local + timedelta(days=1, hours=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return start_local.astimezone(UTC), next_local.astimezone(UTC)


def today_bounds(now: Optional[datetime] = None) -> tuple[datetime, datetime]:
    now = now or datetime.now(UTC)
    return day_bounds(now)


def yesterday_bounds(now: Optional[datetime] = None) -> tuple[datetime, datetime]:
    now = now or datetime.now(UTC)
    y = now.astimezone(LOCAL_TZ) - timedelta(days=1)
    return day_bounds(y)


def month_bounds(any_day_local: datetime) -> tuple[datetime, datetime]:
    local = any_day_local.astimezone(LOCAL_TZ)
    start_local = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ndays = calendar.monthrange(start_local.year, start_local.month)[1]
    end_local = (start_local + timedelta(days=ndays, hours=1)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def this_month_bounds(now: Optional[datetime] = None) -> tuple[datetime, datetime]:
    now = now or datetime.now(UTC)
    return month_bounds(now)


def last_month_bounds(now: Optional[datetime] = None) -> tuple[datetime, datetime]:
    now = now or datetime.now(UTC)
    first_this = month_bounds(now)[0].astimezone(LOCAL_TZ)
    prev = first_this - timedelta(days=1)
    return month_bounds(prev)


def month_forecast(
    month_so_far: PeriodSummary, now: Optional[datetime] = None
) -> Optional[float]:
    """Naive linear run-rate projection of full-month cost.

    forecast = cost_so_far / elapsed_days * days_in_month

    This is a simple projection, NOT a price/weather model. Only defined when we
    have usable data. Returns None if nothing usable yet.
    """
    if month_so_far.n_usable == 0:
        return None
    now = (now or datetime.now(UTC)).astimezone(LOCAL_TZ)
    m_start = month_so_far.start.astimezone(LOCAL_TZ)
    days_in_month = calendar.monthrange(m_start.year, m_start.month)[1]
    elapsed = (now - m_start).total_seconds() / 86400.0
    if elapsed <= 0:
        return None
    daily_rate = month_so_far.total / elapsed
    return daily_rate * days_in_month


__all__ = [
    "Reading",
    "PricePoint",
    "Tariff",
    "SPOT_ONLY",
    "EnergyInterval",
    "CostInterval",
    "PeriodSummary",
    "HomeReport",
    "build_grid",
    "interval_energy",
    "energy_series",
    "price_for_interval",
    "cost_interval",
    "cost_series",
    "compute_device_costs",
    "summarize",
    "home_report",
    "day_bounds",
    "today_bounds",
    "yesterday_bounds",
    "month_bounds",
    "this_month_bounds",
    "last_month_bounds",
    "month_forecast",
    "LOCAL_TZ",
    "UTC",
]
