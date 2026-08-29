# 03 — Embedded UI pages audit (boiler.html / livemap.html / graph.html) + Lovelace

Read-only audit, 2026-08-16. Snapshot of 817 HA states taken same day.
Deploy parity verified by md5 — **all three repo files are byte-identical to the deployed
`/config/www/` copies**:

| file | md5 | deployed mtime |
|---|---|---|
| `miniapp/boiler.html` | `69d825ddf817d5ba4c090cff7a32c779` | 2026-08-16 15:47 |
| `miniapp/livemap.html` | `6bcf508b974ab5dc82b6f7456418600d` | 2026-07-04 22:29 |
| `miniapp/graph.html` | `1ede4921288a373b029b14d0012272c2` | 2026-07-04 22:29 |

---

# A) miniapp/boiler.html — 27 064 B, 365 lines

Served at `/local/boiler.html`; also embedded as the "Котёл" tab inside the Mini App and the
tablet.

## A1. Screens / entities / actions

Single screen, no tabs. Two regions:

**Left stats column** (`section.stats`)

| widget | element id | entity read |
|---|---|---|
| Режим работы | `v-mode`, `mode-dot` | `sensor.boiler_mode` (+ `sensor.boiler_power`, `binary_sensor.boiler_feeder` for the dot) |
| Мощность котла | `v-power` | `sensor.boiler_power` |
| Уровень топлива | `v-fuel` | `sensor.boiler_fuel_level` |
| Поток топлива | `v-feeder` | `binary_sensor.boiler_feeder` |
| Мощность наддува | `v-fan` | `sensor.boiler_fan_power` |
| Пламя | `v-flame` | derived (`power>0 or feeder on`) |
| Авария | `v-alarm` | `sensor.boiler_mode` **only** (since the 2026-08-16 change) |

**Right mnemonic SVG** (`section.diagram`)

| badge | element id | entity |
|---|---|---|
| Улица | `t-out` | `sensor.boiler_outside_temperature` |
| Термостат | `t-room` | `binary_sensor.boiler_thermostat` |
| Дымоход | `t-flue` | `sensor.boiler_flue_gas_temperature` |
| Подача · котёл | `t-co` / `t-coset` | `sensor.boiler_co_temperature` / `sensor.boiler_co_setpoint` |
| MIX 1 · радиатор | `t-mix` / `t-mixset` | `sensor.boiler_mixer_temperature` / `sensor.boiler_mixer_setpoint` |
| Бак ГВС | `t-cwu` / `t-cwuset` | `sensor.boiler_cwu_temperature` / `sensor.boiler_cwu_setpoint` |
| Обратка | `t-ret` | `sensor.boiler_return_temperature` |
| Электро-ТЭН | `t-teng`, `#teng`, `#teng-pill` | `switch.smart_plug_2_socket_1` |
| pump animations | `pw-rad`/`pw-dhw`/`fd-*` | `binary_sensor.boiler_co_pump`, `binary_sensor.boiler_cwu_pump`, `binary_sensor.boiler_circulation_pump` |

**Actions: NONE.** The page is strictly read-only — no `POST`, no `/api/services`, no
`miniapp-action`. Only UI-local controls (theme toggle, manual refresh, token dialog).

**Transport / auth**: `fetch(BASE + "/api/states", {Authorization: "Bearer " + token})` at
line 347, `BASE=""` (line 270), i.e. same-origin `GET /api/states`, pulling **all 817 states**
every 15 s (line 360) just to read 20. Token comes from `localStorage["livemap_token"]`
(shared key with livemap/graph). No token in the file. It does **not** use
`/api/miniapp-auth` or `/api/miniapp-action` — so inside the Telegram Mini App this tab is
LIVE only if the user previously pasted an admin/long-lived token into this browser's
localStorage; otherwise it silently shows DEMO.

## A2. Entity cross-reference vs states.json

All 20 referenced entities **exist**. None is `unavailable`/`unknown` right now:

```
sensor.boiler_mode                    'Догорание'
sensor.boiler_power                   '0'
sensor.boiler_fuel_level              '0'      (sensor physically disconnected — always 0)
sensor.boiler_fan_power               '0'
binary_sensor.boiler_feeder           'off'
sensor.boiler_flue_gas_temperature    '29.5'
sensor.boiler_outside_temperature     '23.9'
sensor.boiler_co_temperature          '29.7'
sensor.boiler_co_setpoint             '67'
sensor.boiler_return_temperature      '26.3'
sensor.boiler_mixer_temperature       '24.5'
sensor.boiler_mixer_setpoint          '20'
sensor.boiler_cwu_temperature         '54.6'
sensor.boiler_cwu_setpoint            '40'
binary_sensor.boiler_co_pump          'on'
binary_sensor.boiler_cwu_pump         'on'
binary_sensor.boiler_circulation_pump 'on'
binary_sensor.boiler_thermostat       'on'
binary_sensor.boiler_alarm            'on'   <-- referenced in ENT but no longer rendered
switch.smart_plug_2_socket_1          'on'
```

Existing boiler entities the page does **not** use: `binary_sensor.boiler_fan`,
`sensor.boiler_feeder_temperature`, `sensor.boiler_total_energy`, `switch.boiler`.

## A3. VERIFICATION of the «ТРЕВОГА» fix claim — **CLAIM HOLDS**

The claim: boiler.html's false «ТРЕВОГА» was fixed today so it reads the real fault mode.

Evidence:

* Lines 314-323 replace the old `binary_sensor.boiler_alarm` read with a `sensor.boiler_mode`
  string test:
  ```
  320:  var mRaw=String(g(ENT.mode)), mLow=mRaw.trim().toLowerCase();
  321:  var alarmNA=(mLow===""||mLow==="unavailable"||mLow==="unknown"||mLow==="none"||mLow==="null"||mLow==="—");
  322:  var alarm=(!alarmNA&&mLow==="авария");
  323:  var av=$("v-alarm"); if(av){av.textContent=alarmNA?"нет данных":(alarm?"ТРЕВОГА":"Нет");av.className="val sm "+(alarmNA?"":(alarm?"bad":"ok"));}
  ```
* `configuration.yaml` line 396 confirms the mode map really contains `9: 'Авария'`, and the
  template emits that exact Cyrillic string (`"Авария".toLowerCase() === "авария"` — the
  comparison is correct).
* `automations.yaml` id `1789400001001` ("🔥 Сторож котла — режим АВАРИЯ") triggers on
  `sensor.boiler_mode to: Авария`, and its own description explicitly states it deliberately
  does **not** watch `binary_sensor.boiler_alarm` because that bit fires normally in summer.
  So the page and the watchdog now agree on one source of truth.
* Live state right now: `sensor.boiler_mode = 'Догорание'`, `binary_sensor.boiler_alarm = 'on'`.
  Under the old code the cell would read «ТРЕВОГА» (red) — a false alarm. Under the new code it
  reads «Нет» (green). **The false positive is gone.**
* The unavailable path is honest too: `alarmNA` → «нет данных» with no colour class, i.e. it
  neither invents a fault nor a fabricated "Нет".

Residual caveat (not a regression, but a new blind spot to record): the page now has **no**
rendering of `binary_sensor.boiler_alarm` at all. A genuine ecoNET `alarmOutput` fault that
does not also drive mode→9 will now be drawn as a green «Нет». `ENT.alarm` is kept in the map
(line 285) but is dead — see A5.

