# Tests

Fast, hermetic tests for the MySmartHome repo. Nothing here touches the real
Home Assistant instance, the Elering price API, or the Tuya cloud — outbound
network calls are stubbed/blocked by default (see `conftest.py`).

## Running

```bash
# from the repo root
python3 -m pytest -q                 # all non-live tests
python3 -m pytest -q tests/test_contract.py
python3 -m pytest -q -m unit         # only the pure/hermetic tier
python3 -m pytest -q -m "not live"   # everything CI runs (the default anyway)
python3 -m pytest -q -m live         # opt in to live-device tests (needs devices)
```

If `pytest` is missing: `python3 -m pip install pytest`. On a box with no
system pytest (and no permission to install one globally), use a scratch venv:

```bash
python3 -m venv /tmp/venv && /tmp/venv/bin/pip install -q pytest
PYTHON=/tmp/venv/bin/python bash tools/run_checks.sh   # run_checks honours $PYTHON
/tmp/venv/bin/python -m pytest -q                       # or run pytest directly
```

Or run the full local check bundle (compile + secret scan + git diff --check +
inline-JS syntax + pytest):

```bash
bash tools/run_checks.sh
```

## Layout

| File | Purpose |
|------|---------|
| `conftest.py` | Shared fixtures + the network guard. Provides `fake_http`, `sample_prices`, `elering_response`, `ha_state`. Auto-skips `live` tests and blocks un-stubbed HTTP. |
| `test_contract.py` | Mini App frontend↔backend allow-list contract check (read-only parse of `custom_components/miniapp_auth/__init__.py` and `miniapp/smarthouse_v8.html`). |
| `test_smoke_imports.py` | Imports every pure-Python module (EV scripts, `ev_common`, `tools.energy_cost.*`); catches import-time errors `py_compile` misses. `ha_ssh` is imported only if `paramiko` is present. |
| `test_ev_common.py` | Unit tests for the shared EV scheduler (window selection, price parsing). |
| `test_ev_query_cache.py` | Unit tests for the EV query cache behaviour. |
| `test_energy_cost.py` | Unit tests for the interval-based energy-cost model (`tools/energy_cost`). |
| `test_miniapp_auth.py` | Unit tests for the `miniapp_auth` HA component (stubs the HA runtime + heavy imports). |

Feature agents own their per-module test files. This stream (CI finalize) owns
`conftest.py`, `test_smoke_imports.py`, `README.md`, the CI workflow, and
`tools/run_checks.sh`.

## Test tiers

Tests are separated by **marker**, not directory (declared in `pyproject.toml`
and `conftest.py`, enforced by `--strict-markers`):

- `unit` — pure/hermetic; no network, no devices. The default bulk.
- `integration` — exercises multiple modules together, still hermetic (stub
  HTTP with `fake_http`). Safe in CI.
- `live` — hits a real device/API (HA, Elering, Tuya). **Deselected by default**
  via `conftest.py`; run with `-m live`. **Never runs in CI** (CI has no
  secrets/devices).

Unmarked tests behave as `unit`. Mark a test only when it differs from that
default (`@pytest.mark.integration`, `@pytest.mark.live`).

## Conventions

- **No live calls in unit/integration tests.** Use the `fake_http` fixture to
  stub responses. Any un-stubbed `urllib`/`requests` call raises with a clear
  message. Genuinely device-dependent tests must be marked `@pytest.mark.live`.
- **No secrets required.** Tests must pass on a bare checkout with no tokens.
  CI installs only `pytest` — no project/runtime deps.
- **Read-only parsing.** The contract test parses source files; it never edits
  them. If the allow-list isn't finalized yet, it skips (unparseable) or
  reports drift as `xfail` rather than breaking the build.

## Fixtures quick reference

```python
def test_prices_have_cheap_window(sample_prices):
    assert min(sample_prices) < 0.04

def test_reads_elering(fake_http, elering_response):
    fake_http.route("elering.ee", elering_response)
    # ... call code that fetches Elering; it receives the canned JSON ...

def test_state_shape(ha_state):
    s = ha_state("sensor.nord_pool_lv_current_price", "0.048")
    assert s["entity_id"].startswith("sensor.")
```
