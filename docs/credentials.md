# Credential Model — Where Secrets Live

This project strictly separates **public source** (committed to Git) from
**private runtime** (never committed). No token, password, private key, or API
secret is ever stored in tracked source, in HTML/JS delivered to a browser, in
agent/tool configuration, or in a URL.

## Public source vs private runtime

| | **Public source** (in Git) | **Private runtime** (never in Git) |
|---|---|---|
| What | React `.jsx`, `miniapp/*.html` templates, `docs/**`, `docs/templates/**`, Python helpers (`ha_ssh.py`, `ev_*.py`, `project_secrets.py`), `tools/secret_scan.py` | Real tokens/passwords/keys, deployed HTML that embeds a local token, backups, caches, agent logs |
| Where it lives | the repository | `local_secrets.json` (chmod 600), HA `secrets.yaml`, environment variables, the browser's `localStorage`, files under `.gitignore` |
| Contains secrets? | **Never** — only placeholders / `!secret` refs / key *names* | Yes — this is the only place real values exist |

Everything under `docs/templates/` and every code example in `docs/` uses
`<PLACEHOLDER>` values or `!secret <name>` / `secret("<KEY>")` references. If you
ever find a real value in tracked source, treat it as a leak: rotate it and run
`python tools/secret_scan.py --all`.

## The three secret stores

1. **`local_secrets.json`** — used by local deploy scripts and by on-HA python
   (`ev_query.py`, etc.). JSON dict of `KEY: value`. **Must be `chmod 600`.**
   Loaded via `project_secrets.secret(name)`, which checks **environment
   variables first**, then this file. Lives beside the repo locally and at
   `/config/local_secrets.json` on HA. Git-ignored. Start from
   `local_secrets.example.json`.
2. **HA `secrets.yaml`** — used by `configuration.yaml` via `!secret <name>`
   (Telegram bot token, boiler user/password, integration keys). Never inline
   these in YAML.
3. **Environment variables** — override both of the above for CI/one-off runs;
   `project_secrets.secret()` reads env before the file.

```bash
# create your private file from the template, then lock it down
cp local_secrets.example.json local_secrets.json
chmod 600 local_secrets.json
```

## Tokens must NEVER be in…

- **HTML / JavaScript** shipped to a browser — the public Mini App HTML carries
  no HA bearer token. The Mini App validates Telegram `initData` server-side and
  proxies allow-listed actions through the `miniapp_auth` custom component.
- **URLs / query strings** — a token in a URL leaks via history, logs, and
  referrers. The tablet bootstraps a token *once* from a URL param, then stores
  it in `localStorage` and strips it from the URL.
- **Agent / tool configuration, CLAUDE.md, or committed docs** — only the
  permission system or the human user grants access; config files never carry
  live secrets.

## Per-consumer token model

Each consumer gets its **own** token scoped to what it needs — never share the
admin token with a browser-facing surface.

| Consumer | Token / auth | Scope | Stored in |
|----------|--------------|-------|-----------|
| **Admin** (deploy scripts, agent) | HA long-lived token (`HA_TOKEN`) | full admin | `local_secrets.json` / env only |
| **EV / Tuya** | Tuya `client_id` + `client_secret` + device_id | cloud device query | `local_secrets.json` |
| **Mini App** | limited HA user token + Telegram `initData` validation | allow-listed states/actions only | server-side in `miniapp_auth`; browser gets none |
| **Tablet** | dedicated limited HA user token | dashboard read + limited control | browser `localStorage` (key `tablet_token`), never in the file |
| **Live Map / Boiler page** | token from `localStorage` (`livemap_token`); demo fallback if absent | read live state | browser `localStorage` only |

Rotating a token affects only its consumer. Revoke the old refresh token in HA
after minting a new one, and never downgrade a limited surface to the admin token.

## Before every commit

```bash
python tools/secret_scan.py          # scans staged files (pre-commit guard)
python tools/secret_scan.py --all    # scans the whole tree incl. ignored runtime files
```

The scanner reports **path, line, type, and a short fingerprint only** — it never
prints secret values. `docs/**` must show **zero** findings.
