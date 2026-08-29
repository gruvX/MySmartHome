# Energy Shadow Ledger — Final Forensic Analysis

**Scope:** Full forensic analysis of the FROZEN shadow ledger (immutable evidence, read-only).
**Ledger:** `docs/audit/shadow_evidence/shadow_snapshots.frozen.jsonl`
**Machine-readable companion:** `docs/audit/energy_shadow_quality.json`
**Analyzed:** 2026-07-16 (Europe/Riga). Nothing fixed — the ledger is immutable evidence; all findings are reported, not remediated.

---

## 0. Integrity / chain of custody

| Metric | Value |
|--------|-------|
| sha256 (recomputed) | `8191d6ea544092bc521d4f4f9e2e8d3a8dfe8dde9f27cd7ea4359383193e54d2` |
| Matches CUSTODY.md | **YES** |
| Byte size | 142 041 bytes |
| File perms / owner | `444` (read-only) / root |
| Lines / records | 96 / 96 (all non-blank, all valid JSON) |
| JSON parse errors | 0 |
| Schema variants | 1 (all records `{context, energy_kwh, price, ts}`) |

The frozen copy is byte-identical to the custody record. No modification performed. HA access during analysis was **read-only** (REST history/logbook only) to cross-check restart/reload timing; no device or production state was touched, no secret printed.

---

## 1. Coverage summary

| | |
|---|---|
| **Window start** | `2026-07-15T18:46:59+03:00` |
| **Window end** | `2026-07-16T18:30:00+03:00` |
| **Span** | 23 h 43 m 01 s |
| **Timezone** | Europe/Riga, offset `+03:00` (EEST) throughout |
| **Expected intervals** (this rolling window) | **96** |
| **Actual records** | **96** |
| **Missing intervals** | **0** |
| **Duplicate records** | **0** |
| **Valid (clean) records** | **89** |
| **Coverage** | **100.0 %** |
| **Clean-record coverage** | **92.71 %** |

### How "expected" was computed for THIS window (not hardcoded 96)

The collector's **first** snapshot is an **off-grid seed** at `18:46:59` (collector's first run right after an HA restart — see §3), not aligned to a quarter-hour. Every subsequent snapshot is grid-aligned to `:00/:15/:30/:45`.

- First grid-aligned point after the seed: `2026-07-15T19:00:00+03:00`.
- Grid points from `19:00:00` (07-15) through `18:30:00` (07-16) inclusive, at 15-min cadence: `(23h30m / 15m) + 1 = 95`.
- Plus the 1 off-grid seed record ⇒ **expected = 96**.

Actual = 96 ⇒ **no missing intervals, no extras, no duplicates**. The seed→first-grid gap is a legitimate 13 m 01 s short interval (grid alignment), not a data gap.

---

## 2. Timezone / DST verdict

- Every `ts` carries offset **`+03:00`** = **EEST** (Eastern European Summer Time). `zoneinfo("Europe/Riga")` confirms the offset is `+03:00` (DST active) at **both** window endpoints.
- **DST verdict: 2026-07-16 is NOT a DST-change day in Europe/Riga — CONFIRMED.** Riga is in continuous summer time across the whole window; the next transition is autumn (`2026-10-25`, EEST→EET). Offset is constant end-to-end, so there is **no 23 h / 25 h day distortion** and no ambiguous/duplicated wall-clock hour inside the window.
- Because the window is a ~23.7 h *rolling* slice (not a calendar day), the "96 = normal full local day" figure is a coincidence, not a hardcode: the expected count was derived from the actual local timeline (§1).

---

## 3. Restart / reload cross-check (HA logs, read-only)

Cross-checked against HA logbook + state history:

