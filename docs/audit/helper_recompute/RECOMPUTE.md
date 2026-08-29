# Cost-accumulator recompute — provably-wrong accruals only

**Date:** 2026-07-16 (Europe/Riga) · **Method:** READ-ONLY (HA REST `/api/states`,
WebSocket `recorder/statistics_during_period`). No HA writes, no devices touched.
**Frozen inputs:** `before_values.json` (this dir), recorder statistics for
`sensor.zigbee_plug_2_total_energy` and `sensor.nord_pool_lv_current_price`.

Root cause: `docs/audit/HYDROPHORE_ENERGY_INVESTIGATION.md`. The 00:01 snapshot
(automation `1778700001002`) coerced an `unavailable` reading to `0` via `| float(0)`;
the 23:58 accrual (`1785000001001`) then billed `total − 0` = the device's whole
lifetime meter as one day. Only the **hydrophore** (`cost_month_gidro`) has the
lifetime-scale signature.

---

## Pricing method — kept IDENTICAL to production (no interval-model switch)

Production accrual prices each day as:
`day_kWh × avg`, where `avg = (nord_pool_lowest + nord_pool_highest) / 2` — the day's
price midpoint captured at 23:58.

Recompute reproduces this exactly, per calendar day:

* `day_kWh` = daily delta of the recorder **`sum`** for
  `sensor.zigbee_plug_2_total_energy` (clean, monotonic, 0 resets — see investigation §2).
* `mid_day` = `(min + max) / 2` of that day's `recorder/statistics_during_period`
  (period=day) for `sensor.nord_pool_lv_current_price`. Daily `min`/`max` of the live
  price sensor **are** the day's lowest/highest, so this is the same midpoint the
  production automation uses — just reconstructed per-day instead of one blended figure.
* `correct_cost_gidro = Σ_day (day_kWh × mid_day)`.

### Per-day arithmetic (July MTD)

| day | kWh | mid €/kWh | cost € |
|---|---|---|---|
| 2026-07-01 | 0.970 | 0.1568 | 0.1521 |
| 2026-07-02 | 0.600 | 0.1391 | 0.0835 |
| 2026-07-03 | 1.400 | 0.0584 | 0.0817 |
| 2026-07-04 | 0.520 | 0.0655 | 0.0341 |
| 2026-07-05 | 2.530 | 0.0604 | 0.1527 |
| 2026-07-06 | 2.490 | 0.0740 | 0.1842 |
| 2026-07-07 | 0.890 | 0.0788 | 0.0701 |
| 2026-07-08 | 1.150 | 0.0666 | 0.0766 |
| 2026-07-09 | 2.070 | 0.1196 | 0.2475 |
| 2026-07-10 | 2.860 | 0.1108 | 0.3169 |
| 2026-07-11 | 1.950 | 0.0827 | 0.1613 |
| 2026-07-12 | 2.140 | 0.0756 | 0.1618 |
| 2026-07-13 | 2.530 | 0.1043 | 0.2638 |
| 2026-07-14 | 2.970 | 0.0971 | 0.2884 |
| 2026-07-15 | 3.290 | 0.1337 | 0.4399 |
| 2026-07-16 | 0.480 | 0.0922 | 0.0443 |
| **MTD** | **28.84 kWh** | — | **€2.76** |

Cross-check: gidro recorder `state` 251.24 (07-01) → 279.11 (now) = **27.87 kWh** device
delta; the `sum`-delta MTD is 28.84 kWh (includes 07-01's full day). Priced at the July
daily-midpoint average of **0.0947 €/kWh** this is €2.6–2.8 — matching the €3.5–4
order-of-magnitude estimate in the investigation, now computed exactly. The €42.29
accumulator equals ≈ the lifetime meter (≈282 kWh) priced once → one bad-snapshot day.

---

## Correction table (only provably-wrong helpers)

| helper | old value | correction | new value | BASIS (evidence) |
|---|---|---|---|---|
| `input_number.cost_month_gidro` | 42.29 | −39.53 | **2.76** | Per-day recompute above, production pricing method, clean recorder `sum` (0 resets, 0 jumps>1 kWh). Phantom = 42.29 − 2.76 = €39.53 ≈ lifetime meter priced once (one `unavailable`-at-00:01 day). |
| `input_number.cost_month_total` | 53.67 | −39.53 | **14.14** | Same delta as gidro (total is the sum of the per-device accruals; only gidro changed). 53.67 − 39.53 = 14.14. |

### Helpers left UNTOUCHED — no provable phantom

Applied the same "lifetime-scale overcount" test to every accumulator
(real MTD kWh from recorder `sum` × July avg midpoint 0.0947 €/kWh vs. the live
`cost_month_*`). A phantom shows as `cost_month` **far above** real cost; none do:

| helper | cost_month € | real MTD kWh | est € (kWh×0.0947) | verdict |
|---|---|---|---|---|
| `cost_month_boiler` | 5.98 | 136.09 | 12.89 | ≤ estimate → no phantom (if anything under-counts). Leave. |
| `cost_month_kalarifer` | 0.33 | 8.01 | 0.76 | ≤ estimate → no phantom. Leave. |
| `cost_month_akv` | 0.30 | 7.82 | 0.74 | ≤ estimate → no phantom. Leave. |
| `cost_month_chep` | 0.30 | 7.56 | 0.72 | ≤ estimate → no phantom. Leave. |
| `cost_month_ev` | 4.46 | 74.45 | 7.05 | ≤ estimate → no phantom. `midnight_ev_energy` = 882.8 (not 0) confirms no bad snapshot pending. Leave. |

The `midnight_*` snapshot helpers are **not** corrected: they are re-derived by the
snapshot automation nightly. Current values are all sane (gidro 278.63 ≈ live 279.11;
none is a stale 0 that would fire tonight). The snapshot **patch** prevents the next
occurrence; no snapshot rewrite is required now.

> Note (out of scope): boiler & EV `cost_month` are *below* the kWh estimate — the
> mirror failure (sensor `unavailable` at the 23:58 accrual → that day skipped) causes
> mild **under**-counting. That is not "provably wrong" per-euro without a full per-day
> reconstruction and is left untouched. The interval model (`tools/energy_cost/`) is the
> real fix and is tracked separately (energy shadow window).

---

## Exact HA service calls for the correction (DO NOT EXECUTE — for orchestrator review)

Two `input_number.set_value` calls, after owner R2 approval:

```yaml
# 1) Rebase hydrophore month cost to the recomputed real value
service: input_number.set_value
target:
  entity_id: input_number.cost_month_gidro
data:
  value: 2.76

# 2) Reduce the month total by the identical delta (−39.53)
service: input_number.set_value
target:
  entity_id: input_number.cost_month_total
data:
  value: 14.14
```

REST equivalent (read-only reference, not executed):

```
POST /api/services/input_number/set_value   {"entity_id":"input_number.cost_month_gidro","value":2.76}
POST /api/services/input_number/set_value   {"entity_id":"input_number.cost_month_total","value":14.14}
```

After the corrections, re-read both helpers to confirm they equal 2.76 and 14.14.
Rollback values in `ROLLBACK.md`.
