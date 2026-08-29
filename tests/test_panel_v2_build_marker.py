"""Drift lock for «Пульт v2» — the self-updater and the honesty invariants (2026-08-16).

Sibling of ``test_panel_build_marker.py``, which guards the OLD panel. Panel v2 is a
separate custom element (``tablet-panel-v2``) served from ``/local/tablet-panel-v2.js``
with its own sidecar ``/local/tablet-v2-version.json`` and its own ``panel_custom`` entry,
so the two can run side by side while the old one is retired. Every assertion below is
about v2's files only; nothing here touches v1.

WHAT THIS FILE LOCKS, and why each lock exists

1. THE DRIFT LOCK. ``PANEL_V2_BUILD`` and the sidecar's ``build`` must agree byte for
   byte. Bump one without the other and auto-update silently dies (or every up-to-date
   tablet is told it is stale). Loop protection caps the damage at one reload per
   distinct build, so nothing storms — which is exactly why the breakage is invisible
   without a test.

2. THE RELOAD GUARDS. This is a wall CONTROL surface that can close the water main. A
   reload storm would be far worse than a stale build, so every guard carried over from
   the old panel must still be present: per-build loop protection, a hard session cap of
   3, and deferral while a dialog is open / during a leak / during smoke / within 30 s of
   a touch / while the document is hidden — with the deferred reload retried, never lost.

3. STORAGE NAMESPACING. v1 and v2 are installed at the same time and share
   sessionStorage. If v2 reused v1's ``panel_reload_*`` keys, each panel would burn the
   other's reload budget and one of them would stop auto-updating for no visible reason.

4. NO MOCK DATA PATH. The old panel painted ~70 fabricated states at boot and showed
   «дверь закрыта» / «дым норма» before any real data existed. v2's central promise is
   that this is structurally impossible, so the file must contain no demo seeding at all.

5. THE HONESTY FUNNEL. Exactly one function may put an entity value on screen
   (``paintValue``), it must throw on a non-Val, and the CSS rule that produces a
   semantic colour must be gated on ``data-kind="real"`` so an unreadable sensor can
   never render green.

6. THE LEAK TRUTH CONTRACT. ``sensor.leak_protection_status`` is the single source of
   truth (see docs + tests/test_leak_truth.py). v2 must read it, must read its
   ``per_sensor``/``blind_names`` attributes, and must NOT re-derive a verdict from the
   individual moisture sensors — nor re-introduce a staleness rule for them (they are
   battery sleepers whose silence is normal; the deleted 3-hour rule produced a permanent
   false «работает вслепую»).

Pure/hermetic: text + JSON parsing only. No network, no HA, no devices, no browser.
Both v2 files are tracked (the panel embeds no secrets — it authenticates through the
injected ``hass`` session), so unlike v1 nothing here needs to skip.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "tablet" / "tablet-panel-v2.js"
SIDECAR = ROOT / "tablet" / "tablet-v2-version.json"

# `const PANEL_V2_BUILD = "20260816-v2-1";` — single/double quotes both accepted.
_BUILD_RE = re.compile(r"""^const\s+PANEL_V2_BUILD\s*=\s*['"]([^'"]+)['"]\s*;""", re.M)
_URL_RE = re.compile(r"""const\s+UPD_URL\s*=\s*['"]/local/tablet-v2-version\.json['"]""")


def _panel_text() -> str:
    assert PANEL.exists(), f"{PANEL} is missing — it is the tracked mirror of /config/www/tablet-panel-v2.js"
    return PANEL.read_text(encoding="utf-8")


def _panel_code() -> str:
    """The panel with FULL-LINE comments removed.

    The header block deliberately quotes the old panel's sins by name — «loadDemo»,
    «screensaver» — so a naive substring scan for those markers would fail on the prose
    that explains why they are banned. Strip whole-line comments (only those: a trailing
    `//` strip would eat the `//` inside URLs) before scanning for CODE.
    """
    return re.sub(r"(?m)^\s*//.*$", "", _panel_text())