- **HA restarted at `2026-07-15T15:12:01Z` = `18:12:01` local** ("stopped" `15:11:09Z` → "started" `15:12:01Z`, followed by the usual `homeassistant.start`-triggered automations). This is **~35 min BEFORE** the ledger window start. The collector's off-grid seed at `18:46:59` is its first post-restart run. `input_boolean.ha_startup_grace` and `binary_sensor.remote_ui` both key off the same restart.
- **No HA restart occurred *during* the ledger window** ⇒ no restart-induced ledger gap.
- The **EV `command_line` sensor** (`sensor.ev_charger_energy`) went `unavailable` for **sub-second blips** at `18:56:52Z` and `03:55:34Z` (command_line reload cycles). These fell **between** 15-min snapshots, so the ledger never captured them and no interval is missing. They do, however, correlate with the EV catch-up jump (§4).

**Verdict:** No restart/reload produced a coverage gap. The only lifecycle artifact visible in the ledger is the benign off-grid seed at window start.

---

## 4. Anomaly categories (with counts)

| Category | Count | Materiality |
|----------|------:|-------------|
| Missing intervals | 0 | — |
| Duplicate records / duplicate ts | 0 | — |
| Non-monotonic (out-of-order) ts | 0 | ts strictly increasing |
| Wrong-length intervals | 1 (the 13 m 01 s seed→grid alignment) | benign, expected |
| Off-quarter-hour timestamps | 1 (the `18:46:59` seed) | benign, expected |
| Corrupted JSON lines | 0 | — |
| Schema changes across records | 0 | single schema |
| Missing-price / stale-price | 0 | see §5 |
| Missing-energy (`unavailable`) | 1 | hydrophore, idx 6 |
| Counter-reset | 0 | no counter decreased |
| **Reconnect-jump (≥2 h stale catch-up)** | **6** | 1 material (EV), rest small/trivial |
| Coarse reporting cadence (~30 min, benign) | 42 intervals | NOT counted as anomaly (see below) |

### 4a. The single `unavailable` gap — hydrophore, idx 6 (`20:15`)
`sensor.zigbee_plug_2_total_energy` reported `avail:false / v:null` for exactly one snapshot, then recovered cleanly at idx 7 (`20:30`, `278.29`) with a continuous value (no jump). Consequence: **the two hydrophore consumption intervals straddling idx 6 cannot be priced** (Δ-kWh undefined). Correctly treated as missing — **never zero-filled**.

### 4b. Reconnect / catch-up jumps (6)
These are counters whose `updated` field was **frozen for hours** and then leapt in a single snapshot, so the accrued energy is mis-attributable to one interval's price:

| idx | ts local | device | Δ kWh | stale duration | cost materiality |
|----:|----------|--------|------:|----------------|------------------|
| 45 | 06:00 | **ev** | **+15.190** | ~8 h (~32 intervals) | **HIGH** — 15.19 kWh of overnight charging collapsed into one 15-min slot |
| 61 | 10:00 | boiler_ten | +0.376 | ~15.4 h | moderate |
| 47 | 06:30 | hydrophore | +0.150 | ~6.7 h | low |
| 57 | 09:00 | aquarium | +0.001 | ~12.5 h | trivial |
| 48 | 06:45 | recirc | +0.001 | ~8.5 h | trivial |
| 92 | 17:45 | recirc | +0.001 | ~8.4 h | trivial |

**EV is the standout.** `sensor.ev_charger_energy` held `882.8` from idx 0–44 (charger paused/free), then jumped to `897.99` at idx 45 (`06:00`). HA state history confirms the sensor's own value only changed at `02:56:52Z` — the +15.19 kWh reflects overnight charging that the coarse Tuya-cloud lifetime counter reported in one step. Pricing all 15.19 kWh at the 05:45→06:00 spot price would badly misprice a large block of EV energy. **This is the primary data-quality risk for interval-cost accounting.**

### 4c. Coarse reporting cadence (~30 min) — NOT an anomaly
42 intervals show a device (mostly `aquarium`, some `recirc`/`boiler_ten`) whose `updated` advanced ~30 min — i.e. the plug natively reports every ~2 intervals, so alternate snapshots repeat a value then step (+0.023 kWh typical for aquarium). This is **expected Tuya sensor granularity**, not a defect. It smears per-interval cost attribution slightly across the two intervals a reading covers, but introduces no error at hourly/daily aggregation. Deliberately **excluded** from the anomaly counts to avoid drowning the real signal (an earlier over-sensitive pass mislabeled 34 of these as reconnect-jumps).

