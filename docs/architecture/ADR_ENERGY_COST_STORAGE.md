# ADR: Storage for the Production Interval-Cost Accumulator

- **Status:** PROPOSED — design only. **Nothing in this ADR is deployed.** Production
  `cost_month_*` helpers and automation `1785000001001` are **NOT touched**; the owner
  decides the switch later (see §11 Phased rollout).
- **Date:** 2026-07-16 (Europe/Riga)
- **Author:** production-cost-architecture-agent
- **Scope:** Choose and specify the persistent store for a per-15-min electricity-cost
  ledger that prices each interval at the Nord Pool price in force during it
  (`interval_cost = interval_kWh × price_of_that_interval`), accumulated forward so
  long-term monthly totals survive the recorder's ~10-day purge cliff.
- **Supersedes / builds on:** `docs/audit/ENERGY_COST_MODEL.md` (§2.4 "accumulate going
  forward", §6 recommendations), `tools/energy_cost/{model,ha_source,shadow_qa}.py`
  (pure model + read-only HA source + shadow QA — all reused unchanged).
- **Evidence baseline:** `docs/audit/shadow_evidence/shadow_snapshots.frozen.jsonl`
  (96 records, sha256 `8191d6ea…3e54d2`, ~23h43m window, 8 devices:
  `ev, boiler_ten, towel, aquarium, recirc, hydrophore, bed_backlight, tv`). **Frozen
  evidence is never mutated** by anything in this design — it is read-only input to QA.

---

## 1. Context and problem

### 1.1 The bug being replaced (context only — do not change yet)

Production automation `1785000001001` accrues daily cost as:

```
avg   = (nord_pool_lv_lowest_price + nord_pool_lv_highest_price) / 2
d_dev = max(total_energy_now − midnight_snapshot, 0)
cost += d_dev × avg     # → cost_month_* input_number helpers
```

The multiplier is the midpoint of the day's cheapest and most-expensive quarter — a
number almost never in force when a device actually ran. A boiler that heats only in the
cheapest quarters is billed at the midpoint; an EV charged at the evening peak is billed
at the same midpoint. `tools/energy_cost/model.py` already implements the correct rule:
`period_cost = Σ (interval_kWh × price_of_that_interval)`. What is missing is a
**durable, transactional place to accumulate those interval costs forward**, because:

### 1.2 The retention cliff (confirmed in ENERGY_COST_MODEL.md §2)

| Data plane | Granularity | Retention | Exact per-interval cost? |
|---|---|---|---|
| States history (`/api/history/period`) | every change | ~10 days (`purge_keep_days` default) | **Yes** (exact 15-min price + counter deltas) |
| Short-term 5-min statistics | 5 min | ~10 days | Yes (price constant within a 15-min slot) |
| Long-term statistics | **hourly** | indefinite | **No** — price stored as hourly `mean`, consumption-agnostic; lossy |

So exact monthly totals **cannot be reconstructed after ~10 days** and **must be
accumulated going forward** into a store we own. This ADR chooses that store.

### 1.3 Requirements this store must satisfy

Functional — must be able to answer, per-device and total:
today, yesterday, current month, last month, **total confirmed** cost,
**incomplete total** (cost of intervals that had gaps), and **coverage %**
(usable intervals ÷ expected intervals).

Cost must stay decomposed into **separate additive components** and never smear the
fixed monthly charge across devices as spot cost:
`spot_energy | supplier_margin | distribution_variable | vat | fixed_monthly`.

Integrity — every one of these is a hard requirement addressed below:
per-interval rows; store **raw delta + accepted delta + price + spot cost + quality**;
**idempotent** (re-running an interval never double-counts); **atomic write**;
**file lock**; **restart recovery**; **catch-up** for a missed interval *only when
source data suffices*; **do not recompute a confirmed interval when the current price
merely changes**; **versioned schema**; **backup + rotation**; **bounded growth**;
**audit trail of excluded deltas**; **never mutate raw evidence**.

---

## 2. Decision

**Use a local, transactional SQLite database** (`/config/energy_cost/cost_ledger.db`,
WAL mode) as the system of record for the interval-cost ledger, written by a nightly
read-only-source accumulator job. Publish rollups to Home Assistant as **template/REST
sensors** with correct `device_class: monetary`, `state_class: total_increasing` (for
running accumulators) / `total` (for closed-period totals), `unit_of_measurement: EUR`.
Keep the whole thing **parallel to and independent of** the existing `cost_month_*`
helpers — this is a shadow production ledger the owner can promote later.

SQLite is chosen over JSONL, HA `input_number` helpers, `utility_meter`, and long-term
statistics because it is the only option that natively gives us **atomic transactions,
a real UNIQUE constraint for idempotency, bounded growth with indexed queries, and a
migration path** — exactly the integrity guarantees in §1.3 — in a single-writer,
low-volume workload (≈ 8 devices × 96 intervals/day ≈ 768 rows/day ≈ 280k rows/year,
trivial for SQLite).

---

## 3. Options considered (ADR comparison)

| Option | Idempotency | Atomicity | Concurrency / lock | Query power (today/month/coverage) | Bounded growth | Migration | Component separation | Verdict |
|---|---|---|---|---|---|---|---|---|
| **A. JSONL append-only** | Manual (must scan/dedupe on read); duplicate lines easy after a retry | Append is ~atomic per line but multi-row "confirm interval" is not; torn writes possible | Advisory `flock` only; no transaction | O(n) full-file scan every query; no index | **Unbounded** — grows forever; rotation is bolt-on | Schema drift handled ad-hoc per line | Possible (nested JSON) but no enforcement | **Rejected** as system-of-record (kept as export/QA format) |
| **B. SQLite (WAL)** | **Native** `UNIQUE(interval_start, device, schema_version)` + `INSERT OR IGNORE` / upsert-guard | **Native** ACID transactions | WAL: one writer + many readers; SQLite file lock + our own advisory lock | **Indexed** range/group-by; trivial today/yesterday/month/coverage | Bounded; VACUUM + archival of closed months | **`schema_version` table + numbered migrations** | Explicit columns per component | **CHOSEN** |
| **C. HA `input_number` helpers** (today's `cost_month_*`) | None — single scalar, last write wins; no interval memory | None (state write) | None | Cannot answer per-interval / coverage / yesterday at all | N/A (fixed set of scalars) | N/A | Would need one helper per component per device → helper explosion | **Rejected** (it is literally the thing we are replacing) |
| **D. `utility_meter`** | Meter cycle handles resets, but it meters a **source sensor**, so it can only integrate a *cost-rate sensor* we'd have to synthesize; no raw/accepted-delta or quality audit | Internal to HA recorder | HA-managed | Gives cycle totals (day/month) but no per-interval provenance, no excluded-delta audit, no coverage% | Bounded (recorder purge applies to its history!) | N/A | One meter per component per device | **Rejected** as system-of-record; **optional** as a cross-check sensor |
| **E. Long-term statistics** (external statistics via `recorder/import_statistics`) | Import is keyed by `(statistic_id, start)` → idempotent per hour | HA-managed | HA-managed | Indefinite retention; native Energy dashboard integration | Bounded, HA-managed | Handled by HA | **Hourly only** → cannot store 15-min provenance or per-interval quality; price already lossy at this grain | **Rejected** as system-of-record; **recommended as a downstream publication target** (§9.3) |

### 3.1 Why not just JSONL (the requirement asks to justify)

The current shadow collector already writes JSONL (`/config/shadow_snapshots.jsonl`) and
that is the right shape for **raw evidence capture** — but it is the wrong shape for an
**accumulator of record**. JSONL cannot enforce "one confirmed row per (interval,
device)"; idempotency becomes a read-time scan that must reconcile duplicates from
retried runs; and "bounded growth" and "don't-recompute-confirmed" both degrade into
manual bookkeeping. SQLite gives all of that as table constraints. We keep JSONL for two
narrow roles: (a) the untouched raw evidence ledger the collector already produces, and
(b) an exported, human-diffable dump of the SQLite ledger for QA (§8.3).

### 3.2 Why SQLite over long-term statistics as the store

Long-term statistics are the correct **publication** target (indefinite retention, Energy
dashboard) and we recommend feeding them (§9.3). They are the wrong **storage** because
they are hourly and carry no room for raw delta, accepted delta, per-component
breakdown, quality flags, or an excluded-delta audit trail. The ledger must retain
15-min provenance to be auditable and to let us re-derive rollups if a bug is found.

---

## 4. Data model / schema (SQLite DDL)

Database file: `/config/energy_cost/cost_ledger.db` (owned by the account the accumulator
runs as; `0640`). WAL mode (`PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;`).

```sql
-- ---------------------------------------------------------------------------
-- 4.1 Schema versioning. Single-row-per-migration audit of DDL applied.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_version (
    version      INTEGER PRIMARY KEY,       -- monotic migration number
    applied_at   TEXT    NOT NULL,          -- ISO-8601 UTC
    description  TEXT    NOT NULL
);
-- The CURRENT schema described here is version 1.

-- ---------------------------------------------------------------------------
-- 4.2 Tariff snapshots. The add-on rates used to price an interval are stored
--     BY REFERENCE so a later tariff change never silently rewrites history.
--     A confirmed interval points at the tariff row that was in force.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tariff (
    tariff_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    valid_from_utc           TEXT    NOT NULL,   -- inclusive
    valid_to_utc             TEXT,               -- NULL = open-ended (current)
    -- all EUR/kWh, owner-provided; NULL = not configured (spot-only for that part)
    supplier_margin_eur_kwh  REAL,
    distribution_day_eur_kwh REAL,
    distribution_night_eur_kwh REAL,
    night_start_hour         INTEGER DEFAULT 23,
    night_end_hour           INTEGER DEFAULT 7,
    excise_eur_kwh           REAL,
    renewables_oik_eur_kwh   REAL,
    vat_rate                 REAL,               -- e.g. 0.21
    fixed_monthly_eur        REAL,               -- standing charge PER MONTH (see 4.5)
    source_note              TEXT NOT NULL,      -- e.g. "owner contract 2026-07, Sadales tikls S-1"
    created_at               TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- 4.3 THE LEDGER: one row per (interval, device). System of record.
--     Immutable once status='confirmed' (see idempotency §6).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS interval_cost (
    schema_version    INTEGER NOT NULL DEFAULT 1,
    device            TEXT    NOT NULL,          -- 'ev','boiler_ten',... (stable keys)
    interval_start_utc TEXT   NOT NULL,          -- ISO-8601 UTC, grid-aligned :00/:15/:30/:45
    interval_end_utc  TEXT    NOT NULL,
    grid_seconds      INTEGER NOT NULL,          -- nominal 900; records off-grid width

    -- ---- ENERGY provenance (raw vs accepted) --------------------------------
    raw_delta_kwh     REAL,                      -- counter delta AS OBSERVED (may be <0 on reset, may be huge on spike). NULL if unknown.
    accepted_delta_kwh REAL,                     -- delta actually banked after reset/spike/gap rules. NULL if not banked.
    reading_start_kwh REAL,                      -- cumulative counter at interval start (anchor)
    reading_end_kwh   REAL,                      -- cumulative counter at interval end

    -- ---- PRICE ---------------------------------------------------------------
    price_eur_kwh     REAL,                      -- Nord Pool spot in force for this interval. NULL if unknown.
    price_source      TEXT,                      -- 'states_history' | 'shadow_ledger' | 'stat_5min'
    price_locked_at   TEXT,                      -- when this interval's price was frozen (see §6.4)

    -- ---- COST COMPONENTS (kept SEPARATE, all EUR, all nullable) --------------
    spot_cost_eur         REAL,                  -- accepted_delta_kwh * price_eur_kwh
    supplier_margin_eur   REAL,                  -- accepted_delta_kwh * margin
    distribution_var_eur  REAL,                  -- accepted_delta_kwh * distribution (day/night aware)
    vat_eur               REAL,                  -- vat_rate * (spot+margin+distribution)
    -- NOTE: fixed_monthly is DELIBERATELY ABSENT here. It is a whole-home,
    --       time-based charge and is NEVER apportioned to a device or an
    --       interval as spot cost. It lives in fixed_charge (§4.5).
    total_variable_eur    REAL,                  -- spot+margin+distribution+vat (device-attributable)

    tariff_id         INTEGER REFERENCES tariff(tariff_id),

    -- ---- QUALITY / status ----------------------------------------------------
    quality           TEXT    NOT NULL,          -- 'A'|'B'|'C'|'D'|'E' (see §4.4)
    status            TEXT    NOT NULL,          -- 'confirmed' | 'incomplete' | 'excluded'
    reset_detected    INTEGER NOT NULL DEFAULT 0,
    energy_complete   INTEGER NOT NULL DEFAULT 1,

    -- ---- AUDIT ---------------------------------------------------------------
    computed_at       TEXT    NOT NULL,          -- when this row was written
    computed_run_id   TEXT    NOT NULL,          -- accumulator run uuid (traceability)
    source_hash       TEXT,                      -- hash of the input readings+price for this row

    PRIMARY KEY (device, interval_start_utc, schema_version)
);

CREATE INDEX IF NOT EXISTS ix_ic_start   ON interval_cost(interval_start_utc);
CREATE INDEX IF NOT EXISTS ix_ic_dev_st  ON interval_cost(device, interval_start_utc);
CREATE INDEX IF NOT EXISTS ix_ic_status  ON interval_cost(status);

-- ---------------------------------------------------------------------------
-- 4.4 EXCLUDED-DELTA AUDIT TRAIL. Every delta we refused to bank is recorded
--     here with the reason, so "why is coverage 97%?" is always answerable and
--     no consumption silently vanishes. This is APPEND-ONLY.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS excluded_delta (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    device            TEXT NOT NULL,
    interval_start_utc TEXT NOT NULL,
    raw_delta_kwh     REAL,                      -- what was observed (never discarded silently)
    reason            TEXT NOT NULL,             -- 'energy_unavailable' | 'price_missing' | 'counter_reset' | 'implausible_spike' | 'gap_in_readings' | 'off_grid_width'
    detail            TEXT,                      -- human-readable specifics
    quality           TEXT,                      -- flag letter at exclusion time
    computed_at       TEXT NOT NULL,
    computed_run_id   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_excl_start ON excluded_delta(interval_start_utc);

-- ---------------------------------------------------------------------------
-- 4.5 FIXED CHARGES. Time-based (per month/day) charges kept SEPARATE from
--     device spot cost. Applied at aggregation time to the PERIOD, never to a
--     device row. This is the guardrail against smearing standing charges.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fixed_charge (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    period_kind   TEXT NOT NULL,                 -- 'month' | 'day'
    period_key    TEXT NOT NULL,                 -- 'YYYY-MM' or 'YYYY-MM-DD' (local)
    amount_eur    REAL NOT NULL,
    tariff_id     INTEGER REFERENCES tariff(tariff_id),
    note          TEXT,
    computed_at   TEXT NOT NULL,
    UNIQUE(period_kind, period_key)              -- idempotent: one fixed charge per period
);

-- ---------------------------------------------------------------------------
-- 4.6 RUN LEDGER. One row per accumulator invocation — restart recovery,
--     catch-up bookkeeping, and audit of what each run covered.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS accumulator_run (
    run_id            TEXT PRIMARY KEY,          -- uuid4
    started_at        TEXT NOT NULL,
    finished_at       TEXT,
    window_start_utc  TEXT NOT NULL,             -- intervals this run attempted
    window_end_utc    TEXT NOT NULL,
    n_confirmed       INTEGER DEFAULT 0,
    n_incomplete      INTEGER DEFAULT 0,
    n_excluded        INTEGER DEFAULT 0,
    n_skipped_locked  INTEGER DEFAULT 0,         -- already-confirmed, not recomputed
    source_low_water  TEXT,                      -- oldest states-history ts available at run time
    status            TEXT NOT NULL,             -- 'ok' | 'partial' | 'error'
    note              TEXT
);
```

Quality flags reuse the model/`shadow_qa.py` vocabulary exactly:

| Flag | Meaning | `status` written |
|---|---|---|
| `A` | usable: energy complete, no reset, price present | `confirmed` |
| `B` | usable but interval width ≠ 15±1 min (off-grid) | `confirmed` |
| `C` | counter reset detected, cost still computed from post-reset value | `confirmed` |
| `D` | energy unavailable/missing or interval touched an `unavailable` reading | `incomplete` + `excluded_delta` row |
| `E` | Nord Pool price missing for the interval | `incomplete` + `excluded_delta` row |

`accepted_delta_kwh`, `spot_cost_eur`, and the component columns are **NULL** for
D/E rows — never 0. Missing is never banked as zero (invariant from `model.py`).

---

## 5. Cost decomposition (never smear the fixed charge)

For a confirmed interval with accepted delta `k` and spot price `p`, and the tariff row
in force:

```
spot_cost_eur        = k * p                              # may be negative (negative prices kept)
supplier_margin_eur  = k * margin                         # 0 if margin NULL
distribution_var_eur = k * distribution(day|night by interval-local hour)
subtotal             = spot + margin + distribution
vat_eur              = vat_rate * subtotal                # 0 if vat_rate NULL
total_variable_eur   = subtotal + vat_eur                 # this is the DEVICE-attributable cost
```

`fixed_monthly_eur` from the tariff is inserted **once per month** into `fixed_charge`
(`period_kind='month'`, `period_key='YYYY-MM'`) at first accrual of that month. It is a
whole-home line item. Period totals are:

```
period_variable = Σ total_variable_eur over interval_cost rows in period   (per device or total)
period_full     = period_variable(total)  +  fixed_charge(period)          # ONLY at whole-home level
```

The fixed charge is **never** divided by device count, never divided by kWh, never added
to any `interval_cost` row. Per-device reports show variable-only; the whole-home report
adds the fixed line explicitly and labels it. When the tariff is all-default (`spot_only`
per `model.Tariff.spot_only`), only `spot_cost_eur` is populated and reports are labelled
"spot energy only".

---

## 6. Integrity guarantees (how each requirement is met)

### 6.1 Idempotency — re-running an interval never double-counts

- PRIMARY KEY `(device, interval_start_utc, schema_version)` makes a second write for the
  same interval a **conflict, not a duplicate**.
- Write path is a guarded upsert:
  - If no row exists → `INSERT` (`confirmed` / `incomplete`).
  - If a row exists with `status='confirmed'` → **skip** (do not recompute; see §6.4),
    increment `accumulator_run.n_skipped_locked`.
  - If a row exists with `status='incomplete'` and the new computation is now `confirmed`
    (source data has since become available) → **upgrade** the row in one transaction and
    close the matching `excluded_delta` reason (append a resolving audit row; the original
    exclusion is never deleted).
- Because rollups are computed by `SUM()` over the ledger — **not** by incrementing a
  running scalar — re-running a day is inherently safe: the sum of a set is independent of
  how many times you recomputed its members.

### 6.2 Atomic write

- All rows for one accumulator run are written inside a single
  `BEGIN IMMEDIATE … COMMIT` transaction. A crash mid-run rolls back to the last COMMIT;
  no partial interval set is ever visible. WAL + `synchronous=NORMAL` gives durability at
  the last checkpoint with good performance for this low write rate.
- The published SQLite file is never edited in place by external tools; the accumulator is
  the sole writer.

### 6.3 File lock (single writer)

- Two layers. (a) SQLite's own file lock (WAL allows concurrent readers, serialises the
  writer). (b) An **advisory lock file** `/config/energy_cost/cost_ledger.lock` acquired
  with `fcntl.flock(LOCK_EX | LOCK_NB)` at process start; if the lock is held, the run
  exits early and logs "another accumulator running" (records a `partial`/skipped run).
  This prevents an overlapping cron + manual invocation from racing.

