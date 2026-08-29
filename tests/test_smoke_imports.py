"""Smoke test: the project's importable modules load without side effects.

`py_compile` (run in CI and run_checks.sh) only checks *syntax*. This test goes
one step further and actually *imports* each pure-Python module, which catches
import-time errors that compilation misses: circular imports, bad top-level
statements, references to names that don't exist, and — critically — any module
that would touch the network or a device just by being imported (the autouse
network guard in conftest.py would trip).

Modules that need heavy third-party deps not installed on a bare CI runner
(paramiko for ha_ssh) are imported behind ``importorskip`` so the suite stays
dependency-free and secretless. The Home Assistant custom component
(``custom_components/miniapp_auth``) is intentionally NOT imported here — it
requires the HA runtime and is covered by test_miniapp_auth.py, which stubs it.
"""
from __future__ import annotations

import importlib

import pytest

pytestmark = pytest.mark.unit


# Pure-stdlib modules: must import cleanly with no third-party deps and no
# network/device access at import time.
PURE_MODULES = [
    "project_secrets",
    "ev_common",
    "ev_best2h",
    "ev_day2h",
    "ev_night2h",
    "ev_query",
    "tools.energy_cost",
    "tools.energy_cost.model",
    "tools.energy_cost.ha_source",
    "tools.energy_cost.shadow_collect",
    "tools.energy_cost.accumulator",
]


@pytest.mark.parametrize("modname", PURE_MODULES)
def test_pure_module_imports(modname: str) -> None:
    mod = importlib.import_module(modname)
    assert mod is not None


def test_ha_ssh_imports_if_paramiko_present() -> None:
    """ha_ssh needs paramiko; skip cleanly when it isn't installed (bare CI)."""
    pytest.importorskip("paramiko", reason="paramiko not installed on this runner")
    mod = importlib.import_module("ha_ssh")
    # The shared SSH helper should expose the documented entry points.
    for name in ("ssh_connect", "run"):
        assert hasattr(mod, name), f"ha_ssh missing expected symbol {name!r}"
