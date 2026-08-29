"""Server (Proxmox) dashboard — read-only guarantees + declarative-model coverage.

The Server screen in tablet/tablet-panel.js must render Proxmox infrastructure
STRICTLY read-only. These tests statically enforce the invariants that matter:

  1. It NEVER references a proxmox ``button.*`` control entity.
  2. Its render code issues NO service call / onclick (no control surface at all).
  3. Thresholds live in ONE declarative config object (PROXMOX.th), not scattered.
  4. Missing / unknown values map to «нет данных», never a fabricated 0.
  5. The Server view is wired into the nav + render pipeline.

They read the shipped source directly (no browser needed), which is enough to
catch a regression that would turn the read-only screen into a control surface.
"""
from pathlib import Path
import re

REPO = Path(__file__).resolve().parent.parent
PANEL = REPO / "tablet" / "tablet-panel.js"


def _src() -> str:
    return PANEL.read_text(encoding="utf-8")


def _server_module(src: str) -> str:
    """The Server module: from its banner comment up to boot()."""
    start = src.index("// SERVER (Proxmox infrastructure)")
    end = src.index("function boot(){", start)
    return src[start:end]


def test_panel_exists():
    assert PANEL.exists(), "tablet-panel.js must exist"


def test_server_view_wired_into_nav_and_render():
    src = _src()
    assert "['server','Server','server']" in src, "Server item missing from NAV"
    assert 'id=\\"view-server\\"' in src, "view-server container missing from markup"
    assert "function renderServer()" in src, "renderServer() not defined"
    # renderServer must be invoked from the central render() dispatcher
    render_fn = src[src.index("function render(){"): src.index("function render(){") + 400]
    assert "renderServer()" in render_fn, "renderServer() not called from render()"


def test_no_proxmox_button_entity_referenced():
    """None of the real proxmox button.* control entities may appear in the panel.

    Checked against the inventory so CSS selectors like ``button.on`` don't
    false-positive — only genuine control entity ids are forbidden.
    """
    import json
    src = _src()
    inv = json.loads((REPO / "docs" / "audit" / "proxmox_inventory.json").read_text("utf-8"))
    button_ids = [e["entity_id"] for e in inv["entities"] if e["entity_id"].startswith("button.")]
    assert button_ids, "inventory should list proxmox button entities to guard against"
    leaked = [b for b in button_ids if b in src]
    assert leaked == [], f"proxmox control button(s) referenced in panel: {leaked}"
    # also: no control-verb button entity id pattern (underscore form) anywhere
    verb = re.findall(r"button\.[a-z0-9]+_(?:start|stop|restart|reset|shut_down|hibernate|"
                      r"create_snapshot|start_all|stop_all|suspend_all)\b", src)
    assert verb == [], f"proxmox control-verb button referenced: {verb}"


def test_server_module_has_no_control_surface():
    """The Server module must not call a service or wire any click handler."""
    seg = _server_module(_src())
    # strip comment lines so the doc-comment's own words don't trip the check
    code = "\n".join(l for l in seg.splitlines() if not l.lstrip().startswith("//"))
    for forbidden in ("callService", "onclick", "svc(", "toggleEntity", "button."):
        assert forbidden not in code, f"read-only violation: '{forbidden}' in Server module"


def test_thresholds_in_single_config_object():
    seg = _server_module(_src())
    assert "const PROXMOX = {" in seg, "declarative PROXMOX model missing"
    assert re.search(r"\bth:\s*\{", seg), "PROXMOX.th threshold object missing"
    for key in ("cpu:", "ram:", "storage:", "backupStaleH:", "metricStaleMin:"):
        assert key in seg, f"threshold '{key}' not in the single config object"
    # thresholds must not be hard-coded as magic numbers in the level helper
    assert "function pxLevel(v, t)" in seg, "pxLevel must take the threshold object as a param"


