"""Server-view history fetch layer — TTL cache + in-flight dedup + supersede abort.

The Server screen's recorder-history sparklines must be efficient AND still
strictly read-only:

  * one authenticated GET, cached per (window|entity-set) with a TTL;
  * re-renders and 24ч↔7д toggles within TTL do NOT refetch;
  * concurrent requests for the same key are de-duplicated (single-flight);
  * a superseded / left-view request is aborted and its late result discarded;
  * after the TTL the next ensure refetches.

Static assertions below pin the mechanism into the source. The behavioral proof
(cache hit, dedup, abort, TTL expiry) runs the REAL extracted code through the
Node harness ``docs/audit/server_dashboard/cache_harness.mjs``.
"""
from pathlib import Path
import shutil
import subprocess

import pytest

REPO = Path(__file__).resolve().parent.parent
PANEL = REPO / "tablet" / "tablet-panel.js"
HARNESS = REPO / "docs" / "audit" / "server_dashboard" / "cache_harness.mjs"


def _src() -> str:
    return PANEL.read_text(encoding="utf-8")


def _server_module(src: str) -> str:
    start = src.index("// SERVER (Proxmox infrastructure)")
    end = src.index("function boot(){", start)
    return src[start:end]


# ----------------------------- static invariants -----------------------------

def test_single_ttl_config_object_with_both_ranges():
    seg = _server_module(_src())
    assert "const PX_HIST_CFG = {" in seg, "TTL/window config must live in ONE object"
    for key in ("TTL_SHORT:", "TTL_LONG:", "WINDOW_H:", "TTL_CUTOFF_H:"):
        assert key in seg, f"config key '{key}' missing from PX_HIST_CFG"
    assert "function pxTtlFor(hours)" in seg, "per-range TTL selector missing"


def test_cache_factory_present_with_dedup_and_abort():
    seg = _server_module(_src())
    assert "function pxMakeHistCache(" in seg, "generic history cache factory missing"
    # single-flight dedup: a pending promise is reused
    assert "e.loading && e.promise) return e.promise" in seg, "single-flight dedup missing"
    # cache hit within TTL short-circuits before any fetch
    assert "if (fresh(e)) return Promise.resolve(e)" in seg, "TTL cache-hit path missing"
    # AbortController per fetch + supersede/leave abort
    assert "AbortController" in seg, "must use AbortController for cancellation"
    assert "function abortAll(" in seg and "function abortKey(" in seg, "abort helpers missing"
    # late/aborted responses must not write state
    assert "if (ctrl.signal.aborted) return e" in seg, "aborted-response state guard missing"


def test_history_still_read_only_get_with_end_time():
    seg = _server_module(_src())
    assert "async function pxFetchHistory(" in seg, "the fetch worker must exist"
    assert "HASS.callApi('GET'" in seg, "history must be a read-only GET"
    assert "'history/period/'" in seg, "must query recorder history endpoint"
    assert "end_time=" in seg, "end_time must be pinned (else empty on young recorder)"
    assert "callService" not in seg, "no service call anywhere in the Server module"


def test_placeholder_states_preserved():
    seg = _server_module(_src())
    assert "Загрузка…" in seg, "«Загрузка…» first-load placeholder must remain"
    assert "История недоступна" in seg, "«История недоступна» error state must remain"
    assert "Недостаточно данных" in seg, "«Недостаточно данных» sparse state must remain"


def test_offview_fetch_guard_and_leave_view_abort():
    src = _src()
    seg = _server_module(src)
    # history is only pulled while the Server view is visible
    assert "if (currentView === 'server') pxHistEnsure()" in seg, \
        "history must only be fetched while the Server view is active"
    # leaving the Server view aborts in-flight fetches
    assert "currentView==='server' && id!=='server'" in src and "pxHistStore.abortAll()" in src, \
        "leaving the Server view must abort in-flight history GETs"


def test_toggle_still_client_side_no_refetch():
    seg = _server_module(_src())
    assert "function pxSetHistRange(" in seg, "range setter missing"
    assert "no refetch" in seg, "range toggle must re-slice client-side (documented no-refetch)"


# --------------------------- behavioral proof (Node) -------------------------

def test_cache_harness_passes():
    """Runs the extracted real cache code: cache-hit/dedup/abort/TTL-expiry."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    assert HARNESS.exists(), "cache harness missing"
    r = subprocess.run([node, str(HARNESS)], capture_output=True, text=True, cwd=str(REPO))
    assert r.returncode == 0, f"cache harness failed:\n{r.stdout}\n{r.stderr}"
    assert "ALL CHECKS PASSED" in r.stdout
    assert "FAIL" not in r.stdout
