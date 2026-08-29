# Setup Guide

Step-by-step instructions for deploying this smart home stack on your own Home Assistant instance.

## Prerequisites

- Home Assistant OS (tested on 2026.5+) on any host (Hyper-V, Proxmox, RPi, NUC…)
- SSH access to your HA instance
- A Telegram bot created via [@BotFather](https://t.me/botfather)
- A Tuya IoT Platform account (for EV charger/smart plug API access)
- Nord Pool or Elering access (for electricity price automations; Latvia/Finland markets)
- Python 3.10+ with `paramiko` installed on your local machine

---

## 1. Clone this repository

```bash
git clone https://github.com/YOUR_USERNAME/MySmartHome.git
cd MySmartHome
pip install paramiko
```

---

## 2. Create your local secrets file

```bash
cp local_secrets.example.json local_secrets.json
```

Open `local_secrets.json` and fill in every value:

| Key | Description |
|-----|-------------|
| `HA_TOKEN` | Long-lived access token from HA → Profile → Security |
| `HA_HOST` | Local IP of your HA instance (e.g. `192.168.1.100`) |
| `HA_PORT` | HA HTTP port, usually `8123` |
| `HA_BASE_URL` | Full URL, e.g. `http://192.168.1.100:8123` |
| `HA_SSH_HOST` | Same as `HA_HOST` (or different if SSH is on another host) |
| `HA_SSH_PORT` | SSH port, usually `22` |
| `HA_SSH_USER` | SSH username, usually `root` for HA OS |
| `HA_SSH_KEY` | Path to your SSH private key, e.g. `~/.ssh/ha_ed25519` |
| `HA_SSH_PASSWORD` | SSH password (fallback if key auth fails) |
| `HA_SUDO_PASSWORD` | Sudo password for writing to `/config/` (same as SSH password for HA OS) |
| `HA_NOTIFY_ENTITY` | Telegram notify entity ID, e.g. `notify.YOUR_BOT_NOTIFY_ENTITY` |
| `TELEGRAM_BOT_TOKEN` | Token from @BotFather |
| `TELEGRAM_ALLOWED_UID` | Your numeric Telegram user ID (get it from @userinfobot) |
| `TUYA_CLIENT_ID` | Tuya IoT Platform client ID |
| `TUYA_CLIENT_SECRET` | Tuya IoT Platform client secret |
| `TUYA_EV_DEVICE_ID` | Tuya device ID of your EV charger |

---

## 3. Configure SSH key authentication

Generate a dedicated key for HA automation:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/ha_ed25519 -C "ha-automation"
```

Add the public key to your HA instance:

```bash
# Copy to clipboard
cat ~/.ssh/ha_ed25519.pub
```

On HA: go to **Settings → SSH Terminal** (or SSH in manually) and add the key to `/etc/ssh/authorized_keys` or `~/.ssh/authorized_keys`.

---

## 4. Deploy files to Home Assistant

These files must live in `/config/` on your HA instance:

```
/config/project_secrets.py
/config/local_secrets.json
/config/ev_best2h.py
/config/ev_query.py
/config/custom_components/miniapp_auth/__init__.py
/config/www/smarthouse.html   ← copy from miniapp/smarthouse_v8.html
```

Copy `project_secrets.py` and `local_secrets.json` to `/config/` via SSH:

```bash
scp project_secrets.py local_secrets.json root@YOUR_HA_IP:/config/
```

Or use the scripts in `scripts/setup/` which use paramiko and the secrets file.

---

## 5. Install the Mini App custom component

```bash
# Create directory on HA
ssh root@YOUR_HA_IP "mkdir -p /config/custom_components/miniapp_auth"

# Copy the component
scp custom_components/miniapp_auth/__init__.py root@YOUR_HA_IP:/config/custom_components/miniapp_auth/
```

Restart Home Assistant after copying.

---

## 6. Configure Home Assistant

### Telegram bot

Add to `configuration.yaml`:

```yaml
telegram_bot:
  - platform: polling
    api_key: !secret telegram_bot_token
    allowed_chat_ids:
      - YOUR_TELEGRAM_CHAT_ID

notify:
  - name: my_telegram_bot
    platform: telegram
    chat_id: YOUR_TELEGRAM_CHAT_ID
```

Add to `secrets.yaml`:

```yaml
telegram_bot_token: "YOUR_BOT_TOKEN"
```

### Nord Pool integration

Install via **Settings → Integrations → Add → Nord Pool**. Select your market (LV, FI, SE, etc.).

### Input helpers

Add to `configuration.yaml`:

```yaml
input_boolean:
  ev_manual_mode:
    name: EV Manual Mode
    icon: mdi:car-electric
  ha_startup_grace:
    name: HA Startup Grace Period

input_number:
  midnight_boiler_energy:
    name: Midnight Boiler Energy Snapshot
    min: 0
    max: 99999
    step: 0.01
    unit_of_measurement: kWh
  midnight_ev_energy:
    name: Midnight EV Energy Snapshot
    min: 0
    max: 99999
    step: 0.01
    unit_of_measurement: kWh

input_datetime:
  ev_charge_start:
    name: EV Next Charge Time
    has_date: true
    has_time: true
```

---

## 7. Configure automations

Import the automation templates from [`docs/templates/automations.yaml`](docs/templates/automations.yaml) (de-identified patterns; replace every `<PLACEHOLDER>`). See also [`docs/templates/`](docs/templates/README.md) for helpers, `command_line`, `rest_command`, and scripts. Key automations:

- **EV scheduler** — calls `ev_best2h.py` daily to find cheapest 2h window
- **Boiler Nord Pool** — turns boiler on/off based on current price threshold (0.04 EUR/kWh in Latvia)
- **Startup grace period** — blocks false moisture alarms for 15 min after HA restart
- **Telegram menu** — sends inline keyboard on "меню" command

Adjust entity IDs and price thresholds for your devices and market.

---

## 8. Set up the Telegram Mini App

1. Create a Mini App via [@BotFather](https://t.me/botfather): `/newapp`
2. Set the Mini App URL to your HA external URL: `https://YOUR_HA_EXTERNAL_URL/local/smarthouse.html`
3. Edit `miniapp/smarthouse_v8.html` — replace `YOUR_HA_EXTERNAL_URL` and `YOUR_BOT_NAME`
4. Copy to HA: `scp miniapp/smarthouse_v8.html root@YOUR_HA_IP:/config/www/smarthouse.html`

For external access, install **Tailscale** or use **DuckDNS + Let's Encrypt** in HA.

---

## 9. EV charger integration

If your EV charger uses Tuya Cloud (protocol 3.5, not supported by LocalTuya):

1. Register on [Tuya IoT Platform](https://iot.tuya.com/)
2. Create a Cloud Project, link your devices
3. Fill in `TUYA_CLIENT_ID`, `TUYA_CLIENT_SECRET`, `TUYA_EV_DEVICE_ID` in `local_secrets.json`
4. Deploy `ev_query.py` to `/config/`

The `ev_query.py` polls your charger status every 10s via HA `command_line` sensor.

---

## 10. Verify the setup

```bash
# Syntax check all Python files
python -m py_compile project_secrets.py ha_ssh.py ev_best2h.py ev_query.py

# Scan for accidentally committed secrets
python tools/secret_scan.py

# Test SSH connection to HA
python -c "from ha_ssh import ssh_connect, run; c=ssh_connect(); print(run(c,'hostname'))"
```

---

## Adapting for Your Setup

This project was built for a specific home in Latvia with Nord Pool LV pricing. Key things to adapt:

| Area | What to change |
|------|----------------|
| Electricity price threshold | `0.04 EUR/kWh` in boiler/floor heating automations |
| Price API | Elering API for LV/FI; swap for your regional day-ahead price source |
| Entity IDs | All entity IDs are specific to the original Tuya/SmartThings devices |
| Timezone | `Europe/Riga` in `ev_best2h.py` and time triggers |
| Currency | EUR; adjust formatting if needed |
| Language | Telegram messages are in Russian; translate as needed |

---

## Troubleshooting

**SSH fails with `AuthenticationException`**
→ Check that your public key is in `/etc/ssh/authorized_keys` on HA. For HA OS, root login via key requires the key there (not `~/.ssh/authorized_keys`).

**`ev_query.py` returns `cloud_error`**
→ Check Tuya credentials and that your HA IP is whitelisted in the Tuya IoT project.

**Telegram bot not responding**
→ Verify `chat_id` matches your user ID. Use `chat_id:` not `target:` in `telegram_bot.send_message` (target was deprecated in HA 2026.9.0).

**Moisture sensor false alarm on restart**
→ Enable the `ha_startup_grace` automation — it blocks the leak alarm for 15 min after HA starts.

**Nord Pool sensor missing attributes**
→ In HA 2026+, Nord Pool has no `today`/`raw_today` list. Use individual `sensor.nord_pool_*_current_price`, `*_next_price`, etc.
