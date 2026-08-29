import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

/**
 * LiveDeviceMap — live, interactive control map of the whole smart home.
 * Reads real states from Home Assistant (/api/states), auto-refreshes, and lets
 * you CONTROL devices by tapping (switches, EV, floor heating, water, security,
 * night-saver mode) with optimistic UI + confirmation for dangerous actions.
 *
 * Token: the HA long-lived token is stored ONLY in the browser
 * (localStorage "livemap_token"), never in this file. Click ⚙ to set it.
 * When HA is unreachable (or no token) it shows an interactive DEMO snapshot.
 *
 * Deploy: fetches "/api/states" same-origin, so served from /config/www/
 * (http://<ha>/local/…) it talks to HA directly. For a remote HA pass `base`,
 * e.g. <LiveDeviceMap base="https://ha.example" />.
 *
 *   import LiveDeviceMap from "./LiveDeviceMap";
 *   <LiveDeviceMap />
 */

const LS_TOKEN = "livemap_token";
const LS_THEME = "livemap_theme";
const REFRESH = 15000;

// real snapshot (fetched live at build time) — interactive DEMO / offline fallback
const DEMO = {
  "switch.smart_plug_2_socket_1": { state: "on" },
  "switch.kalarifer_socket_1": { state: "on" },
  "switch.akvarium_svet_socket_1": { state: "on" },
  "switch.retserkuliatsiia_goriachai_vody_socket_1": { state: "on" },
  "switch.zigbee_plug_2_socket_1": { state: "on" },
  "switch.ev_charger_switch": { state: "off" },
  "switch.voda_kran_switch_1": { state: "on" },
  "sensor.boiler_total_energy": { state: "7.921" },
  "sensor.terarium_total_energy": { state: "0.0" },
  "sensor.akvarium_svet_total_energy": { state: "0.985" },
  "sensor.cherepakha_total_energy": { state: "1.131" },
  "sensor.zigbee_plug_2_total_energy": { state: "251.74" },
  "sensor.ev_charger_energy": { state: "834.73" },
  "input_number.midnight_boiler_energy": { state: "7.50" },
  "input_number.midnight_kalarifer_energy": { state: "0.0" },
  "input_number.midnight_akv_energy": { state: "0.90" },
  "input_number.midnight_chep_energy": { state: "1.00" },
  "input_number.midnight_gidro_energy": { state: "250.90" },
  "input_number.midnight_ev_energy": { state: "820.0" },
  "sensor.nord_pool_lv_current_price": { state: "0.01407" },
  "sensor.nord_pool_lv_next_price": { state: "0.026" },
  "sensor.nord_pool_lv_lowest_price": { state: "0.00999" },
  "sensor.nord_pool_lv_highest_price": { state: "0.19" },
  "sensor.ev_charger_status": { state: "charger_insert" },
  "input_datetime.ev_charge_start": { state: "2026-07-04 14:45:00" },
  "input_boolean.ev_manual_mode": { state: "off" },
  "input_boolean.night_saver": { state: "off" },
  "input_boolean.security_armed": { state: "off" },
  "climate.floor_heating": { state: "heat_cool", temp: 30.0, preset: "manual" },
  "climate.floor_heating_2": { state: "heat_cool", temp: 32.0, preset: "manual" },
  "sensor.boiler_mode": { state: "Догорание" },
  "sensor.boiler_co_temperature": { state: "60.1" },
  "sensor.boiler_cwu_temperature": { state: "45.1" },
  "binary_sensor.door_sensor_door": { state: "off" },
  "binary_sensor.wifi_th_smoke_sensor_smoke": { state: "off" },
  "binary_sensor.vannaia_moisture": { state: "off" },
  "binary_sensor.garazh_moisture": { state: "off" },
  "binary_sensor.kukhnia_moisture": { state: "off" },
  "binary_sensor.water_sensor_4_moisture": { state: "off" },
  "person.owner": { state: "home" },
  "weather.forecast_home": { state: "partlycloudy" },
  "sensor.smart_weather_station_temperature": { state: "unavailable" },
};

const WEATHER = { sunny: "☀️", "clear-night": "🌙", partlycloudy: "⛅", cloudy: "☁️", rainy: "🌧️", pouring: "🌧️", snowy: "❄️", fog: "🌫️", windy: "💨", lightning: "⛈️", "lightning-rainy": "⛈️", hail: "🌨️" };
const EVMAP = { charger_charging: ["Заряжается", "on"], charger_insert: ["Подключён", "idle"], charger_pause: ["Пауза", "idle"], charger_free: ["Свободен", "off"], charger_end: ["Завершено", "off"], cloud_error: ["Ошибка", "alert"] };

