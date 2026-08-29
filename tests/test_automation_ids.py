"""Structural test: every automation `id` in the automations YAML is unique.

Root cause of the water-safety F1/F3 incident was an **id collision** — leak-v4
was written under `id: '1748000001001'`, the same id that used to belong to the
"HA Startup Grace Period" automation, silently destroying the grace manager.

This test parses the actual YAML the deploy would ship and fails loudly on any
duplicate id, so a future collision can never reach production unnoticed.

Pure/hermetic: no network, no HA, no devices — just YAML parsing.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
import yaml

# The safety-fix working copy is the deliverable; fall back to the deployed name
# if someone runs this against a plain `automations.yaml` checkout.
_ROOT = Path(__file__).resolve().parent.parent
_CANDIDATES = ["scratch_automations.yaml", "automations.yaml"]


def _yaml_path() -> Path:
    for name in _CANDIDATES:
        p = _ROOT / name
        if p.exists():
            return p
    pytest.skip(f"none of {_CANDIDATES} found under {_ROOT}")


def _load() -> list[dict]:
    with _yaml_path().open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    assert isinstance(data, list), "automations YAML must be a list of blocks"
    return data


@pytest.mark.unit
def test_yaml_parses_and_is_nonempty():
    blocks = _load()
    assert len(blocks) > 0
    assert all(isinstance(b, dict) for b in blocks)


@pytest.mark.unit
def test_every_automation_has_an_id():
    blocks = _load()
    missing = [i for i, b in enumerate(blocks) if not b.get("id")]
    assert not missing, f"blocks without an id at positions: {missing}"


@pytest.mark.unit
def test_all_automation_ids_are_unique():
    blocks = _load()
    ids = [str(b["id"]) for b in blocks]
    dups = [i for i, n in Counter(ids).items() if n > 1]
    assert not dups, f"duplicate automation ids: {dups}"
    # sanity: count of ids equals count of unique ids equals block count
    assert len(ids) == len(set(ids)) == len(blocks)


@pytest.mark.unit
def test_new_safety_ids_present_and_distinct():
    """FIX B added two brand-new automations; verify their chosen ids exist and
    were not already used elsewhere (guards against re-introducing a collision)."""
    blocks = _load()
    ids = [str(b["id"]) for b in blocks]
    for new_id in ("1789200001001", "1789200001002"):
        assert ids.count(new_id) == 1, f"{new_id} must appear exactly once"
    # leak-v4 keeps its historical id on purpose (avoid orphaning the entity)
    assert ids.count("1748000001001") == 1
