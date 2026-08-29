# HA Jinja2 Gotchas

## DO NOT repeat these bugs

| Wrong | Correct |
|-------|---------|
| `as_datetime(x) \| as_local \| strftime('%H')` | `(as_datetime(x) \| as_local).strftime('%H')` |
| `\| from_json` on LLM output | `\| regex_search('"key"\\s*:\\s*"([^"]+)"')` |
| `time_pattern hours: "/4"` + time condition | Use fixed `at:` triggers (07:00, 11:00...) |
| Mutable list in loop: `{% set items = items + [...] %}` | `{% set ns = namespace(v=[]) %}` + `ns.v` |
| Floor heating: check `hvac_mode != heat_cool` | Check `preset_mode` instead (only one hvac_mode exists) |
| Nord Pool `today` / `raw_today` list | Does NOT exist — only individual sensors |
| `telegram_bot.send_message` with `target: YOUR_CHAT_ID` | Use `chat_id: YOUR_CHAT_ID` (target deprecated → breaks HA 2026.9.0) |

## Template patterns

```jinja2
{# Safe local time from ISO string #}
{{ (as_datetime(some_iso) | as_local).strftime('%d.%m.%Y %H:%M') }}

{# namespace for accumulation in loops #}
{% set ns = namespace(items=[]) %}
{% for x in something %}
  {% set ns.items = ns.items + [x] %}
{% endfor %}

{# Regex parse from LLM/API response #}
{{ response | regex_search('"action"\\s*:\\s*"([^"]+)"', ignorecase=True) | first }}

{# Nord Pool tomorrow (available after ~13:00) #}
{{ state_attr('sensor.nord_pool_lv_current_price', 'tomorrow') }}
```
