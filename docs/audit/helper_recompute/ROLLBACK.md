# Backup & Rollback — snapshot guard + cost recompute

Everything here is LOCAL/manual for the orchestrator. No step has been executed.

## What changes on deploy

1. **`/config/automations.yaml`** — snapshot automation `1778700001002` gets 7 guarded
   `value:` templates (`docs/audit/snapshot_guard.patch`). Additive: only the `float`
   fallback changes from `0` to the helper's own prior value.
2. **Two helpers** — `input_number.cost_month_gidro` → 2.76, `input_number.cost_month_total`
   → 14.14 (see `RECOMPUTE.md`).

## Backup BEFORE deploy (do these first)

### A. Backup automations.yaml (on HA, via SSH sudo)

```bash
# timestamped copy next to the original
sudo cp /config/automations.yaml /config/automations.yaml.bak_snapguard_2026-07-16
sudo ls -l /config/automations.yaml.bak_snapguard_2026-07-16
```

A read-only fetched copy of the pre-change file is also frozen locally this session at
the scratchpad path used to generate the diff; the authoritative on-box backup is the
`.bak_snapguard_2026-07-16` above.

### B. Helper before-values are frozen in `before_values.json`

Captured 2026-07-16T16:27:44Z. Relevant rollback targets:

| helper | before value |
|---|---|
| `input_number.cost_month_gidro` | 42.29 |
| `input_number.cost_month_total` | 53.67 |
| `input_number.midnight_gidro_energy` | 278.63 |
| (all other `midnight_*` / `cost_month_*`) | see `before_values.json` |

## Rollback — automations.yaml

Option 1 — restore the backup file:
```bash
sudo cp /config/automations.yaml.bak_snapguard_2026-07-16 /config/automations.yaml
# reload automations
```
Reload: `POST /api/services/automation/reload`.

Option 2 — reverse the patch in place:
```bash
sudo patch -R -p2 /config/automations.yaml < docs/audit/snapshot_guard.patch
```
(The patch header uses `a/config/automations.yaml`; `-p2` strips `a/config/`.)

## Rollback — helper values

If the corrections need to be undone, restore the before-values:

```yaml
service: input_number.set_value
target: {entity_id: input_number.cost_month_gidro}
data: {value: 42.29}
---
service: input_number.set_value
target: {entity_id: input_number.cost_month_total}
data: {value: 53.67}
```

REST reference:
```
POST /api/services/input_number/set_value {"entity_id":"input_number.cost_month_gidro","value":42.29}
POST /api/services/input_number/set_value {"entity_id":"input_number.cost_month_total","value":53.67}
```

## Verify after rollback

```
GET /api/states/input_number.cost_month_gidro   -> 42.29
GET /api/states/input_number.cost_month_total   -> 53.67
GET /api/states/automation.snimok_energii_polnoch  (or check config reloaded cleanly)
```

## Notes / ordering

* Deploy the **snapshot patch first** (prevents new phantoms), reload automations,
  confirm YAML parses on box, THEN apply the two helper corrections.
* The corrections are point-in-time. If a bad-snapshot night occurs *before* the patch
  is deployed, re-run the recompute (`stats.py`) before correcting.
* `input_number.set_value` is idempotent — re-applying a rollback value is safe.
