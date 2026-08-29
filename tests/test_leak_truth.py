"""Regression lock for the ONE leak-protection source of truth (2026-07-27).

For two months the question "is this leak sensor OK / what does it mean" was answered
independently in ~10 places with different rules, so every point-fix left the other places
lying. The fix is `sensor.leak_protection_status` (a HA template in configuration.yaml) plus
the rule that every UI READS it and NEVER re-derives it.

These tests are pure/hermetic (text + YAML parsing only, no network, no HA, no devices) and
guard the three ways the bug could come back:

  1. The four heavy templates of the entity (state, per_sensor, leak_names, blind_names) must
     carry the BYTE-IDENTICAL rule text — a divergence between them is the same class of bug
     one level down.
  2. The 180-minute ("3 hour") staleness rule must not reappear for the leak sensors in the
     tablet panel or the Mini App. These sensors are battery SLEEPERS: they report only on
     wet/dry events, so silence is NORMAL and must never render as «вслепую».
  3. Neither UI may read the four leak `binary_sensor.*_moisture` states to decide status;
     only the truth entity (and the plain name/label tables) may mention them.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "tablet" / "tablet-panel.js"
MINIAPP = ROOT / "miniapp" / "smarthouse_v8.html"
TRUTH = "sensor.leak_protection_status"
LEAK_IDS = [
    "binary_sensor.vannaia_moisture",
    "binary_sensor.garazh_moisture",
    "binary_sensor.kukhnia_moisture",
    "binary_sensor.water_sensor_4_moisture",
]
# Prefer a real (gitignored) local snapshot of the deployed configuration.yaml when present;
# otherwise fall back to the secret-free fixture copy of just the template block.
CFG_CANDIDATES = ["configuration.yaml", "scratch_configuration.yaml",
                  "tests/fixtures/leak_protection_template.yaml"]


def _cfg_path() -> Path:
    for name in CFG_CANDIDATES:
        p = ROOT / name
        if p.exists():
            return p
    pytest.skip(f"none of {CFG_CANDIDATES} found under {ROOT}")


class _L(yaml.SafeLoader):
    pass


for _tag in ("!include", "!include_dir_named", "!include_dir_merge_named"):
    _L.add_constructor(_tag, lambda l, n: {})
for _tag in ("!include_dir_list", "!include_dir_merge_list"):
    _L.add_constructor(_tag, lambda l, n: [])
for _tag in ("!secret", "!env_var"):
    _L.add_constructor(_tag, lambda l, n: "x")


def _entity() -> dict:
    doc = yaml.load(_cfg_path().read_text(encoding="utf-8"), Loader=_L)
    blocks = doc.get("template")
    assert isinstance(blocks, list), "configuration.yaml must have a top-level template: list"
    sensors = [s for b in blocks if isinstance(b, dict) for s in (b.get("sensor") or [])]
    hits = [s for s in sensors if s.get("unique_id") == "leak_protection_status"]
    assert len(hits) == 1, f"expected exactly one leak_protection_status template, got {len(hits)}"
    return hits[0]


# --------------------------------------------------------------------------- #
# 1. one rule, byte-identical in every template of the entity
# --------------------------------------------------------------------------- #
def test_single_top_level_template_block():
    text = _cfg_path().read_text(encoding="utf-8")
    # `value_template:` false-matches a naive search, so anchor at line start.
    assert len(re.findall(r"(?m)^template:", text)) == 1, "must ADD to the existing template: block"


def test_heavy_templates_share_byte_identical_rule():
    e = _entity()
    attrs = e["attributes"]
    heavy = [e["state"], attrs["per_sensor"], attrs["leak_names"], attrs["blind_names"]]
    # everything up to the final output expression must be identical text
    cores = [h[: h.rindex("{{")] for h in heavy]
    assert len(set(cores)) == 1, "the leak rule has diverged between state and its attributes"
    core = cores[0]
    for eid in LEAK_IDS:
        assert eid in core, f"{eid} missing from the rule"
    # the measured polarity and both liveness paths must be present
    assert "'1'" in core and "online" in core and "src" in core
    assert "86400" in core, "the 24h HA-state fallback bound is gone"
    assert "300" in core, "the 300s cloud-usability bound is gone"


def test_entity_exposes_the_documented_attributes():
    e = _entity()
    assert sorted(e["attributes"]) == [
        "blind_names", "checked", "cloud_age_sec", "cloud_src", "leak_names", "per_sensor",
    ]


def test_rule_has_no_staleness_bound_between_5min_and_24h():
    """A sleeper's silence must not be a blindness signal. The only time bounds allowed are
    the cloud-poll freshness (300 s) and the 24 h HA-state fallback."""
    core = _entity()["state"]
    bad = [n for n in re.findall(r"\b(\d{3,6})\b", core) if 301 <= int(n) < 86400]
    assert not bad, f"suspicious staleness threshold(s) in the leak rule: {bad}"


# --------------------------------------------------------------------------- #
# 2 + 3. the UIs read the truth entity and nothing else
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("path", [PANEL, MINIAPP], ids=["tablet", "miniapp"])
def test_ui_reads_the_truth_entity(path: Path):
    if not path.exists():
        pytest.skip(f"{path.name} not present")
    text = path.read_text(encoding="utf-8")
    assert TRUTH in text, f"{path.name} does not read {TRUTH}"


@pytest.mark.parametrize("path", [PANEL, MINIAPP], ids=["tablet", "miniapp"])
def test_no_three_hour_staleness_rule_for_leak_sensors(path: Path):
    """The deleted rule was `ageMins(id) > 180` / `SAFETY_STALE_MIN = 180`."""
    if not path.exists():
        pytest.skip(f"{path.name} not present")
    code = "\n".join(l for l in path.read_text(encoding="utf-8").splitlines()
                     if not l.lstrip().startswith("//"))
    for banned in ("SAFETY_STALE_MIN", "safetyState("):
        assert banned not in code, f"{path.name} resurrected {banned}"
    assert not re.search(r">\s*180\b", code), f"{path.name} resurrected the 180-minute rule"


@pytest.mark.parametrize("path", [PANEL, MINIAPP], ids=["tablet", "miniapp"])
def test_leak_sensor_states_are_not_read_directly(path: Path):
    """Every mention of a leak entity id must be a label/name table or the LEAK id list —
    never `st(...)`, `state(S, ...)`, `isOn(...)` or an availability probe."""
    if not path.exists():
        pytest.skip(f"{path.name} not present")
    text = path.read_text(encoding="utf-8")
    banned = re.compile(
        r"(?:st|isOn|isKnownBinary|c1unavailable|c1age|c1exists|ageMins|availOf)\s*\(\s*"
        r"(?:S\s*,\s*)?['\"](?:" + "|".join(re.escape(i) for i in LEAK_IDS) + r")['\"]"
    )
    hits = banned.findall(text)
    assert not hits, f"{path.name} still reads a leak sensor state directly: {hits}"


# --------------------------------------------------------------------------- #
# 4. The leak backup must survive on the Tuya free tier (2026-08-19)
#
# `tuya_leak_query.py` is the INDEPENDENT (life-safety) leak source and, since
# 2026-08-19, the ONLY consumer of the Tuya IoT Core free tier: ev_query.py was moved
# off it onto HA's own alive `tuya` integration and now makes zero cloud calls. The
# tier is 26 000 calls/month, so the worst case of the base poll plus the forced
# 30-second burst that automation 1790400001001 drives while the moisture sensors are
# blind has to fit inside it — otherwise the quota dies again and the backup goes dark
# exactly when the primary path is already blind.
#
# If you change any number here, change automation 1790400001001 (`repeat.index <= N`
# and its description) in the same commit, and redo the arithmetic.
# --------------------------------------------------------------------------- #
FREE_TIER_CALLS_PER_MONTH = 26_000
BUDGET_FRACTION = 0.90          # keep headroom for retries and manual probes
DAYS_PER_MONTH = 31             # the expensive month
LEAK_SCAN_INTERVAL_S = 180      # command_line scan_interval for sensor.tuya_leak_cloud
TOKEN_REFRESHES_PER_DAY = 13    # Tuya access_token lives ~2 h
FORCE_POLL_INTERVAL_S = 30      # delay inside the burst loop
FORCE_MAX_ITERATIONS = 5        # `repeat.index | int(0) <= 5` in 1790400001001
FORCE_COOLDOWN_S = 1800         # 30 min per-episode cooldown -> <= 48 episodes/day


def _calls_per_month(force_iterations: int) -> int:
    base = 86_400 // LEAK_SCAN_INTERVAL_S                 # 480 successful polls/day
    episodes = 86_400 // FORCE_COOLDOWN_S                 # 48 worst-case episodes/day
    per_day = base + TOKEN_REFRESHES_PER_DAY + episodes * force_iterations
    return per_day * DAYS_PER_MONTH


def test_leak_cloud_worst_case_fits_the_free_tier():
    budget = FREE_TIER_CALLS_PER_MONTH * BUDGET_FRACTION
    worst = _calls_per_month(FORCE_MAX_ITERATIONS)
    assert worst <= budget, (
        f"worst case {worst} calls/month exceeds {budget:.0f} "
        f"({BUDGET_FRACTION:.0%} of {FREE_TIER_CALLS_PER_MONTH})"
    )
    # And document why the cap had to come down: the previous 20 iterations did not fit.
    assert _calls_per_month(20) > FREE_TIER_CALLS_PER_MONTH, (
        "the old burst cap would now fit — re-check the arithmetic before relaxing it"
    )


def test_a_failing_cloud_cannot_turn_the_burst_into_a_call_storm():
    """Every failure path backs off, so a dead cloud is cheap rather than expensive."""
    import tuya_leak_query as leak

    assert leak.FAIL_BACKOFF >= FORCE_POLL_INTERVAL_S, "generic failures must throttle the burst"
    assert leak.QUOTA_BACKOFF >= leak.FAIL_BACKOFF, "a quota error must back off at least as long"
    assert leak.FRESH_TTL < LEAK_SCAN_INTERVAL_S, "the base poll must still reach the cloud"
    # A served-from-cache answer may never be relabelled as a live read.
    assert leak.as_cache({"src": "cloud", "state": "normal"})["src"] == "cache"
