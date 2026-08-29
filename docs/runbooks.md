# Deploy, Rollback & Incident Runbooks

High-level operational procedures. These reference the safe-ops rules — read them
before touching a live system:

- **Secrets:** never inline; see [`credentials.md`](credentials.md).
- **`/config/` is owned by root** — write via a temp file + `sudo cp`, never edit in place as the SSH user.
- **Reload the narrowest scope** that applies; restart HA only when required.
- **Back up the file you are about to change** first (`cp <file> <file>.bak_<date>`).
- **One entry at a time** for Tuya (`reload_config_entry` always with a specific `entry_id`).

---

## Deploy

1. **Edit locally**, then syntax-check:
   `python -m py_compile <changed>.py` and validate YAML.
2. **Scan for secrets:** `python tools/secret_scan.py` (must be clean).
3. **Back up the remote file**, then push it via `write_remote()` (stdin → `sudo cp`);
   `/config/www/*` is web-exposed, so keep backups **outside** `/config/www`.
4. **Reload the affected domain only:**
   | Changed | Reload |
   |---------|--------|
   | `automations.yaml` | `POST /api/services/automation/reload` |
   | `scripts.yaml` | `POST /api/services/script/reload` |
   | input helpers | `input_boolean/reload`, `input_number/reload`, `input_datetime/reload` |
   | `command_line` sensors (EV) | `POST /api/services/command_line/reload` |
   | `rest_command` | `POST /api/services/rest_command/reload` |
   | new `template:` block / new integration / component code | **full HA restart** |
   | changed availability on REST sensors | `homeassistant.reload_all` |
5. **Verify** the entity/automation behaves before walking away.

## Rollback

1. Restore the `.bak_<date>` you made in step 3 via `write_remote()`.
2. Reload the same domain (or restart if the change required one).
3. Confirm the entity returns to its prior state.
4. If a bad config blocks startup: fix via SSH, check `ha core logs`, then restart.

---

## Incident runbooks

### Water leak
- Auto: moisture sensor (3-min confirm) → water valve closes → Telegram with a
  `/leak_confirm` button. A startup-grace flag suppresses false alarms for ~15 min
  after an HA restart. Only ONE leak automation should be enabled (a disabled
  duplicate is pinned `initial_state: false`).
- Manual: verify physically; reopen the valve only once dry. If a sensor is stuck
  `on` after a Tuya reload, force-sync with `reload_config_entry` (specific entry_id).

### Smoke
- Auto: smoke sensor → siren + Telegram alert.
- Manual: evacuate/verify first; silence the siren from the tablet or Mini App.

### Boiler (ecoNET24, local API)
- Symptoms: sensors read 0 or go unavailable → usually the boiler's WiFi flapped.
- Numeric REST sensors are guarded (missing field → 0, per-field `availability`),
  so a drop no longer spams `ValueError`. Root cause is hardware signal — reserve
  the boiler's IP / improve WiFi.
- Setpoint writes use `rmCurrNewParam` (the plain `newParam` endpoint is a no-op).

### EV charger (Tuya cloud)
- Status/energy come from `ev_query.py` (command_line). Cache is `/config/.ev_cache/`.
- On `cloud_error` / `quota_error`: check Tuya credentials and cloud quota. The
  script backs off and serves stale cache (up to 24h). Increase `scan_interval`
  to conserve quota. Reload with `command_line/reload`.
- Charging is gated by an EV↔boiler interlock; the scheduler writes the next
  window to `input_datetime.ev_charge_start`.

### Tuya quota / entity issues
- Single `ap-` cloud account is the source of truth (owns switches, moisture, EV).
- Stale state → `homeassistant.reload_config_entry` with that entry's `entry_id`.
- After a Tuya reload, moisture sensors may briefly report a stale `on` — the
  startup-grace flag covers this window.

### HA restart
- Needed for: component code changes (e.g. `miniapp_auth`), a new top-level
  integration, or a first `template:` block. `reload_all` won't load those.
- After restart the startup-grace flag blocks the leak alarm ~15 min.
- If startup fails, read `ha core logs`, fix the offending file over SSH, restart again.
