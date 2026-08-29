# Energy Cost Model — Interval-Based Accounting (Audit + Design)

**Author:** nordpool-cost-agent · **Date:** 2026-07-15 · **Scope:** read-only audit of HA
`192.168.1.45:8123` + a local, non-deployed prototype. No production edits, no reloads,
no service calls, no commits.

---

## 0. The one rule

```
interval_cost = interval_kWh × NordPool_price_of_that_interval
period_cost   = Σ interval_cost   (over all intervals in the period)
```

Consumption is priced at the price **in force while it happened**. We never use
`daily_kWh × daily_avg_price`, and we never pre-multiply anything by a single
representative price.

### What the system does today (the bug being replaced)

Automation `1785000001001` ("💶 Учёт стоимости (за день → месяц)") runs at 23:58 and does:

```jinja
avg    = (nord_pool_lv_lowest_price + nord_pool_lv_highest_price) / 2
d_dev  = max(total_energy_now − midnight_snapshot, 0)
cost  += d_dev × avg
```

This is **worse than a daily average**: `avg` is the midpoint of the day's *min* and
*max* price — a number that is almost never representative of when the device actually
ran. A boiler that heats only in the cheapest quarters is billed at the midpoint; an EV
charged during the evening peak is billed at the same midpoint. The error can be large in
either direction. This model replaces that with true per-interval accounting.

---

## 1. Confirmed facts about the live data (read-only investigation)

### 1.1 Nord Pool price — unit and interval

| Property | Confirmed value | Evidence |
|---|---|---|
| Integration | HA **core** Nord Pool (no custom component in `/config/custom_components`) | entity set `sensor.nord_pool_lv_*` + `binary_sensor.nord_pool_lv_tomorrow_price_available` |
| Price sensor | `sensor.nord_pool_lv_current_price` | state `0.02272` |
| **Unit** | **EUR/kWh** (already per-kWh, NOT EUR/MWh, NOT cents) | `unit_of_measurement: "EUR/kWh"` |
| **Market interval** | **15 minutes** | `lowest_price` attr `start=14:30:00 end=14:45:00`; price state history changes exactly on `:00 / :15 / :30 / :45` |
| `state_class` | `measurement` | attribute |
| Currency sensor | `sensor.nord_pool_lv_currency = EUR` | — |

Latvia moved to the 15-minute market resolution (EU-wide MTU change); the sensor and its
recorded history confirm 15-min slots on this box.

**No list attributes.** `sensor.nord_pool_lv_current_price` exposes only
`state_class, unit_of_measurement, friendly_name` — there is **no `today` / `raw_today` /
`tomorrow`** list attribute (CLAUDE.md's note is confirmed; the `state_attr(..., 'tomorrow')`
mention elsewhere in CLAUDE.md is **stale** for this integration). Per-slot prices must come
from the individual sensors or, for a full series, from the **recorder** (see §2).
Tomorrow availability is signalled by `binary_sensor.nord_pool_lv_tomorrow_price_available`
(currently `on`).

Companion price sensors: `current`, `next`, `previous` (all EUR/kWh, no list attrs),
`lowest_price` / `highest_price` (carry `start`/`end` of the slot), `last_updated`.

### 1.2 Energy sensors — cumulative counters

All per-device meters are `device_class: energy`, `unit: kWh`,
`state_class: total_increasing`:

| Device | Energy sensor | Note |
|---|---|---|
| Boiler | `sensor.boiler_total_energy` | plug offline-prone (weak WiFi zone) |
| Towel warmer (полотенцесушитель) | `sensor.terarium_total_energy` | |
| Aquarium | `sensor.akvarium_svet_total_energy` | |
| Turtle/recirc | `sensor.cherepakha_total_energy` | |
| Hydrophone | `sensor.zigbee_plug_2_total_energy` | **observed flapping to `unavailable` every few min** |
| EV charger | `sensor.ev_charger_energy` | command_line, updates only on change |

Real-world data-quality issues observed live in `sensor.zigbee_plug_2_total_energy`
history (3-hour window): repeated `available → unavailable → available` transitions. The
model must treat `unavailable` as *unknown*, not 0.

### 1.3 Timezone / DST

