"""Drift lock for the Telegram Mini App's self-updater (2026-07-28).

Sibling of ``test_panel_build_marker.py``: same failure mode, different surface.

The Mini App is served from ``/local/smarthouse.html``, which HA hands out with
``Cache-Control: public, max-age=2678400`` (31 days). Telegram's webview honours that,
so before this build a deployed change could stay invisible to the owner for a month —
there is no panel_custom ``?v=`` re-stamp to save us here, and a plain
``location.reload()`` would just re-serve the cached copy. The app therefore carries its
own build stamp (``MINIAPP_BUILD``), polls the sidecar ``/local/miniapp-version.json``
and, on a DIFFERENT ``build``, navigates ONCE to ``?v=<build>`` — a new URL the cache
cannot answer.

That mechanism has exactly one way to break silently, and it is a deploy mistake:

  * bump the sidecar but not the HTML -> every open sees "new build" forever (capped at
    one navigation per distinct build, so nothing storms, but auto-update is dead);
  * bump the HTML but not the sidecar -> the sidecar advertises the OLD build, so an
    already-updated app is told it is stale. Again capped, again silently broken.

So these tests assert the two files agree, byte for byte, on one string — plus the two
properties that make this safe on a phone that can close the water valve:

  * the poll is uncached and cache-busted (otherwise the sidecar itself would be cached
    for 31 days and the whole mechanism would be a no-op), and
  * ``location.hash`` is preserved in the navigation target. Telegram passes
    ``tgWebAppData`` — the initData every ``/api/miniapp-*`` call authenticates with — in
    the URL FRAGMENT. A navigation that dropped the hash would leave the owner staring at
    «Ошибка авторизации». This is the highest-consequence assertion in this file.

Pure/hermetic: text + JSON parsing only. No network, no HA, no devices, no browser.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "miniapp" / "smarthouse_v8.html"
SIDECAR = ROOT / "miniapp" / "miniapp-version.json"

# `const MINIAPP_BUILD = "20260728-3";` — the app lives inside an IIFE, so the
# declaration is indented; single/double quotes both accepted.
_BUILD_RE = re.compile(r"""^\s*const\s+MINIAPP_BUILD\s*=\s*['"]([^'"]+)['"]\s*;""", re.M)
_URL_RE = re.compile(r"""const\s+UPD_URL\s*=\s*['"]/local/miniapp-version\.json['"]""")


def _app_text() -> str:
    assert APP.exists(), f"{APP} is missing — it is the tracked mirror of /config/www/smarthouse.html"
    return APP.read_text(encoding="utf-8")


