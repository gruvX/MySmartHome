"""Reachability regression test for the classic tablet panel (tablet/tablet-panel.js).

Guards the P1 fix for the pkg3 densification bug where views became fixed-height
fit-screens (`.view{overflow:hidden}` + `.view>.grid{height:100%}`), so any content
taller than the viewport was CLIPPED with no way to scroll to it — the bottom of the
screen was unreachable.

For every screen, at each required tablet size, in the normal / attention / critical /
unavailable / long-message states, this test asserts:

  (a) the scroll container scrolls to its true bottom (scrollTop + clientHeight >=
      scrollHeight - 2),
  (b) the bottom-sentinel (``.view-end[data-sentinel]``, appended by ensureSentinels())
      is present and fully inside the scroll viewport once scrolled to the bottom,
  (c) the last interactive control can be scrolled fully into view (clickable),
  (d) NO in-flow content is clipped by an ``overflow:hidden`` ancestor
      (no non-scroll element has scrollHeight > clientHeight), and
  (e) there is no horizontal overflow.

A deliberately short viewport tier is included so the fit-screen regression, which only
bites once content exceeds the viewport, is actually exercised (headless font metrics are
more compact than the device, so the nominal sizes alone would not force overflow).

The test needs Playwright + a Chromium build; it SKIPS cleanly when either is absent, so
it stays safe on a bare CI runner. It never touches the real HA instance — states come
from a scrubbed fixture and all outbound fetches are stubbed.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import http.server
import socketserver
import threading
import functools
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[1]
PANEL = REPO / "tablet" / "tablet-panel.js"
FIXTURE = REPO / "tests" / "fixtures" / "tablet_states.json"

# Every screen reachable via setView() that renders scrollable content.
VIEWS = ["home", "control", "scenes", "heat", "energy",
         "security", "automations", "service", "server"]

# Required tablet sizes + one short tier that forces the fit-screen to overflow.
SIZES = [
    ("1280x800", 1280, 800),
    ("1024x768", 1024, 768),
    ("1366x768", 1366, 768),
    ("1024x560", 1024, 560),   # stress: forces overflow so the regression is exercised
]

_LONG = ("Очень длинное сообщение об аварии, которое должно переноситься на несколько "
         "строк и растягивать карточку по высоте: датчик протечки в подвале сработал, "
         "требуется немедленно перекрыть главный кран воды и проверить насосную группу, "
         "бойлер и рециркуляцию горячей воды, а также осмотреть пол в котельной и коридоре.")


def _s(state, **attrs):
    return {"state": state, "attributes": attrs}


SCENARIOS = {
    "normal": {},
    "attention": {
        "binary_sensor.door_sensor_door": _s("on"),
        "input_boolean.security_armed": _s("off"),
        "sensor.nord_pool_lv_current_price": _s("0.185"),
        "sensor.ev_charger_status": _s("quota_error"),
    },
    "critical": {
        "binary_sensor.wifi_th_smoke_sensor_smoke": _s("on"),
        # the single source of truth must agree with the raw sensors it summarises
        "sensor.leak_protection_status": _s("leak", per_sensor={
            "binary_sensor.vannaia_moisture": "leak", "binary_sensor.garazh_moisture": "leak",
            "binary_sensor.kukhnia_moisture": "dry", "binary_sensor.water_sensor_4_moisture": "dry"},
            leak_names=["Ванная", "Гараж"], blind_names=[], cloud_src="cloud", cloud_age_sec=12),
        "binary_sensor.vannaia_moisture": _s("on"),
        "binary_sensor.garazh_moisture": _s("on"),
        "siren.alarm": _s("on"),
        "sensor.boiler_mode": _s("Авария"),
        "binary_sensor.door_sensor_door": _s("on"),
        "input_boolean.security_armed": _s("on"),
    },
    # leak protection reports a genuinely offline sensor (cloud says not-online)
    "blind": {
        "sensor.leak_protection_status": _s("blind", per_sensor={
            "binary_sensor.vannaia_moisture": "dry", "binary_sensor.garazh_moisture": "blind",
            "binary_sensor.kukhnia_moisture": "dry", "binary_sensor.water_sensor_4_moisture": "dry"},
            leak_names=[], blind_names=["Гараж"], cloud_src="cloud", cloud_age_sec=17),
    },
    # the summary entity itself is unreadable -> everything must read «неизвестно», never «сухо»
    "truth_gone": {
        "sensor.leak_protection_status": _s("unavailable"),
    },
    "unavailable": {
        "sensor.leak_protection_status": _s("unavailable"),
        "binary_sensor.door_sensor_door": _s("unavailable"),
        "binary_sensor.wifi_th_smoke_sensor_smoke": _s("unavailable"),
        "binary_sensor.vannaia_moisture": _s("unavailable"),
        "binary_sensor.garazh_moisture": _s("unavailable"),
        "binary_sensor.kukhnia_moisture": _s("unavailable"),
        "binary_sensor.water_sensor_4_moisture": _s("unavailable"),
        "sensor.boiler_mode": _s("unavailable"),
        "sensor.boiler_cwu_temperature": _s("unavailable"),
        "sensor.nord_pool_lv_current_price": _s("unavailable"),
        "switch.voda_kran_switch_1": _s("unavailable"),
        "sensor.ev_charger_status": _s("unavailable"),
    },
    "long": {
        "binary_sensor.wifi_th_smoke_sensor_smoke": _s("on", friendly_name=_LONG),
        "binary_sensor.vannaia_moisture": _s("on", friendly_name=_LONG),
        "binary_sensor.garazh_moisture": _s("on", friendly_name=_LONG),
        "siren.alarm": _s("on"),
        "sensor.boiler_mode": _s("Авария " + _LONG),
        "binary_sensor.door_sensor_door": _s("on"),
        "input_boolean.security_armed": _s("on"),
    },
}

_HOST_HTML = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<style>html,body{margin:0;height:100%;background:#000}</style>
<script>
window.__e=[];addEventListener('error',e=>__e.push(String(e.message)));
addEventListener('unhandledrejection',e=>__e.push('rej:'+e.reason));
window.__origFetch=window.fetch.bind(window);
window.fetch=(u,o)=>{u=String(u);if(u.includes('today_prices')){
  const key=d=>d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
  const t=new Date(),tm=new Date(t);tm.setDate(t.getDate()+1);
  const curve=off=>Object.fromEntries(Array.from({length:24},(_,h)=>[String(h),Number((0.03+Math.sin((h+off)/3)*0.02+(h>=17&&h<=21?0.08:0)).toFixed(4))]));
  return Promise.resolve({ok:true,json:()=>Promise.resolve({updated:new Date().toISOString(),prices:{[key(t)]:curve(0),[key(tm)]:curve(2)}})});}
  if(u.startsWith('http://127.0.0.1')||u.startsWith('/')||u.startsWith('tablet_states.json')) return window.__origFetch(u,o);
  return Promise.reject(new Error('stub'));};
</script></head><body>
<script type="module">
import './tablet-panel.js';
(async function(){
  const base=await (await fetch('tablet_states.json')).json();
  const ov=window.__OVERRIDES||{};
  const states=Object.assign({},base);
  for(const k in ov){
    states[k]=Object.assign({},states[k]||{entity_id:k,attributes:{}},ov[k]);
    if(ov[k].attributes) states[k].attributes=Object.assign({},(base[k]&&base[k].attributes)||{},ov[k].attributes);
  }
  const hass={states,callApi:()=>Promise.resolve([]),callService:()=>Promise.resolve(),
    connection:{subscribeEvents:()=>Promise.resolve(()=>{})},themes:{},language:'ru'};
  await customElements.whenDefined('tablet-panel');
  const el=document.createElement('tablet-panel');
  document.body.appendChild(el); el.hass=hass;
  window.__panelEl=el; window.__ready=true;
})();
</script></body></html>
"""

