import React, { useEffect, useRef } from "react";

/**
 * SmartHomeForceGraph — animated force-directed map of the whole smart home.
 * Physics simulation on <canvas>: device/sensor/automation icons cluster by
 * subsystem, curved links, hover-highlight, drag, zoom/pan, and a click-to-open
 * info card with LIVE values (status, temperature, kWh today, moisture, price…).
 *
 * Live data: reads Home Assistant /api/states with a token kept ONLY in the
 * browser (localStorage "livemap_token" — shared with LiveDeviceMap). Click ⚙
 * to set it. Falls back to an interactive DEMO snapshot when HA is unreachable.
 * Fills its parent container (give the parent a width/height).
 *
 *   import SmartHomeForceGraph from "./SmartHomeForceGraph";
 *   <div style={{width:"100%",height:"100vh"}}><SmartHomeForceGraph/></div>
 */

const LS_TOKEN = "livemap_token";
const GROUPS = {
  core: ["#F2C230", "Home Assistant"], energy: ["#3DDC84", "Энергия / цена"],
  climate: ["#FF8A5B", "Климат / котёл"], ev: ["#4FC3E8", "Электромобиль"],
  safety: ["#FF5D5D", "Безопасность"], control: ["#FF6FA5", "Управление"],
  modes: ["#8B6CFF", "Режимы / присутствие"], reports: ["#5B8DEF", "Отчёты / сервис"],
};
const N = [
  ["HA", "core", 22, "home"],
  ["Nord Pool", "energy", 11, "bolt"], ["Elering", "ev", 9, "chart"], ["ecoNET24", "climate", 10, "flame"], ["Tuya Cloud", "ev", 9, "cloud"], ["Gemini AI", "control", 8, "ai"], ["Tailscale", "control", 7, "globe"],
  ["Бойлер", "energy", 13, "flame"], ["Полотенцесушитель", "energy", 10, "flame"], ["Аквариум", "energy", 9, "fish"], ["Черепаха", "energy", 9, "loop"], ["Гидрофор", "energy", 9, "droplet"],
  ["EV зарядка", "ev", 12, "car"], ["ev_charge_start", "ev", 8, "clock"], ["ev_manual_mode", "ev", 8, "sliders"],
  ["Пол ванная", "climate", 10, "thermo"], ["Пол душевая", "climate", 10, "thermo"],
  ["Влага ванная", "safety", 8, "droplet"], ["Влага гараж", "safety", 8, "droplet"], ["Влага кухня", "safety", 8, "droplet"], ["Влага душевая", "safety", 8, "droplet"],
  ["Дым", "safety", 8, "smoke"], ["Дверь", "safety", 8, "door"], ["Кран воды", "safety", 10, "valve"], ["Сирена", "safety", 8, "siren"],
  ["security_armed", "safety", 8, "shield"], ["grace", "safety", 7, "hourglass"],
  ["Telegram бот", "control", 13, "chat"], ["Mini App", "control", 9, "phone"], ["Планшет", "control", 8, "monitor"], ["Живая карта", "control", 8, "map"],
  ["Меню", "control", 7, "menu"], ["Обработчик кнопок", "control", 10, "button"],
  ["night_saver", "modes", 9, "moon"], ["Присутствие", "modes", 8, "person"],
  ["Бойлер·NordPool", "energy", 7, "flame"], ["Полотенце·NordPool", "energy", 7, "flame"], ["Прогноз цен", "energy", 7, "chart"], ["Скоро дёшево", "energy", 7, "clock"],
  ["Пол ванная·auto", "climate", 7, "thermo"], ["Пол душевая·auto", "climate", 7, "thermo"], ["Турбо ванная", "climate", 6, "flame"], ["Турбо душевая", "climate", 6, "flame"], ["Котёл ГВС", "climate", 7, "droplet"], ["Котёл: уведомл.", "climate", 7, "bell"],
  ["EV планировщик", "ev", 8, "calendar"], ["EV автозарядка", "ev", 8, "bolt"], ["EV сброс", "ev", 6, "loop"], ["EV↔Бойлер интерлок", "ev", 7, "link"],
  ["Утечка воды v4", "safety", 9, "siren"], ["Дым→сирена", "safety", 7, "siren"], ["Тревога охраны", "safety", 7, "shield"], ["Устройство недоступно", "safety", 7, "warning"], ["Startup grace", "safety", 6, "hourglass"], ["Tuya reconnect", "safety", 6, "loop"],
  ["Ночь: расписание", "modes", 7, "clock"], ["Ночь: применить", "modes", 8, "moon"], ["Ночной патруль", "modes", 7, "moon"],
  ["Утренний брифинг", "reports", 7, "sun"], ["Отчёт потребления", "reports", 7, "chart"], ["Снимок энергии", "reports", 7, "save"], ["Самодиагностика", "reports", 7, "medic"], ["Батареи <30%", "reports", 6, "battery"], ["HA обновления", "reports", 7, "refresh"],
];
const L = [
  ["HA", "Nord Pool"], ["HA", "Elering"], ["HA", "ecoNET24"], ["HA", "Tuya Cloud"], ["HA", "Gemini AI"], ["HA", "Tailscale"],
  ["HA", "Telegram бот"], ["HA", "Mini App"], ["HA", "Планшет"], ["HA", "Живая карта"],
  ["Nord Pool", "Бойлер·NordPool"], ["Бойлер·NordPool", "Бойлер"], ["Nord Pool", "Полотенce·NordPool".replace("ce", "це")], ["Полотенце·NordPool", "Полотенцесушитель"],
  ["Nord Pool", "Пол ванная·auto"], ["Пол ванная·auto", "Пол ванная"], ["Nord Pool", "Пол душевая·auto"], ["Пол душевая·auto", "Пол душевая"],
  ["Nord Pool", "Прогноз цен"], ["Прогноз цен", "Telegram бот"], ["Nord Pool", "Скоро дёшево"], ["Скоро дёшево", "Telegram бот"],
  ["Турбо ванная", "Пол ванная"], ["Турбо душевая", "Пол душевая"], ["Nord Pool", "Турбо ванная"], ["Nord Pool", "Турбо душевая"],
  ["ecoNET24", "Бойлер"], ["ecoNET24", "Котёл ГВС"], ["Котёл ГВС", "Бойлер"], ["ecoNET24", "Котёл: уведомл."], ["Котёл: уведомл.", "Telegram бот"], ["Бойлер·NordPool", "Пол ванная"],
  ["Elering", "EV планировщик"], ["EV планировщик", "ev_charge_start"], ["ev_charge_start", "EV автозарядка"],
  ["EV автозарядка", "EV зарядка"], ["ev_manual_mode", "EV автозарядка"], ["EV сброс", "ev_manual_mode"],
  ["Tuya Cloud", "EV зарядка"], ["EV↔Бойлер интерлок", "EV зарядка"], ["EV↔Бойлер интерлок", "Бойлер"], ["EV автозарядка", "Бойлер"],
  ["Влага ванная", "Утечка воды v4"], ["Влага гараж", "Утечка воды v4"], ["Влага кухня", "Утечка воды v4"], ["Влага душевая", "Утечка воды v4"],
  ["Утечка воды v4", "Кран воды"], ["Утечка воды v4", "Telegram бот"], ["grace", "Утечка воды v4"], ["Startup grace", "grace"], ["Tuya reconnect", "grace"],
  ["Дым", "Дым→сирена"], ["Дым→сирена", "Сирена"], ["Дым→сирена", "Telegram бот"],
  ["Дверь", "Тревога охраны"], ["security_armed", "Тревога охраны"], ["Тревога охраны", "Сирена"], ["Тревога охраны", "Telegram бот"],
  ["Устройство недоступно", "Telegram бот"], ["Tuya Cloud", "Устройство недоступно"],
  ["Gemini AI", "Telegram бот"], ["Telegram бот", "Меню"], ["Меню", "Обработчик кнопок"],
  ["Обработчик кнопок", "Бойлер"], ["Обработчик кнопок", "EV зарядка"], ["Обработчик кнопок", "Кран воды"],
  ["Обработчик кнопок", "security_armed"], ["Обработчик кнопок", "night_saver"], ["Обработчик кнопок", "Пол ванная"], ["Обработчик кнопок", "Пол душевая"],
  ["Обработчик кнопок", "Полотенцесушитель"], ["Обработчик кнопок", "Аквариум"], ["Mini App", "Обработчик кнопок"], ["Планшет", "Обработчик кнопок"],
  ["Живая карта", "Бойлер"], ["Живая карта", "EV зарядка"], ["Живая карта", "night_saver"], ["Живая карта", "Кран воды"],
  ["Ночь: расписание", "night_saver"], ["night_saver", "Ночь: применить"],
  ["Ночь: применить", "Полотенцесушитель"], ["Ночь: применить", "Пол ванная"], ["Ночь: применить", "Пол душевая"], ["Ночь: применить", "Аквариум"], ["Ночь: применить", "Черепаха"],
  ["Ночной патруль", "Telegram бот"], ["Присутствие", "security_armed"], ["Присутствие", "Telegram бот"],
  ["Утренний брифинг", "Telegram бот"], ["Отчёт потребления", "Telegram бот"], ["Снимок энергии", "HA"], ["Самодиагностика", "Telegram бот"], ["Батареи <30%", "Telegram бот"], ["HA обновления", "Telegram бот"],
  ["Отчёт потребления", "Бойлер"], ["Отчёт потребления", "EV зарядка"], ["Снимок энергии", "Аквариум"], ["Снимок энергии", "Гидрофор"],
];
const ANIM = { flame: "flick", droplet: "drip", siren: "shake", warning: "shake", bell: "shake", loop: "spin", clock: "spin", refresh: "spin", calendar: "spin", cloud: "drift", globe: "drift", chart: "drift", ai: "drift", person: "drift", home: "hub" };
const META = {
  "HA": ["Home Assistant Core 2026.7.1", "Ядро: оркеструет автоматизации, интеграции и устройства."],
  "Nord Pool": ["sensor.nord_pool_lv_current_price", "Биржевая цена электричества LV. Порог дешёвого — 0.04 €/кВт·ч."],
  "Elering": ["Elering API", "15-минутные цены LV для планировщика EV (с повторными попытками)."],
  "ecoNET24": ["REST (локальная сеть)", "Контроллер котла: температуры CO/ГВС, режим горения."],
  "Tuya Cloud": ["Tuya Cloud API", "Облако Tuya: розетки и EV-зарядка (протокол 3.5)."],
  "Gemini AI": ["Google Gemini", "AI-ассистент: отвечает на команды в Telegram."],
  "Tailscale": ["Tailscale VPN / Funnel", "Внешний доступ в обход CGNAT."],
  "Бойлер": ["switch.smart_plug_2_socket_1", "Умная розетка бойлера. ВКЛ при цене ≤0.04."],
  "Полотенцесушитель": ["switch.kalarifer_socket_1", "Ванная 1 эт. ВКЛ при дешёвой цене."],
  "Аквариум": ["switch.akvarium_svet_socket_1", "Свет аквариума. Гаснет в ночном режиме."],
  "Черепаха": ["switch.retserkuliatsiia_goriachai_vody_socket_1", "Рециркуляция горячей воды."],
  "Гидрофор": ["switch.zigbee_plug_2_socket_1", "Насос водоснабжения."],
  "EV зарядка": ["switch.ev_charger_switch", "Зарядка электромобиля (Tuya 3.5), 2ч по расписанию."],
  "ev_charge_start": ["input_datetime.ev_charge_start", "Время следующей зарядки — ставит планировщик."],
  "ev_manual_mode": ["input_boolean.ev_manual_mode", "Ручной режим — отключает авто-планировщик."],
  "Пол ванная": ["climate.floor_heating", "Тёплый пол: manual 30° дёшево / auto дорого."],
  "Пол душевая": ["climate.floor_heating_2", "Тёплый пол душевой 1 эт."],
  "Влага ванная": ["binary_sensor.vannaia_moisture", "Датчик протечки — ванная."],
  "Влага гараж": ["binary_sensor.garazh_moisture", "Датчик протечки — гараж."],
  "Влага кухня": ["binary_sensor.kukhnia_moisture", "Датчик протечки — кухня."],
  "Влага душевая": ["binary_sensor.water_sensor_4_moisture", "Датчик протечки — душевая."],
  "Дым": ["binary_sensor.wifi_th_smoke_sensor_smoke", "Датчик дыма → сирена."],
  "Дверь": ["binary_sensor.door_sensor_door", "Дверной датчик → охрана."],
  "Кран воды": ["switch.voda_kran_switch_1", "Аварийное перекрытие воды."],
  "Сирена": ["siren.alarm", "Сирена тревоги."],
  "security_armed": ["input_boolean.security_armed", "Режим охраны дома."],
  "grace": ["input_boolean (grace)", "Блокирует ложные тревоги протечки после старта/reconnect."],
  "Telegram бот": ["@your_bot (шаблон)", "Управление и уведомления через Telegram."],
  "Mini App": ["/local/smarthouse.html", "Мобильный интерфейс в Telegram."],
  "Планшет": ["/local/tablet.html", "Настенная панель управления."],
  "Живая карта": ["/local/livemap.html", "Интерактивная карта устройств."],
  "Меню": ["Автоматизация", "Команда «меню» → inline-кнопки."],
  "Обработчик кнопок": ["Автоматизация", "Обрабатывает все нажатия inline-кнопок."],
  "night_saver": ["input_boolean.night_saver", "Ночная экономия 22:00–05:00."],
  "Присутствие": ["person.owner", "Дома ли хозяин (по телефону)."],
  "Бойлер·NordPool": ["Автоматизация", "Бойлер ВКЛ ≤0.04 / ВЫКЛ >0.04."],
  "Полотенце·NordPool": ["Автоматизация", "Полотенцесушитель по цене Nord Pool."],
  "Прогноз цен": ["Автоматизация", "Присылает прогноз цен в Telegram."],
  "Скоро дёшево": ["Автоматизация", "Алерт когда следующая цена станет дешёвой."],
  "Пол ванная·auto": ["Автоматизация", "Управляет полом ванной по цене."],
  "Пол душевая·auto": ["Автоматизация", "Управляет полом душевой по цене."],
  "Турбо ванная": ["Автоматизация", "Доп. нагрев при очень дешёвой цене."],
  "Турбо душевая": ["Автоматизация", "Доп. нагрев при очень дешёвой цене."],
  "Котёл ГВС": ["Автоматизация", "Уставка ГВС 40/55° по состоянию розетки."],
  "Котёл: уведомл.": ["Автоматизация", "Уведомления о режиме/аварии котла."],
  "EV планировщик": ["ev_best2h.py", "Ищет лучшее 2ч окно по ценам Elering."],
  "EV автозарядка": ["Автоматизация", "Стартует зарядку в запланированное время (2ч)."],
  "EV сброс": ["Автоматизация", "Сбрасывает ручной режим после зарядки."],
  "EV↔Бойлер интерлок": ["Автоматизация", "Не даёт греть бойлер и заряжать одновременно."],
  "Утечка воды v4": ["Автоматизация", "Протечка → перекрыть кран + Telegram с кнопками."],
  "Дым→сирена": ["Автоматизация", "Дым → сирена + уведомление."],
  "Тревога охраны": ["Автоматизация", "Открытие двери при охране → тревога."],
  "Устройство недоступно": ["Автоматизация", "Алерт если устройство 5+ мин offline."],
  "Startup grace": ["Автоматизация", "Блокирует ложные тревоги 15 мин после старта HA."],
  "Tuya reconnect": ["Автоматизация", "Блокирует ложные тревоги после reconnect Tuya."],
  "Ночь: расписание": ["Автоматизация", "22:00 вкл / 05:00 выкл ночную экономию."],
  "Ночь: применить": ["Автоматизация", "Ночью выключает приборы (кроме бойлера/EV)."],
  "Ночной патруль": ["Автоматизация", "23:30 — предлагает погасить свет."],
  "Утренний брифинг": ["Автоматизация", "07:00 — сводка дня в Telegram."],
  "Отчёт потребления": ["Автоматизация", "23:00 — отчёт по энергии."],
  "Снимок энергии": ["Автоматизация", "00:01 — снимок счётчиков (расход за день)."],
  "Самодиагностика": ["Автоматизация", "11/15/19:00 — проверка систем."],
  "Батареи <30%": ["Автоматизация", "09:00 — алерт о низком заряде батарей."],
  "HA обновления": ["Автоматизация", "10:00 — проверка обновлений HA."],
};
const NODE_ENT = {
  "Бойлер": { t: "plug", e: "switch.smart_plug_2_socket_1", en: "sensor.boiler_total_energy", mid: "input_number.midnight_boiler_energy" },
  "Полотенцесушитель": { t: "plug", e: "switch.kalarifer_socket_1", en: "sensor.terarium_total_energy", mid: "input_number.midnight_kalarifer_energy" },
  "Аквариум": { t: "plug", e: "switch.akvarium_svet_socket_1", en: "sensor.akvarium_svet_total_energy", mid: "input_number.midnight_akv_energy" },
  "Черепаха": { t: "plug", e: "switch.retserkuliatsiia_goriachai_vody_socket_1", en: "sensor.cherepakha_total_energy", mid: "input_number.midnight_chep_energy" },
  "Гидрофор": { t: "plug", e: "switch.zigbee_plug_2_socket_1", en: "sensor.zigbee_plug_2_total_energy", mid: "input_number.midnight_gidro_energy" },
  "EV зарядка": { t: "ev" }, "Кран воды": { t: "valve", e: "switch.voda_kran_switch_1" },
  "Пол ванная": { t: "climate", e: "climate.floor_heating" }, "Пол душевая": { t: "climate", e: "climate.floor_heating_2" },
  "ecoNET24": { t: "boiler" }, "Nord Pool": { t: "price" },
  "Влага ванная": { t: "wet", e: "binary_sensor.vannaia_moisture" }, "Влага гараж": { t: "wet", e: "binary_sensor.garazh_moisture" },
  "Влага кухня": { t: "wet", e: "binary_sensor.kukhnia_moisture" }, "Влага душевая": { t: "wet", e: "binary_sensor.water_sensor_4_moisture" },
  "Дым": { t: "smoke", e: "binary_sensor.wifi_th_smoke_sensor_smoke" }, "Дверь": { t: "door", e: "binary_sensor.door_sensor_door" },
  "security_armed": { t: "bool", e: "input_boolean.security_armed" }, "night_saver": { t: "bool", e: "input_boolean.night_saver" },
  "ev_manual_mode": { t: "bool", e: "input_boolean.ev_manual_mode" }, "grace": { t: "bool", e: "input_boolean.ha_startup_grace" },
  "Присутствие": { t: "person", e: "person.owner" }, "ev_charge_start": { t: "dt", e: "input_datetime.ev_charge_start" },
};
const DEMO_STATES = {
  "switch.smart_plug_2_socket_1": { state: "on" }, "switch.kalarifer_socket_1": { state: "on" }, "switch.akvarium_svet_socket_1": { state: "on" },
  "switch.retserkuliatsiia_goriachai_vody_socket_1": { state: "on" }, "switch.zigbee_plug_2_socket_1": { state: "on" }, "switch.ev_charger_switch": { state: "off" }, "switch.voda_kran_switch_1": { state: "on" },
  "sensor.boiler_total_energy": { state: "7.921" }, "sensor.terarium_total_energy": { state: "0.0" }, "sensor.akvarium_svet_total_energy": { state: "0.985" },
  "sensor.cherepakha_total_energy": { state: "1.131" }, "sensor.zigbee_plug_2_total_energy": { state: "251.74" }, "sensor.ev_charger_energy": { state: "834.73" },
  "input_number.midnight_boiler_energy": { state: "7.50" }, "input_number.midnight_kalarifer_energy": { state: "0.0" }, "input_number.midnight_akv_energy": { state: "0.90" },
  "input_number.midnight_chep_energy": { state: "1.00" }, "input_number.midnight_gidro_energy": { state: "250.90" }, "input_number.midnight_ev_energy": { state: "820.0" },
  "sensor.nord_pool_lv_current_price": { state: "0.01407" }, "sensor.nord_pool_lv_next_price": { state: "0.026" }, "sensor.nord_pool_lv_lowest_price": { state: "0.00999" }, "sensor.nord_pool_lv_highest_price": { state: "0.19" },
  "sensor.ev_charger_status": { state: "charger_insert" }, "input_datetime.ev_charge_start": { state: "2026-07-04 14:45:00" },
  "input_boolean.ev_manual_mode": { state: "off" }, "input_boolean.night_saver": { state: "off" }, "input_boolean.security_armed": { state: "off" }, "input_boolean.ha_startup_grace": { state: "off" },
  "climate.floor_heating": { state: "heat_cool", temp: 30.0, preset: "manual" }, "climate.floor_heating_2": { state: "heat_cool", temp: 32.0, preset: "manual" },
  "sensor.boiler_mode": { state: "Догорание" }, "sensor.boiler_co_temperature": { state: "60.1" }, "sensor.boiler_cwu_temperature": { state: "45.1" },
  "binary_sensor.door_sensor_door": { state: "off" }, "binary_sensor.wifi_th_smoke_sensor_smoke": { state: "off" },
  "binary_sensor.vannaia_moisture": { state: "off" }, "binary_sensor.garazh_moisture": { state: "off" }, "binary_sensor.kukhnia_moisture": { state: "off" }, "binary_sensor.water_sensor_4_moisture": { state: "off" },
  "person.owner": { state: "home" },
};

