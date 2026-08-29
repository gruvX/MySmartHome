# Backlog Diagnostics — 2026-07-16

Read-only investigation. No devices touched, no config changed, no entities removed.
All irreversible steps are marked **OWNER-GATED (PROPOSE ONLY)**.

Data sources: HA REST `/api/states`, `/api/history`; WS `config/entity_registry/list`,
`config_entries/get`, `config/device_registry/list`; HA core log via Supervisor API
(`http://supervisor/core/logs`); `/config/configuration.yaml` (read via sudo).
Snapshot taken ~2026-07-16 19:30 local.

---

## Item 1 — invalid-auth flood to `/api/states`

### Findings
HA core log `homeassistant.components.http.ban` "Login attempt or request with invalid
authentication" — counts over the log window (2026-07-12 → 2026-07-16 19:31), concentrated
in the last ~24h:

| Client IP | Hits | URL(s) | User-Agent | Active window | Status now |
|---|---|---|---|---|---|
| **192.168.1.43** | **2843** | `/api/states` (100%) | Windows 10 / Chrome desktop | 07-15 19:50 → 07-16 19:31 | **STILL FLOODING** (~1 req / 30s) |
| **192.168.1.44** | **1597** | `/api/states` + 1× `/auth/login_flow/...` | Windows 10 / Chrome desktop | 07-15 16:19 → 07-16 06:40 | Stopped 06:40 today |
| 192.168.1.36 | 217 | `/api/states` | Android 10 (WebView/Chrome mobile) | 07-15 16:17 → 18:23 | Stopped |
| 192.168.1.60 | 5 | `/api/`, `/api/states` | X11 Linux desktop | 07-15 15:27 → 19:53 | Stopped (sporadic) |
| 162.158.182.68/69, 104.23.221.223 (Cloudflare ranges) | 1 each | `/api/config`, `/api/` | Mac / (none) | one-off | Internet background noise via public funnel |

.43 (2843) + .44 (1597) ≈ 4440 ≈ the reported ~4278/24h.

### Interpretation (per client)
- **All high-volume sources are private-LAN own clients**, each polling **one endpoint
  (`/api/states`) at a fixed 30s cadence** with a browser UA. That cadence + endpoint is
  the signature of this project's **custom HTML dashboards** (`tablet.html`, `livemap.html`,
  `boiler.html`, `smarthouse.html`) — Lovelace uses WebSocket, not REST `/api/states`
  polling, so these are the custom pages.
- Those pages read their bearer token from **localStorage** (`tablet_token` /
  `livemap_token`). A **stale/revoked/rotated token in localStorage** → every 30s poll
  returns 401 → logged as "invalid authentication". This matches the two documented issues:
  the old "Tablet" refresh_token was **revoked 2026-07-05**, and the admin token was
  **rotated 2026-07-15** (`set_new_ha_token.py`), which would invalidate any dashboard still
  holding the previous token in localStorage.
  - `.43` (Windows desktop, still flooding): a desktop browser tab left open on
    livemap/boiler/tablet/smarthouse with a stale localStorage token.
  - `.44` (Windows desktop): same; self-stopped at 06:40 (tab closed / machine slept).
  - `.36` (Android): the wall tablet / a phone browser on `tablet.html` with a stale
    `tablet_token` (documented failure mode: "все кнопки 401 если в localStorage протух токен").
  - `.60` (Linux desktop, 5 hits): almost certainly our own test/dev browser sessions.
- **Not an attack.** No credential-stuffing pattern (single endpoint, fixed interval,
  consistent UA, RFC-1918 sources, only 1 `login_flow` attempt total). The 3 Cloudflare-range
  one-offs to `/api/config` are ordinary internet scanning of the public funnel URL, 1 request
  each — trivial, no action.
- **`ip_ban_enabled` is NOT configured** (`configuration.yaml` `http:` block has only
  `use_x_forwarded_for` + `trusted_proxies`; no `/config/ip_bans.yaml`). Default =
  disabled → nothing gets banned, so the flood self-perpetuates AND a real legit device is
  never auto-locked. (Enabling ip_ban would silence the log but risks locking out the wall
  tablet — do NOT enable without first fixing the tokens.)

### Severity: **Low-Medium**
Pure log noise + wasted polling; no data exposed, no auth weakened, no lockout. Nuisance only.

### Proposed safe remediation (per client — all reversible, LAN-side)
- **SAFE LOCAL FIX (no owner decision needed to diagnose; execution is a client-side token
  re-bootstrap, not an HA change):**
  - `.43` and `.44`: on those desktop browsers, clear the dashboard localStorage token and
    re-bootstrap by opening the page once with `?token=<current valid limited-user token>`
    (the pages self-store and strip the URL). Or just close the stale tab on `.43` to stop
    the active flood immediately.
  - `.36` (tablet): re-bootstrap `tablet.html` via `.../local/tablet.html?token=<T>` (the
    documented recovery); the newer `refreshAll` already self-heals on 401 by dropping the
    localStorage token and falling back once — so this client may only need a reload.
  - `.60`: no action (our own test browser).