# Measures reachability + clipping for one view; returns a plain dict.
_MEASURE = r"""
(view)=>{
  const el=window.__panelEl, root=el.shadowRoot;
  const v=root.querySelector('#view-'+view);
  if(!v || getComputedStyle(v).display==='none') return {skip:true};
  const host=v.querySelector(':scope > .srv-wrap') || v;
  host.scrollTop = host.scrollHeight + 9000;
  const hr=host.getBoundingClientRect();
  const clientTop=hr.top, clientBottom=hr.top+host.clientHeight;
  const atMax = host.scrollTop + host.clientHeight >= host.scrollHeight - 2;
  const s = host.querySelector(':scope > .view-end[data-sentinel]');
  let sentinelOk=null;
  if(s){ const r=s.getBoundingClientRect(); sentinelOk=(r.top>=clientTop-2 && r.bottom<=clientBottom+2); }
  // last interactive control -> can it be scrolled fully into view (clickable)?
  const cands=[...host.querySelectorAll('button,[onclick],a[href],input,select')].filter(e=>{
    if(e.closest('details:not([open])')) return false;
    const c=getComputedStyle(e); if(c.display==='none'||c.visibility==='hidden') return false;
    const r=e.getBoundingClientRect(); return r.width>0 && r.height>0;
  });
  let liReachable=null;
  if(cands.length){ const li=cands[cands.length-1];
    li.scrollIntoView({block:'nearest'});
    const h2=host.getBoundingClientRect(); const cb=h2.top+host.clientHeight, ct=h2.top;
    const r=li.getBoundingClientRect();
    liReachable=(r.top>=ct-2 && r.bottom<=cb+2 && r.height<=host.clientHeight+2);
    host.scrollTop=host.scrollHeight+9000;
  }
  // (d) no in-flow content clipped by an overflow:hidden ancestor
  let clipped=0; const clipSample=[];
  v.querySelectorAll('*').forEach(e=>{
    if(e===host) return;
    if(e.closest('details:not([open])')) return;
    const c=getComputedStyle(e);
    if(c.overflowY==='hidden'||c.overflow==='hidden'){
      if(e.scrollHeight - e.clientHeight > 3){ clipped++; if(clipSample.length<3) clipSample.push((e.className||e.tagName).toString().split(' ')[0]+' +'+(e.scrollHeight-e.clientHeight)); }
    }
  });
  // (e) no horizontal overflow
  const hOverflow = v.scrollWidth > v.clientWidth + 2;
  return {view, atMax, hasSentinel:!!s, sentinelOk, liReachable,
          clipped, clipSample, hOverflow,
          scrollH:host.scrollHeight, clientH:host.clientHeight};
}
"""