## A4. HONESTY DEFECTS (priority section)

**H-A1 — full hardcoded DEMO dataset that renders as ordinary numbers (lines 287-298).**
```
287: var DEMO={
288:   "sensor.boiler_mode":{state:"Догорание"},"sensor.boiler_power":{state:"0"},"sensor.boiler_fuel_level":{state:"0"},
...
294:   "sensor.boiler_cwu_temperature":{state:"55.2"},"sensor.boiler_cwu_setpoint":{state:"40"},
...
299: var DATA=DEMO;
```
`DATA` starts as DEMO, `render()` is called before `load()` (line 360), so the **first paint is
always fabricated data**. The values are deliberately plausible (55.2 °C ГВС, 42.9 °C подача,
18.8 °C улица) and are drawn in exactly the same badges as live data. The only differentiator
is a small pill in the top bar and the footer text. Severity: medium — mitigated by the badge,
but the numbers themselves carry no marking.

**H-A2 — every fetch failure silently reverts LIVE→DEMO (line 349).**
```
347: fetch(BASE+"/api/states",{headers:{Authorization:"Bearer "+token}}).then(function(r){if(!r.ok)throw 0;return r.json();})
348:   .then(function(arr){var m={};arr.forEach(function(s){m[s.entity_id]=s});DATA=m;live=true;render();})
349:   .catch(function(){DATA=DEMO;live=false;render();});
```
A 401 (expired token), a network blip or an HA restart replaces real readings with the demo
numbers. The user sees numbers change (e.g. ГВС 54.6 → 55.2) and no error message — only the
pill flips to amber "ДЕМО". There is no "last successful update" timestamp anywhere, so a
viewer glancing at the diagram cannot tell whether the numbers are 2 s or 2 days old.

**H-A3 — no staleness/age marker at all.** Footer is a fixed string (line 342):
```
342: $("foot-l").textContent=live?"данные ecoNET24 · обновляются каждые 15 с":"снимок · демо (нажмите ⚙ и вставьте токен HA)";
```
"обновляются каждые 15 с" describes the *poll interval*, not the data age. `/api/states`
returning successfully proves HA is up; it proves nothing about ecoNET being reachable. The
known failure mode of this house (ecoNET WiFi flap, IP drift .10→.11→.12) makes the boiler
sensors go `unavailable`, which the page renders as "—" per-field — acceptable — but the pill
still says **LIVE** and the footer still says **данные ecoNET24**, so a fully dead boiler feed
is presented under a green LIVE badge.

**H-A4 — unavailable binary sensors rendered as reassuring normal states.**
`on()` (line 302) returns `false` for anything that is not on/true/home/heat, including
`unavailable`:
```
302: function on(e){return ["on","true","home","heat"].indexOf(String(g(e)).toLowerCase())>=0}
313: setTxt("v-feeder", on(ENT.feeder)?"Работает":"Стоп"); setTxt("v-flame", firing?"Есть":"Нет");
329: setTxt("t-room", on(ENT.thermo)?"Запрос":"Норма");
337: var rad=on(ENT.pco), dhw=on(ENT.pcwu), circ=rad||on(ENT.pcirc)||dhw;
```
An unavailable thermostat prints **«Норма»** — a positive assertion the page cannot back.
Likewise unavailable pumps are drawn as stopped (static, grey) rather than unknown, and an
unavailable feeder prints «Стоп». Note the ТЭН badge *does* handle this correctly
(line 331/334: `tengNA` → "н/д"), which proves the pattern was known and simply not applied to
the other five booleans.

**H-A5 — hardcoded numbers inside the SVG markup itself** (lines 193, 207, 214, 215, 223, 224,
232, 233, 239), e.g.:
```
193: <text x="13" y="19" font-size="13" fill="#fff" font-weight="700">☁ <tspan id="t-out">18.8</tspan>°C</text>
214: <rect class="bpill" x="0" y="0" width="70" height="27" rx="13"/><text class="btext" x="13" y="18" font-size="13"><tspan id="t-co">42.9</tspan>°C</text>
232: ... <tspan id="t-cwu">55.2</tspan>°C ...
```
If the script ever fails to run (JS error, CSP), the page is a fully-rendered, plausible-looking
boiler schematic with fake temperatures and no ДЕМО badge (the badge markup at line 117 does say
"ДЕМО" statically, which partly saves this). Correct pattern would be `—` in the markup.

**H-A6 — «Уровень топлива» is displayed even though the sensor is known-dead.**
`sensor.boiler_fuel_level` reads a hard `0` (physically disconnected — documented in project
notes, and the template emits `0` on missing field, `configuration.yaml`). Line 312 renders
`pct()` → **"0%"**, i.e. the page asserts "fuel level: 0%" — an empty hopper — when in truth
there is no measurement. The tablet home page deliberately removed this card for exactly this
reason; boiler.html still shows it.

**H-A7 — fabricated zeros originate upstream, and the page cannot see them.** All 13 numeric
boiler templates use `{% ... %}{{ value }}{% else %}0{% endif %}` (e.g. line 377 of
configuration.yaml for the mixer setpoint). The `availability:` clause normally saves this, but
where the field is present-but-meaningless the page still prints a confident number. Not a
boiler.html bug — recorded because the page has no way to distinguish it.

**No hardcoded threshold/label contradictions found.** The page displays no price thresholds and
no automation labels, so there is nothing to contradict.

## A5. Dead code / unused references

* `ENT.alarm` → `binary_sensor.boiler_alarm` (line 285) is defined and commented as
  "kept for reference/demo parity only" but is **never read** by `render()`. The DEMO map also
  still carries it (line 297). Dead reference, deliberately so.
* `ti()` (line 304) is used (setpoints) — not dead. `pct()` used. `t1()` used.
* No unreferenced functions; the script is tight (≈95 lines). `LS_THEME` used.
* Unused DOM: none found — every `id=` in the SVG is written by `render()` except purely
  decorative elements.

## A6. Structure / reuse verdict

* 365 lines: ~110 CSS, ~140 static SVG, ~95 JS in a single IIFE. No dependencies, no build.
* State flow: `localStorage token → GET /api/states (all 817) → DATA map → render()` every 15 s.
  Single-direction, no caching, no diffing, full re-render of ~25 text nodes. Cheap.
* **Worth reusing**: the SVG mnemonic itself (well-built, theme-aware, `prefers-reduced-motion`
  respected, anchors+leaders layout), the ТЭН NA handling pattern, the token dialog.
* **Worth rebuilding**: the DEMO fallback (should become an explicit "нет связи" state, not
  substitute numbers), the `on()` helper (needs a third `unknown` state), the fuel-level cell
  (drop it), and the transport (fetching all 817 states every 15 s to read 20 — a
  `?filter=` / websocket / `/api/miniapp-states` call would be ~40× cheaper).

---

# B) miniapp/livemap.html — 32 175 B, 329 lines

Served at `/local/livemap.html`. **Deployed copy is from 2026-07-04 and has not been touched
since** (mtime 2026-07-04 22:29) — it predates every 2026-07/08 correctness fix applied to the
tablet and Mini App.

## B1. Screens / entities / actions

Single scrolling page, no tabs; six sections rendered by one `render()` (line 236) into `#app`.

**Header / env chips** (lines 275-282)

