# EV Charger — Technical Details

## Device
- **Real IP**: YOUR_EV_CHARGER_IP (set a static DHCP reservation in your router)
- **Protocol**: Tuya 3.5 — LocalTuya does NOT support (only up to 3.4)
- **Device ID**: stored in ignored `local_secrets.json` as `TUYA_EV_DEVICE_ID`
- **local_key**: stored outside Git

## Tuya Cloud API
- **client_id**: stored in ignored `local_secrets.json` as `TUYA_CLIENT_ID`
- **secret**: stored in ignored `local_secrets.json` as `TUYA_CLIENT_SECRET`
- **region**: EU — IoT Core subscription (Trial Edition)
- **Quota status**: Trial Edition credit **EXHAUSTED** (0.2/0.2 USD, ~2026-06-17). Trial cannot be re-subscribed.
  - Mitigation: `scan_interval` reduced 10s → 300s to slow consumption. Stale cache used for up to 24h when cloud down.
  - Long-term options: new Tuya developer account (fresh Trial), or Tuya Smart Life OAuth API.
- **Script**: `/config/ev_query.py` → queries Tuya Cloud → outputs JSON

## ev_query.py — caching behaviour
| Variable | Value | Meaning |
|----------|-------|---------|
| `RESULT_TTL` | 290s | Fresh cache: skip cloud call (slightly less than scan_interval=300) |
| `STALE_TTL` | 86400s | Use stale cache for up to 24h when cloud unreachable |
| Quota backoff | +30 min | On `code 28841004`: suppress re-attempts for 30 min |

## DPS codes
| Code | Description |
|------|-------------|
| `forward_energy_total` | Total energy ×0.01 = kWh |
| `work_state` | Charger state string |
| `work_mode` | Charge mode |
| `switch` | On/Off switch |
| `charge_energy_once` | Energy this session |

## HA sensors
- `sensor.ev_charger_energy` — kWh total (command_line, **300s** scan_interval)
- `sensor.ev_charger_status` — status string (command_line, **300s** scan_interval)
  - Values: `charger_charging`, `charger_insert`, `charger_pause`, `charger_free`, `charger_end`, `cloud_error`, `quota_error`
  - UI label for `quota_error`: "Нет данных (квота)" (tablet + mini app)
- `switch.ev_charger_switch` — unreliable (proto 3.5), use `sensor.ev_charger_status` for trigger logic

## Ghost entities (do not use)
Entities from deleted Tuya entry `01HAENTRYIDPLACEHOLDER0000` — `restored: True`, will never recover:
- `sensor.ev_charger_ev_status_zariadki`
- `sensor.ev_charger_ev_energiia_total`
- `select.ev_charger_ev_rabota_rezhim`
- `switch.ev_charger_switch_2`

## LocalTuya config entry
- Entry ID: `01HAENTRYIDPLACEHOLDER0000` — EV not functional here due to proto 3.5

## Known bugs in ev_query.py (unresolved as of 2026-06-22)
1. `r.get("result", [])` → TypeError when Tuya returns `result: null`. Fix: `(r.get("result") or [])`.
2. Error dict written as stale cache `data` slot → sensor stuck at `quota_error` for 24h after quota renews.
3. `res["result"]["expire_time"]` raises KeyError if field absent → token discarded, extra API calls.
4. File handles opened without context manager (`open()` not in `with`) — minor FD leak risk.