### 6.4 Do NOT recompute a confirmed interval when the price merely changes

- The Nord Pool spot price for a settled 15-min slot is final once the slot has passed.
  A confirmed row stores `price_eur_kwh` and `price_locked_at`. Later runs that see a
  changed *current* price for a **past, already-confirmed** interval **skip it** (§6.1) —
  the stored price is authoritative. Only `incomplete` rows (price was missing at
  compute time) are eligible to be re-priced, and only from settled history.
- A deliberate override (e.g. a corrected tariff, a discovered price bug) is an explicit
  admin action that bumps `schema_version` or writes a new tariff row and re-derives into
  a *new* row set — history is versioned, not mutated in place.

### 6.5 Restart recovery (after HA / host restart)

- The store is a file; nothing is held only in memory. On the next scheduled run the
  accumulator:
  1. Acquires the lock.
  2. Reads `MAX(interval_start_utc)` among `confirmed` rows = the high-water mark.
  3. Reads the oldest timestamp still in states history (`source_low_water`).
  4. Recomputes the window `[max(high_water, source_low_water) … now_floor_to_grid)` and
     upserts (confirmed intervals skipped, incompletes retried). Any downtime is filled
     as far back as source data allows (§6.6).
- WAL auto-recovers a torn write on open; `PRAGMA wal_checkpoint(TRUNCATE)` is run at end
  of each successful run to bound the WAL file.