| element | entity |
|---|---|
| weather icon + temp | `weather.forecast_home`, `sensor.smart_weather_station_temperature` |
| "Дома / Нет дома" | **`person.owner`** ← does not exist (see B2) |
| LIVE/ДЕМО badge | fetch status only |

**Hero — price** (lines 283-289): `sensor.nord_pool_lv_current_price`,
`sensor.nord_pool_lv_next_price`, `sensor.nord_pool_lv_lowest_price`,
`sensor.nord_pool_lv_highest_price`, plus a computed "сегодня N кВт·ч" total.

**24-hour price chart** (`chartHtml`, line 228): reads `/local/today_prices.json` (no auth),
falls back to a hardcoded array.

**Zone «Энергия»** (`PLUGS`, lines 151-158) — 6 tiles, each *tap = toggle*:

| tile | switch (action) | energy sensor | midnight snapshot |
|---|---|---|---|
| Бойлер | `switch.smart_plug_2_socket_1` | `sensor.boiler_total_energy` | `input_number.midnight_boiler_energy` |
| Полотенцесушитель | `switch.kalarifer_socket_1` | `sensor.terarium_total_energy` | `input_number.midnight_kalarifer_energy` |
| Аквариум | `switch.akvarium_svet_socket_1` | `sensor.akvarium_svet_total_energy` | `input_number.midnight_akv_energy` |
| Черепаха / рецирк. | `switch.retserkuliatsiia_goriachai_vody_socket_1` | `sensor.cherepakha_total_energy` | `input_number.midnight_chep_energy` |
| Гидрофор | `switch.zigbee_plug_2_socket_1` | `sensor.zigbee_plug_2_total_energy` | `input_number.midnight_gidro_energy` |
| EV зарядка | `switch.ev_charger_switch` | `sensor.ev_charger_energy` | `input_number.midnight_ev_energy` |

**Zone «Климат»** (lines 248-252): `climate.floor_heating`, `climate.floor_heating_2`
(tap → `climate.set_preset_mode` manual↔auto), read-only boiler tile
(`sensor.boiler_mode`, `sensor.boiler_co_temperature`, `sensor.boiler_cwu_temperature`).

**Zone «Электромобиль»** (lines 254-260): `sensor.ev_charger_status`,
`switch.ev_charger_switch` (tap → toggle), `input_datetime.ev_charge_start`,
`input_boolean.ev_manual_mode` (tap → toggle), `sensor.ev_charger_energy`.

**Zone «Режимы»** (lines 262-266): `input_boolean.night_saver` (tap),
`input_boolean.security_armed` (tap, confirm on disarm), `switch.voda_kran_switch_1`
(tap, confirm "Перекрыть воду в доме?").

**Zone «Безопасность»** (lines 268-273, read-only): `binary_sensor.door_sensor_door`,
`binary_sensor.wifi_th_smoke_sensor_smoke`, and 4 moisture sensors
(`vannaia`, `garazh`, `kukhnia`, `water_sensor_4`).

**Services it can invoke** (line 194): `POST /api/services/{domain}/{service}` with the raw
localStorage token — i.e. **arbitrary-domain, full-privilege service calls**, currently used
for `switch.turn_on/off`, `input_boolean.turn_on/off`, `climate.set_preset_mode`.
Also `?focus=<entity_id>` deep-link support (line 235).

**Transport / auth**: `GET /api/states` + `POST /api/services/...` with
`Authorization: Bearer <localStorage["livemap_token"]>`. Same token key as boiler.html and
graph.html. It does **not** use `/api/miniapp-auth` or `/api/miniapp-action`, so it is **not
covered by the miniapp_auth allowlist hardening** — whatever token is pasted here has its full
HA privileges exposed to any script on the page.

## B2. Entity cross-reference vs states.json

**MISSING — does not exist in HA:**

* **`person.owner`** (lines 147, 240, 278). The real entity is `person.owner` (`'home'`).
  `isOn("person.owner")` therefore always returns `false`, so the header chip permanently
  reads **«🚶 Нет дома»** regardless of actual presence. This is a false statement rendered as
  fact on every load, live or demo.

All other 30 referenced entities exist. **None currently reads `unavailable`/`unknown`**, but
two need annotating:

* `climate.floor_heating` = **`'off'`** (attrs `preset_mode: manual`, `current_temperature: 26.8`)
* `climate.floor_heating_2` = **`'off'`** (attrs `preset_mode: manual`, `current_temperature: 27.0`)

  The page never reads `state` for climate — only the `preset` attribute (line 179). With
  «Режим Жара» having switched the thermostats off, both tiles render **green / class `on` /
  «manual»** — i.e. the map claims floor heating is engaged while the thermostats are OFF.
  See H-B4.

## B3. HONESTY DEFECTS (priority section)

**H-B1 — hardcoded 24-hour price curve rendered as "Цена по часам · сегодня" (line 221).**
```
221: var PRICES=[0.0186,0.023,0.019,0.0181,0.0193,0.0185,0.0204,0.0224,0.0273,0.0213,0.0159,0.0161,0.0134,0.0108,0.01,0.0119,0.0107,0.015,0.0214,0.033,0.0795,0.1165,0.1212,0.1194];
```
`loadPrices()` (line 222) silently keeps this array on **every** failure path — `!r.ok`, no
`j.prices`, **no entry for today's date**, or a network error (`.catch(function(){})`, line 226).
The chart header then still says «сегодня» and «24 ч данных» (line 233). These are the prices of
2026-07-04, the day the file was written. Today's file is currently present and fresh
(`/config/www/today_prices.json`, updated 2026-08-16T13:20Z, contains the `2026-08-16` key), so
the defect is latent right now — but any day the price pipeline misses, the map shows a full
24-bar chart of nine-week-old numbers with no marking whatsoever. Severity: **high**.

**H-B2 — the "обновлено N сек назад" timestamp is reset on FAILED fetches (lines 185-187).**
```
184:  if(r.ok){return r.json().then(function(a){S=toMap(a);live=true;msg="";updated=new Date();render()})}
185:  if(r.status===401){msg="Токен неверный"} live=false; updated=new Date(); render();
186: }).catch(function(){live=false;updated=new Date();render()});
187: } else { live=false; updated=new Date(); render(); }
```
`updated` is stamped in all four branches, including 401, non-2xx and network error. `S` is left
holding the *previous* (or DEMO) data. Result: the hero line «Цена электричества · Nord Pool LV ·
обновлено 3 сек назад» (line 286) and the footer «обновлено 3 сек назад» (line 296) assert
freshness for data that may be hours old. The only signal is the small badge flipping to amber.
Severity: **high** — this is the textbook stale-data-with-fresh-age-marker defect.

**H-B3 — optimistic UI reports success for service calls that failed, and fabricates control
entirely when there is no token (lines 189-197).**
```
190:  busy[entity]=1; S[entity]=Object.assign({},S[entity]||{},optimistic); render();
195:    body:JSON.stringify(...)}).then(done,done);
196:  } else { done(); }
199:  var on=isOn(ent); var doIt=function(){callService("switch",on?"turn_off":"turn_on",ent,{state:on?"off":"on"});toast(name+": "+(on?"выкл":"вкл"))};
```
`.then(done, done)` discards the HTTP result — a 401/403/500, or the well-known Tuya
`sign invalid` failure that leaves the physical device untouched, all produce the same green
tile plus a toast «Бойлер: вкл». With **no token at all** (line 196) the page never contacts HA
and still flips the tile and shows the toast: the demo mode is *interactive*, so a visitor can
"control" the house and every tap appears to work. Severity: **high**.

