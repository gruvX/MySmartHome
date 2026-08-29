# Water-Leak Canary (fully isolated)

A self-contained, **mock-only** test that proves the leak → shutoff → read-back →
confirm chain of production automation **leak-v4** (`id 1748000001001`) without
ever touching a real device.

## Files
| File | Purpose |
|------|---------|
| `canary.yaml` | Mock helpers (`input_boolean.*` test/dummy) + the canary automation `test_water_canary_0001`. Mirrors leak-v4 logic incl. FIX C read-back, on mock entities. |
| `run_plan.md` | Exact install → drive (9 scenarios) → observe → teardown steps. Toggles only `test_*`/`dummy_*` helpers. |
| `verify_isolation.py` | Greps this package and asserts ZERO production references. Exits non-zero on any hit. Run before anything else. |

## Mock entity map (real role → mock)
| Real role (production, NOT used) | Mock (used here) |
|---|---|
| water valve switch | `input_boolean.dummy_valve` (on=OPEN, off=CLOSED) |
| hydrophore plug switch | `input_boolean.dummy_hydro` |
| moisture binary sensors | `input_boolean.test_moisture_1`, `test_moisture_2` |
| startup / tuya-reconnect grace flags | `input_boolean.test_grace` |
| siren + Telegram alert | `persistent_notification.create` (local, banner `🧪 ТЕСТ`) |
| leak/siren Telegram callbacks | `/noop_test` (no-op, unwired) |
| (n/a — new test knob) | `input_boolean.test_valve_fail` — forces the not-confirmed/CRITICAL path |

## Isolation guarantee
`verify_isolation.py` fails if the package contains any real production entity id,
any real moisture sensor, any siren entity/service, the security flag, Telegram
services/chat-id, or any real device service call (switch/climate/select/number).
This package references **NO production valve, moisture sensor, siren, or security
entity** — only `test_*` / `dummy_*` helpers.

## Order of operations
1. `python docs/audit/water_canary/verify_isolation.py` → must PASS.
2. Independent review of the package.
3. Follow `run_plan.md` (install → drive → observe → **teardown**).

> **Not deployed.** These are local files only; nothing here has been installed or run.