def _find_chromium():
    import glob
    roots = [os.environ.get("PLAYWRIGHT_BROWSERS_PATH"),
             os.path.expanduser("~/.cache/ms-playwright"),
             "/root/.cache/ms-playwright"]
    for r in roots:
        if not r:
            continue
        for pat in ("chromium-*/chrome-linux*/chrome", "chromium-*/chrome-linux/chrome"):
            hits = sorted(glob.glob(os.path.join(r, pat)))
            if hits:
                return r
    return None


def _serve(dir_):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(dir_), **kw)

        def log_message(self, *a):
            pass

    httpd = socketserver.TCPServer(("127.0.0.1", 0), Quiet)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def _run_matrix():
    """Return (results, failures). Each is keyed by 'state|size|view'."""
    from playwright.sync_api import sync_playwright  # noqa: WPS433

    tmp = Path(tempfile.mkdtemp(prefix="tabscroll_"))
    try:
        shutil.copyfile(PANEL, tmp / "tablet-panel.js")
        shutil.copyfile(FIXTURE, tmp / "tablet_states.json")
        (tmp / "host.html").write_text(_HOST_HTML, encoding="utf-8")
        httpd, port = _serve(tmp)
        base = f"http://127.0.0.1:{port}/host.html"
        results, failures = {}, {}
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                for state, overrides in SCENARIOS.items():
                    for label, w, h in SIZES:
                        ctx = browser.new_context(viewport={"width": w, "height": h},
                                                  device_scale_factor=1)
                        page = ctx.new_page()
                        errs = []
                        page.on("pageerror", lambda e: errs.append(str(e)))
                        page.add_init_script(f"window.__OVERRIDES={json.dumps(overrides)};")

                        def route(r):
                            u = r.request.url
                            if u.startswith(f"http://127.0.0.1:{port}"):
                                return r.continue_()
                            try:
                                r.fulfill(status=200, content_type="application/json", body="[]")
                            except Exception:
                                try:
                                    r.abort()
                                except Exception:
                                    pass

                        page.route("**/*", route)
                        page.goto(base, wait_until="load")
                        page.wait_for_function("window.__ready===true", timeout=20000)
                        page.wait_for_timeout(500)
                        for v in VIEWS:
                            page.evaluate("(x)=>window.setView(x)", v)
                            page.wait_for_timeout(200)
                            m = page.evaluate(_MEASURE, v)
                            key = f"{state}|{label}|{v}"
                            m["pageerrors"] = list(errs)
                            results[key] = m
                            if m.get("skip"):
                                continue
                            ok = (m["atMax"] and m["hasSentinel"]
                                  and m["sentinelOk"] is not False
                                  and m["liReachable"] is not False
                                  and m["clipped"] == 0
                                  and not m["hOverflow"]
                                  and not errs)
                            if not ok:
                                failures[key] = m
                        ctx.close()
            finally:
                browser.close()
        httpd.shutdown()
        return results, failures
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_every_screen_scrolls_to_its_bottom():
    if not PANEL.exists():
        pytest.skip("tablet/tablet-panel.js not present (gitignored source)")
    if not FIXTURE.exists():
        pytest.skip("tablet states fixture missing")
    pytest.importorskip("playwright", reason="playwright not installed")
    if _find_chromium() is None:
        pytest.skip("no Chromium build for Playwright")
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH") is None:
        cand = _find_chromium()
        if cand:
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = cand

    results, failures = _run_matrix()
    assert results, "matrix produced no measurements"
    if failures:
        lines = [f"{k}: {v}" for k, v in sorted(failures.items())]
        pytest.fail("Unreachable / clipped screens:\n" + "\n".join(lines))