// energy plugs: [name, emoji, switch, totalSensor, midnightSnapshot]
const PLUGS = [
  ["Бойлер", "♨️", "switch.smart_plug_2_socket_1", "sensor.boiler_total_energy", "input_number.midnight_boiler_energy"],
  ["Полотенцесушитель", "🔥", "switch.kalarifer_socket_1", "sensor.terarium_total_energy", "input_number.midnight_kalarifer_energy"],
  ["Аквариум", "🐠", "switch.akvarium_svet_socket_1", "sensor.akvarium_svet_total_energy", "input_number.midnight_akv_energy"],
  ["Черепаха / рецирк.", "🐢", "switch.retserkuliatsiia_goriachai_vody_socket_1", "sensor.cherepakha_total_energy", "input_number.midnight_chep_energy"],
  ["Гидрофор", "💧", "switch.zigbee_plug_2_socket_1", "sensor.zigbee_plug_2_total_energy", "input_number.midnight_gidro_energy"],
  ["EV зарядка", "🚗", "switch.ev_charger_switch", "sensor.ev_charger_energy", "input_number.midnight_ev_energy"],
];
const MO = [["Ванная", "binary_sensor.vannaia_moisture"], ["Гараж", "binary_sensor.garazh_moisture"], ["Кухня", "binary_sensor.kukhnia_moisture"], ["Душевая", "binary_sensor.water_sensor_4_moisture"]];

const priceColor = (p) => (p <= 0.04 ? "var(--on)" : p <= 0.1 ? "var(--warn)" : "var(--crit)");
const priceTag = (p) => (p <= 0.04 ? "дёшево" : p <= 0.1 ? "средне" : "дорого");