### 6.6 Catch-up for a missed interval — only if source data suffices

- The accumulator determines, per missing interval, whether **exact** inputs exist:
  states history (or 5-min stats) covering both the price and the counter readings for
  that interval. This is only true within the recorder's ~10-day window.
- If inputs exist → compute and confirm (back-fill).
- If inputs are **gone** (older than retention, or a genuine gap) → write an `incomplete`
  row + an `excluded_delta` row with reason `gap_in_readings`/`price_missing`; the
  interval is counted against **coverage %** and its cost lands in **incomplete total**,
  never in **confirmed total**, and never as 0. No estimation is invented.

### 6.7 Never mutate raw evidence

- The accumulator's **only** inputs are (a) HA read-only planes via
  `tools/energy_cost/ha_source.py` (states history / statistics — no service calls) and
  (b) optionally the frozen shadow ledger for QA. Neither is written. The live shadow
  collector JSONL and `docs/audit/shadow_evidence/*.frozen.jsonl` are read-only inputs;
  this design adds no code that opens them for writing.

### 6.8 Versioned schema — see §7.

---

## 7. Schema migrations

- `schema_version` table holds the applied migration numbers. Current DDL = **version 1**.
- Migrations are numbered SQL files under `tools/energy_cost/migrations/NNN_*.sql`, applied
  in order inside a transaction; each records a `schema_version` row on success.
