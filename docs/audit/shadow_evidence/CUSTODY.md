# Chain of Custody — Energy Shadow Ledger Evidence Snapshot

**Purpose:** Immutable, forensic-grade snapshot of the energy shadow ledger for analysis.
**Created:** 2026-07-16 (Europe/Riga)
**Created by:** evidence-snapshot task (read-only + frozen copies only)

## Files

| Role | Path | Perms |
|------|------|-------|
| Live ledger (KEEPS GROWING — do NOT analyze) | `/config/shadow_snapshots.jsonl` (HA 192.168.1.45) | root, writable, appended by collector |
| Frozen copy on HA | `/config/backups/shadow_evidence_20260716/shadow_snapshots.frozen.jsonl` | `chmod 444`, root |
| Frozen copy in repo (ANALYZE THIS) | `docs/audit/shadow_evidence/shadow_snapshots.frozen.jsonl` | `chmod 444` |

## Integrity

| Metric | Value |
|--------|-------|
| **sha256 (live @ copy time)** | `8191d6ea544092bc521d4f4f9e2e8d3a8dfe8dde9f27cd7ea4359383193e54d2` |
| **sha256 (HA frozen)** | `8191d6ea544092bc521d4f4f9e2e8d3a8dfe8dde9f27cd7ea4359383193e54d2` |
| **sha256 (local repo frozen)** | `8191d6ea544092bc521d4f4f9e2e8d3a8dfe8dde9f27cd7ea4359383193e54d2` |
| **All three match** | YES ✅ |
| **Byte size** | 142041 bytes |
| **Line count** | 96 lines (all non-blank, all valid JSON) |

The live file and the frozen copy had identical sha256 and identical byte size (142041)
at the moment of `cp`, confirming a clean, consistent capture with no partial/torn write.

## Record window

| | |
|---|---|
| **First record timestamp** | `2026-07-15T18:46:59+03:00` |
| **Last record timestamp**  | `2026-07-16T18:30:00+03:00` |
| **Timezone seen in records** | `+03:00` (Europe/Riga, EEST) |
| **Span** | ~23h 43m |

## Schema

Every record is a single-line JSON object with keys:

```
["context", "energy_kwh", "price", "ts"]
```

- `ts` — ISO-8601 timestamp with `+03:00` offset
- `energy_kwh` — numeric
- `price` — numeric
- `context` — collector context label

Schema is identical for the first and last record. Head (first 5) and tail (last 5)
lines were parsed with `json.loads`: **0 corrupt lines** detected near head/tail.

## Custody rules for analysis agents

- The **live** ledger `/config/shadow_snapshots.jsonl` keeps growing — the shadow
  collector (automation `1789100001001` / `shell_command.shadow_energy_collect`) was
  **NOT stopped, paused, or modified**. It continues appending.
- Therefore ALL forensic analysis MUST use the **frozen** copy
  (`docs/audit/shadow_evidence/shadow_snapshots.frozen.jsonl`, sha256 above), NEVER
  the live file. Re-reading the live file will produce a different hash.
- The frozen copies are `chmod 444` (read-only). Do not modify them. If re-verification
  is needed, recompute sha256 and confirm it equals the value recorded here.
- No devices were touched. Operation was read-only except for creating the frozen copies.