def test_unknown_maps_to_nd_not_zero():
    """pxNum returns null (→ «нет данных») for unknown/unavailable/empty, never 0."""
    seg = _server_module(_src())
    m = re.search(r"function pxNum\(id\)\s*\{[^}]*\}", seg)
    assert m, "pxNum accessor not found"
    body = m.group(0)
    assert "'unavailable'" in body and "'unknown'" in body, "pxNum must reject unavailable/unknown"
    assert "return null" in body, "pxNum must return null for missing values"
    # the «нет данных» sentinel exists and is used
    assert "нет данных" in seg, "missing «нет данных» sentinel"
    assert "function pxNd(" in seg, "pxNd() helper missing"


def test_resources_discovered_by_pattern_not_hardcoded():
    """Guests/nodes/storages are iterated by regex, so a rescan surfaces new ones."""
    seg = _server_module(_src())
    assert "function pxDiscover()" in seg, "pattern-based discovery missing"
    assert "reCpu" in seg and "reStorage" in seg, "discovery regexes missing"
    assert "for (const id in S)" in seg, "must iterate the live state map"


def test_intentionally_stopped_template_is_neutral():
    seg = _server_module(_src())
    assert "reTemplate" in seg, "template-name rule missing"
    assert "остановлена (шаблон)" in seg, "intentionally-stopped guests must read neutrally"


def test_inactive_storage_not_shown_as_zero():
    seg = _server_module(_src())
    # inactive storage renders «неактивно», never 0%
    assert "неактивно" in seg, "inactive storage must render «неактивно»"


# --------------------------------------------------------------------------
# History charts + storage-fill forecast (extension) — still strictly read-only
# --------------------------------------------------------------------------

def test_history_is_fetched_read_only_via_get():
    """Charts pull recorder history with an authenticated GET — never a service call."""
    seg = _server_module(_src())
    assert "function pxLoadHistory()" in seg, "history loader missing"
    assert "'history/period/'" in seg, "must query the recorder history endpoint"
    assert "HASS.callApi('GET'" in seg, "history must be a read-only GET via callApi"
    # the no-control-surface test already forbids callService/onclick/svc(/button.
    # here we double-check the loader itself does not mutate state
    assert "callService" not in seg, "history loader must not call a service"


def test_history_request_passes_end_time():
    """Without end_time HA defaults end=start+1d, so a 7d-ago start returns an empty
    slice on a young recorder. The request MUST pin end_time to now."""
    seg = _server_module(_src())
    assert "end_time=" in seg, "history request must pass end_time (else empty on young recorder)"


def test_range_toggle_has_no_inline_onclick():
    """The 24h/7d toggle must be data-driven (delegated listener), not an onclick."""
    seg = _server_module(_src())
    assert "data-px-range" in seg, "range toggle must use a data attribute"
    assert "function pxSetHistRange(" in seg, "range setter missing"
    # (no_control_surface test already asserts 'onclick' absent in the whole module)


def test_insufficient_and_noisy_forecast_never_invented():
    seg = _server_module(_src())
    assert "function pxForecast(" in seg and "function pxLinFit(" in seg, "forecast helpers missing"
    assert "недостаточно данных" in seg, "must have a «недостаточно данных» fallback"
    for kind in ("insufficient", "noisy", "stable", "inactive"):
        assert "'" + kind + "'" in seg, f"forecast branch '{kind}' missing"
    # a real R^2 gate must exist so noisy trends do not produce a fake projection
    assert "r2 <" in seg, "forecast must reject low-R² (noisy) trends"


def test_empty_or_sparse_series_shows_placeholder_not_fake_chart():
    seg = _server_module(_src())
    assert "pts.length < 2" in seg, "a sparse series must fall back to a placeholder"
    assert "Недостаточно данных" in seg, "sparse chart must read «Недостаточно данных»"


def test_ram_cache_and_swap_annotations_present():
    """Task 3: RAM % may include cache — annotate, and note swap/OOM is not measured."""
    src = _src()
    assert "вкл. кеш" in src, "RAM must be annotated as including Linux cache"
    assert "Своп / OOM" in src or "своп/OOM" in src, "swap/OOM-not-measured note missing"


def test_charts_use_inline_svg_no_external_libs():
    seg = _server_module(_src())
    assert "function pxChartSvg(" in seg, "inline-SVG chart renderer missing"
    assert "<svg" in seg and "<polyline" in seg, "charts must be self-contained inline SVG"