- Migration policy:
  - **Additive** changes (new nullable column, new index, new table) → in-place migration,
    ledger rows stay valid; bump version.
  - **Semantic** changes to how an interval is priced (new component, changed rounding)
    → do **not** overwrite historical rows. Bump `schema_version`; new rows carry the new
    version; old rows keep theirs. Rollups either read a single version or explicitly
    reconcile — the PK includes `schema_version` precisely so both can coexist.
- On startup the accumulator runs `PRAGMA user_version` / checks `schema_version` and
  applies any pending migration **before** writing.

---

## 8. Backup, rotation, bounded growth

### 8.1 Backup

- Before each run, if the DB changed since the last backup, create a **consistent** copy
  with the SQLite backup API / `VACUUM INTO '/config/energy_cost/backups/cost_ledger_YYYYMMDD.db'`
  (safe on a live WAL DB; not a file `cp`).
- Retain daily backups 14 days, weekly 8 weeks, monthly 12 months (tiered rotation);
  prune older. Backups live under `/config/energy_cost/backups/` and are included in HA's
  normal snapshot of `/config` for off-box durability.
- A monthly integrity check: `PRAGMA integrity_check` + a checksum recorded to a small
  `docs/audit/` note (CUSTODY-style), so corruption is caught early.

### 8.2 Bounded growth