HA stores all timestamps in UTC (epoch-ms in statistics, ISO-UTC in states). Europe/Riga is
EET/EEST with DST: spring-forward day = 23 h, fall-back day = 25 h. All interval math is done
in **UTC**; calendar day/month buckets are computed in **Europe/Riga** so DST-length days are
handled (prototype tests assert 23 h / 24 h / 25 h days).

### 1.4 Negative / missing prices

Nord Pool prices can go negative (already common in the Baltics on windy low-demand hours).
Cost must be allowed to go negative and **must not be clamped**. Missing prices (integration
gap, or tomorrow not yet published) must be treated as *unknown* → that interval's cost is
`None` and is reported as incomplete, never summed as 0.

---

## 2. Where per-interval data actually lives (recorder audit)

There is **no `recorder:` key** in `configuration.yaml`, so HA defaults apply:
`purge_keep_days: 10`. Two data planes:

### 2.1 States history — exact, ~10-day retention

REST `GET /api/history/period/<start>?filter_entity_id=...`

- **Price:** every 15-min change of `sensor.nord_pool_lv_current_price` is recorded with
  its exact value → the **exact per-15-min price series** is available for ~10 days.
- **Energy:** raw counter readings (event-driven), including `unavailable` rows → per-15-min
  deltas reconstructable for ~10 days.

### 2.2 Long-term statistics — indefinite, but lossy for price

WebSocket `recorder/statistics_during_period`. Verified via `recorder/list_statistic_ids`:

| Statistic | `has_mean` | `has_sum` | Meaning |
|---|---|---|---|
| `sensor.nord_pool_lv_current_price` | **true** | false | hourly (and 5-min) **mean/min/max** price only |
| `sensor.*_total_energy`, `sensor.ev_charger_energy`, `sensor.boiler_total_energy` | false | **true** | hourly (and 5-min) **sum** (kWh delta) + `state` |

Granularities returned: `5minute`, `hour`, `day`, `month`. Retention: **hourly+ kept
indefinitely; 5-minute short-term kept ~10 days** (same window as states).

**Critical consequence for accuracy:**

- The price statistic stores **`mean`, not `sum`** (there is no such thing as a price sum),
  and long-term granularity is **hourly**. `hourly_mean_price` is *consumption-agnostic* — it
  is the plain average of the 4 quarter-prices, so `hourly_kWh × hourly_mean_price` is **an
  approximation**, not the exact sum of the 4 quarter costs (they diverge whenever
  consumption is unevenly distributed across the hour).
- **5-minute** statistics *do* reconstruct exact per-quarter cost, because the price is
  constant within each 15-min slot and three 5-min windows nest cleanly inside it — but 5-min
  stats only exist for ~10 days.

### 2.3 Can we compute correct per-interval cost **right now**?

- **Yes, exactly, for roughly the last 10 days** — from states history (exact 15-min price ×
  15-min counter deltas), or equivalently from 5-minute statistics.
- **No, not exactly, for anything older than ~10 days** — only hourly statistics survive, and
  the price side is hourly-mean. Best achievable retroactively for old periods is the hourly
  approximation `Σ hourly_kWh × hourly_mean_price` (still far better than the current
  min/max-midpoint method, but not exact).
- **`this-month` early in a fresh month is fine** (within the 10-day window); **`last-month`
  and the earlier part of a long month are already outside exact range.**

### 2.4 What is needed for correct long-term totals

Because fine-grained data is purged after 10 days, exact monthly cost **cannot be
reconstructed after the fact** — it must be **accumulated going forward**. Options (design
only; not implemented/deployed here):

1. **Accumulate per-interval cost daily** (recommended): a nightly read-only job pulls the
   last day's exact 15-min price × 15-min energy from states/5-min stats, computes
   `Σ interval_cost` per device, and adds it to persistent `cost_month_*` accumulators.
   Replaces the flawed midpoint automation with a correct-by-construction one. Runs each day
   well inside the 10-day window.
2. **Per-device cost sensors** via a template/`utility_meter`-style cost integral, or the
   `nordpool`/`ha-energy` "cost" pattern, so HA itself records a `total_increasing` **cost**
   statistic (kept indefinitely) alongside energy.
3. **Extend `recorder purge_keep_days`** (e.g. to 40) so `last-month` stays exactly
   reconstructable — costs DB size/IO; a helper for reconstruction, not a substitute for
   accumulation.

