"""Registration lock for the `panel_custom:` entries of both wall panels (2026-08-17).

A panel that HA never registered is invisible no matter how good its code is, and a panel
registered under a URL the browser already cached is *equally* invisible. On 2026-08-17 the
owner said «не вижу изменений» three times and was right all three times, because both of
those failure modes were live at once:

  1. THE DROPPED ENTRY. A Stage-1 agent added the `tablet-panel-v2` entry; several later
     agents edited `configuration.yaml` in sequence and one of them wrote from a backup
     taken *before* that entry existed, silently deleting it. Nothing errors when a
     `panel_custom` entry vanishes — the sidebar item just isn't there, and the owner keeps
     opening the old panel.

  2. THE STALE CACHE-BUST. HA serves `/local/` with `Cache-Control: public,
     max-age=2678400` (31 days). The entry's `module_url` carried `?v=20260816-v2-1` while
     the file on disk had moved on to build `20260817-v2-ctl-1`. Because the URL *string*
     was unchanged, Chromium kept replaying the month-old module from disk cache — even
     across `location.reload()`, which is exactly why the panel's own self-updater could
     not rescue it: the updater reloads the page, and the page re-requests the same cached
     URL. A URL the browser has never seen is the only cache-bust that cannot fail.

So these tests assert the registration itself, not the panel's behaviour (that is
`test_panel_build_marker.py` for v1 and `test_panel_v2_build_marker.py` for v2):

  * both panels are registered, with unique `name`/`url_path` — fails if an entry is dropped;
  * every `panel_custom.name` equals the tag the shipped file passes to
    `customElements.define()` — a mismatch registers a panel HA can never instantiate,
    and it is a one-character typo away at all times;
  * `module_url` points at the file we actually ship;
  * v2's `?v=` equals its build marker — fails if the version drifts.

THE VERSION LOCK IS DELIBERATELY ASYMMETRIC. v2's `?v=` is pinned to its build; v1's is a
hand-chosen label (`classic-20260727-2`) that has *never* tracked `PANEL_BUILD` and whose
entry had to stay byte-identical during the 2026-08-17 repair, so pinning it here would
fail the suite for a pre-existing condition this change did not own. `PIN_VERSION` records
that per panel instead of pretending both behave alike; flip v1's flag to True in the same
commit that re-stamps its `module_url`. See `test_v1_version_pin_is_off_on_purpose`.

Pure/hermetic: YAML + text parsing only. No network, no HA, no devices, no browser.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[1]

# Prefer a real (gitignored) local snapshot of the deployed configuration.yaml when present;
# otherwise fall back to the secret-free fixture copy of just the panel_custom block.
# Same precedence as tests/test_leak_truth.py.
CFG_CANDIDATES = [
    "configuration.yaml",
    "scratch_configuration.yaml",
    "tests/fixtures/panel_custom.yaml",
]


@dataclass(frozen=True)
class PanelSpec:
    """What the repo expects one `panel_custom` entry to look like."""

    url_path: str
    file: Path  # repo mirror of the deployed /config/www/<file>
    element: str  # tag the file must pass to customElements.define()
    local_url: str  # module_url path, without the ?v= query
    build_var: str  # the `const <NAME> = "...";` build marker inside the file
    sidecar: Path | None  # tracked sidecar advertising the same build, if any
    pin_version: bool  # must module_url's ?v= equal the build marker?


PANELS: dict[str, PanelSpec] = {
    "tablet-panel": PanelSpec(
        url_path="tablet-panel",
        file=ROOT / "tablet" / "tablet-panel.js",
        element="tablet-panel",
        local_url="/local/tablet-panel.js",
        build_var="PANEL_BUILD",
        sidecar=ROOT / "tablet" / "tablet-version.json",
        pin_version=False,  # see module docstring + test_v1_version_pin_is_off_on_purpose
    ),
    "tablet-panel-v2": PanelSpec(
        url_path="tablet-panel-v2",
        file=ROOT / "tablet" / "tablet-panel-v2.js",
        element="tablet-panel-v2",
        local_url="/local/tablet-panel-v2.js",
        build_var="PANEL_V2_BUILD",
        sidecar=ROOT / "tablet" / "tablet-v2-version.json",
        pin_version=True,
    ),
}


# --------------------------------------------------------------------------- #
# configuration.yaml loading
# --------------------------------------------------------------------------- #
class _L(yaml.SafeLoader):
    """SafeLoader that tolerates HA's custom tags (!include, !secret, ...)."""


for _tag in ("!include", "!include_dir_named", "!include_dir_merge_named"):
    _L.add_constructor(_tag, lambda l, n: {})
for _tag in ("!include_dir_list", "!include_dir_merge_list"):
    _L.add_constructor(_tag, lambda l, n: [])
for _tag in ("!secret", "!env_var"):
    _L.add_constructor(_tag, lambda l, n: "x")


