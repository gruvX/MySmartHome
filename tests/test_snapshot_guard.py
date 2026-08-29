"""Snapshot-guard regression: the midnight energy snapshot must NEVER write 0 for
an ``unavailable``/``unknown`` sensor.

Root cause (see docs/audit/HYDROPHORE_ENERGY_INVESTIGATION.md): automation
``1778700001002`` wrote ``input_number.midnight_* = states(sensor) | float(0)``.
When the plug was ``unavailable`` at 00:01, ``| float(0)`` coerced it to 0, and the
23:58 accrual then billed the whole lifetime meter as one day (~€42 phantom on gidro).

The fix (docs/audit/snapshot_guard.patch) changes each write's fallback from ``0`` to
the helper's own prior value: ``states(sensor) | float(states(helper) | float(0))``.
So on a missing reading the snapshot keeps the last good anchor, never 0.

This test renders the ACTUAL guarded templates extracted from the patch with a
HA-faithful ``float`` filter + ``states`` mock and asserts the never-zero property.
Pure/hermetic: no network, no HA, no devices.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment

_ROOT = Path(__file__).resolve().parent.parent
_PATCH = _ROOT / "docs" / "audit" / "snapshot_guard.patch"

# (sensor entity_id, helper entity_id) pairs the snapshot writes.
_PAIRS = {
    "sensor.boiler_total_energy": "input_number.midnight_boiler_energy",
    "sensor.terarium_total_energy": "input_number.midnight_kalarifer_energy",
    "sensor.akvarium_svet_total_energy": "input_number.midnight_akv_energy",
    "sensor.cherepakha_total_energy": "input_number.midnight_chep_energy",
    "sensor.zigbee_plug_2_total_energy": "input_number.midnight_gidro_energy",
    "sensor.ev_charger_energy": "input_number.midnight_ev_energy",
    "sensor.75_qled_energy": "input_number.midnight_tv_energy",
}


def _ha_float(value, default=0.0):
    """Mimic Home Assistant's ``float`` Jinja filter: return default on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _env(states: dict[str, str]) -> Environment:
    env = Environment()
    env.filters["float"] = _ha_float
    env.globals["states"] = lambda eid: states.get(eid, "unknown")
    return env


def _added_value_templates() -> list[str]:
    """Extract the guarded Jinja strings from the '+' lines of the patch."""
    assert _PATCH.exists(), f"patch missing: {_PATCH}"
    tmpls: list[str] = []
    for line in _PATCH.read_text(encoding="utf-8").splitlines():
        if line.startswith("+") and "value:" in line and "{{" in line:
            frag = line[1:].strip()  # drop leading '+'
            # frag == "value: '{{ ... }}'"  -> parse via YAML to unescape quotes
            parsed = yaml.safe_load(frag)
            tmpls.append(parsed["value"])
    return tmpls


def test_patch_has_all_seven_guarded_writes():
    tmpls = _added_value_templates()
    assert len(tmpls) == 7, f"expected 7 guarded writes, found {len(tmpls)}"
    # every guarded template must fall back to its own helper, not a bare float(0)
    for t in tmpls:
        assert "float(states(" in t.replace(" ", ""), f"no helper fallback in: {t}"


@pytest.mark.parametrize("sensor,helper", list(_PAIRS.items()))
@pytest.mark.parametrize("missing", ["unavailable", "unknown", "none", "None", ""])
def test_never_writes_zero_when_sensor_missing(sensor, helper, missing):
    """When the sensor is missing, the snapshot keeps the helper's prior value, not 0."""
    tmpls = _added_value_templates()
    tmpl = next(t for t in tmpls if sensor in t)
    prior = "278.63"  # a realistic non-zero prior anchor
    env = _env({sensor: missing, helper: prior})
    rendered = env.from_string("{{ %s }}" % _inner(tmpl)).render()
    assert float(rendered) == float(prior), (
        f"{sensor} missing -> should keep prior {prior}, got {rendered!r}"
    )
    assert float(rendered) != 0.0, f"{sensor} missing must NOT write 0"


@pytest.mark.parametrize("sensor,helper", list(_PAIRS.items()))
def test_passes_through_available_reading(sensor, helper):
    """When the sensor is available, the snapshot records the live reading."""
    tmpls = _added_value_templates()
    tmpl = next(t for t in tmpls if sensor in t)
    env = _env({sensor: "123.45", helper: "999.0"})
    rendered = env.from_string("{{ %s }}" % _inner(tmpl)).render()
    assert float(rendered) == 123.45


@pytest.mark.parametrize("sensor,helper", list(_PAIRS.items()))
def test_available_zero_is_recorded(sensor, helper):
    """A genuine available 0 (e.g. daily-reset counter) is still recorded as 0."""
    tmpls = _added_value_templates()
    tmpl = next(t for t in tmpls if sensor in t)
    env = _env({sensor: "0", helper: "5.0"})
    rendered = env.from_string("{{ %s }}" % _inner(tmpl)).render()
    assert float(rendered) == 0.0


def _inner(value_template: str) -> str:
    """Strip the surrounding ``{{ ... }}`` so we can re-wrap for rendering."""
    m = re.search(r"\{\{(.*)\}\}", value_template, re.DOTALL)
    assert m, f"not a jinja expression: {value_template}"
    return m.group(1).strip()