---

## 3. Model design

### 3.1 Data types (see `tools/energy_cost/model.py`)

- `Reading(ts, value)` — one cumulative counter observation (kWh). `value is None` ⇒
  `unavailable`/`unknown` (a **gap marker**, never 0).
- `PricePoint(start, end, price)` — price (EUR/kWh) valid over `[start, end)`; `price` may be
  `None` (unknown slot).
- `Tariff(...)` — **owner-provided** retail add-ons (see §4). Default = spot-only.
- `EnergyInterval` — per-cell `kwh` (or `None`), `complete`, `reset`.
- `CostInterval` — per-cell `kwh`, `price`, `spot_cost`, `addon_cost`, `vat`, `total`
  (`None` when price or energy missing), plus `price_missing` / `energy_missing` / `reset`
  flags.
- `PeriodSummary` — aggregated `kwh` / `spot_cost` / `addon_cost` / `vat` / `fixed_cost` /
  `total` **plus** data-quality counters (`n_intervals`, `n_usable`, `n_price_missing`,
  `n_energy_missing`, `n_incomplete`, `n_reset`) and a `completeness` ratio.
- `HomeReport` — whole-home rollup: per-device summaries, ranking, min-completeness, and
  (if a main meter is supplied) reconciliation + unaccounted metrics.

### 3.2 Per-interval energy from a `total_increasing` counter

For each grid cell `[t0, t1)`:

1. **Anchor** = last reading at/before `t0` (carry-forward). Together with readings inside the
   cell it defines the delta.
2. Walk the value sequence, summing **positive** diffs.
3. **Counter reset**: a drop in value ⇒ counter restarted; add the post-reset value and set
   `reset=True` (this is the utility-meter convention; the impossible negative jump is not
   subtracted).
4. **`unavailable` (None)** breaks continuity: mark `complete=False` and drop the running
   value. A gap is **never** bridged with 0.
5. **No known value applies at all** ⇒ `kwh = None` (missing), **not 0**.
6. **Available-but-idle** (a valid anchor, no new pulses) ⇒ `kwh = 0`, `complete=True` — this
   is a *real* measurement of zero consumption (recorder only writes on change), and is the
   only case where 0 is legitimate.

### 3.3 Price alignment

`price_for_interval` selects the `PricePoint` whose `[start, end)` contains the cell's start
instant. A missing slot returns `None` ⇒ interval flagged `price_missing`, cost `None`.

### 3.4 Cost per interval

```
spot_cost = kwh × price                       # may be negative
addon     = kwh × Σ(configured per-kWh add-ons)
subtotal  = spot_cost + addon
vat       = subtotal × vat_rate               # only if configured
total     = subtotal + vat
```

If **either** price or energy is missing ⇒ `total = None` (surfaced in data quality; never 0).
Spot and add-ons are tracked separately so the spot-energy component is always visible even
when negative.

### 3.5 Aggregation (never substitute missing with zero)

`summarize()` sums only **usable** intervals into `kwh`/costs, while counting missing/incomplete
intervals separately. `completeness = n_usable / n_intervals`. A period with gaps is explicitly
partial — the totals are "cost of the measured portion", and the gap count travels with it.

### 3.6 Periods, comparison, reconciliation, forecast

- **today / yesterday / this-month / last-month**: `day_bounds` / `month_bounds` compute
  UTC spans from Europe/Riga calendar boundaries (DST-safe).
- **Device comparison**: `HomeReport.ranking` — devices sorted by cost, descending.
- **Whole-home cost**: `Σ` device costs.
- **Sum-of-devices vs main-meter reconciliation**: `HomeReport` accepts an optional main-meter
  `PeriodSummary`. **There is currently no whole-home / grid meter entity in HA** (scan for
  `meter/grid/house/main/import/smart_meter` energy sensors returned nothing). So today
  whole-home cost = sum of the 7 metered plugs and **excludes all unmetered load** (general
  lighting, kitchen appliances, HVAC not on these plugs). Reconciliation + the
  **unaccounted-consumption** metric (`main_kWh − Σ device_kWh`, and its €/%) are only
  computable once the owner adds/identifies a main meter (e.g. a grid CT clamp or utility
  smart-meter feed). Until then `unaccounted_*` is `None` by design.