- Volume is ≈ 768 rows/day (8 devices × 96) ≈ 280k rows/year — a few tens of MB/year,
  fully indexed; no action strictly required for years.
- Still, closed months older than **13 months** are **archived**: their `interval_cost`
  rows are exported to a compressed per-month file
  (`archive/interval_cost_YYYY-MM.jsonl.gz`) and a single immutable **month rollup** row
  is retained in a `month_rollup` summary table; the fine-grained rows are then deleted
  and the DB `VACUUM`ed. Confirmed period totals for archived months are served from the
  rollup table, so queries stay O(1) and the live DB stays small.
- `excluded_delta` and `accumulator_run` follow the same 13-month archive.

### 8.3 Export / QA dump

- A read-only exporter dumps the ledger (or a date range) to newline-delimited JSON for
  human diffing and for `shadow_qa.py`-style QA, reusing the existing flag vocabulary.
  This is the *only* JSONL the accumulator produces, and it is a derived artefact, never
  a source.

---

## 9. Home Assistant publication (sensors)

The ledger is the source of truth; HA sensors are a **read-only projection**. Nothing here
overwrites `cost_month_*`.

### 9.1 Mechanism

A small read-only publisher (or `command_line`/REST sensor set) exposes rollups the
accumulator writes to a tiny JSON at `/config/www/energy_cost/rollup.json` (or via a
lightweight local endpoint). Sensors read that JSON. No admin service calls needed beyond
the sensors' own polling.