**H-B4 — an OFF thermostat is drawn as a green, heating tile (lines 179, 250-251).**
```
179: function toMap(arr){var m={};arr.forEach(function(s){m[s.entity_id]={state:s.state,temp:...current_temperature,preset:...preset_mode}});return m}
250: tile({icon:"🌡️",name:"Пол · ванная",extra:"heat",...,on:fb.preset==="manual",stateTxt:fb.preset||"—",...})
```
`state` is captured but never consulted for climate. Both thermostats are currently `off`
(Режим Жара) yet both tiles show class `on` (green border, pulsing dot) and the label «manual».
Tapping them calls `climate.set_preset_mode`, which cannot restore heat on an `off` thermostat —
so the control is also non-functional in this state while appearing to work (compounds H-B3).

**H-B5 — hardcoded «порог 0.04» contradicts the live boiler automation (line 289).**
```
289: '<div class="next">Следующий час: <b ...>'+...+'</b> · порог <b>0.04</b> · сегодня <b>'+totalToday.toFixed(1)+' кВт·ч</b></div>'
```
Verified in `/config/automations.yaml`: the boiler Nord Pool automation uses
`threshold: 0.10` (line 569), while the floor-heating (line 1446) and towel-warmer (line 4551)
automations use `0.04`. The map prints a single global «порог 0.04», which is wrong for the
largest load in the house. Same hardcoding drives the colour/label logic:
```
170: function priceColor(p){return p<=0.04?"var(--on)":p<=0.10?"var(--warn)":"var(--crit)"}
171: function priceTag(p){return p<=0.04?"дёшево":p<=0.10?"средне":"дорого"}
```

**H-B6 — fabricated zeros in the day total (line 241) and lifetime-as-today (line 169).**
```
169: function todayKwh(t,s){var T=num(t),Sn=num(s);if(T==null)return null;if(Sn==null)return T;return Math.max(0,T-Sn)}
241: var totalToday=PLUGS.reduce(function(a,d){return a+(todayKwh(d[3],d[4])||0)},0);
```
Line 241 is the classic `||0`: any unavailable meter contributes a silent `0` to the headline
«сегодня N кВт·ч», so a partly-dead set of sensors produces a confidently low, wrong total with
no indication. Line 169's `if(Sn==null)return T` is worse in kind: when the midnight snapshot is
missing it returns the **lifetime cumulative total** (e.g. 1035.97 kWh for the EV) and labels it
«сегодня».

**H-B7 — non-existent `person.owner` renders a false «Нет дома»** — see B2. Line 240:
```
240: var wIcon=WEATHER[g("weather.forecast_home").state]||"🌡️", wTemp=num("sensor.smart_weather_station_temperature"), home=isOn("person.owner");
```

**H-B8 — safety tiles assert "clean/dry" for unavailable sensors (lines 268-273).**
`isOn()` (line 168) maps `unavailable` → `false`, so an offline door sensor prints «Закрыта», an
offline smoke sensor prints «Чисто», and offline moisture sensors print «Сухо» with a `·` glyph
that is visually identical to a genuine dry reading. The page also **ignores
`sensor.leak_protection_status`** (which exists, currently `'ok'`) — the single agreed source of
leak truth in this house. Severity: **high**, because these are the tiles a user would trust in
an emergency.

**H-B9 — a 45-entity hardcoded DEMO snapshot is the initial render state (lines 128-148).**
`S` is seeded from `DEMO` (line 161) and `render()` runs before `load()` (line 325), so the first
paint always shows invented values (price 0.01407 €, EV 834.73 kWh, ГВС 45.1°, all plugs on).
The DEMO map even contains `"sensor.smart_weather_station_temperature":{state:"unavailable"}`
(line 147) — a deliberately faked unavailability. Badged ДЕМО, but the numbers themselves are
unmarked and the page is fully interactive in this state (H-B3).

**H-B10 — no age marker on the price chart.** `today_prices.json` carries an `"updated"`
timestamp (currently `2026-08-16T13:20:00Z`) which `loadPrices()` reads past and discards
(line 225 only touches `j.prices`). The chart cannot tell the viewer how old the curve is.

## B4. Dead code / unused references

* No unreferenced functions — every helper (`esc`, `toast`, `relTxt`, `zone`, `tile`,
  `chartHtml`, `showConfirm`, `toggleSwitch`, `toggleBool`, `toggleFloor`, `evToggle`) is called.
* `person.owner` is referenced but resolves to nothing (B2) — a dead entity reference that still
  renders output.
* `msg` (line 161) is only ever set to "Токен неверный" on HTTP 401; a 403 or 500 leaves it
  empty, so those failures are indistinguishable from "no token".
* `j.updated` from `today_prices.json` and `j.prices15` (15-minute series, present in the file)
  are both ignored.
* `busy[]` is set for every `callService` but `render()` on the no-token path clears it
  immediately, so `.pending` styling is effectively invisible without a token.

## B5. Structure / reuse verdict

* 329 lines: ~103 CSS, ~200 JS, one IIFE, full innerHTML re-render into `#app` every 10 s
  (`setInterval(render,10000)`, line 325) plus a state fetch every 15 s and a price fetch every
  10 min. No dependencies.
* State flow: `DEMO seed → GET /api/states → toMap() (keeps only state + current_temperature +
  preset_mode) → S → render() → innerHTML`. `toMap` throws away all other attributes, which is
  why climate `state` and any `unavailable` nuance are lost downstream.
* **Worth reusing**: the tile/zone HTML builders, the `?focus=` deep-link highlight, the price
  range/mark hero, the confirm dialog for destructive actions (water valve, disarm).
* **Worth rebuilding**: everything in B3. Concretely — drop `DEMO` and the `PRICES` fallback in
  favour of an explicit "нет данных" state; stamp `updated` only on success; surface
  service-call failures; read `state` for climate; use `sensor.leak_protection_status`;
  fix `person.owner`; drive the threshold label from the automation instead of a literal; and
  move service calls behind `/api/miniapp-action` so this page stops carrying an unrestricted
  admin token.

---

# C) miniapp/graph.html — 59 119 B, 413 lines

Served at `/local/graph.html`. Force-directed canvas graph of the house. **Deployed copy dates
from 2026-07-04 and has not been touched since.** Referenced from the Mini App as the
"force-graph" screen.

## C1. Screens / entities / actions

One full-screen canvas, no tabs. Overlays: title + LIVE/ДЕМО badge, hint, colour legend,
HUD (⚙ token / ⟳ refresh / + / − / ⤢ fit), and a **detail panel** that opens on node click.

The graph itself is **entirely hand-authored**: 64 nodes (`N`, lines 83-101) and 98 edges
(`L`, lines 102-123), verified internally consistent — 0 orphan link endpoints, every node has
a `META` entry, every `NODE_ENT` key is a real node.

Only **23 of the 64 nodes carry live data** (`NODE_ENT`, lines 191-204). Entities read:

