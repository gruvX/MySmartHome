# Mini App auth diagnosis — 2026-07-23

**Scope:** read-only investigation. Nothing was modified or deployed. No secret
values were printed. Owner report: Telegram Mini App (MySmartHome) shows **no
data** and **frequent "ошибка авторизации"**.

---

## One-line root cause

The deployed `_validate()` builds the Telegram HMAC data-check-string from **all
initData fields except `hash`**, which now **includes Telegram's `signature`
field**. Telegram computes `hash` **excluding both `hash` and `signature`**, so
every genuine, fresh initData fails the HMAC check → constant `401` on
`/api/miniapp-auth` → the frontend shows "Ошибка авторизации" and never loads
state. All other suspected causes (missing/wrong bot token, clock skew, tight
MAX_AGE, unavailable entities) were checked and **ruled out**.

## The fix (minimal, not applied)

In `/config/custom_components/miniapp_auth/__init__.py`, function `_validate`
(deployed ~line 194, right after `received = params.pop("hash", "")`), also drop
the signature field before computing the data-check-string:

```python
received = params.pop("hash", "")
params.pop("signature", None)   # <-- ADD: Telegram excludes signature from the HMAC hash
```

Then apply with a component reload / `homeassistant.restart`. **No secret change
is required** — the bot token on the box is correct and valid.

Apply the same one-line change to the repo working-tree copy
(`custom_components/miniapp_auth/__init__.py`, ~line 345) so the fix is not lost.

---

## What was verified (evidence)

| Check | Result | Verdict |
|-------|--------|---------|
| Bot token present on box | `/config/local_secrets.json` key `TELEGRAM_BOT_TOKEN`, len 46, contains `:` | Present |
| Bot token **valid** | Telegram `getMe` → `ok:true`, username `your_home_bot` | **Correct token, not revoked** |
| Token source resolves in HA context | `project_secrets.secret("TELEGRAM_BOT_TOKEN")` non-empty via `/config/local_secrets.json`; `/config/__pycache__/project_secrets.cpython-314.pyc` exists → HA imports it fine | BOT_TOKEN populated in running process |
| Deployed file written | `/config/.../miniapp_auth/__init__.py` mtime Jul 17 12:28 (pyc Jul 17 12:29) — deploy forced an HA reload **after** the Jul 15 token file | Running module read the valid token |
| Clock skew | Box epoch == local epoch (0 s difference); `MAX_FUTURE_SKEW` not in deployed version anyway | Not a factor |
| Deployed `MAX_AGE` | **86400** (24 h) — generous, not tight | Not the primary cause |
| Endpoints registered | POST with dummy initData → `/api/miniapp-auth` `401 {"ok":false}`, `/api/miniapp-state` & `/api/miniapp-action` `401 {"error":"unauthorized"}` | Component loaded & routed |
| `miniapp_auth:` in configuration.yaml | line 398 | Enabled |
| STATE_IDS entity availability | `weather.forecast_home=cloudy`, `sensor.nord_pool_lv_current_price=0.17869`, `switch.smart_plug_2_socket_1=off`, `switch.kalarifer_socket_1=off`, `sensor.boiler_total_energy=20.069`, `binary_sensor.door_sensor_door=off`, `sensor.kukhnia_temperature=22.9`, `input_boolean.security_armed=off` | **All available with fresh data** |
| Frontend HA_URL | `HA_URL=""` inside Telegram (same-origin, relative calls to the funnel host = HA) | No wrong-URL/network cause |
| `signature` handling | **Absent** in both deployed (`grep signature` → none) and repo hardened version | Root cause locus |

### "No data" is a consequence of auth, not entity outage
All sampled STATE_IDS entities are live and returning values. In the frontend
(`smarthouse.html`), `fetchData()` (line 281) returns early unless auth
succeeded, and the "Ошибка авторизации" full-screen (line 409) is reached only
when the **initial** `POST /api/miniapp-auth` (line 308) returns non-2xx with
initData present. So no-data is strictly downstream of the 401.

### Why the token / clock / MAX_AGE are NOT the cause
- Token is present, resolves in HA's runtime, and Telegram `getMe` confirms it is
  the live token for `@your_home_bot` (not revoked / not wrong).
- HA box clock is in exact sync — no skew making initData look expired/future.
- Deployed MAX_AGE is 24 h; a normally-opened Mini App presents a fresh
  `auth_date`, so expiry does not explain failures on a fresh open.

### Why `signature` is the cause (high confidence)
Telegram added a `signature` field to Mini App `initData` (Ed25519 third-party
verification) and computes the legacy `hash` **excluding** it. Any validator
that folds every field-except-`hash` into the data-check-string (as this one
does, deployed line 203 / repo line 359) now produces a mismatching HMAC for
**every** genuine initData once the client sends `signature`. This matches all
observed symptoms: sudden onset, universal failure, fresh opens still fail, no
data. This is a well-documented breaking change that forced the same one-line
patch in mainstream libraries (python-telegram-bot, aiogram, grammy, etc.).

**Confidence caveat:** a live initData string could not be captured to visually
confirm the `signature` key is present — forging a signed initData for a positive
control was blocked by policy, and HA does not log request bodies or the 401s.
The `signature` conclusion is therefore inferred from (a) elimination of every
other cause and (b) Telegram's documented rollout. Recommended confirmation:
temporarily log `sorted(params.keys())` in `_validate` for one request (or log
whether `"signature" in params`), verify the key is present, apply the fix, and
confirm auth succeeds.

---

## Deployed vs repo drift

- **Deployed:** `/config/custom_components/miniapp_auth/__init__.py` = **431
  lines**, `MAX_AGE = 86400`, no rate-limit, no future-skew, no `signature`
  handling.
- **Repo working-tree:** `custom_components/miniapp_auth/__init__.py` = **647
  lines** (P0 hardening, commit `7bb6019` "NOT yet deployed"), `MAX_AGE = 3600`,
  `MAX_FUTURE_SKEW = 300`, rate-limiter, body cap — **but still no `signature`
  handling**.

**Do NOT deploy the repo hardened version as "the fix".** It does not strip
`signature` either (so it would not fix the 401), and it *tightens* MAX_AGE from
24 h → 1 h, which would make expiry-related failures worse for long-lived
sessions. Add the `params.pop("signature", None)` line first; deploy the
hardened version only after that line is in it.

---

## Secondary observations (not the root cause)

- **initData reuse for polling:** the frontend captures `tg.initData` once at
  open (line 308) and reuses it for every poll. With deployed MAX_AGE 86400 this
  is fine for ~24 h; with the repo's 3600 it would 401 after 1 h of an open
  session (state fetch failures show as stale data, not the error screen).
- **HA core log is flooded** with unrelated boiler template errors
  (`Error rendering availability template for sensor.boiler_* : 'value_json' is
  undefined`, ~1/sec), which is why the 2000-line log tail spans only ~34 min.
  HomeAssistantView 401s are not logged, so auth 401 frequency cannot be read
  from logs. Unrelated to the Mini App but worth a separate cleanup.
- HA core `2026.7.2`, update `2026.7.3` available.