def _sidecar_build() -> str:
    assert SIDECAR.exists(), (
        f"{SIDECAR} is missing — the Mini App polls /local/miniapp-version.json, so the "
        "repo must keep a tracked reference copy of it"
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


def _app_build(text: str) -> str:
    m = _BUILD_RE.search(text)
    assert m, 'no `const MINIAPP_BUILD = "...";` found in miniapp/smarthouse_v8.html'
    assert len(_BUILD_RE.findall(text)) == 1, "MINIAPP_BUILD is declared more than once"
    build = m.group(1)
    assert build and build.strip() == build, f"MINIAPP_BUILD must be a trimmed non-empty string: {build!r}"
    return build


def test_sidecar_is_valid_and_minimal():
    """miniapp/miniapp-version.json parses and advertises one non-empty build string."""
    build = _sidecar_build()
    assert len(build) <= 64, f"build string implausibly long ({len(build)} chars): {build!r}"


def test_miniapp_build_matches_sidecar_exactly():
    """THE drift lock: MINIAPP_BUILD == miniapp-version.json "build", byte for byte."""
    app = _app_build(_app_text())
    side = _sidecar_build()
    assert app == side, (
        "build marker drift: miniapp/smarthouse_v8.html MINIAPP_BUILD="
        f"{app!r} but miniapp/miniapp-version.json build={side!r}. "
        "Bump BOTH (and deploy both files) or Mini App auto-update breaks."
    )


def test_poller_targets_the_sidecar_we_ship_uncached():
    """A cached version-poll would make the whole mechanism a silent no-op."""
    text = _app_text()
    assert _URL_RE.search(text), "UPD_URL must point at '/local/miniapp-version.json'"
    assert 'cache:"no-store"' in text or "cache:'no-store'" in text, \
        "the version poll must be uncached (cache:'no-store')"
    assert 'UPD_URL+"?t="+Date.now()' in text or "UPD_URL+'?t='+Date.now()" in text, \
        "the version poll must be cache-busted per request (?t=<now>)"
    assert re.search(r"const\s+UPD_POLL_MS\s*=\s*60000\b", text), "poll cadence must stay 60 s"
    assert re.search(r"const\s+UPD_MAX_JSON\s*=\s*4096\b", text), \
        "the sidecar body must stay capped at 4096 bytes"


def test_navigation_preserves_the_telegram_initdata_hash():
    """Telegram puts tgWebAppData in the FRAGMENT — the navigation must keep it verbatim.

    Dropping location.hash would break /api/miniapp-auth for every subsequent open and
    the owner would see «Ошибка авторизации» instead of the app.
    """
    text = _app_text()
    m = re.search(r"function\s+updTargetUrl\(([^)]*)\)\{(.*?)\n  \}", text, re.S)
    assert m, "updTargetUrl() (the cache-busting URL builder) is missing"
    body = m.group(2)
    assert "location.hash" in body, \
        "updTargetUrl() must append location.hash — tgWebAppData/initData lives there"
    assert re.search(r"location\.pathname\s*\+\s*[\"']\?[\"']\s*\+\s*query\s*\+\s*location\.hash", body), \
        "the target must be pathname + '?' + <query> + location.hash (hash LAST, verbatim)"
    assert 'encodeURIComponent(b)' in body, "the build value must be URL-encoded"
    # Pre-existing query params are rebuilt, not clobbered; only `v` is replaced.
    assert "new URLSearchParams(location.search)" in body and 'p.delete("v")' in body, \
        "updTargetUrl() must rebuild the query string, carrying over params other than v"
    # location.replace (not reload) is what actually busts a 31-day cached URL, and it
    # must exist in exactly one guarded place.
    assert len(re.findall(r"location\.replace\(", text)) == 1, \
        "location.replace() must live only in miniappNavigate(), behind updMaybeNavigate()"


def test_navigation_guards_are_still_present():
    """A phone that arms security must never enter a navigation storm: keep every guard."""
    text = _app_text()
    required = {
        "per-build loop protection": "updNavigatedBuilds()",
        "persisted build we navigated for": '"miniapp_upd_for"',
        "navigation counter": '"miniapp_upd_count"',
        "hard session cap": "updNavCount()>=UPD_MAX_NAV",
        "refuse to navigate with no storage": "if(!updStore())",
        "startup deferral": 'app.auth!=="ok"||!app.updatedAt',
        "modal deferral": "if(app.modal)return",
        "leak deferral": "leakInfo()",
        "smoke deferral": "UPD_SMOKE_ID",
        "interaction deferral": "UPD_INTERACT_MS",
        "hidden-document deferral": 'document.visibilityState==="hidden"',
        "pending navigation retried on visibility": 'if(document.visibilityState==="visible")updMaybeNavigate()',
        "pending navigation retried on every poll": "updMaybeNavigate();",
    }
    missing = [name for name, needle in required.items() if needle not in text]
    assert not missing, f"self-update guards missing from the Mini App: {missing}"
    assert re.search(r"const\s+UPD_MAX_NAV\s*=\s*3\b", text), \
        "the hard per-session navigation cap must stay at 3"
    assert re.search(r"const\s+UPD_INTERACT_MS\s*=\s*10000\b", text), \
        "the post-interaction quiet period must stay at 10 s"
    assert "sessionStorage" in text and "localStorage" in text, \
        "bookkeeping must try sessionStorage first and fall back to localStorage"


def test_update_is_quiet_never_a_dialog():
    """Suppressed/pending updates are reported as one read-only line, never intrusively."""
    text = _app_text()
    code = re.sub(r"(?m)^\s*//.*$", "", text)  # drop full-line comments (they discuss alert())
    assert not re.search(r"(?<![\w.$])alert\s*\(", code), \
        "the Mini App must never alert(); the update hint is quiet"
    assert not re.search(r"(?<![\w.$])confirm\s*\(", code), "no blocking confirm() either"
    assert "data-upd-line" in text, \
        "the quiet update line must be rendered (data-upd-line) in «Ещё» → Диагностика"
    assert "updLine()" in text, "the quiet hint text builder updLine() must be rendered"
    # The updater must not toast on every poll.
    upd_block = text.split("SELF-UPDATE (2026-07-28)", 1)[-1]
    assert "toast(" not in upd_block, "the self-updater must not toast"


def test_leak_truth_and_floor_heating_contracts_untouched():
    """The self-updater must not have touched the safety/UI contracts it reads from."""
    text = _app_text()
    for marker in (
        'const LEAK_TRUTH="sensor.leak_protection_status"',   # one source of truth
        "a.per_sensor",                                       # per-sensor verdicts
        "function leakInfo()",
        "function cmdVerified(",                              # verification tolerance
        "/api/miniapp-auth",
        "/api/miniapp-state",
        "/api/miniapp-action",
    ):
        assert marker in text, f"pre-existing contract marker vanished: {marker}"
    # No staleness rule may be (re)introduced for the leak sleepers.
    assert "cloud_age_sec" in text, "leak cloud-age attribute read must stay"