export default function LiveDeviceMap({ base = "" }) {
  const [data, setData] = useState(DEMO);
  const [live, setLive] = useState(false);
  const [msg, setMsg] = useState("");
  const [updated, setUpdated] = useState(null);
  const [dlg, setDlg] = useState(false);
  const [confirm, setConfirm] = useState(null); // {text, fn}
  const [toast, setToast] = useState("");
  const [busy, setBusy] = useState({}); // entity_id -> true
  const [, setTick] = useState(0); // re-render for relative time
  const [theme, setTheme] = useState(() => (typeof localStorage !== "undefined" && localStorage.getItem(LS_THEME)) || "dark");
  const tokenInput = useRef(null);
  const toastT = useRef(null);

  const g = useCallback((eid) => data[eid] || { state: "unavailable" }, [data]);
  const num = useCallback((eid) => { const v = parseFloat(g(eid).state); return isNaN(v) ? null : v; }, [g]);
  const isOn = useCallback((eid) => ["on", "home", "true", "open", "heat_cool", "heat"].includes((g(eid).state || "").toLowerCase()), [g]);

  const flash = useCallback((t) => {
    setToast(t);
    if (toastT.current) clearTimeout(toastT.current);
    toastT.current = setTimeout(() => setToast(""), 2600);
  }, []);

  const load = useCallback(async () => {
    const token = typeof localStorage !== "undefined" && localStorage.getItem(LS_TOKEN);
    if (token) {
      try {
        const r = await fetch(base + "/api/states", { headers: { Authorization: "Bearer " + token } });
        if (r.ok) {
          const arr = await r.json();
          const m = {};
          arr.forEach((s) => { m[s.entity_id] = { state: s.state, temp: s.attributes && s.attributes.current_temperature, preset: s.attributes && s.attributes.preset_mode }; });
          setData(m); setLive(true); setMsg(""); setUpdated(new Date());
          return;
        }
        if (r.status === 401) setMsg("Токен неверный");
      } catch { /* unreachable → keep current (demo/optimistic) */ }
    }
    // demo / offline: keep existing state (so optimistic toggles persist), just stamp time
    setData((prev) => prev || DEMO); setLive(false); setUpdated(new Date());
  }, [base]);

  useEffect(() => { load(); const t = setInterval(load, REFRESH); return () => clearInterval(t); }, [load]);
  useEffect(() => { const t = setInterval(() => setTick((x) => x + 1), 10000); return () => clearInterval(t); }, []);
  useEffect(() => { if (typeof localStorage !== "undefined") localStorage.setItem(LS_THEME, theme); }, [theme]);

  // ---- control: optimistic + real service call (or demo-local mutation) ----
  const callService = useCallback(async (domain, service, entity_id, patch) => {
    const extra = patch && patch._data ? patch._data : {};
    const optimistic = { ...patch }; delete optimistic._data;
    setBusy((b) => ({ ...b, [entity_id]: true }));
    setData((d) => ({ ...d, [entity_id]: { ...(d[entity_id] || {}), ...optimistic } })); // optimistic
    const token = typeof localStorage !== "undefined" && localStorage.getItem(LS_TOKEN);
    if (token) {
      try {
        await fetch(base + `/api/services/${domain}/${service}`, {
          method: "POST",
          headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" },
          body: JSON.stringify({ entity_id, ...extra }),
        });
      } catch { /* ignore; reconcile on next load */ }
    }
    setBusy((b) => { const n = { ...b }; delete n[entity_id]; return n; });
    if (token) setTimeout(load, 1200); // reconcile with real state
  }, [base, load]);

  const toggleSwitch = (entity, opts = {}) => {
    const on = isOn(entity);
    const doIt = () => { callService("switch", on ? "turn_off" : "turn_on", entity, { state: on ? "off" : "on" }); flash(`${opts.name || "Устройство"}: ${on ? "выкл" : "вкл"}`); };
    if (on && opts.confirmOff) setConfirm({ text: opts.confirmOff, fn: doIt });
    else doIt();
  };
  const toggleBool = (entity, name) => {
    const on = isOn(entity);
    const doIt = () => { callService("input_boolean", on ? "turn_off" : "turn_on", entity, { state: on ? "off" : "on" }); flash(`${name}: ${on ? "выкл" : "вкл"}`); };
    if (on && name === "Охрана") setConfirm({ text: "Снять охрану?", fn: doIt });
    else doIt();
  };
  const toggleFloor = (entity, name) => {
    const manual = g(entity).preset === "manual";
    const next = manual ? "auto" : "manual";
    callService("climate", "set_preset_mode", entity, { preset: next, _data: { preset_mode: next } });
    flash(`${name}: ${manual ? "авто (эко)" : "нагрев"}`);
  };
  const evToggle = () => {
    const st = g("sensor.ev_charger_status").state;
    const charging = isOn("switch.ev_charger_switch") || st === "charger_charging";
    callService("switch", charging ? "turn_off" : "turn_on", "switch.ev_charger_switch", { state: charging ? "off" : "on" });
    flash(charging ? "EV: стоп" : "EV: зарядка");
  };

  const saveToken = () => { const v = tokenInput.current.value.trim(); if (v) localStorage.setItem(LS_TOKEN, v); setDlg(false); load(); };
  const clearToken = () => { localStorage.removeItem(LS_TOKEN); setDlg(false); load(); };

  // ---- derived ----
  const p = num("sensor.nord_pool_lv_current_price");
  const nx = num("sensor.nord_pool_lv_next_price");
  const lo = num("sensor.nord_pool_lv_lowest_price"), hi = num("sensor.nord_pool_lv_highest_price");
  const pc = p == null ? "var(--dim)" : priceColor(p);
  const markPct = lo != null && hi != null && p != null && hi > lo ? Math.max(0, Math.min(100, ((p - lo) / (hi - lo)) * 100)) : 50;
  const wIcon = WEATHER[g("weather.forecast_home").state] || "🌡️";
  const wTemp = num("sensor.smart_weather_station_temperature");
  const home = isOn("person.owner");

  const todayKwh = useCallback((total, snap) => {
    const t = num(total), s = num(snap);
    if (t == null) return null;
    if (s == null) return t;
    return Math.max(0, t - s);
  }, [num]);
  const totalToday = useMemo(() => PLUGS.reduce((a, d) => a + (todayKwh(d[3], d[4]) || 0), 0), [todayKwh]);
  const onCount = PLUGS.filter((d) => isOn(d[2])).length;

  const rel = updated ? Math.round((Date.now() - updated.getTime()) / 1000) : null;
  const relTxt = rel == null ? "…" : rel < 60 ? `${rel} сек назад` : `${Math.round(rel / 60)} мин назад`;

  const Tile = ({ icon, name, sub, big, stateTxt, right, on, alert, extra, onClick, pending }) => {
    const interactive = !!onClick;
    return (
      <div
        className={"lm-tile" + (on ? " on" : "") + (alert ? " alert" : "") + (extra ? " " + extra : "") + (interactive ? " tap" : "") + (pending ? " pending" : "")}
        onClick={onClick}
        role={interactive ? "button" : undefined}
        tabIndex={interactive ? 0 : undefined}
        aria-label={interactive ? `${name}: ${stateTxt || ""} — переключить` : undefined}
        onKeyDown={interactive ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick(); } } : undefined}
      >
        <div className="th"><div className="ic">{icon}</div><div><div className="nm">{name}</div>{sub && <div className="sub">{sub}</div>}</div>{interactive && <span className="tapdot" aria-hidden>⌁</span>}</div>
        {big != null && <div className="val" dangerouslySetInnerHTML={{ __html: big }} />}
        <div className="foot"><span className="state"><span className="d" />{pending ? "…" : stateTxt}</span>{right && <span className="sub" style={{ fontSize: ".7rem" }}>{right}</span>}</div>
      </div>
    );
  };
  const Zone = ({ icon, title, count, children }) => (
    <div className="lm-zone">
      <div className="zt"><div className="zi">{icon}</div><h2>{title}</h2><span className="zc">{count}</span></div>
      <div className="grid">{children}</div>
    </div>
  );

  const evst = g("sensor.ev_charger_status").state, evm = EVMAP[evst] || [evst, "idle"];
  const nextC = g("input_datetime.ev_charge_start").state;
  const nextShort = nextC && nextC.length >= 16 ? nextC.slice(5, 16) : "—";
  const manual = isOn("input_boolean.ev_manual_mode");
  const evkwh = todayKwh("sensor.ev_charger_energy", "input_number.midnight_ev_energy");
  const bmode = g("sensor.boiler_mode").state, co = num("sensor.boiler_co_temperature"), cwu = num("sensor.boiler_cwu_temperature");
  const fb = g("climate.floor_heating"), fs = g("climate.floor_heating_2");
  const wet = MO.filter((m) => isOn(m[1])).length;
  const armed = isOn("input_boolean.security_armed");
  const nightOn = isOn("input_boolean.night_saver");
  const valveOpen = isOn("switch.voda_kran_switch_1");

  return (
    <div className={"lm-root " + (theme === "light" ? "lm-light" : "")}>
      <style>{CSS}</style>
      <div className="wrap">
        <div className="top">
          <div className="brand"><span className="k">Home Assistant · Рига</span><h1>Живая карта дома</h1></div>
          <div className="env">
            <span className="chip">{wIcon} <b>{wTemp != null ? wTemp.toFixed(1) + "°" : g("weather.forecast_home").state}</b></span>
            <span className="chip">{home ? "🏠" : "🚶"} <b>{home ? "Дома" : "Нет дома"}</b></span>
          </div>
          <span className={"badge " + (live ? "live" : "demo")} title={relTxt}><span className="led" />{msg || (live ? "LIVE" : "ДЕМО")}</span>
          <button className="iconbtn" onClick={() => setTheme(theme === "light" ? "dark" : "light")} title="Тема" aria-label="Сменить тему">{theme === "light" ? "🌙" : "☀️"}</button>
          <button className="iconbtn" onClick={load} title="Обновить" aria-label="Обновить">⟳</button>
          <button className="iconbtn" onClick={() => setDlg(true)} title="Подключить к HA" aria-label="Настройки подключения">⚙</button>
        </div>

        <div className="hero">
          <div className="glow" style={{ background: `radial-gradient(420px 180px at 12% 40%, color-mix(in srgb, ${pc} 16%, transparent), transparent 70%)` }} />
          <div className="gauge">
            <div className="val" style={{ color: pc }}>{p == null ? "—" : p.toFixed(4)}</div>
            <div className="unit">€ / кВт·ч</div>
            <div className="tag" style={{ background: `color-mix(in srgb, ${pc} 20%, transparent)`, color: pc }}>{p == null ? "—" : priceTag(p)}</div>
          </div>
          <div className="heromid">
            <div className="lbl">Цена электричества · Nord Pool LV · обновлено {relTxt}</div>
            <div className="range"><div className="mark" style={{ left: markPct + "%" }} /></div>
            <div className="ends"><span>min {lo != null ? lo.toFixed(3) : "—"}</span><span>max {hi != null ? hi.toFixed(3) : "—"}</span></div>
            <div className="next">Следующий час: <b style={{ color: nx != null ? priceColor(nx) : "" }}>{nx != null ? nx.toFixed(4) + " €" : "—"}</b> · порог <b>0.04</b> · сегодня <b>{totalToday.toFixed(1)} кВт·ч</b></div>
          </div>
        </div>

        <Zone icon="⚡" title="Энергия" count={`${onCount}/${PLUGS.length} вкл · тап = переключить`}>
          {PLUGS.map((d) => {
            const on = isOn(d[2]); const kwh = todayKwh(d[3], d[4]);
            return (
              <Tile key={d[2]} icon={d[1]} name={d[0]} on={on} pending={busy[d[2]]}
                stateTxt={on ? "вкл" : "выкл"} right="сегодня"
                big={kwh != null ? `${kwh.toFixed(kwh < 100 ? 2 : 1)} <small>кВт·ч</small>` : "—"}
                onClick={() => toggleSwitch(d[2], { name: d[0] })} />
            );
          })}
        </Zone>

        <Zone icon="🌡️" title="Климат" count="полы: тап = авто / нагрев">
          <Tile icon="🌡️" name="Пол · ванная" extra="heat" pending={busy["climate.floor_heating"]}
            on={fb.preset === "manual"} stateTxt={fb.preset || "—"} right="тап"
            big={(fb.temp != null ? fb.temp.toFixed(1) : "—") + " <small>°C</small>"}
            onClick={() => toggleFloor("climate.floor_heating", "Пол ванная")} />
          <Tile icon="🌡️" name="Пол · душевая" extra="heat" pending={busy["climate.floor_heating_2"]}
            on={fs.preset === "manual"} stateTxt={fs.preset || "—"} right="тап"
            big={(fs.temp != null ? fs.temp.toFixed(1) : "—") + " <small>°C</small>"}
            onClick={() => toggleFloor("climate.floor_heating_2", "Пол душевая")} />
          <Tile icon="🔥" name="Котёл" extra="heat" sub={bmode}
            big={(co != null ? co.toFixed(0) : "—") + "° <small>CO</small>"}
            stateTxt={(cwu != null ? cwu.toFixed(0) : "—") + "° ГВС"} right="ecoNET" />
        </Zone>

        <Zone icon="🚗" title="Электромобиль" count={manual ? "ручной режим" : "авто-план"}>
          <Tile icon="🔌" name="Зарядка" extra="ev" on={evm[1] === "on"} alert={evm[1] === "alert"} pending={busy["switch.ev_charger_switch"]}
            big={`<span style="color:var(--ev)">${evm[0]}</span>`} stateTxt={isOn("switch.ev_charger_switch") ? "стоп ⏹" : "старт ▶"}
            onClick={evToggle} />
          <Tile icon="🕒" name="След. сеанс" extra="ev" big={nextShort} stateTxt="план" right="старт" />
          <Tile icon="🎛️" name="Ручной режим" extra="ev" on={manual} pending={busy["input_boolean.ev_manual_mode"]}
            big={manual ? "ВКЛ" : "Авто"} stateTxt={manual ? "не по плану" : "по цене"}
            onClick={() => toggleBool("input_boolean.ev_manual_mode", "Ручной EV")} />
          <Tile icon="⚡" name="Сессия сегодня" extra="ev" big={(evkwh != null ? evkwh.toFixed(1) : "—") + " <small>кВт·ч</small>"} stateTxt="заряжено" />
        </Zone>

        <Zone icon="🎚️" title="Режимы" count="тап = переключить">
          <Tile icon="🌙" name="Ночная экономия" on={nightOn} pending={busy["input_boolean.night_saver"]}
            big={nightOn ? "ВКЛ" : "Выкл"} stateTxt={nightOn ? "22–05 активно" : "по расписанию"} right="эконом"
            onClick={() => toggleBool("input_boolean.night_saver", "Ночная экономия")} />
          <Tile icon="🛡️" name="Охрана" on={armed} pending={busy["input_boolean.security_armed"]}
            big={armed ? "Включена" : "Снята"} stateTxt={armed ? "на охране" : "снята"}
            onClick={() => toggleBool("input_boolean.security_armed", "Охрана")} />
          <Tile icon="🚰" name="Кран воды" on={valveOpen} pending={busy["switch.voda_kran_switch_1"]}
            big={valveOpen ? "Открыт" : "Закрыт"} stateTxt={valveOpen ? "открыт" : "закрыт"}
            onClick={() => toggleSwitch("switch.voda_kran_switch_1", { name: "Кран воды", confirmOff: "Перекрыть воду в доме?" })} />
        </Zone>

        <Zone icon="🚨" title="Безопасность" count={wet ? `⚠ утечка ×${wet}` : "всё спокойно"}>
          <Tile icon="🚪" name="Входная дверь" alert={isOn("binary_sensor.door_sensor_door")} big={isOn("binary_sensor.door_sensor_door") ? "Открыта" : "Закрыта"} stateTxt={isOn("binary_sensor.door_sensor_door") ? "открыто" : "закрыто"} />
          <Tile icon="🔥" name="Датчик дыма" alert={isOn("binary_sensor.wifi_th_smoke_sensor_smoke")} big={isOn("binary_sensor.wifi_th_smoke_sensor_smoke") ? "ДЫМ!" : "Чисто"} stateTxt={isOn("binary_sensor.wifi_th_smoke_sensor_smoke") ? "тревога" : "норма"} />
          <Tile icon="💦" name="Датчики влаги ×4" alert={wet > 0} big={wet > 0 ? `${wet} мокро` : "Сухо"} stateTxt={MO.map((m) => (isOn(m[1]) ? "⚠" : "·")).join(" ")} right="ван·гар·кух·душ" />
        </Zone>

        <div className="foot2">
          <span>{live ? "обновлено " : "снимок · "}{relTxt}{live ? "" : " (демо)"}</span>
          <span>/api/states · автообновление 15с · тап по плитке = управление</span>
        </div>
      </div>

      {toast && <div className="lm-toast">{toast}</div>}

      {confirm && (
        <div className="dlg show" onClick={(e) => { if (e.target.classList.contains("dlg")) setConfirm(null); }}>
          <div className="box">
            <h3>Подтверждение</h3>
            <p>{confirm.text}</p>
            <div className="row">
              <button onClick={() => setConfirm(null)}>Отмена</button>
              <button className="danger" onClick={() => { const f = confirm.fn; setConfirm(null); f(); }}>Да</button>
            </div>
          </div>
        </div>
      )}

      {dlg && (
        <div className="dlg show" onClick={(e) => { if (e.target.classList.contains("dlg")) setDlg(false); }}>
          <div className="box">
            <h3>Подключить к Home Assistant</h3>
            <p>Вставь <b>Long-Lived Access Token</b> (Профиль → Безопасность). Хранится только в этом браузере (localStorage), в файл не попадёт.</p>
            <input ref={tokenInput} type="password" defaultValue={(typeof localStorage !== "undefined" && localStorage.getItem(LS_TOKEN)) || ""} placeholder="eyJhbGciOiJ..." autoComplete="off" spellCheck="false" />
            <div className="row">
              <button className="clear" onClick={clearToken}>Отключить</button>
              <button onClick={() => setDlg(false)}>Отмена</button>
              <button className="primary" onClick={saveToken}>Подключить</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const CSS = `
.lm-root{--bg:#0A0D12;--card:#141a22;--card2:#1a212b;--line:#28313d;--ink:#EAF0F6;--dim:#93A2B3;--mute:#5d6a78;
  --on:#3DDC84;--off:#3a4453;--warn:#F5B342;--crit:#FF5D5D;--ev:#4FC3E8;--heat:#FF8A5B;--accent:#7C5CFF;
  color:var(--ink); font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif; -webkit-font-smoothing:antialiased;
  position:relative; min-height:100%; background:var(--bg);}
.lm-root.lm-light{--bg:#eef1f6;--card:#ffffff;--card2:#f2f5fa;--line:#d8dee8;--ink:#141a22;--dim:#5a6675;--mute:#8a97a6;--off:#c3ccd8;}
.lm-root .wrap{max-width:1200px; margin:0 auto; padding:clamp(16px,3vw,30px) clamp(14px,3vw,26px) 60px;}
.lm-root .top{display:flex; align-items:center; gap:12px; flex-wrap:wrap; margin-bottom:22px;}
.lm-root .brand{display:flex; flex-direction:column; gap:2px; margin-right:auto;}
.lm-root .brand .k{font-family:ui-monospace,Menlo,Consolas,monospace; font-size:.7rem; letter-spacing:.28em; text-transform:uppercase; color:var(--on);}
.lm-root .brand h1{margin:0; font-size:clamp(1.3rem,3.4vw,1.9rem); letter-spacing:-.02em; font-weight:680;}
.lm-root .badge{display:inline-flex; align-items:center; gap:7px; font-family:ui-monospace,Menlo,Consolas,monospace; font-size:.72rem; padding:6px 11px; border-radius:999px; border:1px solid var(--line); background:var(--card); color:var(--dim);}
.lm-root .badge .led{width:8px; height:8px; border-radius:50%; background:var(--mute);}
.lm-root .badge.live .led{background:var(--on); box-shadow:0 0 10px var(--on); animation:lm-blink 1.6s ease-in-out infinite;}
.lm-root .badge.demo .led{background:var(--warn);}
@keyframes lm-blink{50%{opacity:.35;}}
.lm-root .iconbtn{width:38px; height:38px; border-radius:11px; border:1px solid var(--line); background:var(--card); color:var(--ink); font-size:16px; cursor:pointer; display:grid; place-items:center; transition:.15s;}
.lm-root .iconbtn:hover{border-color:var(--accent); transform:translateY(-1px);}
.lm-root .iconbtn:focus-visible{outline:2px solid var(--ev); outline-offset:2px;}
.lm-root .env{display:flex; gap:8px; flex-wrap:wrap;}
.lm-root .env .chip{display:inline-flex; align-items:center; gap:7px; font-size:.8rem; color:var(--dim); background:var(--card); border:1px solid var(--line); border-radius:999px; padding:6px 12px;}
.lm-root .env .chip b{color:var(--ink); font-weight:600;}
.lm-root .hero{background:linear-gradient(160deg,var(--card),color-mix(in srgb,var(--card) 80%, #000)); border:1px solid var(--line); border-radius:18px; padding:20px 22px; margin-bottom:16px; display:grid; grid-template-columns:auto 1fr; gap:24px; align-items:center; position:relative; overflow:hidden;}
.lm-root .hero .glow{position:absolute; inset:0; pointer-events:none; opacity:.5; transition:background .6s;}
.lm-root .gauge{display:flex; flex-direction:column; align-items:center; gap:4px; min-width:150px; z-index:1;}
.lm-root .gauge .val{font-size:clamp(2.2rem,6vw,3.4rem); font-weight:760; letter-spacing:-.03em; line-height:1; font-variant-numeric:tabular-nums; transition:color .5s;}
.lm-root .gauge .unit{font-family:ui-monospace,Menlo,Consolas,monospace; font-size:.74rem; color:var(--dim); letter-spacing:.05em;}
.lm-root .gauge .tag{margin-top:6px; font-family:ui-monospace,Menlo,Consolas,monospace; font-size:.7rem; letter-spacing:.14em; text-transform:uppercase; padding:3px 10px; border-radius:999px;}
.lm-root .heromid{z-index:1; min-width:0;}
.lm-root .heromid .lbl{font-family:ui-monospace,Menlo,Consolas,monospace; font-size:.66rem; letter-spacing:.1em; text-transform:uppercase; color:var(--mute); margin-bottom:10px;}
.lm-root .range{height:12px; border-radius:999px; position:relative; background:linear-gradient(90deg,var(--on) 0%,var(--warn) 55%,var(--crit) 100%);}
.lm-root .range .mark{position:absolute; top:-5px; width:4px; height:22px; border-radius:3px; background:#fff; box-shadow:0 0 8px rgba(255,255,255,.7); transition:left .6s cubic-bezier(.2,.7,.2,1);}
.lm-root .range .ends{display:flex; justify-content:space-between; margin-top:8px; font-family:ui-monospace,Menlo,Consolas,monospace; font-size:.72rem; color:var(--dim);}
.lm-root .heromid .next{margin-top:14px; font-size:.84rem; color:var(--dim);} .lm-root .heromid .next b{color:var(--ink);}
.lm-root .lm-zone{margin-top:22px;}
.lm-root .zt{display:flex; align-items:center; gap:10px; margin:0 0 12px;}
.lm-root .zt .zi{width:30px; height:30px; border-radius:9px; display:grid; place-items:center; font-size:15px; background:var(--card2); border:1px solid var(--line);}
.lm-root .zt h2{margin:0; font-size:1.02rem; font-weight:640; letter-spacing:-.01em;}
.lm-root .zt .zc{font-family:ui-monospace,Menlo,Consolas,monospace; font-size:.7rem; color:var(--mute); margin-left:auto;}
.lm-root .grid{display:grid; gap:11px; grid-template-columns:repeat(auto-fill,minmax(172px,1fr));}
.lm-tile{background:var(--card); border:1px solid var(--line); border-radius:14px; padding:13px 14px; position:relative; overflow:hidden; transition:transform .16s,border-color .3s,box-shadow .4s; animation:lm-rise .5s both;}
@keyframes lm-rise{from{opacity:0; transform:translateY(10px);} to{opacity:1; transform:none;}}
.lm-tile.tap{cursor:pointer;}
.lm-tile.tap:hover{transform:translateY(-3px); border-color:color-mix(in srgb,var(--accent) 45%,var(--line));}
.lm-tile.tap:active{transform:translateY(-1px) scale(.985);}
.lm-tile.tap:focus-visible{outline:2px solid var(--ev); outline-offset:2px;}
.lm-tile.pending{opacity:.72;}
.lm-tile .th{display:flex; align-items:center; gap:9px; margin-bottom:9px;}
.lm-tile .ic{width:30px; height:30px; border-radius:9px; display:grid; place-items:center; font-size:15px; background:var(--card2); border:1px solid var(--line); flex:0 0 auto; transition:.3s;}
.lm-tile .nm{font-size:.82rem; font-weight:600; line-height:1.15; letter-spacing:-.005em;}
.lm-tile .sub{font-family:ui-monospace,Menlo,Consolas,monospace; font-size:.68rem; color:var(--mute); margin-top:1px;}
.lm-tile .tapdot{margin-left:auto; color:var(--mute); font-size:.9rem; opacity:.5;}
.lm-tile .val{font-size:1.05rem; font-weight:680; font-variant-numeric:tabular-nums; letter-spacing:-.01em;}
.lm-tile .val small{font-size:.72rem; color:var(--dim); font-weight:500;}
.lm-tile .foot{display:flex; align-items:center; justify-content:space-between; margin-top:8px;}
.lm-tile .state{display:inline-flex; align-items:center; gap:6px; font-family:ui-monospace,Menlo,Consolas,monospace; font-size:.7rem; letter-spacing:.06em; text-transform:uppercase; color:var(--dim);}
.lm-tile .state .d{width:8px; height:8px; border-radius:50%; background:var(--off); transition:.3s;}
.lm-tile.on{border-color:color-mix(in srgb,var(--on) 45%,var(--line));}
.lm-tile.on .ic{background:color-mix(in srgb,var(--on) 22%,var(--card2)); border-color:transparent; box-shadow:0 0 16px color-mix(in srgb,var(--on) 40%,transparent);}
.lm-tile.on .state .d{background:var(--on); box-shadow:0 0 10px var(--on); animation:lm-blink 1.8s ease-in-out infinite;}
.lm-tile.on .state{color:var(--on);}
.lm-tile.on::after{content:""; position:absolute; inset:0; border-radius:14px; pointer-events:none; background:radial-gradient(120px 60px at 100% 0%, color-mix(in srgb,var(--on) 12%,transparent), transparent 70%);}
.lm-tile.alert{border-color:var(--crit); animation:lm-pulseR 1.2s ease-in-out infinite;}
.lm-tile.alert .ic{background:color-mix(in srgb,var(--crit) 25%,var(--card2)); box-shadow:0 0 16px var(--crit);}
.lm-tile.alert .state{color:var(--crit);} .lm-tile.alert .state .d{background:var(--crit); box-shadow:0 0 10px var(--crit);}
@keyframes lm-pulseR{50%{box-shadow:0 0 0 3px rgba(255,93,93,.12);}}
.lm-tile.heat .ic{color:var(--heat);} .lm-tile.ev .ic{color:var(--ev);}
.lm-root .foot2{margin-top:36px; padding-top:16px; border-top:1px solid var(--line); display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px; font-family:ui-monospace,Menlo,Consolas,monospace; font-size:.7rem; color:var(--mute);}
.lm-toast{position:fixed; left:50%; bottom:26px; transform:translateX(-50%); background:var(--accent); color:#fff; font-size:.86rem; font-weight:600; padding:11px 18px; border-radius:12px; box-shadow:0 10px 30px rgba(0,0,0,.4); z-index:60; animation:lm-rise .25s both;}
.lm-root .dlg{position:fixed; inset:0; background:rgba(6,9,13,.82); display:flex; align-items:center; justify-content:center; z-index:50; backdrop-filter:blur(6px); padding:20px;}
.lm-root .dlg .box{background:var(--card); border:1px solid var(--line); border-radius:16px; padding:22px; max-width:440px; width:100%;}
.lm-root .dlg h3{margin:0 0 6px; font-size:1.05rem;}
.lm-root .dlg p{margin:0 0 14px; font-size:.86rem; color:var(--dim); line-height:1.5;}
.lm-root .dlg input{width:100%; background:var(--bg); border:1px solid var(--line); color:var(--ink); border-radius:10px; padding:11px 12px; font-family:ui-monospace,Menlo,Consolas,monospace; font-size:.78rem; margin-bottom:12px;}
.lm-root .dlg .row{display:flex; gap:8px; justify-content:flex-end;}
.lm-root .dlg button{border:1px solid var(--line); background:var(--card2); color:var(--ink); border-radius:10px; padding:9px 15px; font-size:.82rem; cursor:pointer;}
.lm-root .dlg button.primary{background:var(--on); color:#08130c; border-color:transparent; font-weight:700;}
.lm-root .dlg button.danger{background:var(--crit); color:#fff; border-color:transparent; font-weight:700;}
.lm-root .dlg .clear{margin-right:auto; color:var(--dim); background:transparent; border:none;}
@media (prefers-reduced-motion:reduce){ .lm-root *{animation:none !important;} }
`;
