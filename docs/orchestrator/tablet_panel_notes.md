# Tablet UI → Home Assistant native custom panel (`panel_custom`)

**Goal achieved:** the standalone tablet UI now runs as a Home Assistant *native*
custom panel that uses the **current HA-authenticated session**. There is **no token
anywhere** — not in the file, not in `localStorage`, not in the URL query string.

- **Repo source of truth:** `tablet/tablet-panel.js` (the panel_custom module)
- **Local mock harness:** `tablet/tablet-panel.dev.html` (renders without HA, drives assertions)
- **Old standalone left untouched:** `tablet/tablet.html` (still token-based; unchanged)

Author note: `tablet-panel.js` was mechanically derived from `tablet/tablet.html` —
identical CSS, markup, and render logic; **only the transport layer and token handling
changed**. Future *design* changes are easiest to make in `tablet.html` and re-migrate
(swap transport again); *transport/lifecycle* changes go straight into `tablet-panel.js`.

---

## 1. How it works (architecture)

`panel_custom` loads `module_url` as an ES module and instantiates a custom element
whose tag equals the panel `name`. HA sets `.hass`, `.narrow`, `.route`, `.panel`
properties on that element.

`tablet-panel.js` defines:

```js
class TabletPanel extends HTMLElement {
  set hass(h){ HASS = h; /* boot on first hass, else throttled re-render */ }
  connectedCallback(){ /* inject <style> + markup once; boot() when hass present */ }
  disconnectedCallback(){ /* clear timers, release wake lock */ }
}
customElements.define('tablet-panel', TabletPanel);
```

- **State reads** come from `this._hass.states` (object `entity_id -> {state, attributes}`),
  copied into the existing `S` map. HA re-sets `.hass` frequently, so re-render is
  **throttled to ~1.2 s** (`scheduleHassUpdate`). Heavy work (calendars/prices) runs
  only on the periodic timer + explicit actions, not on every hass push.
- **Service calls**: `svc(domain,service,data)` → `this._hass.callService(...)`.
- **Calendars**: `this._hass.callApi('GET','calendars')` and
  `callApi('GET','calendars/<id>?start=..&end=..')` (authenticated session, no headers built).
- **Today prices**: same-origin `fetch('/local/today_prices.json')` (static file, no auth).
- **Rendering (SHADOW DOM)**: HA mounts a `panel_custom` element **inside
  `ha-panel-custom`'s shadow root**. So the element creates its **own** `shadowRoot`
  (`attachShadow({mode:'open'})`) and mounts BOTH the `<style>` (all tablet CSS) and the
  markup inside it. All panel DOM access is scoped to that shadow root via helpers
  `qid`/`qs`/`qsa` (ShadowRoot has `querySelector` but **no** `getElementById`). Inline
  `onclick=…` handlers still resolve from global scope, so the module keeps its handler
  functions on `window`. CSS is encapsulated: `:root` → `:host`, and every document-level
  flag selector (`[data-theme="x"]`, `[data-density=…]`, …) → `:host([data-…])`, with the
  theme/pref flags set on the **host element** (`applyTheme`/`applyPrefs` write
  `ROOT.host.dataset`). The host is `:host{position:fixed; inset:0; z-index:999}`, so it
  fills the panel area and its own fixed overlays (settings / idle / toast) layer within it.

  > **Why the first deploy showed a black screen:** the original attempt used light DOM +
  > `document.getElementById(...)`, which resolves against the MAIN document and returns
  > `null` when the element is nested in `ha-panel-custom`'s shadow → `null.innerHTML`
  > threw → nothing rendered. Fixed by the self-contained shadow-root approach above.
- **Placeholder**: if `hass` is not yet set, the home view shows a small **“Загрузка…”**
  and boot is deferred until the session arrives. There is **no token prompt** — ever.

### Transport mapping (old standalone → this panel)

| Old (standalone `tablet.html`)                                  | New (`tablet-panel.js`)                                      |
|----------------------------------------------------------------|-------------------------------------------------------------|
| `GET /api/states` + `Authorization: Bearer <token>`            | `this._hass.states`                                         |
| `POST /api/services/<d>/<s>` + Bearer header                   | `this._hass.callService(d, s, data)`                        |
| `GET /api/calendars` + Bearer                                  | `this._hass.callApi('GET','calendars')`                     |
| `GET /api/calendars/<id>?start=..&end=..` + Bearer            | `this._hass.callApi('GET','calendars/<id>?start=..&end=..')`|
| `GET /local/today_prices.json` (Bearer sent, but static)      | `fetch('/local/today_prices.json')` (same-origin, no auth)  |
| `GET /api/` probe + token dialog + `localStorage['tablet_token']` + `?token=` bootstrap | **removed entirely** (session is implicit)     |

---

## 2. Owner setup

1. **Deploy the module** to HA web root (orchestrator step):
   `tablet/tablet-panel.js` → `/config/www/tablet-panel.js` (served at `/local/tablet-panel.js`).
2. **Register the panel** — add the block below to `/config/configuration.yaml`
   (orchestrator step; see §3).