| node | entity/entities |
|---|---|
| Бойлер | `switch.smart_plug_2_socket_1`, `sensor.boiler_total_energy`, `input_number.midnight_boiler_energy` |
| Полотенцесушитель | `switch.kalarifer_socket_1`, `sensor.terarium_total_energy`, `input_number.midnight_kalarifer_energy` |
| Аквариум | `switch.akvarium_svet_socket_1`, `sensor.akvarium_svet_total_energy`, `input_number.midnight_akv_energy` |
| Черепаха | `switch.retserkuliatsiia_goriachai_vody_socket_1`, `sensor.cherepakha_total_energy`, `input_number.midnight_chep_energy` |
| Гидрофор | `switch.zigbee_plug_2_socket_1`, `sensor.zigbee_plug_2_total_energy`, `input_number.midnight_gidro_energy` |
| EV зарядка | `switch.ev_charger_switch`, `sensor.ev_charger_status`, `sensor.ev_charger_energy`, `input_number.midnight_ev_energy`, `input_datetime.ev_charge_start`, `input_boolean.ev_manual_mode` |
| Кран воды | `switch.voda_kran_switch_1` |
| Пол ванная / душевая | `climate.floor_heating`, `climate.floor_heating_2` |
| ecoNET24 | `sensor.boiler_mode`, `sensor.boiler_co_temperature`, `sensor.boiler_cwu_temperature` |
| Nord Pool | `sensor.nord_pool_lv_current_price`, `_next_price`, `_lowest_price`, `_highest_price` |
| Влага ×4 | `binary_sensor.vannaia_moisture`, `garazh_moisture`, `kukhnia_moisture`, `water_sensor_4_moisture` |
| Дым / Дверь | `binary_sensor.wifi_th_smoke_sensor_smoke`, `binary_sensor.door_sensor_door` |
| security_armed / night_saver / ev_manual_mode / grace | `input_boolean.security_armed`, `night_saver`, `ev_manual_mode`, `ha_startup_grace` |
| Присутствие | **`person.owner`** ← does not exist |
| ev_charge_start | `input_datetime.ev_charge_start` |

**Actions** (panel `controlsHTML`, line 290; dispatcher line 311):

* `homeassistant.turn_on` / `homeassistant.turn_off` on plug / valve / bool / EV entities
  (generic domain — line 312)
* `climate.set_preset_mode` (`manual`) **followed by** `climate.set_temperature` `30` — the
  "Тепло 30°" button (line 314)
* `climate.set_preset_mode` (`auto`) — the "Авто" button (line 315)
* `🗺 В живой карте` → navigates the **top window** to `/local/livemap.html?focus=<entity>`
  (line 288) — note `window.top.location.href`, so inside the Mini App this replaces the whole
  app, not a tab.

**Transport / auth**: `GET /api/states` every 20 s (line 408) and
`POST /api/services/{domain}/{service}` (line 287), both with
`Authorization: Bearer <localStorage["livemap_token"]>` — the same shared key as boiler.html
and livemap.html. Again **not** routed through `/api/miniapp-auth` / `/api/miniapp-action`, so
no allowlist applies.

## C2. Entity cross-reference vs states.json

Referenced entities: 42. **Missing: 1.**

* **`person.owner`** — lines 160 (`META`), 203 (`NODE_ENT`), 215 (`DEMO_STATES`). Real entity is
  `person.owner`. `ON("person.owner")` is permanently `false`, so the «Присутствие» node is
  always drawn dim (`st:"off"`, 50 % alpha) and its panel row always reads **«Нет дома»**.
  Identical bug to livemap.html.

**None** of the other 41 entities is `unavailable`/`unknown` right now. Two need annotating for
the same reason as livemap: `climate.floor_heating` and `climate.floor_heating_2` are both
`state: 'off'` with `preset_mode: 'manual'` — and line 239 keys off `preset` only.

`siren.alarm` (`'off'`) is mentioned in `META` text (line 150) but is **not** in `NODE_ENT`, so
the «Сирена» node has no live state — see C4.

## C3. HONESTY DEFECTS (priority section)

**H-C1 — the graph topology is a hand-drawn 2026-07-04 snapshot presented under a LIVE badge.**
`N` (64 nodes) and `L` (98 edges) are literals; nothing is derived from HA. HA currently runs
**69 automations**; the graph depicts roughly 40 of them. Everything added since 2026-07-04 is
absent: all 6 Proxmox watchdogs, «Tuya: авто-лечение обрыва сессии (sign invalid)», «Tuya:
авто-перезагрузка при обрыве датчика влаги», «Сторож котла — режим АВАРИЯ», «Сторож сирены»,
«Сторож крана воды», «Сторож Tuya — состояния зависли», «Сторож EV», «Тёплый пол: термостат
недоступен», «Утечка (облако Tuya)», «Микроклимат: алерты», «Гард сброса счётчика энергии»,
«Учёт стоимости»/«Месячный отчёт», «Сводка по дому», «Shadow: сбор энергии/цены», «Изменения в
доме», «/noop_test», and the whole «Режим Жара» mechanism. The badge at line 68/252 says
**LIVE** once a token is present, but that badge only ever describes the 23 nodes in
`NODE_ENT`; it is placed next to the title of the whole diagram. A viewer reasonably reads
"LIVE" as "this map reflects the current house". It does not. Severity: **high** — this is the
single biggest honesty problem on this page.

**H-C2 — hardcoded thresholds in `META` that contradict the live automations.**
```
127: "Nord Pool":["sensor.nord_pool_lv_current_price","Биржевая цена электричества LV. Порог дешёвого — 0.04 €/кВт·ч."],
133: "Бойлер":["switch.smart_plug_2_socket_1","Умная розетка бойлера. ВКЛ при цене ≤0.04."],
161: "Бойлер·NordPool":["Автоматизация","Бойлер ВКЛ ≤0.04 / ВЫКЛ >0.04."],
```
The live automation is named «🔥 Бойлер по Nord Pool (<=0.10 ON, >0.10 OFF)» and carries
`threshold: 0.10` (automations.yaml line 569). The page states 0.04 three times. The same 0.04
literal drives the colour classification at line 235:
```
235: function priceLevel(p){return p<=0.04?["дёшево","on"]:p<=0.10?["средне","idle"]:["дорого","alert"];}
```

**H-C3 — placeholder text shipped to production (line 153).**
```
153: "Telegram бот":["@your_bot (шаблон)","Управление и уведомления через Telegram."],
```
Literally labelled «шаблон» (template). The real bot is `@your_home_bot`. The node's code chip
renders this string verbatim in the detail panel.

**H-C4 — a 40-entity hardcoded DEMO snapshot is the initial and no-token render state
(lines 205-216).**
```
205: var DEMO_STATES={
206:   "switch.smart_plug_2_socket_1":{state:"on"},"switch.kalarifer_socket_1":{state:"on"},...
209:   "sensor.nord_pool_lv_current_price":{state:"0.01407"},...
213:   "sensor.boiler_mode":{state:"Догорание"},"sensor.boiler_co_temperature":{state:"60.1"},"sensor.boiler_cwu_temperature":{state:"45.1"},
229: var DATA=DEMO_STATES,islive=false,selected=null;
```
`computeLive()` runs on this before any fetch (line 408), so node colours (green = on,
dim = off, red pulse = alert) are seeded from invented values. Without a token this is the
permanent state and every panel row is fiction. The panel does mark it — line 307 prints
«○ сейчас · снимок» vs «● сейчас · LIVE» — which is the **best** honesty marker of the three
pages, but the canvas node colours themselves carry no such marking.