---

## 5. Price integrity

- **Nord Pool is a 15-min product here.** `current` price changes each quarter; `current[i] == next[i-1]` holds for **all** 15-min steps (0 mismatches) — perfectly consistent rolling price series.
- **Stale-price: 0.** Max `current.updated` lag vs snapshot ts = **14 m 59 s** (i.e. always within the same 15-min quarter). No price was carried stale across a boundary.
- **Missing-price: 0.** All four price fields (`current/next/lowest/highest`) were `avail:true` with non-null `v` in every one of the 96 records.
- The three short "identical current price" runs (`0.014`, `0.02`, `0.02001`) are genuine consecutive market values (their `updated` timestamps advance normally) — not staleness.
- Prices span `0.012 … 0.26643 EUR/kWh`; no negatives in this window (would have been preserved, not clamped, per the cost model).

---

## 6. Per-status tally (per-record, statuses may overlap)

| Status | Records |
|--------|--------:|
| valid | 89 |
| reconnect-jump | 6 |
| missing-energy | 1 |
| unavailable | 1 |
| duplicate | 0 |
| gap-before | 0 |
| stale-price | 0 |
| missing-price | 0 |
| counter-reset | 0 |
| schema-error | 0 |

(89 records are clean; 7 distinct records carry ≥1 anomaly — idx 6 carries two statuses.)

---

## 7. File size & growth projection

- Current: **142 041 bytes / 96 records ≈ 1 480 bytes/record**.
- Projected append-only growth at 96 records/day: **≈ 139 KB/day ≈ 4.06 MB/30-day month ≈ 49.4 MB/year**.
- Manageable indefinitely, but for multi-year retention consider periodic rotation/compression (jsonl compresses well). No rotation is required for the shadow-validation window.

---

## 8. Readiness assessment

**Coverage & timekeeping: PASS.** 100 % interval coverage over a full ~24 h rolling window, strictly monotonic timestamps, single stable schema, zero corrupt/duplicate/missing intervals, zero counter resets, and a clean price series (no missing/stale price). Timezone is unambiguous EEST with no DST transition. The custody hash verifies.

**Blocking caveat before trusting shadow interval cost as ground truth:**

1. **EV coarse counter (HIGH).** `sensor.ev_charger_energy` is a slow, lifetime Tuya-cloud total that updates only every several hours and dumps hours of charging into a single interval (+15.19 kWh at idx 45). Interval-cost for EV from this sensor will be **systematically mispriced** whenever a stale block lands on a non-representative quarter. Recommend: attribute EV energy across the stale span (spread by time or by the interval prices that were in force during the `updated`→`updated` window) rather than to the single catch-up interval — or source EV energy from a finer sensor. **Do not treat EV interval cost from this ledger as exact.**
2. **One unavailable gap (hydrophore idx 6)** leaves two hydrophore intervals unpriceable — correctly surfaced as missing, must stay missing (never zero-filled).
3. **~30-min plug cadence** is acceptable for hourly/daily rollups but is not true 15-min resolution for aquarium/recirc.

**Overall:** The ledger is a **structurally sound, complete, tamper-evident** 24 h capture — suitable as evidence and for aggregate (hourly/daily/monthly) shadow cost validation. It is **not yet safe to promote to production cost-of-record for EV interval pricing** until the coarse-counter catch-up is handled. Consistent with the standing guidance not to switch production `cost_month_*` off the old model on the strength of a single 24 h shadow window.

---

*Companion machine-readable output: `docs/audit/energy_shadow_quality.json` (per-interval index/ts/status/notes + summary totals + coverage%). Analysis is read-only; the frozen ledger was not modified.*