export default function SmartHomeForceGraph({ base = "" }) {
  const host = useRef(null);

  useEffect(() => {
    const root = host.current;
    const cv = root.querySelector(".sfg-c");
    const ctx = cv.getContext("2d");
    const DPR = Math.min(2, window.devicePixelRatio || 1);
    let W = 0, Hh = 0;
    const q = (c) => root.querySelector(c);

    function size() { return [root.clientWidth || 900, root.clientHeight || 600]; }
    function resize() { const s = size(); W = s[0]; Hh = s[1]; cv.style.width = W + "px"; cv.style.height = Hh + "px"; cv.width = W * DPR; cv.height = Hh * DPR; ctx.setTransform(DPR, 0, 0, DPR, 0, 0); }

    // build graph
    const nodes = {}, arr = [];
    N.forEach((n, i) => { const o = { id: n[0], g: n[1], base: n[2] || 8, icon: n[3], anim: ANIM[n[3]] || "breathe", ph: i * 0.7, deg: 0, x: 450, y: 450, vx: 0, vy: 0, fx: null, fy: null, live: null, rows: [] }; nodes[n[0]] = o; arr.push(o); });
    const links = L.map((l) => { const a = nodes[l[0]], b = nodes[l[1]]; if (a) a.deg++; if (b) b.deg++; return { a, b }; }).filter((l) => l.a && l.b);
    const adj = {}; arr.forEach((n) => (adj[n.id] = new Set([n.id]))); links.forEach((l) => { adj[l.a.id].add(l.b.id); adj[l.b.id].add(l.a.id); });
    const rad = (n) => Math.max(12, n.base + Math.min(10, n.deg * 0.7));

    // live data
    let DATA = DEMO_STATES, islive = false, selected = null;
    const G = (e) => DATA[e] || { state: "unavailable" };
    const NU = (e) => { const v = parseFloat(G(e).state); return isNaN(v) ? null : v; };
    const ON = (e) => ["on", "home", "true", "open", "heat_cool", "heat"].includes((G(e).state || "").toLowerCase());
    const tkwh = (t, m) => { const T = NU(t), M = NU(m); if (T == null) return null; if (M == null) return T; return Math.max(0, T - M); };
    const EVRU = { charger_charging: "Заряжается", charger_insert: "Подключён", charger_pause: "Пауза", charger_free: "Свободен", charger_end: "Завершено", cloud_error: "Ошибка облака" };
    const priceLevel = (p) => (p <= 0.04 ? ["дёшево", "on"] : p <= 0.1 ? ["средне", "idle"] : ["дорого", "alert"]);
    function nodeLive(id) {
      const c = NODE_ENT[id]; if (!c) return { st: null, rows: [] };
      const rows = []; let st = "idle";
      if (c.t === "plug") { const on = ON(c.e), k = tkwh(c.en, c.mid); st = on ? "on" : "off"; rows.push(["Статус", on ? "Включён" : "Выключен"]); if (k != null) rows.push(["Расход сегодня", k.toFixed(k < 100 ? 2 : 1) + " кВт·ч"]); }
      else if (c.t === "valve") { const o = ON(c.e); st = o ? "on" : "off"; rows.push(["Кран воды", o ? "Открыт" : "Закрыт"]); }
      else if (c.t === "climate") { const s = G(c.e); st = s.preset === "manual" ? "on" : "idle"; rows.push(["Температура", s.temp != null ? s.temp + "°C" : "—"]); rows.push(["Режим", s.preset || "—"]); }
      else if (c.t === "boiler") { rows.push(["Режим", G("sensor.boiler_mode").state]); rows.push(["Контур CO", (NU("sensor.boiler_co_temperature") || "—") + "°"]); rows.push(["ГВС", (NU("sensor.boiler_cwu_temperature") || "—") + "°"]); }
      else if (c.t === "price") { const p = NU("sensor.nord_pool_lv_current_price"), nx = NU("sensor.nord_pool_lv_next_price"), lo = NU("sensor.nord_pool_lv_lowest_price"), hi = NU("sensor.nord_pool_lv_highest_price"); const pl = p != null ? priceLevel(p) : ["—", "idle"]; st = pl[1]; rows.push(["Сейчас", (p != null ? p.toFixed(4) : "—") + " €/кВт·ч"]); rows.push(["Уровень", pl[0]]); if (nx != null) rows.push(["Следующий час", nx.toFixed(4) + " €"]); if (lo != null && hi != null) rows.push(["Мин / Макс", lo.toFixed(3) + " / " + hi.toFixed(3)]); }
      else if (c.t === "wet") { const w = ON(c.e); st = w ? "alert" : "idle"; rows.push(["Состояние", w ? "МОКРО ⚠" : "Сухо"]); }
      else if (c.t === "smoke") { const w = ON(c.e); st = w ? "alert" : "idle"; rows.push(["Дым", w ? "ТРЕВОГА ⚠" : "Чисто"]); }
      else if (c.t === "door") { const o = ON(c.e); st = o ? "idle" : "off"; rows.push(["Дверь", o ? "Открыта" : "Закрыта"]); }
      else if (c.t === "bool") { const on = ON(c.e); st = on ? "on" : "off"; rows.push(["Состояние", on ? "Включено" : "Выключено"]); }
      else if (c.t === "person") { const h = ON(c.e); st = h ? "on" : "off"; rows.push(["Присутствие", h ? "Дома" : "Нет дома"]); }
      else if (c.t === "dt") { rows.push(["Запланировано", G(c.e).state]); }
      else if (c.t === "ev") { const on = ON("switch.ev_charger_switch"), stt = G("sensor.ev_charger_status").state; const ch = on || stt === "charger_charging"; st = stt === "cloud_error" ? "alert" : ch ? "on" : "off"; rows.push(["Статус", EVRU[stt] || stt]); rows.push(["Зарядка", ch ? "идёт" : "стоп"]); const k = tkwh("sensor.ev_charger_energy", "input_number.midnight_ev_energy"); if (k != null) rows.push(["Сессия сегодня", k.toFixed(1) + " кВт·ч"]); const nc = G("input_datetime.ev_charge_start").state; if (nc) rows.push(["След. сеанс", nc.slice(5, 16)]); rows.push(["Режим", ON("input_boolean.ev_manual_mode") ? "ручной" : "авто"]); }
      return { st, rows };
    }
    function computeLive() { arr.forEach((n) => { const r = nodeLive(n.id); n.live = r.st; n.rows = r.rows; }); }
    const toMap = (a) => { const m = {}; a.forEach((s) => (m[s.entity_id] = { state: s.state, temp: s.attributes && s.attributes.current_temperature, preset: s.attributes && s.attributes.preset_mode })); return m; };
    function updBadge() { const b = q(".sfg-badge"); b.className = "sfg-badge " + (islive ? "live" : "demo"); q(".sfg-btxt").textContent = islive ? "LIVE" : "ДЕМО"; }
    function loadHA() {
      const token = localStorage.getItem(LS_TOKEN);
      if (token) {
        fetch(base + "/api/states", { headers: { Authorization: "Bearer " + token } }).then((r) => {
          if (r.ok) return r.json().then((a) => { DATA = toMap(a); islive = true; computeLive(); updBadge(); if (selected) renderPanel(); });
          islive = false; updBadge();
        }).catch(() => { islive = false; updBadge(); });
      } else { DATA = DEMO_STATES; islive = false; computeLive(); updBadge(); }
    }

    // view
    let scale = 1, tx = 0, ty = 0, autoFit = true;
    function step() {
      const cx = W / 2, cy = Hh / 2; let i, j;
      for (i = 0; i < arr.length; i++) { const n = arr[i]; n.vx += (cx - n.x) * 0.004; n.vy += (cy - n.y) * 0.004; }
      for (i = 0; i < arr.length; i++) { const a = arr[i]; for (j = i + 1; j < arr.length; j++) { const b = arr[j]; const dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy + 0.01, d = Math.sqrt(d2); const rep = Math.min(8, 6000 / d2); const fx = dx / d * rep, fy = dy / d * rep; a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy; } }
      for (let k = 0; k < links.length; k++) { const l = links[k], a = l.a, b = l.b; const dx = b.x - a.x, dy = b.y - a.y, d = Math.sqrt(dx * dx + dy * dy) + 0.01; const L0 = 64 + (rad(a) + rad(b)); const f = (d - L0) * 0.03; const fx = dx / d * f, fy = dy / d * f; a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy; }
      for (i = 0; i < arr.length; i++) { const n = arr[i]; if (n.fx != null) { n.x = n.fx; n.y = n.fy; n.vx = 0; n.vy = 0; continue; } n.vx *= 0.9; n.vy *= 0.9; n.x += Math.max(-25, Math.min(25, n.vx)); n.y += Math.max(-25, Math.min(25, n.vy)); }
    }
    function fitTarget() { let mnx = 1e9, mny = 1e9, mxx = -1e9, mxy = -1e9; arr.forEach((n) => { mnx = Math.min(mnx, n.x); mny = Math.min(mny, n.y); mxx = Math.max(mxx, n.x); mxy = Math.max(mxy, n.y); }); const gw = mxx - mnx + 120, gh = mxy - mny + 120; const s = Math.max(0.35, Math.min(W / gw, Hh / gh, 2.0)); return { s, x: W / 2 - (mnx + mxx) / 2 * s, y: Hh / 2 - (mny + mxy) / 2 * s }; }
    function snapFit() { const f = fitTarget(); scale = f.s; tx = f.x; ty = f.y; }

    // interaction
    let hover = null, drag = null, pan = false, panSX = 0, panSY = 0, panTX = 0, panTY = 0, press = null;
    const s2w = (mx, my) => ({ x: (mx - tx) / scale, y: (my - ty) / scale });
    function pick(mx, my) { const w = s2w(mx, my); let best = null, bd = 1e9; for (let i = 0; i < arr.length; i++) { const n = arr[i], dx = n.x - w.x, dy = n.y - w.y, d = dx * dx + dy * dy, r = rad(n) + 7; if (d < r * r && d < bd) { bd = d; best = n; } } return best; }
    const rel = (e) => { const r = cv.getBoundingClientRect(); const p = e.touches ? e.touches[0] : e; return { x: p.clientX - r.left, y: p.clientY - r.top }; };
    function onMove(e) { const m = rel(e); if (press && !press.moved && (Math.abs(m.x - press.x) > 4 || Math.abs(m.y - press.y) > 4)) press.moved = true; if (drag) { if (press && press.moved) autoFit = false; const w = s2w(m.x, m.y); drag.fx = w.x; drag.fy = w.y; return; } if (pan) { autoFit = false; tx = panTX + (m.x - panSX); ty = panTY + (m.y - panSY); return; } if (!e.touches) { hover = pick(m.x, m.y); cv.style.cursor = hover ? "pointer" : "grab"; } }
    function onDown(e) { const m = rel(e); const n = pick(m.x, m.y); press = { n, x: m.x, y: m.y, moved: false }; if (n) { drag = n; n.fx = n.x; n.fy = n.y; hover = n; } else { pan = true; cv.classList.add("grab"); panSX = m.x; panSY = m.y; panTX = tx; panTY = ty; } }
    function onUp() { if (press && !press.moved) { if (press.n) openInfo(press.n); else closeInfo(); } if (drag) { drag.fx = null; drag.fy = null; drag = null; } pan = false; cv.classList.remove("grab"); press = null; }
    function onWheel(e) { e.preventDefault(); autoFit = false; const m = rel(e); const f = e.deltaY < 0 ? 1.12 : 1 / 1.12, ns = Math.max(0.25, Math.min(3, scale * f)); tx = m.x - (m.x - tx) * (ns / scale); ty = m.y - (m.y - ty) * (ns / scale); scale = ns; }
    function onKey(e) { if (e.key === "Escape") closeInfo(); }
    function onDbl() { arr.forEach((n) => { n.fx = null; n.fy = null; }); }

    cv.addEventListener("mousemove", onMove); cv.addEventListener("mousedown", onDown);
    window.addEventListener("mouseup", onUp); cv.addEventListener("wheel", onWheel, { passive: false });
    cv.addEventListener("dblclick", onDbl); window.addEventListener("keydown", onKey);
    cv.addEventListener("touchstart", (e) => { if (e.touches.length === 1) onDown(e); }, { passive: true });
    cv.addEventListener("touchmove", (e) => { if (e.touches.length === 1) onMove(e); }, { passive: true });
    cv.addEventListener("touchend", onUp);

    // info panel
    const esc = (s) => String(s).replace(/[&<>]/g, (c) => (c === "&" ? "&amp;" : c === "<" ? "&lt;" : "&gt;"));
    const hex = (c, a) => { const n = parseInt(c.slice(1), 16); return "rgba(" + ((n >> 16) & 255) + "," + ((n >> 8) & 255) + "," + (n & 255) + "," + a + ")"; };
    function ic(k,s){ctx.beginPath();
      if(k==="home"){ctx.moveTo(-s,-.05*s);ctx.lineTo(0,-s);ctx.lineTo(s,-.05*s);ctx.moveTo(-.72*s,-.18*s);ctx.lineTo(-.72*s,.8*s);ctx.lineTo(.72*s,.8*s);ctx.lineTo(.72*s,-.18*s);ctx.stroke();}
      else if(k==="bolt"){ctx.moveTo(.18*s,-s);ctx.lineTo(-.5*s,.12*s);ctx.lineTo(-.02*s,.12*s);ctx.lineTo(-.18*s,s);ctx.lineTo(.55*s,-.16*s);ctx.lineTo(.06*s,-.16*s);ctx.closePath();ctx.stroke();}
      else if(k==="chart"){ctx.moveTo(-.8*s,-.8*s);ctx.lineTo(-.8*s,.8*s);ctx.lineTo(.85*s,.8*s);ctx.moveTo(-.5*s,.3*s);ctx.lineTo(-.1*s,-.15*s);ctx.lineTo(.25*s,.15*s);ctx.lineTo(.75*s,-.5*s);ctx.stroke();}
      else if(k==="cloud"){ctx.arc(-.25*s,.1*s,.42*s,Math.PI*0.6,Math.PI*1.9);ctx.arc(.3*s,-.05*s,.5*s,Math.PI*1.2,Math.PI*0.2);ctx.lineTo(-.55*s,.5*s);ctx.stroke();}
      else if(k==="ai"){var a=.7*s;ctx.moveTo(-a+3,-a);ctx.lineTo(a-3,-a);ctx.arc(a-3,-a+3,3,-Math.PI/2,0);ctx.lineTo(a,a-3);ctx.arc(a-3,a-3,3,0,Math.PI/2);ctx.lineTo(-a+3,a);ctx.arc(-a+3,a-3,3,Math.PI/2,Math.PI);ctx.lineTo(-a,-a+3);ctx.arc(-a+3,-a+3,3,Math.PI,Math.PI*1.5);ctx.stroke();ctx.beginPath();ctx.arc(-.28*s,-.05*s,.09*s,0,6.28);ctx.arc(.28*s,-.05*s,.09*s,0,6.28);ctx.moveTo(-.3*s,.35*s);ctx.lineTo(.3*s,.35*s);ctx.stroke();}
      else if(k==="globe"){ctx.arc(0,0,.85*s,0,6.28);ctx.moveTo(-.85*s,0);ctx.lineTo(.85*s,0);ctx.moveTo(0,-.85*s);ctx.lineTo(0,.85*s);ctx.ellipse(0,0,.4*s,.85*s,0,0,6.28);ctx.stroke();}
      else if(k==="flame"){ctx.moveTo(0,-s);ctx.bezierCurveTo(.7*s,-.3*s,.55*s,.9*s,0,.9*s);ctx.bezierCurveTo(-.55*s,.9*s,-.55*s,-.05*s,-.05*s,-.35*s);ctx.bezierCurveTo(.05*s,0,.25*s,-.1*s,0,-s);ctx.stroke();}
      else if(k==="fish"){ctx.ellipse(-.05*s,0,.65*s,.42*s,0,0,6.28);ctx.moveTo(.55*s,0);ctx.lineTo(.95*s,-.35*s);ctx.lineTo(.95*s,.35*s);ctx.closePath();ctx.stroke();ctx.beginPath();ctx.arc(-.45*s,-.08*s,.05*s,0,6.28);ctx.stroke();}
      else if(k==="loop"){ctx.arc(0,0,.7*s,Math.PI*0.15,Math.PI*1.5);ctx.moveTo(.6*s,-.35*s);ctx.lineTo(.68*s,.05*s);ctx.lineTo(.98*s,-.2*s);ctx.stroke();}
      else if(k==="droplet"){ctx.moveTo(0,-s);ctx.bezierCurveTo(.75*s,-.1*s,.6*s,.9*s,0,.9*s);ctx.bezierCurveTo(-.6*s,.9*s,-.75*s,-.1*s,0,-s);ctx.stroke();}
      else if(k==="car"){ctx.moveTo(-.85*s,.25*s);ctx.lineTo(-.6*s,-.15*s);ctx.lineTo(.6*s,-.15*s);ctx.lineTo(.85*s,.25*s);ctx.lineTo(.85*s,.5*s);ctx.lineTo(-.85*s,.5*s);ctx.closePath();ctx.stroke();ctx.beginPath();ctx.arc(-.5*s,.5*s,.16*s,0,6.28);ctx.arc(.5*s,.5*s,.16*s,0,6.28);ctx.stroke();}
      else if(k==="clock"){ctx.arc(0,0,.85*s,0,6.28);ctx.moveTo(0,-.5*s);ctx.lineTo(0,0);ctx.lineTo(.4*s,.2*s);ctx.stroke();}
      else if(k==="sliders"){ctx.moveTo(-.8*s,-.4*s);ctx.lineTo(.8*s,-.4*s);ctx.moveTo(-.8*s,.4*s);ctx.lineTo(.8*s,.4*s);ctx.stroke();ctx.beginPath();ctx.arc(.3*s,-.4*s,.16*s,0,6.28);ctx.arc(-.3*s,.4*s,.16*s,0,6.28);ctx.stroke();}
      else if(k==="thermo"){ctx.moveTo(-.15*s,-.75*s);ctx.arc(0,-.75*s,.15*s,Math.PI,0);ctx.lineTo(.15*s,.35*s);ctx.arc(0,.5*s,.32*s,-Math.PI*0.35,Math.PI*1.35);ctx.lineTo(-.15*s,-.75*s);ctx.stroke();}
      else if(k==="smoke"){for(var w=0;w<3;w++){var xx=(-.5+w*.5)*s;ctx.moveTo(xx,-.8*s);ctx.bezierCurveTo(xx+.35*s,-.5*s,xx-.35*s,-.1*s,xx,.25*s);ctx.bezierCurveTo(xx+.3*s,.55*s,xx-.2*s,.7*s,xx,.85*s);}ctx.stroke();}
      else if(k==="door"){ctx.moveTo(-.55*s,-.85*s);ctx.lineTo(-.55*s,.85*s);ctx.lineTo(.55*s,.85*s);ctx.lineTo(.55*s,-.85*s);ctx.closePath();ctx.stroke();ctx.beginPath();ctx.arc(.3*s,.05*s,.08*s,0,6.28);ctx.stroke();}
      else if(k==="valve"){ctx.moveTo(-.9*s,.3*s);ctx.lineTo(.9*s,.3*s);ctx.moveTo(0,.3*s);ctx.lineTo(0,-.2*s);ctx.stroke();ctx.beginPath();ctx.arc(0,-.45*s,.3*s,0,6.28);ctx.moveTo(-.3*s,-.45*s);ctx.lineTo(.3*s,-.45*s);ctx.stroke();}
      else if(k==="siren"){ctx.moveTo(-.7*s,.6*s);ctx.arc(0,.6*s,.7*s,Math.PI,0);ctx.lineTo(.7*s,.6*s);ctx.closePath();ctx.stroke();ctx.beginPath();ctx.moveTo(0,-.1*s);ctx.lineTo(0,-.85*s);ctx.stroke();}
      else if(k==="shield"){ctx.moveTo(0,-.85*s);ctx.lineTo(.7*s,-.5*s);ctx.lineTo(.7*s,.15*s);ctx.bezierCurveTo(.7*s,.6*s,.3*s,.85*s,0,.95*s);ctx.bezierCurveTo(-.3*s,.85*s,-.7*s,.6*s,-.7*s,.15*s);ctx.lineTo(-.7*s,-.5*s);ctx.closePath();ctx.stroke();}
      else if(k==="hourglass"){ctx.moveTo(-.55*s,-.8*s);ctx.lineTo(.55*s,-.8*s);ctx.lineTo(-.55*s,.8*s);ctx.lineTo(.55*s,.8*s);ctx.closePath();ctx.stroke();}
      else if(k==="chat"){ctx.moveTo(-.8*s,-.7*s);ctx.lineTo(.8*s,-.7*s);ctx.lineTo(.8*s,.35*s);ctx.lineTo(-.3*s,.35*s);ctx.lineTo(-.6*s,.8*s);ctx.lineTo(-.6*s,.35*s);ctx.lineTo(-.8*s,.35*s);ctx.closePath();ctx.stroke();}
      else if(k==="phone"){ctx.moveTo(-.45*s,-.85*s);ctx.lineTo(.45*s,-.85*s);ctx.lineTo(.45*s,.85*s);ctx.lineTo(-.45*s,.85*s);ctx.closePath();ctx.moveTo(-.15*s,.62*s);ctx.lineTo(.15*s,.62*s);ctx.stroke();}
      else if(k==="monitor"){ctx.moveTo(-.85*s,-.7*s);ctx.lineTo(.85*s,-.7*s);ctx.lineTo(.85*s,.35*s);ctx.lineTo(-.85*s,.35*s);ctx.closePath();ctx.moveTo(-.3*s,.75*s);ctx.lineTo(.3*s,.75*s);ctx.moveTo(0,.35*s);ctx.lineTo(0,.75*s);ctx.stroke();}
      else if(k==="map"){ctx.moveTo(0,-.9*s);ctx.bezierCurveTo(.6*s,-.9*s,.6*s,-.15*s,0,.9*s);ctx.bezierCurveTo(-.6*s,-.15*s,-.6*s,-.9*s,0,-.9*s);ctx.stroke();ctx.beginPath();ctx.arc(0,-.35*s,.2*s,0,6.28);ctx.stroke();}
      else if(k==="menu"){ctx.moveTo(-.75*s,-.5*s);ctx.lineTo(.75*s,-.5*s);ctx.moveTo(-.75*s,0);ctx.lineTo(.75*s,0);ctx.moveTo(-.75*s,.5*s);ctx.lineTo(.75*s,.5*s);ctx.stroke();}
      else if(k==="button"){ctx.arc(0,0,.8*s,0,6.28);ctx.moveTo(.3*s,0);ctx.arc(0,0,.3*s,0,6.28);ctx.stroke();}
      else if(k==="moon"){ctx.arc(.1*s,0,.8*s,Math.PI*0.5,Math.PI*1.5);ctx.bezierCurveTo(-.35*s,-.5*s,-.35*s,.5*s,.1*s,.8*s);ctx.stroke();}
      else if(k==="person"){ctx.arc(0,-.45*s,.3*s,0,6.28);ctx.moveTo(-.55*s,.85*s);ctx.bezierCurveTo(-.55*s,.2*s,.55*s,.2*s,.55*s,.85*s);ctx.stroke();}
      else if(k==="calendar"){ctx.moveTo(-.75*s,-.6*s);ctx.lineTo(.75*s,-.6*s);ctx.lineTo(.75*s,.8*s);ctx.lineTo(-.75*s,.8*s);ctx.closePath();ctx.moveTo(-.75*s,-.25*s);ctx.lineTo(.75*s,-.25*s);ctx.moveTo(-.4*s,-.85*s);ctx.lineTo(-.4*s,-.45*s);ctx.moveTo(.4*s,-.85*s);ctx.lineTo(.4*s,-.45*s);ctx.stroke();}
      else if(k==="link"){ctx.ellipse(-.3*s,-.3*s,.28*s,.42*s,Math.PI/4,0,6.28);ctx.ellipse(.3*s,.3*s,.28*s,.42*s,Math.PI/4,0,6.28);ctx.stroke();}
      else if(k==="warning"){ctx.moveTo(0,-.85*s);ctx.lineTo(.85*s,.7*s);ctx.lineTo(-.85*s,.7*s);ctx.closePath();ctx.moveTo(0,-.25*s);ctx.lineTo(0,.25*s);ctx.stroke();}
      else if(k==="sun"){ctx.arc(0,0,.4*s,0,6.28);ctx.stroke();for(var d=0;d<8;d++){var an=d*Math.PI/4;ctx.beginPath();ctx.moveTo(Math.cos(an)*.6*s,Math.sin(an)*.6*s);ctx.lineTo(Math.cos(an)*.85*s,Math.sin(an)*.85*s);ctx.stroke();}}
      else if(k==="save"){ctx.moveTo(-.75*s,-.75*s);ctx.lineTo(.5*s,-.75*s);ctx.lineTo(.75*s,-.5*s);ctx.lineTo(.75*s,.75*s);ctx.lineTo(-.75*s,.75*s);ctx.closePath();ctx.moveTo(-.4*s,-.75*s);ctx.lineTo(-.4*s,-.35*s);ctx.lineTo(.35*s,-.35*s);ctx.lineTo(.35*s,-.75*s);ctx.stroke();}
      else if(k==="medic"){ctx.moveTo(0,-.7*s);ctx.lineTo(0,.7*s);ctx.moveTo(-.7*s,0);ctx.lineTo(.7*s,0);ctx.stroke();}
      else if(k==="battery"){ctx.moveTo(-.8*s,-.35*s);ctx.lineTo(.65*s,-.35*s);ctx.lineTo(.65*s,.35*s);ctx.lineTo(-.8*s,.35*s);ctx.closePath();ctx.moveTo(.65*s,-.15*s);ctx.lineTo(.85*s,-.15*s);ctx.lineTo(.85*s,.15*s);ctx.lineTo(.65*s,.15*s);ctx.stroke();ctx.beginPath();ctx.moveTo(-.6*s,-.15*s);ctx.lineTo(-.15*s,-.15*s);ctx.lineTo(-.15*s,.15*s);ctx.lineTo(-.6*s,.15*s);ctx.closePath();ctx.stroke();}
      else if(k==="bell"){ctx.moveTo(-.6*s,.4*s);ctx.bezierCurveTo(-.6*s,-.1*s,-.5*s,-.7*s,0,-.7*s);ctx.bezierCurveTo(.5*s,-.7*s,.6*s,-.1*s,.6*s,.4*s);ctx.lineTo(-.6*s,.4*s);ctx.moveTo(-.15*s,.6*s);ctx.arc(0,.5*s,.16*s,Math.PI,0);ctx.stroke();}
      else if(k==="refresh"){ctx.arc(0,0,.7*s,Math.PI*0.5,Math.PI*2.1);ctx.moveTo(0,-.7*s);ctx.lineTo(-.35*s,-.7*s);ctx.moveTo(0,-.7*s);ctx.lineTo(0,-.35*s);ctx.stroke();}
      else{ctx.arc(0,0,.5*s,0,6.28);ctx.stroke();}
    }
    function svgIcon(k){var M={home:'<path d="M-9 -1 L0 -10 L9 -1 M-6.5 -2 L-6.5 7 L6.5 7 L6.5 -2"/>',bolt:'<path d="M2 -10 L-5 1 L0 1 L-2 10 L6 -2 L1 -2 Z"/>',flame:'<path d="M0 -10 C7 -3 5 9 0 9 C-6 9 -6 -1 -1 -4 C0 0 3 -1 0 -10 Z"/>',droplet:'<path d="M0 -10 C8 -1 6 9 0 9 C-6 9 -8 -1 0 -10 Z"/>',car:'<path d="M-9 3 L-6 -2 L6 -2 L9 3 L9 5 L-9 5 Z"/><circle cx="-5" cy="5" r="1.6"/><circle cx="5" cy="5" r="1.6"/>',thermo:'<path d="M-1.5 -8 a1.5 1.5 0 0 1 3 0 L1.5 4 a3 3 0 1 1 -3 0 Z"/>',shield:'<path d="M0 -9 L7 -5 L7 2 C7 6 3 9 0 10 C-3 9 -7 6 -7 2 L-7 -5 Z"/>',chat:'<path d="M-8 -7 L8 -7 L8 3 L-3 3 L-6 8 L-6 3 L-8 3 Z"/>',phone:'<rect x="-4.5" y="-8.5" width="9" height="17" rx="1.5"/><path d="M-1.5 6 L1.5 6"/>',monitor:'<rect x="-8.5" y="-7" width="17" height="10.5"/><path d="M-3 7.5 L3 7.5 M0 3.5 L0 7.5"/>',map:'<path d="M0 -9 C6 -9 6 -1 0 9 C-6 -1 -6 -9 0 -9 Z"/><circle cx="0" cy="-3.5" r="2"/>',menu:'<path d="M-7 -5 L7 -5 M-7 0 L7 0 M-7 5 L7 5"/>',button:'<circle r="8"/><circle r="3"/>',moon:'<path d="M4 -8 A8 8 0 1 0 4 8 A6 6 0 0 1 4 -8 Z"/>',person:'<circle cx="0" cy="-4.5" r="3"/><path d="M-5.5 9 C-5.5 2 5.5 2 5.5 9"/>',clock:'<circle r="8.5"/><path d="M0 -5 L0 0 L4 2"/>',sliders:'<path d="M-8 -4 L8 -4 M-8 4 L8 4"/><circle cx="3" cy="-4" r="1.7"/><circle cx="-3" cy="4" r="1.7"/>',cloud:'<path d="M-6 5 A4 4 0 0 1 -3 -2 A5 5 0 0 1 6 -1 A3 3 0 0 1 6 5 Z"/>',ai:'<rect x="-7" y="-7" width="14" height="14" rx="3"/><circle cx="-3" cy="-0.5" r="1"/><circle cx="3" cy="-0.5" r="1"/><path d="M-3 3.5 L3 3.5"/>',globe:'<circle r="8.5"/><path d="M-8.5 0 L8.5 0 M0 -8.5 L0 8.5"/><ellipse rx="4" ry="8.5"/>',chart:'<path d="M-8 -8 L-8 8 L8 8 M-5 3 L-1 -1.5 L2.5 1.5 L7 -5"/>',fish:'<ellipse cx="-0.5" cy="0" rx="6.5" ry="4"/><path d="M5.5 0 L9.5 -3.5 L9.5 3.5 Z"/>',loop:'<path d="M6 -3.5 A7 7 0 1 0 7 0.5"/><path d="M6 -3.5 L6.8 0.5 L9.8 -2"/>',calendar:'<rect x="-7.5" y="-6" width="15" height="14"/><path d="M-7.5 -2.5 L7.5 -2.5 M-4 -8.5 L-4 -4.5 M4 -8.5 L4 -4.5"/>',link:'<path d="M-2 2 L-5 5 A3 3 0 0 1 -9 1 L-6 -2 M2 -2 L5 -5 A3 3 0 0 1 9 -1 L6 2 M-3 3 L3 -3"/>',warning:'<path d="M0 -8.5 L8.5 7 L-8.5 7 Z M0 -2.5 L0 2.5"/>',sun:'<circle r="4"/><path d="M0 -8 L0 -6 M0 6 L0 8 M-8 0 L-6 0 M6 0 L8 0 M-5.6 -5.6 L-4.2 -4.2 M5.6 5.6 L4.2 4.2 M5.6 -5.6 L4.2 -4.2 M-5.6 5.6 L-4.2 4.2"/>',save:'<path d="M-7.5 -7.5 L5 -7.5 L7.5 -5 L7.5 7.5 L-7.5 7.5 Z M-4 -7.5 L-4 -3.5 L3.5 -3.5 L3.5 -7.5"/>',medic:'<path d="M0 -7 L0 7 M-7 0 L7 0"/>',battery:'<rect x="-8" y="-3.5" width="14.5" height="7"/><path d="M6.5 -1.5 L8.5 -1.5 L8.5 1.5 L6.5 1.5"/>',bell:'<path d="M-6 4 C-6 -1 -5 -7 0 -7 C5 -7 6 -1 6 4 Z M-1.6 6 A1.6 1.6 0 0 0 1.6 6"/>',refresh:'<path d="M7 0 A7 7 0 1 1 4.5 -5.4 M4.5 -7 L4.5 -3 L8.5 -3"/>',valve:'<path d="M-9 3 L9 3 M0 3 L0 -2"/><circle cx="0" cy="-4.5" r="3"/><path d="M-3 -4.5 L3 -4.5"/>',smoke:'<path d="M-5 -8 C-2 -5 -8 -1 -5 3 C-2 6 -8 8 -5 9 M0 -8 C3 -5 -3 -1 0 3 C3 6 -3 8 0 9 M5 -8 C8 -5 2 -1 5 3 C8 6 2 8 5 9"/>',door:'<rect x="-5.5" y="-8.5" width="11" height="17"/><circle cx="3" cy="0.5" r="1"/>',siren:'<path d="M-7 6 A7 7 0 0 1 7 6 Z M0 -1 L0 -8.5"/>',hourglass:'<path d="M-5.5 -8 L5.5 -8 L-5.5 8 L5.5 8 Z"/>'};return M[k]||'<circle r="5"/>';}
    const PANEL = q(".sfg-panel");
    function openInfo(n) { selected = n; renderPanel(); }
    function closeInfo() { selected = null; PANEL.style.display = "none"; }
    function renderPanel() {
      const n = selected; if (!n) { PANEL.style.display = "none"; return; }
      const m = META[n.id] || ["", ""], col = GROUPS[n.g][0];
      const outs = links.filter((l) => l.a === n).map((l) => l.b);
      const ins = links.filter((l) => l.b === n).map((l) => l.a);
      const chips = (list) => (list.length ? list.map((x) => '<span class="sfg-chip2" data-id="' + esc(x.id) + '">' + '<i style="display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;background:' + GROUPS[x.g][0] + '"></i>' + esc(x.id) + "</span>").join("") : '<span class="sfg-muted">нет</span>');
      PANEL.style.display = "block"; PANEL.scrollTop = 0;
      PANEL.innerHTML =
        '<div class="sfg-ph"><div class="sfg-pic" style="background:' + hex(col, 0.18) + ";border-color:" + col + '"><svg width="24" height="24" viewBox="-12 -12 24 24" fill="none" stroke="' + col + '" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">' + svgIcon(n.icon) + '</svg></div>" +
        '<div><div class="sfg-pname">' + esc(n.id) + '</div><div class="sfg-pgrp" style="color:' + col + '">' + esc(GROUPS[n.g][1]) + "</div></div>" +
        '<button class="sfg-pclose" data-close="1" aria-label="Закрыть">×</button></div>' +
        (m[0] ? '<div class="sfg-pcode">' + esc(m[0]) + "</div>" : "") +
        (m[1] ? '<div class="sfg-pdesc">' + esc(m[1]) + "</div>" : "") +
        (n.rows && n.rows.length ? '<div class="sfg-plbl">' + (islive ? "● сейчас · LIVE" : "○ сейчас · снимок") + '</div><div class="sfg-prows">' + n.rows.map((r) => '<div class="sfg-pr"><span>' + esc(r[0]) + "</span><b>" + esc(r[1]) + "</b></div>").join("") + "</div>" : "") +
        '<div class="sfg-pstat"><b>' + n.deg + "</b> связей · <b>" + outs.length + "</b> исходящих · <b>" + ins.length + "</b> входящих</div>" +
        '<div class="sfg-plbl">→ Влияет на</div><div class="sfg-pchips">' + chips(outs) + "</div>" +
        '<div class="sfg-plbl">← Зависит от / триггеры</div><div class="sfg-pchips">' + chips(ins) + "</div>";
    }
    PANEL.addEventListener("click", (e) => { const c = e.target.closest("[data-close]"); if (c) { closeInfo(); return; } const el = e.target.closest("[data-id]"); if (el && nodes[el.dataset.id]) openInfo(nodes[el.dataset.id]); });

    // buttons
    q(".sfg-fit").onclick = () => { autoFit = true; snapFit(); };
    q(".sfg-zin").onclick = () => { autoFit = false; const ns = Math.min(3, scale * 1.2); tx = W / 2 - (W / 2 - tx) * (ns / scale); ty = Hh / 2 - (Hh / 2 - ty) * (ns / scale); scale = ns; };
    q(".sfg-zout").onclick = () => { autoFit = false; const ns = Math.max(0.25, scale / 1.2); tx = W / 2 - (W / 2 - tx) * (ns / scale); ty = Hh / 2 - (Hh / 2 - ty) * (ns / scale); scale = ns; };
    const TOK = q(".sfg-tok");
    q(".sfg-cfg").onclick = () => { q(".sfg-tokin").value = localStorage.getItem(LS_TOKEN) || ""; TOK.style.display = "flex"; };
    q(".sfg-rfs").onclick = () => loadHA();
    q(".sfg-tokcan").onclick = () => { TOK.style.display = "none"; };
    q(".sfg-toksv").onclick = () => { const v = q(".sfg-tokin").value.trim(); if (v) localStorage.setItem(LS_TOKEN, v); TOK.style.display = "none"; loadHA(); };
    q(".sfg-tokclr").onclick = () => { localStorage.removeItem(LS_TOKEN); TOK.style.display = "none"; loadHA(); };
    TOK.addEventListener("click", (e) => { if (e.target === TOK) TOK.style.display = "none"; });
    q(".sfg-legend").innerHTML = Object.keys(GROUPS).map((k) => '<div class="r"><span class="d" style="color:' + GROUPS[k][0] + ";background:" + GROUPS[k][0] + '"></span>' + GROUPS[k][1] + "</div>").join("");

    // render loop
    let t = 0, raf = 0;
    function draw() {
      t += 0.016;
      const [cw, ch] = size(); if (W !== cw || Hh !== ch) resize();
      if (autoFit) { const f = fitTarget(); scale += (f.s - scale) * 0.12; tx += (f.x - tx) * 0.12; ty += (f.y - ty) * 0.12; }
      const fnode = hover || selected; const focus = fnode ? adj[fnode.id] : null;
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0); ctx.clearRect(0, 0, W, Hh);
      const bg = ctx.createRadialGradient(W * 0.5, Hh * 0.42, 80, W * 0.5, Hh * 0.5, Math.max(W, Hh) * 0.75);
      bg.addColorStop(0, "#10151d"); bg.addColorStop(1, "#0b0e13"); ctx.fillStyle = bg; ctx.fillRect(0, 0, W, Hh);
      ctx.save(); ctx.translate(tx, ty); ctx.scale(scale, scale);
      for (let k = 0; k < links.length; k++) { const l = links[k], a = l.a, b = l.b; const on = !focus || (focus.has(a.id) && focus.has(b.id)); const col = GROUPS[a.g][0]; ctx.strokeStyle = hex(col, on ? (focus ? 0.85 : 0.22) : 0.05); ctx.lineWidth = on && focus ? 2 : 1; const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2, dx = b.x - a.x, dy = b.y - a.y; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.quadraticCurveTo(mx - dy * 0.14, my + dx * 0.14, b.x, b.y); ctx.stroke(); if (on && focus) { const pp = (t * 0.6 + k * 0.13) % 1, qv = 1 - pp; const px = qv * qv * a.x + 2 * qv * pp * (mx - dy * 0.14) + pp * pp * b.x, py = qv * qv * a.y + 2 * qv * pp * (my + dx * 0.14) + pp * pp * b.y; ctx.fillStyle = hex(col, 0.9); ctx.beginPath(); ctx.arc(px, py, 2.4, 0, 6.2832); ctx.fill(); } }
      for (let i = 0; i < arr.length; i++) {
        const n = arr[i]; const on = !focus || focus.has(n.id); const lv = n.live; const col = GROUPS[n.g][0]; const r = rad(n); const vis = on ? (lv === "off" ? 0.5 : 1) : 0.16;
        const ga = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, r * 2.4); ga.addColorStop(0, hex(col, on ? (lv === "off" ? 0.16 : 0.55) : 0.12)); ga.addColorStop(0.55, hex(col, on ? 0.14 : 0.04)); ga.addColorStop(1, hex(col, 0)); ctx.fillStyle = ga; ctx.beginPath(); ctx.arc(n.x, n.y, r * 2.4, 0, 6.2832); ctx.fill();
        ctx.globalAlpha = vis; ctx.fillStyle = hex("#0b0e13", 0.62); ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, 6.2832); ctx.fill();
        ctx.lineWidth = n.id === "HA" ? 3 : 2; ctx.strokeStyle = hex(col, on ? 0.85 : 0.25); ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, 6.2832); ctx.stroke();
        if (lv === "alert" && on) { const apr = 1 + Math.sin(t * 8) * 0.18; ctx.lineWidth = 3; ctx.strokeStyle = hex("#FF5D5D", 0.9); ctx.beginPath(); ctx.arc(n.x, n.y, r + 5 * apr, 0, 6.2832); ctx.stroke(); }
        if (selected && selected.id === n.id) { ctx.lineWidth = 3; ctx.strokeStyle = "#ffffff"; ctx.beginPath(); ctx.arc(n.x, n.y, r + 4, 0, 6.2832); ctx.stroke(); }
        ctx.save(); ctx.translate(n.x, n.y); const ph = n.ph;
        if (n.anim === "flick") { const s = 1 + Math.sin(t * 9 + ph) * 0.08; ctx.scale(s, s); } else if (n.anim === "drip") { ctx.translate(0, Math.sin(t * 3 + ph) * 2.2); } else if (n.anim === "shake") { ctx.rotate(Math.sin(t * 13 + ph) * 0.1); } else if (n.anim === "spin") { ctx.rotate(t * 0.6 + ph); } else if (n.anim === "drift") { ctx.translate(Math.sin(t * 1.3 + ph) * 2.5, 0); } else if (n.anim === "hub") { const h = 1 + Math.sin(t * 2) * 0.08; ctx.scale(h, h); } else { const bth = 1 + Math.sin(t * 2 + ph) * 0.05; ctx.scale(bth, bth); }
        ctx.lineWidth = Math.max(1.4, r * 0.11); ctx.lineCap = "round"; ctx.lineJoin = "round"; ctx.strokeStyle = hex(col, 0.95); ic(n.icon, r * 0.6); ctx.restore(); ctx.globalAlpha = 1;
      }
      ctx.textAlign = "center"; ctx.textBaseline = "top";
      for (let i = 0; i < arr.length; i++) { const n = arr[i]; const big = n.base >= 9 || n.id === "HA"; const show = big || scale > 1.2 || (focus && focus.has(n.id)); if (!show) continue; const on = !focus || focus.has(n.id); if (!on) continue; const r = rad(n), fs = n.id === "HA" ? 13 : 11; ctx.font = "600 " + fs + "px system-ui,Arial"; const tw = ctx.measureText(n.id).width, ly = n.y + r + 4; ctx.fillStyle = "rgba(8,11,16,0.62)"; rr(n.x - tw / 2 - 5, ly - 1, tw + 10, fs + 6, 5); ctx.fill(); ctx.fillStyle = "#eef2f7"; ctx.fillText(n.id, n.x, ly + 1); }
      ctx.restore(); step(); raf = requestAnimationFrame(draw);
    }
    function rr(x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }

    resize();
    arr.forEach((n, i) => { n.x = W / 2 + Math.cos(i * 2.4) * (80 + (i % 9) * 22); n.y = Hh / 2 + Math.sin(i * 2.4) * (80 + (i % 9) * 22); });
    for (let s = 0; s < 450; s++) step();
    snapFit(); computeLive(); updBadge(); loadHA();
    const iv = setInterval(loadHA, 20000);
    let ro = null; if (window.ResizeObserver) { ro = new ResizeObserver(resize); ro.observe(root); }
    raf = requestAnimationFrame(draw);

    return () => { cancelAnimationFrame(raf); clearInterval(iv); if (ro) ro.disconnect(); window.removeEventListener("mouseup", onUp); window.removeEventListener("keydown", onKey); };
  }, [base]);

  return (
    <div className="sfg" ref={host}>
      <style>{CSS}</style>
      <canvas className="sfg-c" />
      <div className="sfg-ov sfg-title"><div className="k">Home Assistant</div><h1>Карта устройств и связей</h1>
        <div className="s">Клик по узлу — инфо и состояние, наведи — связи, тяни, колесо — зум.</div>
        <div className="sfg-badge demo"><span className="dot" /><span className="sfg-btxt">ДЕМО</span></div></div>
      <div className="sfg-ov sfg-hint">клик = инфо · наведи = связи<br />перетащи · колесо = зум · 2×клик = разжать</div>
      <div className="sfg-ov sfg-legend" />
      <div className="sfg-panel" style={{ display: "none" }} />
      <div className="sfg-ov sfg-hud">
        <button className="sfg-b sfg-cfg" title="Подключить к HA (живые данные)">⚙</button>
        <button className="sfg-b sfg-rfs" title="Обновить">⟳</button>
        <button className="sfg-b sfg-zin">+</button><button className="sfg-b sfg-zout">−</button><button className="sfg-b sfg-fit">⤢</button>
      </div>
      <div className="sfg-tok" style={{ display: "none" }}>
        <div className="box">
          <h3>Живые данные из Home Assistant</h3>
          <p>Вставь <b>Long-Lived токен</b> (Профиль → Безопасность). Хранится только в браузере, показывает реальный статус, температуру, расход и т.д.</p>
          <input className="sfg-tokin" type="password" placeholder="eyJhbGci..." autoComplete="off" spellCheck="false" />
          <div className="rw"><button className="sfg-tokclr lnk">Отключить</button><button className="sfg-tokcan">Отмена</button><button className="sfg-toksv pr">Подключить</button></div>
        </div>
      </div>
    </div>
  );
}