def _cfg_path() -> Path:
    for name in CFG_CANDIDATES:
        p = ROOT / name
        if p.exists():
            return p
    pytest.skip(f"none of {CFG_CANDIDATES} found under {ROOT}")


def _entries() -> list[dict]:
    """The `panel_custom:` list, validated as a list of mappings."""
    path = _cfg_path()
    doc = yaml.load(path.read_text(encoding="utf-8"), Loader=_L)
    assert isinstance(doc, dict), f"{path} must parse to a mapping"
    block = doc.get("panel_custom")
    assert isinstance(block, list), (
        f"{path} must have a top-level `panel_custom:` LIST; got {type(block).__name__}. "
        "Without it neither wall panel is registered and the sidebar entries vanish."
    )
    for i, e in enumerate(block):
        assert isinstance(e, dict), f"panel_custom[{i}] must be a mapping, got {e!r}"
    return block


def _by_url_path() -> dict[str, dict]:
    return {e.get("url_path"): e for e in _entries()}


def _panel_text(spec: PanelSpec) -> str:
    """Source of the shipped panel, or SKIP when the gitignored build is absent."""
    if not spec.file.exists():
        pytest.skip(f"{spec.file.relative_to(ROOT)} not present (gitignored deployed build)")
    return spec.file.read_text(encoding="utf-8")


def _version_of(module_url: str) -> str:
    """The `?v=` cache-bust token of a module_url."""
    m = re.search(r"\?v=([^&\s]+)$", module_url)
    assert m, (
        f"module_url {module_url!r} carries no `?v=` cache-bust. HA serves /local/ with "
        "max-age=2678400, so without a fresh query string the browser replays the old "
        "module from cache — even across location.reload()."
    )
    return m.group(1)


# --------------------------------------------------------------------------- #
# 1. The dropped-entry lock
# --------------------------------------------------------------------------- #
def test_both_panels_are_registered():
    """THE lock: dropping either `panel_custom` entry fails the suite.

    This is the exact regression of 2026-08-17 — a config restored from a stale backup
    lost the v2 entry, and nothing anywhere errored.
    """
    found = _by_url_path()
    missing = [u for u in PANELS if u not in found]
    assert not missing, (
        f"panel_custom is missing {missing}; registered url_paths are {sorted(found)}. "
        "An entry was dropped (this is what a restore-from-stale-backup looks like) — "
        "re-add it, because a missing entry produces NO error, just an absent sidebar item."
    )


def test_registration_keys_are_unique():
    """Duplicate name/url_path silently shadows one panel with the other."""
    entries = _entries()
    for key in ("name", "url_path"):
        vals = [e.get(key) for e in entries]
        dupes = {v for v in vals if vals.count(v) > 1}
        assert not dupes, f"duplicate panel_custom {key}: {sorted(dupes)}"


def test_every_entry_is_complete_and_reachable_without_admin():
    """Each entry declares the keys HA needs, and the wall tablet is not admin-gated.

    The tablet on the wall is not logged in as an admin, so `require_admin: true` would
    make the panel a 404 for the one client that matters.
    """
    for url_path, spec in PANELS.items():
        e = _by_url_path().get(url_path)
        if e is None:
            pytest.fail(f"{url_path} not registered (see test_both_panels_are_registered)")
        for key in ("name", "url_path", "sidebar_title", "sidebar_icon", "module_url"):
            v = e.get(key)
            assert isinstance(v, str) and v.strip(), f"{url_path}: `{key}` must be a non-empty string, got {v!r}"
        assert e.get("require_admin") is False, (
            f"{url_path}: require_admin must be explicitly false — the wall tablet has no "
            f"admin session, so anything else hides the panel from it; got {e.get('require_admin')!r}"
        )
        assert e["sidebar_icon"].startswith("mdi:"), f"{url_path}: sidebar_icon must be an mdi: icon"


def test_the_two_panels_are_visually_distinguishable_in_the_sidebar():
    """Same title or same icon for both panels = the owner opens the wrong one.

    That is not hypothetical: the whole 2026-08-17 incident was the owner unknowingly
    looking at the old panel.
    """
    entries = [_by_url_path()[u] for u in PANELS if u in _by_url_path()]
    if len(entries) < 2:
        pytest.skip("both panels must be registered first")
    for key in ("sidebar_title", "sidebar_icon"):
        vals = [e[key] for e in entries]
        assert len(set(vals)) == len(vals), (
            f"both panels share {key}={vals!r} — they must be tellable apart in the sidebar"
        )