### 9.2 Sensor attributes (correct classes/units)

| Sensor (proposed id) | state | `device_class` | `state_class` | `unit_of_measurement` | Notes |
|---|---|---|---|---|---|
| `sensor.cost2_total_confirmed_month` | month confirmed € (variable, all devices) | `monetary` | `total_increasing` | `EUR` | resets at month boundary → allowed for `total_increasing` |
| `sensor.cost2_total_confirmed_today` | today confirmed € | `monetary` | `total_increasing` | `EUR` | |
| `sensor.cost2_yesterday` | yesterday confirmed € | `monetary` | `total` | `EUR` | closed period |
| `sensor.cost2_last_month` | last month full € (variable + fixed) | `monetary` | `total` | `EUR` | closed period |
| `sensor.cost2_month_incomplete` | month **incomplete** € (cost sitting in gappy intervals) | `monetary` | `total` | `EUR` | surfaces uncertainty, never mixed into confirmed |
| `sensor.cost2_month_coverage_pct` | usable ÷ expected intervals this month | — (`measurement`) | `measurement` | `%` | data-quality gauge |
| `sensor.cost2_dev_<device>_month` | per-device month € (variable only) | `monetary` | `total_increasing` | `EUR` | one per device key |
| `sensor.cost2_fixed_month` | month fixed/standing charge € | `monetary` | `total` | `EUR` | published as its OWN line, not folded into device sensors |

