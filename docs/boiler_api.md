# ecoNET24 Boiler — API Reference

## Device
- **IP**: YOUR_BOILER_IP (use a static DHCP reservation in your router)
- **Credentials**: stored outside Git, HTTP port 80

## Read
```
GET /econet/regParams
```
Returns JSON with `curr.tempCWU`, `tempCWUSet`, `pumpCWU`, `mode`, `tempCOSet`, etc.

## Write — IMPORTANT
- `GET /econet/rmCurrNewParam?newParamKey=INDEX&newParamValue=VALUE` — **actually works**
- `GET /econet/newParam?newParamName=X&newParamValue=Y` — returns OK but does NOT change values

## Parameter indices
| Index | Parameter | Range |
|-------|-----------|-------|
| 1281 | tempCWUSet (CWU setpoint) | 40–60°C |
| 1280 | tempCOSet (CO setpoint) | — |
| 75 | power on/off | 0=off, 1=on |

## HA rest_commands
| Command | Action |
|---------|--------|
| `rest_command.disable_boiler_cwu` | CWU setpoint → 40°C (stops ГВС heating) |
| `rest_command.enable_boiler_cwu` | CWU setpoint → 55°C |
| `rest_command.set_boiler_cwu_temp` | Parametric CWU (40/45/50/55/60°C), `{temp: N}` |
| `rest_command.set_boiler_co_temp` | Parametric CO (50/60/68/75°C), `{temp: N}` |
| `rest_command.boiler_turn_on` | Power ON |
| `rest_command.boiler_turn_off` | Power OFF |

**After adding new rest_command**: reload with `POST /api/services/rest_command/reload`
(not just `reload_core_config` — that doesn't reload rest_command!)
