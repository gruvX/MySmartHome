# Configuration Templates

De-identified, copy-paste-ready Home Assistant snippets that mirror the patterns
used by this project. **Nothing here contains a real entity ID, token, IP, or
secret** — every site-specific value is a `<PLACEHOLDER>` you must replace.

| File | Goes into | Purpose |
|------|-----------|---------|
| `helpers.yaml` | `configuration.yaml` | `input_boolean` / `input_number` / `input_datetime` + a `template` presence sensor |
| `shell_command.yaml` | `configuration.yaml` | `command_line` / `shell_command` for the EV scripts |
| `rest_command.yaml` | `configuration.yaml` | REST calls to a local boiler / device API |
| `automations.yaml` | `automations.yaml` | price-based heating, safety (leak/smoke), EV, Telegram menu |
| `scripts.yaml` | `scripts.yaml` | reusable scenes callable from Telegram / Mini App / tablet |

## How to use

1. Copy the block you need into the matching HA file.
2. Replace every `<PLACEHOLDER>` — entity IDs (`<SWITCH_BOILER>`), thresholds
   (`<PRICE_THRESHOLD>`), IDs (`<CHAT_ID>`), etc.
3. **Never inline a secret.** Use `!secret <key>` (from `secrets.yaml`) for API
   keys and tokens. See [`../credentials.md`](../credentials.md).
4. Reload the relevant domain (see [`../runbooks.md`](../runbooks.md)) or restart HA.

## Placeholder convention

- `<SWITCH_*>`, `<SENSOR_*>`, `<CLIMATE_*>`, `<BINARY_SENSOR_*>` — entity IDs
- `<PRICE_THRESHOLD>` — number, e.g. `0.10` EUR/kWh
- `<CHAT_ID>` — your numeric Telegram user/chat ID
- `<HA_BASE_URL>`, `<DEVICE_IP>` — hosts/URLs (keep out of Git in real config)
- `!secret <name>` — value stored in `secrets.yaml`, never in the template