const CSS = `
.sfg{position:relative;width:100%;height:100%;min-height:420px;background:#0b0e13;overflow:hidden;color:#e7ecf2;font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;}
.sfg .sfg-c{position:absolute;top:0;left:0;display:block;cursor:grab;}
.sfg .sfg-c.grab{cursor:grabbing;}
.sfg .sfg-ov{position:absolute;z-index:5;pointer-events:none;}
.sfg .sfg-title{top:16px;left:18px;}
.sfg .sfg-title .k{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.66rem;letter-spacing:.3em;text-transform:uppercase;color:#4fc3e8;}
.sfg .sfg-title h1{margin:2px 0 0;font-size:clamp(1rem,2.4vw,1.5rem);font-weight:700;letter-spacing:-.02em;}
.sfg .sfg-title .s{font-size:.75rem;color:#93a2b3;margin-top:4px;max-width:42ch;}
.sfg .sfg-badge{display:inline-flex;align-items:center;gap:6px;margin-top:9px;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.65rem;color:#93a2b3;background:rgba(15,19,26,.6);border:1px solid #232b36;border-radius:999px;padding:4px 9px;}
.sfg .sfg-badge .dot{width:7px;height:7px;border-radius:50%;background:#5f6b7a;}
.sfg .sfg-badge.live .dot{background:#3DDC84;box-shadow:0 0 8px #3DDC84;}
.sfg .sfg-badge.demo .dot{background:#F5B342;}
.sfg .sfg-hint{top:18px;right:18px;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.66rem;color:#5f6b7a;text-align:right;line-height:1.7;}
.sfg .sfg-legend{bottom:16px;left:18px;background:rgba(15,19,26,.72);border:1px solid #232b36;border-radius:12px;padding:10px 12px;backdrop-filter:blur(8px);display:grid;grid-template-columns:auto auto;gap:5px 16px;}
.sfg .sfg-legend .r{display:flex;align-items:center;gap:8px;font-size:.72rem;color:#aeb9c6;}
.sfg .sfg-legend .d{width:11px;height:11px;border-radius:50%;flex:0 0 auto;box-shadow:0 0 8px currentColor;}
.sfg .sfg-hud{bottom:16px;right:16px;display:flex;gap:7px;pointer-events:auto;}
.sfg .sfg-b{width:40px;height:40px;border-radius:10px;background:rgba(20,26,34,.8);border:1px solid #2a323d;color:#e7ecf2;font-size:17px;cursor:pointer;backdrop-filter:blur(6px);display:grid;place-items:center;}
.sfg .sfg-b:hover{border-color:#8b6cff;}
.sfg .sfg-panel{position:absolute;top:60px;right:14px;width:290px;max-width:82%;max-height:calc(100% - 130px);overflow:auto;background:rgba(14,18,25,.93);border:1px solid #2a323d;border-radius:14px;padding:14px 15px;backdrop-filter:blur(10px);z-index:6;font-size:.85rem;box-shadow:0 16px 40px rgba(0,0,0,.55);}
.sfg .sfg-ph{display:flex;align-items:flex-start;gap:10px;margin-bottom:10px;}
.sfg .sfg-pic{width:42px;height:42px;border-radius:11px;border:1px solid;display:grid;place-items:center;font-size:21px;flex:0 0 auto;}
.sfg .sfg-pname{font-weight:700;font-size:.95rem;line-height:1.2;}
.sfg .sfg-pgrp{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.66rem;text-transform:uppercase;letter-spacing:.08em;margin-top:3px;}
.sfg .sfg-pclose{margin-left:auto;background:none;border:none;color:#93a2b3;font-size:22px;cursor:pointer;line-height:1;}
.sfg .sfg-pclose:hover{color:#fff;}
.sfg .sfg-pcode{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.72rem;color:#4fc3e8;background:rgba(79,195,232,.1);border:1px solid rgba(79,195,232,.25);border-radius:7px;padding:5px 8px;margin-bottom:9px;word-break:break-all;}
.sfg .sfg-pdesc{color:#c2ccd8;line-height:1.5;margin-bottom:11px;}
.sfg .sfg-prows{display:flex;flex-direction:column;gap:4px;margin:2px 0 4px;}
.sfg .sfg-pr{display:flex;justify-content:space-between;gap:10px;font-size:.8rem;padding:5px 9px;background:rgba(255,255,255,.035);border-radius:7px;}
.sfg .sfg-pr span{color:#93a2b3;} .sfg .sfg-pr b{color:#eef2f7;font-weight:600;text-align:right;}
.sfg .sfg-pstat{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.72rem;color:#8a97a6;margin:6px 0;}
.sfg .sfg-pstat b{color:#e7ecf2;}
.sfg .sfg-plbl{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.63rem;text-transform:uppercase;letter-spacing:.12em;color:#5f6b7a;margin:11px 0 6px;}
.sfg .sfg-pchips{display:flex;flex-wrap:wrap;gap:5px;}
.sfg .sfg-chip2{font-size:.72rem;padding:4px 8px;border-radius:999px;background:rgba(255,255,255,.04);border:1px solid #333c48;cursor:pointer;white-space:nowrap;color:#dfe6ee;}
.sfg .sfg-chip2:hover{background:rgba(255,255,255,.1);}
.sfg .sfg-muted{color:#5f6b7a;}
.sfg .sfg-tok{position:absolute;inset:0;background:rgba(6,9,13,.82);display:flex;align-items:center;justify-content:center;z-index:20;backdrop-filter:blur(6px);padding:20px;}
.sfg .sfg-tok .box{background:#141a22;border:1px solid #2a323d;border-radius:16px;padding:22px;max-width:430px;width:100%;}
.sfg .sfg-tok h3{margin:0 0 6px;font-size:1.05rem;} .sfg .sfg-tok p{margin:0 0 13px;font-size:.83rem;color:#93a2b3;line-height:1.5;}
.sfg .sfg-tok input{width:100%;box-sizing:border-box;background:#0b0e13;border:1px solid #2a323d;color:#e7ecf2;border-radius:10px;padding:11px 12px;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.78rem;margin-bottom:12px;}
.sfg .sfg-tok .rw{display:flex;gap:8px;justify-content:flex-end;} .sfg .sfg-tok button{border:1px solid #2a323d;background:#1a212b;color:#e7ecf2;border-radius:10px;padding:9px 15px;font-size:.82rem;cursor:pointer;}
.sfg .sfg-tok .pr{background:#3DDC84;color:#08130c;border-color:transparent;font-weight:700;} .sfg .sfg-tok .lnk{margin-right:auto;background:none;border:none;color:#93a2b3;}
@media (prefers-reduced-motion:reduce){.sfg *{animation:none !important;}}
`;