Attributes on the totals carry the component breakdown
(`spot_eur, margin_eur, distribution_eur, vat_eur, fixed_eur`), `coverage_pct`,
`n_confirmed`, `n_incomplete`, `spot_only` (bool), and `as_of` so the UI can show
provenance. The `cost2_` prefix keeps them unmistakably distinct from `cost_month_*`.

### 9.3 Optional downstream: long-term statistics

To get indefinite retention + native Energy-dashboard cost lines, the accumulator can
additionally push **external statistics** via `recorder/import_statistics` (idempotent per
hour, HA-managed retention) as a *publication* of confirmed hourly cost sums. This is
optional, additive, and still not a replacement for the SQLite ledger (which keeps 15-min
provenance the statistics cannot).

### 9.4 Optional cross-check: `utility_meter`

A `utility_meter` on a synthesized cost-rate sensor can run in parallel purely as an
independent sanity cross-check against the ledger's monthly total. Advisory only.

---

## 10. Query recipes (proves the required questions are answerable)

```sql
-- Today confirmed, per device (local day → precomputed UTC bounds from model.day_bounds)
SELECT device, ROUND(SUM(total_variable_eur),4) AS eur
FROM interval_cost
WHERE status='confirmed' AND interval_start_utc >= :day_start AND interval_start_utc < :day_end
GROUP BY device;

-- Total confirmed vs incomplete this month (never mixed)
SELECT status, ROUND(SUM(total_variable_eur),4)
FROM interval_cost
WHERE interval_start_utc >= :m_start AND interval_start_utc < :m_end
GROUP BY status;                       -- 'confirmed' row = confirmed total; 'incomplete' row = incomplete total

-- Coverage % this month
SELECT 100.0 * SUM(status='confirmed') / COUNT(*) AS coverage_pct
FROM interval_cost
WHERE interval_start_utc >= :m_start AND interval_start_utc < :m_end;

-- Whole-home month full cost = variable + fixed (fixed added ONCE, here, not per device)
SELECT (SELECT SUM(total_variable_eur) FROM interval_cost
        WHERE status='confirmed' AND interval_start_utc>=:m_start AND interval_start_utc<:m_end)
     + (SELECT COALESCE(amount_eur,0) FROM fixed_charge
        WHERE period_kind='month' AND period_key=:month_key) AS full_month_eur;

-- Excluded-delta audit for a day (why coverage < 100%)
SELECT device, interval_start_utc, raw_delta_kwh, reason, detail
FROM excluded_delta WHERE interval_start_utc >= :day_start AND interval_start_utc < :day_end
ORDER BY interval_start_utc;
```