3. **Restart Home Assistant** (required — see §4).
4. **On the tablet (SM-T595)**: point the kiosk/browser start URL to
   `http://192.168.1.45:8123/tablet-panel`
   (external: `https://homeassistant.your-tailnet.ts.net/tablet-panel`).
   Log into HA **once** in that browser; the session cookie persists, so the panel
   loads authenticated on every boot with **no token entry**.
   - Wake-lock/no-sleep works best over HTTPS (Tailscale funnel) or `localhost`; over
     plain-LAN `http://192.168.1.45` the Screen Wake Lock API is unavailable and the
     built-in canvas/video no-sleep fallback kicks in automatically (unchanged behavior).

### `panel_custom` YAML to add to `configuration.yaml`

```yaml
panel_custom:
  - name: tablet-panel          # MUST equal the custom element tag defined in the module
    url_path: tablet-panel      # opens at /tablet-panel
    sidebar_title: Умный дом
    sidebar_icon: mdi:tablet-dashboard
    module_url: /local/tablet-panel.js
    require_admin: false        # non-admin session users may open it
    embed_iframe: false         # render the element directly (no iframe) so it shares the HA session
```

> Cache-busting on updates: HA caches `module_url`. After deploying a new
> `tablet-panel.js`, bump the URL to `/local/tablet-panel.js?v=2` (etc.) or hard-refresh
> the tablet browser, otherwise the old module may be served from cache.

---

## 3. Restart & rollback

- **Restart required: YES.** `panel_custom` is registered during HA setup;
  `homeassistant.reload_all` / core-config reload will **not** register a new panel.
  A full **HA restart** is needed after adding the YAML (and after first deploying the file).
- **Rollback:**
  1. Remove the `panel_custom:` block from `configuration.yaml`.
  2. (Optional) delete `/config/www/tablet-panel.js`.
  3. Restart HA.
  The old standalone `/local/tablet.html` is untouched and remains available as before.

---

## 4. Verification performed (no deploy, no real devices)

- **No secrets in the module** — grep of `tablet/tablet-panel.js` returns **0** for each of:
  `eyJ` (JWT), `Bearer`, `Authorization`, `?token=`, `headers:H`, `tablet_token`,
  `LS_TOKEN`, `localStorage…token`, `fetch(…headers…)`, `showTokenDialog`, `verifyToken`.
  The only `fetch()` calls remaining are external namedays (graceful-fail) and the
  same-origin static `today_prices.json`.
- **Syntax:** `node --check tablet/tablet-panel.js` → OK.
- **Mock transport test** (Node VM with stubbed browser globals + spy `hass`) — all pass:
  - element defined & rendered from a stubbed `hass` with **no token**;
  - state reads come from `hass.states` (`st`, `num`, `isOn`);
  - control actions route through `hass.callService` (verified `allLightsOff`,
    `toggleEntity`, `runScene`) — **not** fetch+auth;
  - calendars route through `hass.callApi`;
  - **no fetch call ever carried an `Authorization` header / `Bearer`**;
  - `render()` produced real markup (home ≈ 11 KB, energy ≈ 9.8 KB, security, heat).

**Could NOT verify in this sandbox:** a live *authenticated* `hass` from a running HA
instance, and a Chromium visual screenshot (headless Chromium is killed by the sandbox
on local sockets). Rendering itself was exercised head-lessly via the Node VM harness and
`tablet/tablet-panel.dev.html` is provided for a manual browser check on the owner's machine.

---

## 5. Backlog / not preserved via `hass`

- **Embedded sub-pages still token-based.** The `graph` / `boiler` / `livemap` tabs embed
  `/local/graph.html`, `/local/boiler.html`, `/local/livemap.html` in iframes. Those pages
  keep their **own** `localStorage['livemap_token']` auth (out of scope here). They are not
  in the sidebar NAV but are reachable via `setView('graph'|'boiler'|'livemap')`. Migrating
  them to session-based transport is a separate task.
- **External namedays may be blocked by HA’s frontend CSP.** `api.prompt.lv` /
  `nameday.abalin.net` are cross-origin; HA’s Content-Security-Policy (`connect-src`) can
  block them. The code already degrades to “нет данных”. If namedays matter, proxy them
  through a same-origin file/endpoint. (`today_prices.json` is same-origin and unaffected.)
- **Kiosk chrome overlap.** The host covers the HA sidebar/header (fixed, full-viewport) —
  intended for a fullscreen kiosk. While the panel is open you navigate via the tablet’s own
  nav, not HA’s sidebar. If HA-sidebar access is ever wanted, lower the host `z-index` and
  drop `position:fixed` (accepting HA’s layout constraints).
- **Prerequisites unchanged:** Google Calendar events still require the HA Calendar
  integration; `today_prices.json` still comes from the existing “Elering цены дня”
  automation writing `/config/www/today_prices.json`.

---

## 6. Residual risks

- HA re-sets `.hass` very often; re-render is throttled to ~1.2 s. After a `callService`,
  HA’s `states` update arrives asynchronously over the websocket — the UI reflects the new
  state on the next hass push (the existing PENDING/“pending” tile styling covers the gap,
  same as before). No optimistic state flips are done.
- `module_url` caching (see §2) can serve a stale module after an update — bump `?v=`.
- Because the element uses **light DOM** and exposes handlers on `window`, it assumes a
  single panel instance (the norm for a sidebar panel). Multiple simultaneous instances are
  not supported (also true of the original page).