def _sidecar_build() -> str:
    assert SIDECAR.exists(), (
        f"{SIDECAR} is missing — panel v2 polls /local/tablet-v2-version.json, so the repo "
        "must keep a tracked reference copy of it"
    )
    data = json.loads(SIDECAR.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{SIDECAR} must be a JSON object, got {type(data)}"
    build = data.get("build")
    assert isinstance(build, str) and build.strip(), (
        f'{SIDECAR} must carry a non-empty string "build"; got {build!r}'
    )
    assert build == build.strip(), f'{SIDECAR} "build" has surrounding whitespace: {build!r}'
    return build


def _panel_build(text: str) -> str:
    m = _BUILD_RE.search(text)
    assert m, 'no top-level `const PANEL_V2_BUILD = "...";` found in tablet/tablet-panel-v2.js'
    assert len(_BUILD_RE.findall(text)) == 1, "PANEL_V2_BUILD is declared more than once"
    build = m.group(1)
    assert build and build.strip() == build, f"PANEL_V2_BUILD must be a trimmed non-empty string: {build!r}"
    return build


# ------------------------------------------------------------------ 1. the drift lock
def test_sidecar_is_valid_and_minimal():
    build = _sidecar_build()
    assert len(build) <= 64, f"build string implausibly long ({len(build)} chars): {build!r}"


def test_panel_v2_build_matches_sidecar_exactly():
    panel = _panel_build(_panel_text())
    side = _sidecar_build()
    assert panel == side, (
        "build marker drift: tablet/tablet-panel-v2.js PANEL_V2_BUILD="
        f"{panel!r} but tablet/tablet-v2-version.json build={side!r}. "
        "Bump BOTH (and deploy both files) or auto-update breaks."
    )


def test_v1_and_v2_builds_are_independent():
    """The two panels must not be forced to share a build string.

    They ship separately; coupling them would mean every v2 deploy needlessly reloads
    every v1 tablet (and vice versa). This is a smoke check that the v2 file does not
    reference v1's constant or v1's sidecar.
    """
    text = _panel_text()
    assert "PANEL_BUILD" not in text.replace("PANEL_V2_BUILD", ""), \
        "panel v2 must not reference v1's PANEL_BUILD"
    assert "/local/tablet-version.json" not in text, \
        "panel v2 must poll its OWN sidecar, not v1's"


def test_poller_targets_the_sidecar_we_ship():
    text = _panel_text()
    assert _URL_RE.search(text), "UPD_URL must point at '/local/tablet-v2-version.json'"
    assert "cache: 'no-store' }" in text or "cache:'no-store'" in text, \
        "the version poll must be uncached (cache:'no-store')"
    assert "UPD_URL + '?t=' + Date.now()" in text or "UPD_URL+'?t='+Date.now()" in text, \
        "the version poll must be cache-busted per request"
    assert re.search(r"const\s+UPD_POLL_MS\s*=\s*60000\b", text), "poll cadence must stay 60 s"
    assert re.search(r"const\s+UPD_MAX_JSON\s*=\s*4096\b", text), \
        "the sidecar body must stay capped at 4096 bytes"


# ------------------------------------------------------------------ 2. the reload guards
def test_reload_guards_are_still_present():
    text = _panel_text()
    required = {
        "per-build loop protection": "updReloadedBuilds()",
        "persisted build we reloaded for": "'panel_v2_reload_for'",
        "reload counter": "'panel_v2_reload_count'",
        "hard session cap": "updReloadCount() >= UPD_MAX_RELOADS",
        "refuse to reload with no storage": "if (!updStore())",
        "modal deferral": "updModalOpen()",
        "leak deferral": "leakVerdict() === 'leak'",
        "smoke deferral": "rawState(UPD_SMOKE_ID) === 'on'",
        "interaction deferral": "UPD_INTERACT_MS",
        "hidden-document deferral": "document.visibilityState === 'hidden'",
        "pending reload retried on visibility": "if (document.visibilityState === 'visible') updMaybeReload()",
        "pending reload retried on every poll": "updMaybeReload();",
    }
    missing = [name for name, needle in required.items() if needle not in text]
    assert not missing, f"self-update guards missing from panel v2: {missing}"
    assert re.search(r"const\s+UPD_MAX_RELOADS\s*=\s*3\b", text), \
        "the hard per-session reload cap must stay at 3"
    assert re.search(r"const\s+UPD_INTERACT_MS\s*=\s*30000\b", text), \
        "the post-interaction quiet period must stay at 30 s"
    assert len(re.findall(r"location\.reload\(\)", text)) == 1, \
        "location.reload() must live only in panelReload(), behind updMaybeReload()'s guards"


def test_reload_busts_the_module_cache_before_navigating():
    """HA serves /local/ with max-age=2678400 and Chromium revalidates only the main resource.

    Without a forced re-fetch of the module URL the tablet reloads onto byte-identical old
    code, and the poller then parks on «файл панели не изменился». Measured against the live
    HA instance on 2026-08-17: `Cache-Control: public, max-age=2678400` on
    /local/tablet-panel-v2.js.
    """
    text = _panel_text()
    m = re.search(r"function panelReload\(\) \{(.*?)\n\}", text, re.S)
    assert m, "panelReload() is missing"
    body = m.group(1)
    assert "cache: 'reload'" in body, \
        "the reload must force-refresh the cached module, or the new build never loads"
    assert "getEntriesByType('resource')" in body, \
        "the module URL (with panel_custom's ?v=) must be taken from resource timing"
    assert "location.reload()" in body, "it must still actually reload"
    assert "setTimeout(go, UPD_PREWARM_MS)" in body, \
        "a hung prewarm must not strand the wall panel on an old build"


def test_update_is_quiet_never_a_dialog():
    text = _panel_text()
    code = re.sub(r"(?m)^\s*//.*$", "", text)   # drop full-line comments
    assert not re.search(r"(?<![\w.$])alert\s*\(", code), "the panel must never alert()"
    assert not re.search(r"(?<![\w.$])confirm\s*\(", code), \
        "no blocking confirm() — confirmation is the in-panel modal, which the guards can see"


# ------------------------------------------------------------------ 3. storage namespacing
def test_storage_keys_do_not_collide_with_panel_v1():
    """Both panels are installed at once; each needs its own reload budget."""
    text = _panel_text()
    for v1_key in ("'panel_reload_builds'", "'panel_reload_count'", "'panel_reload_for'",
                   "'tablet-command-last-view'", "'tablet_token'"):
        assert v1_key not in text, f"panel v2 reuses panel v1's storage key {v1_key}"
    for v2_key in ("'panel_v2_reload_builds'", "'panel_v2_reload_count'", "'panel_v2_reload_for'"):
        assert v2_key in text, f"expected namespaced storage key {v2_key}"
    assert "const PREFS_KEY = 'panel_v2_prefs'" in text, \
        "prefs must live under their own namespaced key too"


# ------------------------------------------------------------------ 4. no mock data path
def test_there_is_no_demo_or_mock_data_path():
    """The old panel's boot lie must be impossible to re-introduce by copy/paste."""
    text = _panel_text()
    code = _panel_code()
    banned = ["loadDemo", "DEMO_STATES", "demoStates", "FAKE_STATES", "mockStates", "seedStates"]
    found = [b for b in banned if b in code]
    assert not found, f"a demo/mock data path reappeared in panel v2: {found}"
    # The store must start with NO states at all — `{}` would make every read look like a
    # missing entity but would also make `if (!STORE.states)` false, defeating the
    # "нет соединения" branch.
    assert re.search(r"states:\s*null,", text), \
        "STORE.states must start as null (not {}), so 'no session yet' is distinguishable"


def test_no_screensaver_or_idle_regression():
    """The wall tablet must always show the control UI (owner requirement)."""
    code = _panel_code()
    for marker in ("showIdleScreen", "idle-screen", "screen-guard", "screensaver"):
        assert marker not in code, f"screensaver/idle marker present: {marker}"


# ------------------------------------------------------------------ 5. the honesty funnel
def test_paint_value_is_the_only_way_a_value_reaches_the_dom():
    text = _panel_text()
    assert "function paintValue(node, v) {" in text, "paintValue() is the honesty funnel; it must exist"
    # It must REFUSE a non-Val rather than coerce it.
    m = re.search(r"function paintValue\(node, v\) \{(.*?)\n\}", text, re.S)
    assert m, "could not isolate paintValue()"
    body = m.group(1)
    assert "throw new TypeError" in body, \
        "paintValue must THROW on a non-Val — that is what makes the guarantee structural"
    assert "isVal(v)" in body, "paintValue must test isVal()"
    assert "setAttr(node, 'data-kind', v.kind)" in body, \
        "paintValue must stamp data-kind so the audit can prove every slot was painted"
    # The tone (and therefore the colour) must be dropped for anything that is not real.
    assert "v.kind === 'real' ? (v.tone || 'neutral') : 'neutral'" in body, \
        "a non-real value must never carry a tone"


def test_only_real_values_can_be_coloured_by_css():
    """Belt and braces: even a caller mistake cannot paint an unreadable sensor green."""
    text = _panel_text()
    for tone in ("good", "warn", "bad"):
        rule = f'[data-kind="real"][data-tone="{tone}"]'
        assert rule in text, f"missing the gated colour rule {rule}"
        # There must be no ungated rule for the same tone.
        ungated = re.findall(r'(?<!\])\[data-tone="' + tone + r'"\]', text)
        assert not ungated, f'found an UNGATED [data-tone="{tone}"] colour rule: {ungated}'
    assert '[data-kind="unknown"]' in text, "unknown values need their own neutral style"
    assert '[data-kind="stale"]' in text, "stale values need their own style"


def test_the_value_kinds_are_exactly_the_documented_four():
    """real / stale / unknown / partial — and nothing else, ever.

    `partial` arrived in build 20260819-v2-sum-1. Until then any unreadable addend poisoned a
    whole sum, which deleted «ДОМ ПОТРЕБЛЯЕТ» from the wall the moment one of seven plugs went
    quiet — the house's normal state while the Tuya IoT Core trial quota is exhausted. A
    partial sum is still not a `real` whole-house figure, so it gets its own kind rather than
    being laundered into `real`; see the §3 comment block in the panel.
    """
    text = _panel_text()
    m = re.search(r"const Val = \{(.*?)\n\};", text, re.S)
    assert m, "could not isolate the Val factory table"
    kinds = set(re.findall(r"mkVal\('(\w+)'", text))
    assert kinds == {"real", "stale", "unknown", "partial"}, \
        f"the honesty renderer must know exactly real/stale/unknown/partial; found {sorted(kinds)}"
    # A partial value must be able to name what it left out, and must never be colourable.
    assert re.search(r"partial:\s*\(text, extra\) => mkVal\('partial'", text), \
        "Val.partial must take an extra bag (missing / of / stale)"
    assert '[data-kind="partial"]' in text, "partial values need their own visual treatment"
    ungated = re.findall(r'(?<!\])\[data-tone="(?:good|warn|bad)"\]', text)
    assert not ungated, f"an UNGATED tone colour rule appeared: {ungated}"


def test_a_sum_never_pretends_a_partial_total_is_the_whole():
    """vSum has exactly three outcomes and none of them is a bare zero for missing data."""
    text = _panel_text()
    m = re.search(r"function vSum\(vals, unit, dec, opt\) \{(.*?)\n\}", text, re.S)
    assert m, "vSum(vals, unit, dec, opt) is missing"
    body = m.group(1)
    assert "if (!have) return Val.unknown(" in body, \
        "with NO readable addend a sum must be unknown — never 0, which is a measurement"
    assert "if (miss.length) return Val.partial(" in body, \
        "with SOME readable addends a sum must be partial, carrying the names it left out"
    assert "missing: miss" in body and ("of," in body or "of:" in body), \
        "a partial sum must carry both the excluded names and the population size"
    assert "Val.real(txt, { num: total })" in body, \
        "only a complete sum may be real"


def test_the_partial_exclusion_is_rendered_next_to_the_number():
    """A caveat the owner cannot see is not a caveat. No tooltips on a wall panel."""
    text = _panel_text()
    assert "function missNote(" in text and "function missNoteShort(" in text, \
        "both forms of the exclusion note must exist (the two slots are 230 px and 90 px)"
    assert "function powerRoll(" in text, \
        "the house total must live in ONE place so the hero chip and the card header agree"
    # the hero chip prints the long form under the number...
    assert "powerSub: roll.note" in text, "the hero chip must print the exclusion note"
    # ...and the card header prints the short form on the number's own baseline
    assert "paintValue(totN, m.note)" in text, "the loads card header must print its note"
    assert "asideNote: true" in text, "the card header needs its note slot"
    # the partial title must spell out that it is not the whole house
    m = re.search(r"function partialWhy\(v\) \{(.*?)\n\}", text, re.S)
    assert m, "partialWhy() is missing"
    assert "это не показание по всему дому" in m.group(1), \
        "the title of a partial sum must say plainly that it is not the whole house"


def test_a_running_load_that_is_not_measured_is_excluded_and_named():
    text = _panel_text()
    m = re.search(r"function powerRoll\(rows\) \{(.*?)\n\}", text, re.S)
    assert m, "powerRoll() is missing"
    body = m.group(1)
    assert "if (r.stKind !== 'real') { miss.push(r.short); continue; }" in body, \
        "a load whose on/off state is unreadable must be excluded and named"
    assert "if (r.on !== true) continue;" in body, \
        "a readably-OFF load contributes nothing and is NOT an exclusion"
    assert "if (!contrib.length)" in body and "Val.unknown(" in body, \
        "with nothing running measured the answer must be «нет данных», never «0 Вт»"
    assert "Val.real(t, { tone: 'neutral' })" in body or "neutral('0 Вт')" in body, \
        "a house that is genuinely all-off still reports 0 Вт — there zero IS the measurement"


# ------------------------------------------------------------------ the Tuya outage line
def test_the_tuya_line_is_derived_from_live_state_with_hysteresis():
    """One calm line, no hardcoded flag, and it must clear itself when the cloud returns."""
    text = _panel_text()
    assert "function tuyaTick()" in text and "function tuyaState()" in text, \
        "the Tuya verdict must be a computed function, not a stored flag"
    assert re.search(r"const TUYA_CLOUD_DARK_S = 1800;", text), \
        "«no answer straight from the cloud for 30 min» is the direct-probe threshold"
    assert re.search(r"const TUYA_DARK_ON\s*=\s*0\.25;", text) and \
           re.search(r"const TUYA_DARK_OFF\s*=\s*0\.12;", text), \
        "the census share needs a DEAD BAND (on at 25 %, off below 12 %) or it blinks"
    assert re.search(r"const TUYA_DWELL_MS = 120000;", text), \
        "a changed verdict must dwell before it commits"
    assert "t.cloudSrc === 'error'" in text and "t.cloudSrc === 'cache' && t.cloudAge != null" in text, \
        "the direct probe must read cloud_src / cloud_age_sec off the leak truth entity"
    # `cache` alone is healthy behaviour (the query script re-serves its own answer for 20 s).
    assert "t.cloudAge > TUYA_CLOUD_DARK_S" in text, \
        "a fresh cache answer must NOT be reported as an outage"
    # It must not invent an outage out of a house that lost an entity from the registry.
    assert "if (!e) continue;" in text, \
        "an entity missing from hass must be skipped, not counted as dark"
    # And it must never touch the leak verdict.
    m = re.search(r"function tuyaTick\(\) \{(.*?)\n\}", text, re.S)
    assert "leakVerdict" not in m.group(1), "the Tuya line must not re-derive the leak verdict"


def test_the_tuya_line_yields_to_leak_and_smoke():
    text = _panel_text()
    assert "leakVerdict() !== 'leak' && rawState(SMOKE_ID) !== 'on'" in text, \
        "precedence is leak -> smoke -> everything else: the Tuya line steps aside during an alarm"
    assert "setCls(bar, 'cloudy', !!m.cloud);" in text, \
        "the top bar must only re-flow while the line is actually shown"
    assert ".topbar.cloudy .tb-cloud{display:block}" in text, \
        "the notice is display:none unless the verdict is on, so a healthy panel is unchanged"
    assert ".safety-note" not in text, \
        "the notice must NOT live in the safety strip: its 84 px are spoken for by the leak "\
        "tile's three lines, which are needed exactly when the cloud is down (blind + outage)"


# ------------------------------------------------------------------ the hero photographs
def test_hero_image_paths_exist_in_exactly_one_place():
    """Build 20260819-v2-sum-1: adding a daytime photograph must be a one-constant change."""
    text = _panel_text()
    assert "const HERO_IMG_DAY     = null;" in text, \
        "день ships photo-less; the constant is the seam for dropping a real render in later"
    assert re.search(r"const HERO_IMG = \{ day: HERO_IMG_DAY, evening: HERO_IMG_EVENING, night: HERO_IMG_NIGHT \};", text), \
        "the three constants must be the single source of truth for the hero images"
    # the CSS must carry no url() for the hero any more
    # 2026-08-24: both renders were recompressed to JPEG (1.6 MB -> 160 KB each) because the
    # tablet decodes them on every boot. The guard still pins TWO renders named in exactly one
    # place; only the extension moved.
    assert "home-hero-evening.jpg'" in text and "home-hero-orbital.jpg'" in text, \
        "the two shipped renders must still be referenced by the constants"
    css_urls = re.findall(r"url\('/local/assets/home-hero[^']*'\)", text)
    assert not css_urls, f"a hero image URL leaked back into the CSS: {css_urls}"
    assert "function applyHeroImage()" in text, "the image must be applied from the tier, once"
    assert "setCls(HERO_NODE, 'flat', !url)" in text, \
        "a tier with no image must degrade into the designed photo-less treatment"
    assert ".hero:not(.flat){" in text, \
        "the light-on-photograph palette must be pinned ONLY where there is a photograph"
    assert ".hero.flat{background:" in text, "the photo-less hero needs its own ground"
    # and the settings screen must say so in one line
    assert "HERO_IMG_DAY" in text and "рисованный" in text, \
        "Настройки must state that день is drawn and how to give it a photograph"


# ------------------------------------------------------------------ 6. the leak contract
def test_leak_truth_is_the_single_source():
    text = _panel_text()
    assert "const LEAK_TRUTH = 'sensor.leak_protection_status';" in text, \
        "the leak verdict must come from sensor.leak_protection_status"
    assert "a.per_sensor" in text or "a.per_sensor &&" in text, "per_sensor must be read"
    assert "blind_names" in text and "leak_names" in text, \
        "the named leak/blind lists must come from HA, not be re-derived"
    # The individual moisture sensors must never appear as a verdict source.
    for moisture in ("binary_sensor.vannaia_moisture", "binary_sensor.garazh_moisture",
                     "binary_sensor.kukhnia_moisture", "binary_sensor.water_sensor_4_moisture"):
        assert moisture not in text, (
            f"panel v2 references {moisture} directly — the leak verdict must come ONLY from "
            "sensor.leak_protection_status (see docs + tests/test_leak_truth.py)"
        )


def test_no_staleness_rule_is_applied_to_the_leak_sleepers():
    """The 4 moisture sensors report only on wet/dry events; silence is normal.

    A per-UI age rule for them produced a permanent false «защита работает вслепую» once
    already. v2 applies TTLs only to periodic numeric telemetry, and the leak truth entity
    must not be among them.
    """
    text = _panel_text()
    # vLeak() must not consult ageSec() at all.
    m = re.search(r"function vLeak\(\) \{(.*?)\n\}", text, re.S)
    assert m, "vLeak() is missing"
    assert "ageSec" not in m.group(1), "vLeak() must not apply a staleness rule"
    assert "LEAK_TTL" not in text, "there must be no TTL constant for the leak truth entity"
    # And the TTLs that DO exist must be the three telemetry ones only.
    ttls = set(re.findall(r"const (\w+_TTL)\s*=", text))
    assert ttls == {"PRICE_TTL", "ROOM_TTL", "POWER_TTL"}, \
        f"unexpected staleness budgets defined: {sorted(ttls)}"


# ------------------------------------------------------------------ the action contract
def test_commands_are_verified_by_reading_the_state_back():
    text = _panel_text()
    m = re.search(r"async function commandVerified\(opts\) \{(.*?)\n\}", text, re.S)
    assert m, "commandVerified() — the send/await/re-read contract — is missing"
    body = m.group(1)
    assert "refreshStates()" in body, "the contract must RE-READ state after sending"
    assert "rawState(entityId) === expect" in body, "the read-back must compare against the expected state"
    assert "verified ? okMsg" in body, "success may only be claimed when the read-back confirms"
    assert "проверьте вручную" in body, \
        "an unverified command must SAY so plainly instead of claiming success"
    assert re.search(r"const VERIFY_TRIES = 6, VERIFY_GAP_MS = 700;", text), \
        "the read-back budget must stay 6 x 700 ms (~4 s), as in the old panel"


def test_closing_the_water_is_one_tap_plus_one_confirmation():
    """The whole point of the safety strip: the old panel needed 4 taps behind «Ещё»."""
    text = _panel_text()
    assert "btn.id = 'closeWaterBtn';" in text, "the one-tap water button must exist"
    assert "btn.addEventListener('click', askCloseWater)" in text, \
        "the button must go straight to the confirmation, with nothing in between"
    m = re.search(r"function askCloseWater\(\) \{(.*?)\n\}", text, re.S)
    assert m, "askCloseWater() is missing"
    body = m.group(1)
    assert "openModal({" in body, "closing the water must require an explicit confirmation"
    assert "commandVerified({" in body, "the close must go through the verification contract"
    assert "service: 'turn_off'" in body and "VALVE_ID" in body, \
        "the confirmation must close the valve"
    # The strip lives outside the screen container, so it is on every screen by construction.
    assert "app.appendChild(safety.node);" in text and "app.appendChild(screens);" in text, \
        "the safety strip must be a sibling of the screens, not inside one"
    idx_safety = text.index("app.appendChild(safety.node);")
    idx_screens = text.index("app.appendChild(screens);")
    assert idx_safety < idx_screens, "the safety strip must be mounted above the screens"


def test_no_close_path_ever_reopens_the_valve():
    """Safety invariant shared with tests/test_water_safety.py: the valve is opened by hand."""
    text = _panel_text()
    m = re.search(r"function askCloseWater\(\) \{(.*?)\n\}", text, re.S)
    assert "turn_on" not in m.group(1), "the close path must never issue switch.turn_on on the valve"
    # v2 deliberately offers no "open the water" button at all.
    assert "openWater" not in text, "panel v2 must not offer a one-tap valve OPEN"


# ------------------------------------------------------------------ theme resolution
def test_theme_has_three_tiers_with_hysteresis_and_a_manual_override():
    text = _panel_text()
    assert re.search(r"const THEME_LABEL = \{ day: 'день', evening: 'вечер', night: 'ночь' \};", text), \
        "the three tiers must stay день / вечер / ночь"
    assert re.search(r"const THEME_DWELL_MS = 120000;", text), \
        "the dwell time that prevents oscillation must stay 120 s"
    assert re.search(r"const ILLUM_MAX_AGE_S = 1800;", text), \
        "an illuminance reading older than 30 min must not drive the theme"
    assert "sun.sun" in text, "sun.sun must be the second source"
    assert "'часы'" in text, "the clock must be the final fallback"
    # Every illuminance source needs its own dead band (the two sensors are on different scales).
    m = re.search(r"const ILLUM_SOURCES = \[(.*?)\];", text, re.S)
    assert m, "ILLUM_SOURCES is missing"
    srcs = m.group(1)
    assert srcs.count("dayOn:") == srcs.count("dayOff:") >= 2, \
        "each illuminance source must declare BOTH dayOn and dayOff (the hysteresis dead band)"
    assert "themeMode" in text and "'auto', 'light', 'dark', 'night'" in text, \
        "the manual override must offer авто / светлая / тёмная / ночь and be persisted"


def test_render_models_carry_no_continuously_varying_field():
    """«Render only what changed» is defeated by any field that ticks every millisecond.

    The component skip test is JSON.stringify(model); putting a live age into a `real`
    Val silently made every model different on every frame. Guard the fix.
    """
    text = _panel_text()
    m = re.search(r"return Val\.real\(txt, \{ num: n, tone:([^}]*)\}\);", text)
    assert m, "could not find vNum()'s real-value return"
    assert "age" not in m.group(1), \
        "a `real` Val must not carry the live age — it would defeat the render-skip test"


# ------------------------------------------------------------------ 7. the control IA
# Build 20260817-v2-ctl-1 restructured the navigation after the owner asked «ну а где кнопки
# управления светом, розетками, устройствами, автоматизации и так далее?». Two of those
# answers are safety-critical and must not be able to rot back out of the file.
LIFE_SAFETY_AUTOMATION_IDS = {
    "1748000001001": "утечка воды v4 (entity_id — легаси automation.ha_startup_grace_period)",
    "1789600001001": "утечка по облаку Tuya — независимая проверка",
    "1779200002001": "задымление — сирена",
    "1779200003001": "охрана — тревога",
    "1789300001001": "сторож сирены",
    "1790000001001": "сторож крана воды",
    "1790000001002": "сторож зависших состояний Tuya",
    "1790200001001": "Tuya: авто-лечение sign invalid",
    "1789400001001": "сторож котла (АВАРИЯ)",
    "1789800001001": "сторож термостатов тёплого пола",
}
# Deliberately disabled in automations.yaml via `initial_state: false`. See
# tests/test_leak_truth.py and the memory notes: v2 doubled the siren on one leak, and the
# recirculation automation was killing the aquarium filter.
LOCKED_AUTOMATION_IDS = {"1775638334800", "1789000001001"}


def test_nav_has_five_destinations_and_upravlenie_replaced_komnaty():
    """«Комнаты» was read by the owner as "not control"; it is now a lens, not a slot."""
    text = _panel_text()
    m = re.search(r"const NAV = \[(.*?)\n\];", text, re.S)
    assert m, "the NAV table is missing"
    nav = m.group(1)
    labels = re.findall(r"\[\s*'(\w+)',\s*'([^']+)'", nav)
    keys = [k for k, _ in labels]
    names = [n for _, n in labels]
    assert keys == ["home", "control", "climate", "energy", "security"], \
        f"the five destinations must be home/control/climate/energy/security; got {keys}"
    assert names == ["Дом", "Управление", "Климат", "Энергия", "Безопасность"], \
        f"nav wording drifted: {names}"
    assert "'Комнаты'" not in nav, "«Комнаты» must not occupy a nav slot any more"
    # …but room browsing must still exist, as a lens inside «Управление».
    assert "'По типам'" in text and "'По комнатам'" in text, \
        "the «По типам / По комнатам» lens is the only place room browsing survives"
    assert "buildRoomsGrid()" in text, "the room cards must still be built"


def test_control_landing_signposts_every_category():
    text = _panel_text()
    m = re.search(r"const CAT_LANDING = \[(.*?)\];", text, re.S)
    assert m, "CAT_LANDING (the category board order) is missing"
    keys = re.findall(r"'([a-z_]+)'", m.group(1))
    required = ["light", "load", "climate", "media", "scene", "script", "mode", "automation", "other"]
    missing = [k for k in required if k not in keys]
    assert not missing, f"the category board must signpost at least {required}; missing {missing}"
    for label in ("'Свет'", "'Розетки'", "'Климат'", "'Медиа'", "'Сцены'", "'Сценарии'",
                  "'Режимы'", "'Автоматизации'", "'Прочее'"):
        assert label in text, f"a category tile must be labelled {label} in plain Russian"
    # the catch-all must stay LAST and must stay unconditional
    mg = re.search(r"const CAT_GROUPS = \[(.*?)\n\];", text, re.S)
    assert mg, "CAT_GROUPS is missing"
    groups = re.findall(r"\{ key: '(\w+)'", mg.group(1))
    assert groups[-1] == "other", f"the catch-all group must stay last; got {groups}"
    assert re.search(r"key: 'other',.*?test: \(\) => true", mg.group(1), re.S), \
        "the catch-all group's test must stay unconditional, so coverage cannot silently drop"


def test_automations_are_enumerated_from_hass_not_hand_listed():
    text = _panel_text()
    assert re.search(r"function autoList\(\)", text), "autoList() must exist"
    m = re.search(r"function autoList\(\) \{(.*?)\n\}", text, re.S)
    body = m.group(1)
    assert "Object.keys(STORE.states)" in body and "'automation'" in body, \
        "the automation list must be enumerated from hass"
    # the honest never-fired wording, and it must be a REAL value, not a fabricated date
    assert "'не срабатывала'" in text, "an automation that never fired must say «не срабатывала»"
    ml = re.search(r"function vAutoLast\(id\) \{(.*?)\n\}", text, re.S)
    assert ml, "vAutoLast() is missing"
    lb = ml.group(1)
    assert "last_triggered" in lb, "the last-triggered value must come from the attribute"
    assert "Val.real('не срабатывала'" in lb, "«не срабатывала» is a fact and must be a real Val"
    assert "Val.unknown('автоматизация недоступна')" in lb, \
        "an unavailable automation must be unknown, never «не срабатывала»"


def test_life_safety_automations_are_resolved_by_id_and_named():
    """Resolved by the `id` ATTRIBUTE — the leak-v4 slug lies about what it is."""
    text = _panel_text()
    m = re.search(r"const AUTO_SAFE = \{(.*?)\n\};", text, re.S)
    assert m, "AUTO_SAFE (the life-safety table) is missing"
    body = m.group(1)
    for ida, what in LIFE_SAFETY_AUTOMATION_IDS.items():
        assert f"'{ida}'" in body, f"life-safety automation {ida} ({what}) is not protected"
    # each entry must carry a sentence that says what it protects
    entries = re.findall(r"'(\d+)':\s*'([^']+)'", body)
    assert len(entries) >= len(LIFE_SAFETY_AUTOMATION_IDS)
    for ida, note in entries:
        assert len(note) > 25, f"the consequence text for {ida} is too short to be useful: {note!r}"
    # resolution is by attribute, never by entity_id slug
    ma = re.search(r"function autoId\(e\) \{(.*?)\n\}", text, re.S)
    assert ma and "attributes.id" in ma.group(1), "autoId() must read attributes.id"
    assert "automation.ha_startup_grace_period" not in _panel_code(), \
        "the leak-v4 automation must never be matched by its misleading slug in CODE"


def test_deliberately_disabled_automations_cannot_be_re_enabled_by_a_stray_tap():
    text = _panel_text()
    m = re.search(r"const AUTO_LOCKED = \{(.*?)\n\};", text, re.S)
    assert m, "AUTO_LOCKED (the initial_state:false table) is missing"
    body = m.group(1)
    for ida in LOCKED_AUTOMATION_IDS:
        assert f"'{ida}'" in body, f"deliberately-disabled automation {ida} is not marked"
    assert "намеренно" in body, "the lock explanation must say the automation is off on purpose"
    # the toggle path must confirm before enabling a locked automation, and before disabling
    # a life-safety one
    mt = re.search(r"function autoToggle\(id\) \{(.*?)\n\}", text, re.S)
    assert mt, "autoToggle() is missing"
    tb = mt.group(1)
    assert "autoIsLocked(e)" in tb and "openModal({" in tb, \
        "enabling a locked automation must open a confirmation"
    assert "autoIsSafe(e)" in tb, "disabling a life-safety automation must be recognised"
    assert tb.count("openModal({") >= 2, \
        "both classes (locked-on and safety-off) need their own confirmation"
    assert "AUTO_LOCKED[autoId(e)]" in tb and "AUTO_SAFE[autoId(e)]" in tb, \
        "each confirmation must quote the reason/consequence text, not a generic warning"
    # and the row must be marked on screen, not only in the dialog
    assert "'отключена намеренно'" in text, "a locked automation must be labelled on screen"
    assert "setCls(r.row, 'locked'" in text and "setCls(r.row, 'safe'" in text, \
        "both classes must be marked on the row itself"


def test_running_an_automation_by_hand_always_confirms_and_never_claims_success():
    """`automation.trigger` is the one tap that can move hardware with nothing to read back."""
    text = _panel_text()
    m = re.search(r"function autoRun\(id\) \{(.*?)\n\}", text, re.S)
    assert m, "autoRun() is missing"
    body = m.group(1)
    assert "openModal({" in body, "«Запустить» must always confirm first"
    assert "service: 'trigger'" in body, "«Запустить» must call automation.trigger"
    assert "onOk" in body and body.index("openModal({") < body.index("service: 'trigger'"), \
        "the service call must live INSIDE the confirmation handler"
    assert "условия проверяться не будут" in body, \
        "the dialog must say that the automation's own conditions are skipped"
    assert "результат панель проверить не может" in body, \
        "a triggered automation has no state to read back and the toast must admit it"
    # trigger must not appear anywhere else in the file
    assert len(re.findall(r"service: 'trigger'", text)) == 1, \
        "automation.trigger must have exactly one call site, inside autoRun()"


def test_server_diagnostics_exist_but_get_no_nav_slot():
    text = _panel_text()
    assert "const SRV_ROWS = [" in text, "the server/Proxmox diagnostics table is missing"
    assert "'Сервер и Proxmox'" in text, "the diagnostics card must be labelled"
    assert "binary_sensor.mylab_status" in text, "the Proxmox node status must be shown"
    # it lives on the settings screen, which is reached from the gear, not from the dock
    m = re.search(r"const NAV = \[(.*?)\n\];", text, re.S)
    assert "settings" not in m.group(1), "Настройки must stay behind the gear"
    assert "'server'" not in m.group(1) and "'diag'" not in m.group(1), \
        "diagnostics must not take a nav slot"
    # and there must be no control on that card
    m2 = re.search(r"const \{ card: c3, body: b3 \} = card\('Сервер и Proxmox'\);(.*?)wrap\.appendChild\(c3\);",
                   text, re.S)
    assert m2, "could not isolate the server card construction"
    assert "wireControl" not in m2.group(1) and "button" not in m2.group(1), \
        "the server card is diagnostic: it must carry no button at all"


def test_service_screen_links_to_the_read_only_electrical_map():
    text = _panel_text()
    assert "'/local/electrical-map/index.html'" in text
    assert "'Карта электрощитка'" in text
    assert "target = '_blank'" in text and "rel = 'noopener'" in text
    assert "AUTO_PAGE = 6" in text, "two-line automation names need the readable 2x3 layout"
    assert "-webkit-line-clamp:3" in text, "safety provenance must have room for three lines"


# ------------------------------------------------------------------ secrets
def test_the_panel_embeds_no_secret():
    """v2 authenticates through the injected hass session; nothing may be baked in.

    This file is TRACKED (unlike v1's panel, which is gitignored precisely because
    deployed builds embedded bearer tokens), so the no-secret property has to hold by
    construction rather than by exclusion. Note the deny-list below carries no real
    credential of its own — a test that names a live password would itself be the leak.
    """
    text = _panel_text()
    for needle in ("eyJhbGciOi", "Bearer ", "?token=", "tablet_token", "access_token",
                   "long_lived", "secrets.yaml", "supervisor_token"):
        assert needle not in text, f"possible secret material in panel v2: {needle!r}"
    # Anything JWT-shaped, whatever it is called.
    jwt = re.search(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}", text)
    assert not jwt, f"JWT-shaped string in panel v2 at offset {jwt.start() if jwt else -1}"
    # No hard-coded credential assignment of any kind.
    cred = re.search(r"(?i)(password|passwd|api[_-]?key|secret)\s*[:=]\s*['\"][^'\"]{6,}", text)
    assert not cred, f"credential-shaped assignment in panel v2: {cred.group(0)[:40]!r}"
    assert "callService" in text and "Authorization" not in text, \
        "transport must be hass.callService, never a hand-built Authorization header"