`today / yesterday / this_month / last_month` UTC bounds come straight from
`model.today_bounds / yesterday_bounds / this_month_bounds / last_month_bounds`
(DST-aware, already implemented and tested).

---

## 11. Phased rollout (production `cost_month_*` untouched)

Each phase is reversible and gated on owner approval per `CLAUDE.md` risk rules. **No
phase changes automation `1785000001001` or the `cost_month_*` helpers until Phase 5,
which is the owner's explicit switch.**

| Phase | What | Risk | Touches prod cost? |
|---|---|---|---|
| **0. This ADR** | Design accepted | R0 | No |
| **1. Local ledger build** | Implement SQLite store + accumulator + migrations, run **entirely off-box** against the **frozen** evidence ledger; unit-test idempotency/atomicity/lock/recovery | R0 (repo only) | No |
| **2. Shadow accumulate (read-only source)** | Run the accumulator on a schedule reading HA **read-only** planes, writing to `/config/energy_cost/cost_ledger.db`. Nothing published, nothing overwritten | R1 (writes a NEW file on HA; no services, no device, no existing state) | No |
| **3. Shadow sensors** | Publish `cost2_*` sensors (read-only projection). Compare `cost2_total_confirmed_month` vs the live `cost_month_total` on the tablet/Mini App side-by-side for ≥1 full month | R1 | No — parallel display |
| **4. Reconciliation review** | Owner reviews divergence (expected: midpoint model over/under-charges), coverage %, excluded-delta audit. Sign-off | R0 | No |
| **5. Owner switch (out of scope here)** | Only on explicit owner decision: point UI/reports at `cost2_*` and retire/rewrite automation `1785000001001`. Old helpers kept read-only for one month as fallback | R2 | **Yes — owner-gated** |

Rollback at any phase before 5 is: stop the accumulator, delete `/config/energy_cost/`
(no production state was ever modified).

---

## 12. Consequences

**Positive:** correct-by-construction interval cost; full provenance (raw vs accepted
delta, price, per-component cost, quality) auditable per interval; idempotent and
crash-safe; every required rollup (today/yesterday/month/last-month/per-device/confirmed/
incomplete/coverage) is a one-line indexed query; fixed charges structurally cannot be
smeared onto devices; the flawed production accumulator is left untouched until the owner
chooses to switch.

**Negative / costs:** a new dependency on a SQLite file on `/config` (mitigated by
backups + HA snapshots); the accumulator must run reliably nightly (mitigated by
catch-up + restart recovery); one more moving part to maintain (mitigated by reusing the
already-tested `model.py`).

**Neutral:** JSONL remains for raw evidence and exports; long-term statistics and
`utility_meter` remain available as optional downstream publication/cross-check, not as
the store.

---

## 13. Summary answers to the brief

- **Chosen store:** local **SQLite (WAL)** at `/config/energy_cost/cost_ledger.db`, one
  row per `(device, interval_start_utc, schema_version)`, plus `tariff`,
  `excluded_delta`, `fixed_charge`, `accumulator_run`, `schema_version` tables.
- **Rationale:** only option giving native ACID atomicity, a UNIQUE constraint for
  idempotency, indexed rollups, bounded growth with archival, and versioned migrations —
  in a tiny single-writer workload — while keeping cost components separate and never
  smearing the fixed charge. JSONL (unbounded, no constraints), `input_number` (the very
  thing being replaced), `utility_meter` (no provenance), and long-term statistics
  (hourly, lossy) are each unfit as the store and are relegated to evidence/export/
  publication/cross-check roles.
- **Idempotency:** PRIMARY KEY conflict → confirmed rows skipped, incompletes upgraded;
  rollups are `SUM()` over the set, so recomputation cannot double-count.
- **Atomicity:** one `BEGIN IMMEDIATE … COMMIT` per run on a WAL DB; crash rolls back.
- **Recovery:** file-based store + high-water-mark scan + bounded catch-up within source
  retention on the next run; WAL auto-recovers torn writes.
- **Not touching production:** entirely parallel `cost2_*` surface; `cost_month_*` and
  automation `1785000001001` remain unchanged until an explicit owner-gated Phase 5.
```