**H-C5 — stale rows after a failed refresh, with the badge as the only cue (line 254).**
```
254: if(token){fetch("/api/states",...).then(function(r){if(r.ok){...}islive=false;updBadge();}).catch(function(){islive=false;updBadge();});}
```
On failure `DATA` is **not** reverted and `computeLive()` is **not** re-run — the node colours
and any open panel keep showing the last successful values indefinitely while the badge flips
to amber ДЕМО. Better than livemap's "fresh timestamp on failure" (H-B2) because there is no
false age claim, but there is also **no age indicator at all** on this page — nothing tells you
whether the last success was 20 s or 20 h ago.

**H-C6 — unavailable safety sensors render as safe (lines 242-244).**
```
242: else if(c.t==="wet"){var w=ON(c.e);st=w?"alert":"idle";rows.push(["Состояние",w?"МОКРО ⚠":"Сухо"]);}
243: else if(c.t==="smoke"){var w=ON(c.e);st=w?"alert":"idle";rows.push(["Дым",w?"ТРЕВОГА ⚠":"Чисто"]);}
244: else if(c.t==="door"){var o=ON(c.e);st=o?"idle":"off";rows.push(["Дверь",o?"Открыта":"Закрыта"]);}
```
`ON()` (line 232) maps `unavailable` → false, so an offline leak sensor is drawn as a calm
node with «Сухо», an offline smoke detector as «Чисто», an offline door as «Закрыта». As with
livemap, `sensor.leak_protection_status` — the agreed single source of leak truth — is not used
anywhere on this page.

**H-C7 — an OFF thermostat is drawn as heating (line 239).**
```
239: else if(c.t==="climate"){var s=G(c.e);st=s.preset==="manual"?"on":"idle";rows.push(["Температура",(s.temp!=null?s.temp+"°C":"—")]);rows.push(["Режим",s.preset||"—"]);}
```
`toMap` (line 251) keeps only `state`, `current_temperature`, `preset_mode`, and `state` is then
ignored for climate. Both floor nodes currently render green/on with «Режим: manual» while both
thermostats are `off`. The "Тепло 30°" button will also appear to succeed
(`set_preset_mode` + `set_temperature` both return 200) without producing heat.

**H-C8 — `||` on numeric values turns a genuine 0 into «—» (line 240).**
```
240: else if(c.t==="boiler"){rows.push(["Режим",G("sensor.boiler_mode").state]);rows.push(["Контур CO",(NU("sensor.boiler_co_temperature")||"—")+"°"]);rows.push(["ГВС",(NU("sensor.boiler_cwu_temperature")||"—")+"°"]);}
```
A real 0.0 °C reading is falsy and is displayed as «—°». Inverse of the usual `||0` defect —
data loss rather than fabrication, but still wrong. Also note the same line prints
`G("sensor.boiler_mode").state` **raw**, so an unavailable boiler prints the literal string
`unavailable` in the panel — ugly but at least honest.

**H-C9 — `tkwh` shows lifetime totals as "today" when the midnight snapshot is missing
(line 233).**
```
233: function tkwh(t,m){var T=NU(t),M=NU(m);if(T==null)return null;if(M==null)return T;return Math.max(0,T-M);}
```
Same defect as livemap H-B6 (first half). Row labels are «Расход сегодня» / «Сессия сегодня».

**What this page gets RIGHT (worth preserving):**
* Service calls are **not** optimistic. `svc()` (line 286) rejects with no token and shows
  «Нужен токен (⚙)»; line 287 throws on `!r.ok`; the toasts at lines 312/314/315 fire only in
  the success path. A failed command produces **no** false confirmation. (It produces no error
  message either — silent failure — which should be fixed, but it does not lie.)
* The panel data block is explicitly labelled `● сейчас · LIVE` vs `○ сейчас · снимок`
  (line 307).

## C4. Dead code / unused references

* `siren.alarm` (line 150) appears only inside a `META` description string; the «Сирена» node
  has no `NODE_ENT` entry, so its real state (`'off'`) is never read or shown.
* 41 of 64 nodes have no live binding at all (`nodeLive` returns `{st:null,rows:[]}`, line 236)
  — they are static diagram furniture. Not a bug, but it means `computeLive()` iterates 64
  nodes to update 23.
* `person.owner` — referenced in three places, resolves to nothing (C2).
* `input_number.midnight_ev_energy` is used, but there is no `midnight_tv_energy` node — the
  7th accumulator that exists in HA is simply absent (consistent with livemap).
* No orphan links, no unreachable `META`, no node without `META` (verified programmatically).
* Every declared function is called: `ic`, `svgIcon`, `hex`, `rr`, `esc`, `toast`, `svc`,
  `openMap`, `ctrlEnt`, `controlsHTML`, `renderPanel`, `openInfo`, `closeInfo`, `nodeLive`,
  `computeLive`, `toMap`, `updBadge`, `loadHA`, `step`, `fitTarget`, `snapFit`, `s2w`, `pick`,
  `RP`, `resize`, `rad`, `priceLevel`, `tkwh`, `NU`, `ON`, `G`, `draw`. **No dead functions
  found.**

## C5. Structure / reuse verdict

* 413 lines: ~52 CSS, ~360 JS. Zero dependencies — the force simulation, the canvas renderer,
  and 30+ vector icons (twice: canvas `ic()` line 321 and SVG `svgIcon()` line 362) are all
  hand-written. This is the largest and most self-contained of the three pages.
* State flow: `DEMO_STATES → GET /api/states (20 s) → toMap() → DATA → computeLive() → per-node
  {live, rows} → canvas draw loop (rAF) + panel innerHTML`. The physics `step()` runs inside
  `draw()` on every frame, forever — this page never idles, which matters on the wall tablet.
* **Worth reusing**: the icon sets, the force layout + fit logic, the hover/focus adjacency
  highlight, the `?focus=` hand-off to livemap, the honest `svc()` error handling, and the
  `● LIVE / ○ снимок` panel label.
* **Worth rebuilding**: the topology must be **generated** from `automations.yaml` +
  `NODE_ENT` rather than hand-maintained — it is already 29 automations out of date after six
  weeks and will keep drifting. Everything else in C3 (person.owner, 0.04 labels, `@your_bot`,
  DEMO seed, climate `state`, leak truth source, `||` on numerics) is a small local fix.

---

# D) Lovelace dashboards (`/config/.storage/lovelace*`)

Read over SSH with sudo. Five dashboards registered in `lovelace_dashboards`.

## D1. Registry — storage-mode config keys present

`/config/.storage/lovelace_dashboards` → `data.items[]`, keys per item:
`id`, `title`, `url_path`, `mode`, `show_in_sidebar`, `require_admin`, and optionally `icon`.
**Every dashboard is `"mode": "storage"`** — none is YAML-mode, so nothing here is version
controlled and none of it lives in the repo.

