"""Drift lock for the tablet panel's self-updater (2026-07-28).

The wall panel is served from `/local/tablet-panel.js`, which HA caches hard, and
panel_custom only re-stamps `module_url?v=` on an HA restart — so before this build a
deploy could stay invisible on the tablet for days. The panel now carries its own build
stamp (`PANEL_BUILD`) and polls the sidecar `/local/tablet-version.json`; a DIFFERENT
`build` value there makes the page reload itself once and pick up the new JS.

That mechanism has exactly one way to break silently, and it is a deploy mistake, not a
code bug:

  * bump the sidecar but not the JS  -> the tablet sees "new build" forever. The panel's
    loop protection caps this at one reload per distinct build, so nothing storms, but
    auto-update is dead until someone notices.
  * bump the JS but not the sidecar  -> the sidecar advertises the OLD build, so every
    tablet that already runs the new JS is told it is out of date. Again capped, again
    silently broken.

So these tests assert the two files agree, byte for byte, on one string — and that the
guards that make an automatic reload safe on a wall control surface are still present.

Pure/hermetic: text + JSON parsing only. No network, no HA, no devices, no browser.
The panel itself is gitignored (deployed builds may embed tokens), so the file-content
assertions SKIP cleanly when it is absent; the sidecar is tracked, so its own shape is
always checked.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[1]
# Сайдкар tablet-version.json описывает ТУ панель, которая реально стоит на планшете,
# а это tablet-panel.deployed.js. Раньше тест смотрел на tablet-panel-flow.js —
# черновой файл со своей нумерацией сборок, поэтому «расхождение» он показывал
# всегда, а настоящее расхождение пропустил бы. Берём задеплоенную, с откатом на
# черновую, если задеплоенной нет.
_CANDIDATES = [
    ROOT / "tablet" / "tablet-panel.deployed.js",
    ROOT / "tablet" / "tablet-panel-flow.js",
]
PANEL = next((p for p in _CANDIDATES if p.exists()), _CANDIDATES[0])
SIDECAR = ROOT / "tablet" / "tablet-version.json"

# `const PANEL_BUILD = "20260728-1";` — single/double quotes both accepted.
_BUILD_RE = re.compile(r"""^const\s+PANEL_BUILD\s*=\s*['"]([^'"]+)['"]\s*;""", re.M)
# The URL the poller fetches must be the sidecar we ship, no-store, cache-busted.
_URL_RE = re.compile(r"""const\s+UPD_URL\s*=\s*['"]/local/tablet-version\.json['"]""")


def _panel_text() -> str:
    if not PANEL.exists():
        pytest.skip(f"{PANEL.name} not present (deployed source unavailable)")
    return PANEL.read_text(encoding="utf-8")


def _sidecar_build() -> str:
    assert SIDECAR.exists(), (
        f"{SIDECAR} is missing — the panel polls /local/tablet-version.json, so the repo "
        "must keep a tracked reference copy of it"
    )
    raw = SIDECAR.read_text(encoding="utf-8")
    data = json.loads(raw)  # must be valid JSON, not a template or a comment-laden file
    assert isinstance(data, dict), f"{SIDECAR} must be a JSON object, got {type(data)}"
    build = data.get("build")
    assert isinstance(build, str) and build.strip(), (
        f'{SIDECAR} must carry a non-empty string "build"; got {build!r}'
    )
    assert build == build.strip(), f'{SIDECAR} "build" has surrounding whitespace: {build!r}'
    return build


def _panel_build(text: str) -> str:
    m = _BUILD_RE.search(text)
    assert m, f"no top-level `const PANEL_BUILD = \"...\";` found in {PANEL.name}"
    assert len(_BUILD_RE.findall(text)) == 1, "PANEL_BUILD is declared more than once"
    build = m.group(1)
    assert build.strip() == build and build, f"PANEL_BUILD must be a trimmed non-empty string: {build!r}"
    return build


def test_sidecar_is_valid_and_minimal():
    """tablet/tablet-version.json parses and advertises one non-empty build string."""
    build = _sidecar_build()
    assert len(build) <= 64, f"build string implausibly long ({len(build)} chars): {build!r}"


def test_panel_build_matches_sidecar_exactly():
    """THE drift lock: PANEL_BUILD == tablet-version.json "build", byte for byte.

    Fails the suite when a deploy bumps one and forgets the other — the failure mode that
    would otherwise disable auto-update (or make every up-to-date tablet think it is
    stale) without any visible symptom.
    """
    panel = _panel_build(_panel_text())
    side = _sidecar_build()
    assert panel == side, (
        f"build marker drift: {PANEL.name} PANEL_BUILD="
        f"{panel!r} but tablet/tablet-version.json build={side!r}. "
        "Bump BOTH (and deploy both files) or auto-update breaks."
    )


def test_poller_targets_the_sidecar_we_ship():
    text = _panel_text()
    assert _URL_RE.search(text), "UPD_URL must point at '/local/tablet-version.json'"
    assert "cache:'no-store'" in text.replace('cache: "no-store"', "cache:'no-store'"), \
        "the version poll must be uncached (cache:'no-store')"
    assert "UPD_URL+'?t='+Date.now()" in text, "the version poll must be cache-busted per request"


def test_reload_guards_are_still_present():
    """A wall control surface must never enter a reload storm: keep every guard."""
    text = _panel_text()
    required = {
        "per-build loop protection": "updReloadedBuilds()",
        "persisted build we reloaded for": "'panel_reload_for'",
        "reload counter": "'panel_reload_count'",
        "hard session cap": "updReloadCount()>=UPD_MAX_RELOADS",
        "modal deferral": "updModalOpen()",
        "leak deferral": "leakVerdict()==='leak'",
        "smoke deferral": "isOn(UPD_SMOKE_ID)",
        "interaction deferral": "UPD_INTERACT_MS",
        "hidden-document deferral": "document.visibilityState==='hidden'",
        "pending reload retried on visibility": "if(document.visibilityState==='visible') updMaybeReload()",
    }
    missing = [name for name, needle in required.items() if needle not in text]
    assert not missing, f"self-update guards missing from the panel: {missing}"
    assert re.search(r"const\s+UPD_MAX_RELOADS\s*=\s*3\b", text), \
        "the hard per-session reload cap must stay at 3"
    assert re.search(r"const\s+UPD_INTERACT_MS\s*=\s*30000\b", text), \
        "the post-interaction quiet period must stay at 30 s"
    # location.reload() must be reachable from exactly one guarded place.
    assert len(re.findall(r"location\.reload\(\)", text)) == 1, \
        "location.reload() must live only in panelReload(), behind updMaybeReload()'s guards"
    # The auto-updater must never block the wall panel with a dialog.
    code = re.sub(r"(?m)^\s*//.*$", "", text)  # drop full-line comments (they discuss alert())
    assert not re.search(r"(?<![\w.$])alert\s*\(", code), \
        "the panel must never alert(); the update hint is quiet"


def test_no_screensaver_or_idle_regression_via_selfupdate():
    """The self-updater must not have (re)introduced any blank/idle screen path."""
    text = _panel_text()
    for marker in ("showIdleScreen", "idle-screen", "screen-guard"):
        assert marker not in text, f"screensaver/idle marker reappeared: {marker}"


def test_classic_panel_links_to_electrical_map_without_embedding_data():
    """The panel links to the isolated map; it must not duplicate electrical facts."""
    text = _panel_text()
    assert "openHaUrl('/local/electrical-map/index.html')" in text
    assert "Электрощиток" in text