- **DO NOT** enable `ip_ban_enabled` as a "fix" — it would risk banning the wall tablet.
- **DO NOT** mint new admin/broad tokens for dashboards; keep them on the limited
  MiniApp/Tablet users. No auth weakening.

---

## Item 2 — `binary_sensor.boiler_alarm` ON ~4.5h

### What it maps to
Defined in `configuration.yaml` as a **REST** binary_sensor (platform `rest`, not
plum_ecomax), device_class `problem`:
```
value_template: {{ value_json.curr.alarmOutput }}
availability:   value_json.curr.alarmOutput is defined
```
→ it mirrors the ecoNET/ecoMAX controller field **`curr.alarmOutput`** — the controller's
**alarm-output relay**.

### Benign relay vs. real fault → **real (low-urgency) fault**
History for 2026-07-16:
- `binary_sensor.boiler_alarm`: **ON 08:37:34 → OFF 15:59:40** (~7.4h; it was still ON when
  this backlog item was captured at ~4.5h). Frequent brief `unavailable` flaps throughout
  (the known ecoNET WiFi flapping at 192.168.1.10).
- `sensor.boiler_mode` during the same window: **`Догорание` (burn-out / dying fire)** the
  entire morning, i.e. the fire was going out. `sensor.boiler_co_temperature` steadily
  **declined 45.1 °C → ~40 °C and below** across 05:00–09:00. The boiler only returned to
  `Работа` at 15:39, then `Надзор`/`Ожидание`, and the alarm cleared at 15:59.
- `sensor.boiler_fuel_level` is physically disconnected (always 0) — consistent with a
  **pellet fire that burned out / ran low**, tripping the controller alarm relay.

So `alarmOutput` was asserting a genuine controller alarm (fire-out / failed-to-heat class),
not a spurious relay toggle. Low urgency (no safety hazard — a dead pellet fire), but the
house had **no hot-water/heat production for ~7h and nobody was told**.

### Notification path: **NONE exists**
- No automation references `boiler_alarm` / `alarmOutput` (grep of automations = 0 hits).
- The existing boiler-notify automation (id `1779000001002`) triggers only on
  `sensor.boiler_mode` = `Выключен`/`Авария` — it does **not** catch `Догорание` nor the
  `alarmOutput` relay, so this 7h burn-out was silent.

### Severity: **Medium** (comfort/operational, not life-safety)

### Proposed safe action — **PROPOSE ONLY (owner decision; it would add an automation)**
Add a notification automation on `binary_sensor.boiler_alarm` off→on **sustained for N
minutes** (e.g. `for: 00:05:00`, to ride out the WiFi flaps), Telegram-only, daytime-gated,
with a cooldown — message like "Котёл: сигнал тревоги / горение угасает (режим Догорание),
CO temp падает". Optionally also alert when `boiler_mode` stays `Догорание` > ~30 min while
not `Ожидание`. Do NOT auto-act on the boiler. (Note: fixing the ecoNET WiFi flapping /
reserving its IP would also reduce the `unavailable` churn — hardware follow-up already in
the known-issues list.)

---

## Item 3 — long-standing unavailable entities

### Count & method
Snapshot: **130** entities in `unavailable`/`unknown`/`none` (of 588 states).
All flipped at **2026-07-15 15:11–15:12** = the last HA restart, and none recovered since
(~28h) → these are steady-state, not transient blips.

**Important:** the raw 130 is inflated by entity types that are `unknown` **by design** and
are NOT broken. Reclassified:

| Bucket | ~Count | Detail | Removable? |
|---|---|---|---|
| **Normal-`unknown` by design (NOT broken)** | ~28 | 19 Tuya `scene.*` (scenes have no state); `stt.*`/`tts.*` (cloud, google_ai, google_translate); `binary_sensor.remote_ui` (HA Cloud unused — they use Tailscale) | **No — leave** |
| **Dead / offline device, integration loaded** | ~60 | **xiaomi_home (55, dominated by ONE offline device — Mijia Air Purifier 3 `zhimi_...mb3`, ~35 diag entities)** + Xiaomi smoke alarm `lumi_...3ed434`, door magnet `lumi_...431e0e2`; **matter (15)** = Matter gateway + 4-scene-switch + dimmers + occupancy all down (bridge offline); **androidtv_remote (2)** MiTV-MSSP2 (config `setup_retry`, known offline); **roborock (4)** vacuum (known setup_error); **dlna_dmr (2)** XBOX/SOLAS TV (normal when powered off) | **No — recover device, or owner may keep** |
| **Tuya offline hardware** | ~5 | `light.dimmer_switch_11_light_1/2` + `select...power_on_behavior` ("Подсветка остров" dimmer, offline island-light rep); `binary_sensor.signalizatsiia_dvernogo_datchika_door` + `sensor..._battery` (the "Сигн." door sensor — the known 0%-battery unit) | Owner decision |
| **Ghost / orphaned from DELETED integration/device** | ~22 | **mobile_app `phone` leftovers (18):** `device_tracker.unknown`, `notify.unknown`/`_2`, `sensor.*_2` (activity_2, ssid_2, bssid_2, steps_2, storage_2, …) — remnants of the **deleted SM-T595 tablet companion**. **smartthings ghosts (4):** `switch.podsvetka_ostrov` (see Item 4), `light.lg_tv`, `binary_sensor.signalizatsiia_dvernogo_datchika_door_2` + `sensor..._battery_2` (duplicate of the Tuya door sensor) | **Yes — safe-to-remove candidates (owner-gated)** |