| id | title | url_path | sidebar | icon | storage file | file size | last written |
|---|---|---|---|---|---|---|---|
| `lovelace` | Обзор | `/lovelace` | yes | mdi:view-dashboard | `lovelace.lovelace` | 246 B | 2026-02-20 |
| `map` | Map | `/map` | **no** | mdi:map | `lovelace.map` | 154 B | 2024-12-16 |
| `moj_dom` | Мой дом | `/moj-dom` | yes | — | `lovelace.moj_dom` | 101 558 B | 2026-04-13 |
| `mojdom_v2` | МойДом v2 | `/mojdom-v2` | yes | mdi:home-variant | `lovelace.mojdom_v2` | 42 837 B | 2026-02-20 |
| `dashboard_tv` | TV | `/dashboard-tv` | yes | mdi:television | `lovelace.dashboard_tv` | 47 765 B | 2026-04-13 |

`require_admin: false` on all five. No `default_panel` override exists
(`frontend.user_data_7f0f8e…` contains only language + `showAdvanced`), so the default landing
page is the auto-generated **Обзор**.

`lovelace_resources` registers **12 HACS frontend modules**, all present on disk under
`/config/www/community/`: `lovelace-mushroom`, `button-card`, `mini-graph-card`,
`apexcharts-card`, `lovelace-card-mod`, `lumina-energy-card`, `energy-flow-card-plus`,
`lovelace-wallpanel`, `status-card`, `lovelace-layout-card`, `lovelace-auto-entities`,
`lovelace-fold-entity-row`. These load on **every** Lovelace page view, including the
auto-generated Обзор.

## D2. Per-dashboard content

**`lovelace` (Обзор)** — not a hand-built dashboard at all:
```json
{"config":{"strategy":{"type":"original-states","hide_energy":false,"hide_entities_without_area":false}}}
```
Auto-generated from the entity registry. Exposes *everything*, so it is not meaningful to list
its entity set. It is the default landing page.

**`map`** — `{"config":{"strategy":{"type":"map"}}}`. Built-in map strategy, hidden from the
sidebar, untouched since 2024-12-16. Vestigial.

**`moj_dom` (Мой дом)** — 2 views, 78 card nodes, 53 distinct entity refs.
* view «Дом» (`home`): 1 top-level card — a `custom:layout-card` wrapping 30
  `custom:button-card`s, 5 `custom:mushroom-entity-card`s, 2 `thermostat` cards, a
  `picture-entity` (doorbell camera).
* view «Графики» (`graphs`): 5 cards, mostly `custom:apexcharts-card` + `entities`.

**`mojdom_v2` (МойДом v2, internal title "COSMOS")** — 2 views, 57 card nodes, 49 entity refs.
* view «Дом»: `custom:grid-layout`, 5 cards (16 button-cards, mushroom light/climate/chips,
  mini-graph).
* view «Статистика»: modern `sections` layout, 3 sections × 3 cards (apexcharts).

**`dashboard_tv` (TV, internal title "COSMOS TV - Parker")** — 1 view («ТВ»), 66 card nodes,
42 entity refs. Heaviest use of `custom:button-card` (45) with a shared
`button_card_templates.tv_card` style block. Built for a TV/large screen.

## D3. Used or vestigial?

**I cannot measure page views** — Lovelace storage files are rewritten only on *edit*, not on
*view*, and HA keeps no per-dashboard usage counter that is readable from the state machine or
the config directory. So the following is inference, stated as such:

* `map` — **vestigial with high confidence.** Untouched since 2024-12-16, hidden from the
  sidebar, and it is a built-in strategy with no customisation.
* `moj_dom`, `mojdom_v2`, `dashboard_tv` — **almost certainly vestigial.** Last edited
  2026-02-20 / 2026-04-13, i.e. **before** the whole tablet-panel + Mini App v8 effort
  (2026-05 → 2026-08) that produced the UIs the owner actually uses. Three of them are
  overlapping attempts at the same "home" screen (`moj_dom` → `mojdom_v2` → `dashboard_tv`), and
  the newest of the three is the TV one. They still contain **stale entity references** (D4)
  that a maintained dashboard would have surfaced as red "Entity not available" cards. The
  known live surfaces are `/local/tablet.html`, the Telegram Mini App, and `/local/*.html` —
  none of the repo scripts or docs reference `/moj-dom`, `/mojdom-v2` or `/dashboard-tv` except
  a single mention in `docs/HA_System_Report.md`.
* `lovelace` (Обзор) — **used by default**, since no `defaultPanel` is set; anyone opening
  HA lands here.

Cost of keeping them: the 12 HACS frontend modules stay installed and are loaded on every
Lovelace page.

## D4. Broken references inside the dashboards

`moj_dom` — 3 entities that no longer exist:
`automation.kriticheski_dorogaia_tsena_elektrichestva` (documented as a deleted automation),
`camera.intellektualnyi_dvernoi_zvonok`, `sensor.intellektualnyi_dvernoi_zvonok_battery`.
Plus 1 unavailable: `sensor.signalizatsiia_dvernogo_datchika_battery`.

`mojdom_v2` — 6 missing: `automation.ai_status_doma_kazhdye_2_chasa`,
`binary_sensor.kamera_dlia_sobak_motion`, `group.cosmos_lights`, `group.cosmos_sockets`,
`group.cosmos_switches`, `sensor.intellektualnyi_dvernoi_zvonok_battery`.
Plus 1 unavailable: `binary_sensor.signalizatsiia_dvernogo_datchika_door`.
(The three `group.cosmos_*` are gone entirely — this dashboard's light/socket/switch controls
are therefore dead.)

`dashboard_tv` — 2 missing: `camera.intellektualnyi_dvernoi_zvonok`,
`sensor.intellektualnyi_dvernoi_zvonok_battery`. No unavailable.

## D5. Entity sets (for your cross-reference)

**`lovelace.moj_dom` — 53 refs**
```
automation.boiler_kalorifer_po_tsene_porog_0_04  automation.ev_zariadka_po_tsene_0_04
automation.kriticheski_dorogaia_tsena_elektrichestva*  automation.skoro_budet_deshevoe_elektrichestvo
automation.teplyi_pol_po_nord_pool_0_04_heat_30c_0_04_auto  automation.utechka_vody_avariinoe_otkliuchenie
binary_sensor.door_sensor_door  binary_sensor.garazh_moisture  binary_sensor.kukhnia_moisture
binary_sensor.motion_sensor_motion  binary_sensor.pir_motion_sensor_motion  binary_sensor.vannaia_moisture
binary_sensor.water_sensor_4_moisture  binary_sensor.wifi_th_smoke_sensor_smoke
camera.intellektualnyi_dvernoi_zvonok*  climate.floor_heating  climate.floor_heating_2
light.svet_pervyi_etazh_1_light  light.veranda_light  light.vtoroi_etazh_light
sensor.akvarium_svet_total_energy  sensor.boiler_total_energy  sensor.cherepakha_total_energy
sensor.door_sensor_battery  sensor.electricity_maps_co2_intensity  sensor.garazh_battery
sensor.intellektualnyi_dvernoi_zvonok_battery*  sensor.kukhnia_battery  sensor.kukhnia_humidity
sensor.kukhnia_temperature  sensor.nord_pool_lv_current_price  sensor.nord_pool_lv_highest_price
sensor.nord_pool_lv_lowest_price  sensor.nord_pool_lv_next_price  sensor.perenosnoi_pult_battery
sensor.pir_motion_sensor_battery  sensor.signalizatsiia_dvernogo_datchika_battery(unavail)
sensor.sm_t595_battery_level  sensor.smart_weather_station_humidity  sensor.smart_weather_station_temperature
sensor.stsenarnyi_pult_battery  sensor.terarium_total_energy  sensor.water_sensor_4_battery
sensor.zigbee_plug_2_total_energy  sensor.zigbee_plug_total_energy
switch.220v_wifi_smart_dry_contact_switch_switch_3  switch.220v_wifi_smart_dry_contact_switch_switch_4
switch.akvarium_svet_socket_1  switch.ev_charger_switch  switch.kalarifer_socket_1
switch.retserkuliatsiia_goriachai_vody_socket_1  switch.smart_plug_2_socket_1  switch.zigbee_plug_2_socket_1
```