- **Month forecast**: `month_forecast` = simple linear run-rate
  (`cost_so_far / elapsed_days × days_in_month`). Explicitly a projection, not a price/weather
  model; `None` until there is usable data.

### 3.7 Data-quality / completeness

Every summary carries: total intervals, usable intervals, price-missing, energy-missing,
incomplete (gap-touched), reset count, and a completeness ratio. This makes "this number is
based on 88/96 quarters" visible rather than hidden.

---

## 4. Contractual add-ons — OWNER-PROVIDED, not invented

The Nord Pool spot price is only part of a Latvian electricity bill. The following are **not
known to this agent** and are therefore exposed as configurable `Tariff` parameters that
default to *not applied*. **No values are invented.** The owner must fill them from the actual
supplier contract + Sadales tīkls distribution tariff:

| Component | `Tariff` field | Unit | Notes |
|---|---|---|---|
| Supplier margin / trade markup | `supplier_margin_eur_per_kwh` | EUR/kWh | on top of spot |
| Distribution (Sadales tīkls) | `distribution_eur_per_kwh` | EUR/kWh | per-kWh part |
| — day/night split (optional) | `distribution_day/night_eur_per_kwh` + `night_start/end_hour` | EUR/kWh | if the owner is on a time-of-use distribution plan |
| Transmission (AST) | `transmission_eur_per_kwh` | EUR/kWh | often folded into distribution |
| Electricity excise | `excise_eur_per_kwh` | EUR/kWh | |
| Mandatory procurement / OIK | `renewables_oik_eur_per_kwh` | EUR/kWh | |
| VAT | `vat_rate` | fraction | LV standard 21% — but still owner-confirmed |
| Fixed/standing charge | `fixed_daily_eur` | EUR/day | applied at day aggregation |

With an all-default `Tariff` (`SPOT_ONLY`), results are the **spot-energy component only** and
are flagged `spot_only=True`. This is the honest default: it reports the market-price cost and
does not pretend to be a full bill.

---

## 5. Prototype & tests (local only — nothing deployed)

```
tools/energy_cost/
  __init__.py      public API re-exports
  model.py         pure-Python model (stdlib only: datetime, zoneinfo, dataclasses)
  ha_source.py     READ-ONLY HA adapter (states history + stats via stdlib WS); never writes
tests/test_energy_cost.py   27 unit tests, all mocked (no HA access)
```

`model.py` and `tests/` use **only the standard library**. `ha_source.py` reads secrets via
`project_secrets` (in-process; token never printed) and performs only GET/read WS queries.

### Test coverage (all pass)

- hourly grid & 15-min grid end-to-end;
- correct per-interval cost vs the naive daily/avg method (load-shift case where they differ);
- negative price not clamped;
- missing price ⇒ `None` cost, counted in data quality;
- missing/`unavailable` energy ⇒ `None`, never 0; available-but-idle ⇒ real 0;
- counter reset detection and propagation to the summary;
- DST spring-forward (23 h) / fall-back (25 h) / normal (24 h) day bounds; month & last-month
  bounds;
- tariff add-ons + VAT; fixed daily charge; spot-only flag;
- home report ranking, reconciliation, unaccounted metric, and its absence without a main
  meter;
- month linear-runrate forecast (and `None` without data).

### How to run

```bash
python3 -m py_compile tools/energy_cost/*.py tests/test_energy_cost.py
python3 -m pytest tests/test_energy_cost.py -q      # 27 passed
```

(Verified in a scratch venv: `27 passed`.)

---

## 6. Recommendations (design only — deployment is out of scope here)

1. **Replace** automation `1785000001001` with a correct-by-construction daily accumulator
   that sums exact 15-min `interval_kWh × interval_price` (data is in range each night).
2. Consider **per-device cost statistics** so HA records cost indefinitely (no 10-day cliff).
3. **Add a whole-home / grid meter** to unlock reconciliation + the unaccounted metric.
4. Optionally raise `recorder purge_keep_days` (e.g. 40) so `last-month` stays exactly
   reconstructable.
5. Have the owner supply the **Tariff** add-ons so reported figures become full-bill €, not
   spot-only.
```