# --------------------------------------------------------------------------- #
# 2. name <-> custom element tag
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("url_path", sorted(PANELS))
def test_name_matches_the_custom_element_the_file_defines(url_path: str):
    """`panel_custom.name` IS the tag HA instantiates; a mismatch renders nothing.

    HA does `document.createElement(name)` after importing module_url, so if the file
    defines `tablet-panel-v2` and the entry says `tablet-panel-2`, the import succeeds,
    the element stays unknown, and the panel is a blank page with no console error worth
    noticing.
    """
    spec = PANELS[url_path]
    entry = _by_url_path().get(url_path)
    if entry is None:
        pytest.fail(f"{url_path} not registered (see test_both_panels_are_registered)")
    assert entry["name"] == spec.element, (
        f"{url_path}: panel_custom.name={entry['name']!r} but the repo expects the custom "
        f"element {spec.element!r}"
    )
    text = _panel_text(spec)
    tags = re.findall(r"""customElements\.define\(\s*['"]([^'"]+)['"]""", text)
    assert entry["name"] in tags, (
        f"{url_path}: panel_custom.name={entry['name']!r} is not defined by "
        f"{spec.file.name}; that file defines {tags!r}. HA would create an unknown element "
        "and the panel would render as an empty page."
    )


@pytest.mark.parametrize("url_path", sorted(PANELS))
def test_module_url_points_at_the_file_we_ship(url_path: str):
    spec = PANELS[url_path]
    entry = _by_url_path().get(url_path)
    if entry is None:
        pytest.fail(f"{url_path} not registered (see test_both_panels_are_registered)")
    url = entry["module_url"]
    assert url.split("?")[0] == spec.local_url, (
        f"{url_path}: module_url points at {url.split('?')[0]!r}, expected {spec.local_url!r}"
    )


# --------------------------------------------------------------------------- #
# 3. The version-drift lock
# --------------------------------------------------------------------------- #
_PINNED = sorted(u for u, s in PANELS.items() if s.pin_version)


@pytest.mark.parametrize("url_path", _PINNED)
def test_module_url_version_matches_the_sidecar_build(url_path: str):
    """`?v=` == the tracked sidecar's `build` — always runs, even in a bare checkout.

    The sidecar is tracked while the panel build is gitignored, so this is the half of the
    drift lock that can never degrade to a skip. Chained with
    `test_panel_v2_build_marker.py::test_panel_v2_build_matches_sidecar_exactly`
    (sidecar == PANEL_V2_BUILD), it pins `?v=` to the real build transitively.
    """
    import json

    spec = PANELS[url_path]
    entry = _by_url_path().get(url_path)
    if entry is None:
        pytest.fail(f"{url_path} not registered (see test_both_panels_are_registered)")
    assert spec.sidecar is not None and spec.sidecar.exists(), f"{spec.sidecar} must be tracked"
    build = json.loads(spec.sidecar.read_text(encoding="utf-8"))["build"]
    got = _version_of(entry["module_url"])
    assert got == build, (
        f"{url_path}: module_url `?v={got}` but {spec.sidecar.name} advertises build "
        f"{build!r}. The browser has already cached ?v={got}, so it will keep serving the "
        "OLD module (HA sets max-age=2678400 on /local/) and the deploy stays invisible — "
        "even across location.reload(). Re-stamp module_url and restart HA."
    )


@pytest.mark.parametrize("url_path", _PINNED)
def test_module_url_version_matches_the_build_marker_in_the_file(url_path: str):
    """`?v=` == the `const <BUILD_VAR>` embedded in the shipped panel itself."""
    spec = PANELS[url_path]
    entry = _by_url_path().get(url_path)
    if entry is None:
        pytest.fail(f"{url_path} not registered (see test_both_panels_are_registered)")
    text = _panel_text(spec)
    m = re.search(
        rf"""^const\s+{re.escape(spec.build_var)}\s*=\s*['"]([^'"]+)['"]\s*;""", text, re.M
    )
    assert m, f"no top-level `const {spec.build_var} = \"...\";` in {spec.file.name}"
    got = _version_of(entry["module_url"])
    assert got == m.group(1), (
        f"{url_path}: module_url `?v={got}` but {spec.file.name} is build {m.group(1)!r}. "
        "The tablet will keep running the cached older module."
    )


def test_v1_version_pin_is_off_on_purpose():
    """Documents WHY v1 is exempt, so the exemption is a decision and not an oversight.

    v1's `?v=` is a hand-picked label that never tracked `PANEL_BUILD`, and its entry had
    to stay byte-identical during the 2026-08-17 v2 repair. This test states that; it does
    NOT assert the drift persists, so flipping `pin_version=True` (in the same commit that
    re-stamps v1's module_url) simply retires it rather than breaking the suite.
    """
    spec = PANELS["tablet-panel"]
    if spec.pin_version:
        pytest.skip("v1 is now version-pinned; the generic drift lock covers it")
    entry = _by_url_path().get("tablet-panel")
    if entry is None:
        pytest.fail("tablet-panel not registered (see test_both_panels_are_registered)")
    # The only standing requirement while unpinned: a cache-bust token must still exist.
    assert _version_of(entry["module_url"]), "even unpinned, v1 needs some ?v= token"