**`lovelace.mojdom_v2` — 49 refs**
```
automation.ai_status_doma_kazhdye_2_chasa*  automation.nochnoi_patrul_podsvetki_proverka_v_23_30
automation.polnaia_samodiagnostika_doma_ai  binary_sensor.kamera_dlia_sobak_motion*
binary_sensor.signalizatsiia_dvernogo_datchika_door(unavail)  binary_sensor.wifi_th_smoke_sensor_smoke
climate.floor_heating  group.cosmos_lights*  group.cosmos_sockets*  group.cosmos_switches*
humidifier.pro4_humidifier  light.dream_color_rgb  light.dream_color_rgb_2
light.prikhozhaia_i_fanar_light  light.prikhozhaia_i_fanar_light_2  light.svet_pervyi_etazh_1_light
light.svet_pervyi_etazh_1_light_2  light.veranda_light  light.vtoroi_etazh_light  person.owner
sensor.akvarium_svet_total_energy  sensor.backup_backup_manager_state  sensor.boiler_total_energy
sensor.cherepakha_total_energy  sensor.intellektualnyi_dvernoi_zvonok_battery*  sensor.kukhnia_humidity
sensor.kukhnia_temperature  sensor.nord_pool_lv_current_price  sensor.nord_pool_lv_highest_price
sensor.nord_pool_lv_lowest_price  sensor.nord_pool_lv_next_price  sensor.smart_weather_station_humidity
sensor.smart_weather_station_temperature  sensor.zigbee_plug_total_energy
switch.akvarium_svet  switch.akvarium_svet_socket_1  switch.boiler  switch.cherepakha
switch.kalarifer_socket_1  switch.kukhnia_poloski  switch.prikhozhaia_i_fanar
switch.retserkuliatsiia_goriachai_vody_socket_1  switch.smart_plug_2_socket_1
switch.smart_switch_2ch_switch_1  switch.smart_switch_2ch_switch_2  switch.svet_tv_zona
switch.zigbee_plug_socket_1  update.home_assistant_core_update  weather.forecast_home
```

**`lovelace.dashboard_tv` — 42 refs**
```
automation.boiler_kalorifer_po_tsene_porog_0_04  automation.ev_zariadka_po_tsene_0_04
automation.teplyi_pol_po_nord_pool_0_04_heat_30c_0_04_auto  automation.utechka_vody_avariinoe_otkliuchenie
binary_sensor.door_sensor_door  binary_sensor.floor_heating_valve  binary_sensor.floor_heating_valve_2
binary_sensor.garazh_moisture  binary_sensor.kukhnia_moisture  binary_sensor.motion_sensor_motion
binary_sensor.vannaia_moisture  binary_sensor.water_sensor_4_moisture  binary_sensor.wifi_th_smoke_sensor_smoke
camera.intellektualnyi_dvernoi_zvonok*  climate.floor_heating  climate.floor_heating_2
sensor.akvarium_svet_total_energy  sensor.backup_backup_manager_state  sensor.boiler_total_energy
sensor.cherepakha_total_energy  sensor.intellektualnyi_dvernoi_zvonok_battery*  sensor.kukhnia_humidity
sensor.kukhnia_temperature  sensor.nord_pool_lv_current_price  sensor.nord_pool_lv_highest_price
sensor.nord_pool_lv_lowest_price  sensor.nord_pool_lv_next_price  sensor.smart_weather_station_humidity
sensor.smart_weather_station_temperature  sensor.terarium_total_energy  sensor.zigbee_plug_2_total_energy
sensor.zigbee_plug_total_energy  switch.220v_wifi_smart_dry_contact_switch_switch_3
switch.akvarium_svet_socket_1  switch.ev_charger_switch  switch.kalarifer_socket_1
switch.retserkuliatsiia_goriachai_vody_socket_1  switch.smart_plug_2_socket_1  switch.voda_kran_switch_1
switch.zigbee_plug_2_socket_1  update.home_assistant_core_update  weather.forecast_home
```
`*` = does not exist in HA today.

**Notable classes of entity that appear ONLY in these Lovelace dashboards** (i.e. absent from
boiler/livemap/graph — the pages in this audit; cross-check against tablet-panel.js and
smarthouse_v8.html yourself):
* **Lighting**: `light.svet_pervyi_etazh_1_light`, `light.svet_pervyi_etazh_1_light_2`,
  `light.veranda_light`, `light.vtoroi_etazh_light`, `light.dream_color_rgb`,
  `light.dream_color_rgb_2`, `light.prikhozhaia_i_fanar_light`, `light.prikhozhaia_i_fanar_light_2`,
  `switch.kukhnia_poloski`, `switch.svet_tv_zona`, `switch.prikhozhaia_i_fanar`,
  `switch.smart_switch_2ch_switch_1/2`, `switch.220v_wifi_smart_dry_contact_switch_switch_3/4`
* **Battery levels**: `sensor.door_sensor_battery`, `sensor.garazh_battery`,
  `sensor.kukhnia_battery`, `sensor.perenosnoi_pult_battery`, `sensor.pir_motion_sensor_battery`,
  `sensor.signalizatsiia_dvernogo_datchika_battery`, `sensor.water_sensor_4_battery`,
  `sensor.sm_t595_battery_level`
* **Motion**: `binary_sensor.motion_sensor_motion`, `binary_sensor.pir_motion_sensor_motion`
* **Floor-heating valve feedback**: `binary_sensor.floor_heating_valve`,
  `binary_sensor.floor_heating_valve_2` (real hardware feedback that none of the three
  embedded pages reads — potentially the honest answer to "is the floor actually heating")
* **Other**: `sensor.electricity_maps_co2_intensity`, `humidifier.pro4_humidifier`,
  `sensor.backup_backup_manager_state`, `update.home_assistant_core_update`,
  `sensor.zigbee_plug_total_energy` / `switch.zigbee_plug_socket_1` (the *other* zigbee plug),
  `switch.akvarium_svet`, `switch.cherepakha`, `switch.boiler` (duplicate/alias switches)

## D6. Verdict

Four hand-built dashboards (`moj_dom`, `mojdom_v2`, `dashboard_tv`, plus the built-in `map`) are
almost certainly abandoned: last edited February–April 2026, all superseded by the tablet panel
and Mini App, three of them containing entity references that no longer resolve (including all
three `group.cosmos_*` groups that `mojdom_v2`'s controls depend on). They are all in
`storage` mode, so none of it is in the repo and none of it is under review. The only Lovelace
surface that is certainly in daily use is the auto-generated **Обзор** strategy dashboard,
because nothing sets a different default panel.

The one genuinely useful thing hiding in them is entity coverage the embedded pages lack —
lighting, per-device battery levels, motion sensors, and especially
`binary_sensor.floor_heating_valve` / `_valve_2`, which are physical valve-position feedback
that no page in this audit reads.