### Safe-to-remove candidates (best signal-to-noise)
**PROPOSE ONLY — registry deletes are irreversible/owner-gated:**
- The **18 `mobile_app` `*_2` / `*.unknown` leftovers** of the deleted tablet companion.
  **CAUTION:** the two `mobile_app` config entries (`01JF7JNNA5…`, `01KDX32ERB…`) are
  intermixed and one of them holds the **ACTIVE `device_tracker.myiphone` / notify**.
  → Remove the specific **unavailable** leftover entities individually; **do NOT delete a
  whole mobile_app config entry** (would kill the working iPhone presence/notify).
- `light.lg_tv`, `binary_sensor.signalizatsiia_dvernogo_datchika_door_2`,
  `sensor.signalizatsiia_dvernogo_datchika_battery_2` (SmartThings duplicates/ghosts).

**Do NOT bulk-remove** the xiaomi/matter/roborock/dlna sets — those are live integrations
whose devices are merely powered off/offline and will self-recover; and **SmartThings "Дом"
owns many ACTIVE entities** (switch.boiler, switch.veranda, switch.cherepakha, 75" QLED
sensors, kukhnia temp/humidity, etc.) — the integration is healthy, only individual dead
devices are ghosts.

### Severity: **Low** (cosmetic registry clutter; a few affect UI dropdowns)

---

## Item 4 — ghost entity `switch.podsvetka_ostrov` (reappeared)

### Findings
- **Recreated by the SmartThings integration.** Registry: `platform=smartthings`,
  `config_entry_id=01HAENTRYIDPLACEHOLDER0000` (domain `smartthings`, title **"Дом"**,
  state `loaded`), `unique_id=edad76d8-8352-4962-9c75-e6563669c7db_main_switch_switch_switch`,
  device "Подсветка остров" identifiers `['smartthings','edad76d8-…']`.
- **created_at ≈ 2026-07-15**, modified 2026-07-16 → it was re-added at the last integration
  reload/HA restart, **after** the 2026-07-12 WS `entity_registry/remove`.
- Current state: **`unavailable`** since 2026-07-15 15:12. The physical device is offline;
  the island is actually controlled by other live entities (`switch.vkliuchit_svet_ostrov`,
  `switch.vykliuchit_ostrov_svet`, `switch.svet_pervyi_etazh_1_ostrov_i_stol`, etc.).

### Why it came back / true orphan?
It is a **true orphan on the HA side but still present in the SmartThings cloud account
"Дом"**. Deleting only the HA registry entry does nothing durable — on the next SmartThings
resync/reload/restart HA re-enumerates the cloud device list and **recreates** it. This is
exactly why the 2026-07-12 removal didn't stick.

### Proposed safe removal path — **OWNER-GATED (PROPOSE ONLY)**
Two options, pick per owner preference:
1. **Durable, but outside HA:** remove/delete the "Подсветка остров" device from the
   **SmartThings app / cloud account** first, then reload the SmartThings entry / remove the
   HA entity. Only this stops it from re-appearing.
2. **HA-side, reversible, survives resync:** **disable** the entity in HA
   (`disabled_by: user`) instead of deleting — a disabled entity is not recreated as enabled
   on resync and can be re-enabled anytime. This is the safest reversible option and my
   recommended default if the owner isn't ready to touch SmartThings.

Do **not** remove/disable the SmartThings config entry itself — it owns many active devices.

### Severity: **Low** (single unavailable ghost; no functional impact — island has live controls)

---

## Summary — safe local fix vs. owner decision

| Item | Severity | Safe local (client-side / reversible) | Needs owner decision (irreversible / adds automation / cloud change) |
|---|---|---|---|
| 1 invalid-auth flood | Low-Med | **Yes** — re-bootstrap/clear stale localStorage token on .43/.44/.36; close stale .43 tab to stop it now. Not an attack. | No new access; explicitly do NOT enable ip_ban |
| 2 boiler_alarm | Med | No | **Yes** — add Telegram alert on sustained `boiler_alarm` on (real burn-out fault went 7h silent; no path exists) |
| 3 unavailable entities | Low | Classification only (read-only) | **Yes** — per-entity registry deletes of the ~22 ghosts (esp. 18 tablet mobile_app `*_2`); keep whole config entries intact |
| 4 podsvetka_ostrov | Low | No (deleting entity alone won't stick) | **Yes** — remove from SmartThings cloud OR disable entity in HA (recommended reversible option) |
