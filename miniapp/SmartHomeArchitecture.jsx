import React from "react";

/**
 * SmartHomeArchitecture — self-contained architecture diagram of the
 * Home Assistant smart home (control → access → brain → devices).
 *
 * Zero external dependencies (only React). Styles are injected via a scoped
 * <style> block so hover / keyframes / media-queries work without a CSS build.
 *
 * Usage:
 *   import SmartHomeArchitecture from "./SmartHomeArchitecture";
 *   <SmartHomeArchitecture />
 */

const T = {
  bg: "#0E1116",
  panel: "#171C24",
  line: "#28303B",
  ink: "#E6EBF0",
  inkDim: "#A3B0BF",
  inkMute: "#6B7887",
  signal: "#3DDC84", // electric green — energy / control path
  signalDim: "#1f6e44",
  data: "#4FC3E8", // cyan — data / API feeds
  cheap: "#3DDC84",
  mid: "#F5B342",
  pricey: "#FF5D5D",
  climate: "#F5B342",
  safety: "#FF7A7A",
};

const META = [
  { text: "Рига, Латвия · EUR", dot: true },
  { text: "HA OS 2026.6.4 · Hyper-V VM", strong: "2026.6.4" },
  { text: "Порог цены 0.04 €/кВт·ч", strong: "0.04 €/кВт·ч" },
  { text: "38 автоматизаций", strong: "38" },
];

const CONTROL = [
  { icon: "💬", title: "Telegram бот", desc: "команды, inline-кнопки, AI-ответы через Google Gemini.", code: "@your_bot" },
  { icon: "📱", title: "Telegram Mini App", desc: "мобильный интерфейс с плитками управления.", code: "smarthouse.html" },
  { icon: "🖥️", title: "Планшет / панель", desc: "настенный дашборд: статус, цена, безопасность.", code: "tablet.html" },
];

const ACCESS = [
  { icon: "🌐", title: "Tailscale VPN / Funnel", desc: "внешний доступ в обход CGNAT-провайдера (проброс портов невозможен)." },
  { icon: "🏠", title: "Локальная сеть", desc: "прямой доступ внутри дома.", code: "192.168.x.x" },
];

const FEEDS = [
  { icon: "⚡", title: "Nord Pool LV", sub: "цена электричества, €/кВт·ч" },
  { icon: "📈", title: "Elering API", sub: "15-мин цены · EV-планировщик" },
  { icon: "🤖", title: "Google Gemini", sub: "AI-ассистент в Telegram" },
  { icon: "☁️", title: "Tuya Cloud", sub: "EV-зарядка (протокол 3.5)" },
  { icon: "🔥", title: "ecoNET24", sub: "котёл · REST · локальный IP" },
];

const STATS = [
  { n: "38", l: "автоматизаций" },
  { n: "7", l: "интеграций" },
  { n: "24/7", l: "аптайм" },
];

const DEVICE_GROUPS = [
  {
    key: "energy",
    accent: T.signal,
    label: "Энергия · переключается по цене",
    devices: [
      { icon: "♨️", title: "Бойлер", desc: "Вкл ≤0.04, выкл >0.04 €/кВт·ч." },
      { icon: "🔌", title: "Полотенцесушитель", desc: "Нагрев при дешёвой цене." },
      { icon: "🐠", title: "Аквариум", desc: "Свет и оборудование." },
      { icon: "🐢", title: "Черепаха / рециркуляция", desc: "Рециркуляция горячей воды." },
      { icon: "💧", title: "Гидрофон", desc: "Насосная станция." },
      { icon: "🚗", title: "EV-зарядка", desc: "2ч-окно + интерлок с бойлером." },
      { icon: "🚰", title: "Кран воды", desc: "Аварийное перекрытие при утечке." },
    ],
  },
  {
    key: "climate",
    accent: T.climate,
    label: "Климат",
    devices: [
      { icon: "🌡️", title: "Тёплый пол — ванная", desc: "preset manual/auto по цене." },
      { icon: "🌡️", title: "Тёплый пол — душевая", desc: "preset manual/auto по цене." },
      { icon: "🔥", title: "Котёл (CO / ГВС)", desc: "Уставки CWU/CO через ecoNET24." },
    ],
  },
  {
    key: "safety",
    accent: T.safety,
    label: "Безопасность",
    devices: [
      { icon: "🚪", title: "Датчик двери", desc: "Открытие/закрытие · охрана." },
      { icon: "🔥", title: "Дым", desc: "Задымление → сирена." },
      { icon: "💦", title: "Утечка воды ×4", desc: "Ванная · гараж · кухня · тех. Grace-период от ложных." },
      { icon: "🛡️", title: "Охрана", desc: "Тревога · ночной патруль 23:30." },
    ],
  },
];

const PRICE_LEVELS = [
  { lamp: "g", color: T.cheap, title: "Дёшево", range: "≤ 0.04 €/кВт·ч", desc: "Дом греет всё: бойлер, полы, EV. Максимум потребления." },
  { lamp: "y", color: T.mid, title: "Средне", range: "0.04 – 0.10 €/кВт·ч", desc: "Только базовые нужды, тяжёлая нагрузка отложена." },
  { lamp: "r", color: T.pricey, title: "Дорого", range: "> 0.10 €/кВт·ч", desc: "Дорогие устройства выключены. Индикатор цены пульсирует красным." },
];

/* ---------- small presentational pieces ---------- */

function Card({ d, accent }) {
  return (
    <div className="sha-card" style={accent ? { borderTop: `2px solid ${accent}` } : undefined}>
      <div className="sha-ct">
        <span className="sha-ico">{d.icon}</span>
        <h3>{d.title}</h3>
      </div>
      <p>
        {d.desc} {d.code && <code>{d.code}</code>}
      </p>
    </div>
  );
}

function Layer({ n, kicker, title, brain, children }) {
  return (
    <section className="sha-layer">
      <div className="sha-spine">
        <div className={"sha-node" + (brain ? " sha-brain" : "")}>{n}</div>
      </div>
      <div className="sha-body">
        <div className="sha-layer-title">
          <span className="sha-kicker">{kicker}</span>
          <h2>{title}</h2>
        </div>
        {children}
      </div>
    </section>
  );
}

/* ---------- main component ---------- */

export default function SmartHomeArchitecture() {
  return (
    <div className="sha-root">
      <style>{CSS}</style>
      <div className="sha-wrap">
        <header className="sha-head">
          <p className="sha-eyebrow">Архитектура системы</p>
          <h1>
            Умный дом на <span className="sha-accent">Home Assistant</span>
          </h1>
          <p className="sha-lede">
            Дом принимает решения по цене электричества в реальном времени. Сигнал идёт от тебя
            через Telegram к мозгу Home Assistant, который оркеструет 38 автоматизаций и переключает
            устройства — включая дорогое только когда электричество дешёвое.
          </p>
          <div className="sha-meta">
            {META.map((m, i) => (
              <span className="sha-chip" key={i}>
                {m.dot && <span className="sha-dot" />}
                {m.strong ? (
                  <>
                    {m.text.split(m.strong)[0]}
                    <b>{m.strong}</b>
                    {m.text.split(m.strong)[1]}
                  </>
                ) : (
                  m.text
                )}
              </span>
            ))}
          </div>
        </header>

        <div className="sha-flow">
          <Layer n="01" kicker="Слой 01" title="Управление">
            <div className="sha-cards">
              {CONTROL.map((d, i) => (
                <Card d={d} key={i} />
              ))}
            </div>
          </Layer>

          <Layer n="02" kicker="Слой 02" title="Доступ">
            <div className="sha-cards">
              {ACCESS.map((d, i) => (
                <Card d={d} key={i} />
              ))}
            </div>
          </Layer>

          <Layer n="03" kicker="Слой 03 · ядро" title="Мозг — Home Assistant" brain>
            <div className="sha-brainband">
              <div className="sha-brain-core">
                <h3>Home Assistant OS</h3>
                <p className="sha-sub">оркестратор · автоматизации · логика</p>
                <div className="sha-stat-row">
                  {STATS.map((s, i) => (
                    <div className="sha-stat" key={i}>
                      <span className="sha-n">{s.n}</span>
                      <span className="sha-l">{s.l}</span>
                    </div>
                  ))}
                </div>
                <p className="sha-rule">
                  Ключевая логика: <b>оптимизация по Nord&nbsp;Pool</b>. Дорогие устройства
                  включаются только при цене <b>≤ 0.04&nbsp;€/кВт·ч</b>; EV-планировщик ищет лучшее
                  2-часовое окно на сутки вперёд.
                </p>
              </div>
              <div className="sha-feed">
                <div className="sha-feed-h">Входные данные / API</div>
                <ul>
                  {FEEDS.map((f, i) => (
                    <li key={i}>
                      <span className="sha-fi">{f.icon}</span>
                      <div>
                        <b>{f.title}</b>
                        <span>{f.sub}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </Layer>

          <Layer n="04" kicker="Слой 04 · выходы" title="Устройства">
            {DEVICE_GROUPS.map((g) => (
              <React.Fragment key={g.key}>
                <div className="sha-group-label">
                  <span className="sha-sw" style={{ background: g.accent }} />
                  {g.label}
                </div>
                <div className="sha-cards">
                  {g.devices.map((d, i) => (
                    <Card d={d} accent={g.accent} key={i} />
                  ))}
                </div>
              </React.Fragment>
            ))}
          </Layer>
        </div>

        <section className="sha-legend">
          <h4>Светофор цены электричества</h4>
          <p className="sha-ls">
            по этому правилу дом решает, что включать — зашито в автоматизациях и в интерфейсе
          </p>
          <div className="sha-bars">
            {PRICE_LEVELS.map((p, i) => (
              <div className="sha-bar" key={i}>
                <div className="sha-bh">
                  <span className="sha-lamp" style={{ color: p.color, background: p.color }} />
                  <span className="sha-bt">{p.title}</span>
                </div>
                <div className="sha-pv">{p.range}</div>
                <p>{p.desc}</p>
              </div>
            ))}
          </div>
        </section>

        <footer className="sha-footer">
          <span>MySmartHome · Home Assistant</span>
          <span>Поток сигнала: ты → Telegram → HA → устройства</span>
        </footer>
      </div>
    </div>
  );
}

/* ---------- scoped styles ---------- */

const CSS = `
.sha-root{
  --bg:${T.bg};--panel:${T.panel};--line:${T.line};--ink:${T.ink};
  --ink-dim:${T.inkDim};--ink-mute:${T.inkMute};--signal:${T.signal};
  --signal-dim:${T.signalDim};--data:${T.data};
  --mono:ui-monospace,"Cascadia Code","SF Mono","JetBrains Mono",Menlo,Consolas,monospace;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  background:
    radial-gradient(1200px 700px at 78% -8%, rgba(79,195,232,.07), transparent 60%),
    radial-gradient(900px 600px at 10% 108%, rgba(61,220,132,.06), transparent 55%),
    var(--bg);
  color:var(--ink);font-family:var(--sans);line-height:1.5;
  -webkit-font-smoothing:antialiased;
}
.sha-root *{box-sizing:border-box;}
.sha-wrap{max-width:1080px;margin:0 auto;padding:clamp(24px,5vw,64px) clamp(16px,4vw,40px) 72px;}

.sha-head{margin-bottom:44px;}
.sha-eyebrow{font-family:var(--mono);font-size:.72rem;letter-spacing:.22em;text-transform:uppercase;
  color:var(--signal);display:flex;align-items:center;gap:10px;margin:0 0 16px;}
.sha-eyebrow::before{content:"";width:26px;height:1px;background:var(--signal);display:inline-block;}
.sha-head h1{font-size:clamp(1.9rem,5vw,3rem);line-height:1.05;letter-spacing:-.02em;margin:0 0 14px;
  text-wrap:balance;font-weight:680;}
.sha-accent{color:var(--signal);}
.sha-lede{max-width:60ch;color:var(--ink-dim);font-size:clamp(.98rem,2vw,1.08rem);margin:0 0 22px;}
.sha-meta{display:flex;flex-wrap:wrap;gap:8px 10px;}
.sha-chip{font-family:var(--mono);font-size:.72rem;letter-spacing:.04em;color:var(--ink-dim);
  background:var(--panel);border:1px solid var(--line);border-radius:999px;padding:5px 12px;
  display:inline-flex;align-items:center;gap:7px;}
.sha-chip b{color:var(--ink);font-weight:600;}
.sha-dot{width:7px;height:7px;border-radius:50%;display:inline-block;background:${T.cheap};}

.sha-flow{display:grid;grid-template-columns:64px 1fr;gap:0;}
.sha-layer{display:contents;}
.sha-spine{position:relative;display:flex;flex-direction:column;align-items:center;}
.sha-spine::before{content:"";position:absolute;top:0;bottom:-4px;left:50%;width:2px;
  transform:translateX(-50%);background:var(--line);}
.sha-layer:first-child .sha-spine::before{top:22px;}
.sha-layer:last-child .sha-spine::before{bottom:auto;height:26px;}
.sha-node{position:relative;z-index:1;margin-top:4px;width:40px;height:40px;border-radius:11px;
  background:var(--panel);border:1px solid var(--line);color:var(--ink-dim);font-family:var(--mono);
  font-size:.82rem;font-weight:600;display:grid;place-items:center;}
.sha-brain{background:color-mix(in srgb,var(--signal) 14%,var(--panel));border-color:var(--signal);
  color:var(--signal);box-shadow:0 0 0 4px rgba(61,220,132,.10);}

.sha-body{padding:0 0 30px 20px;min-width:0;}
.sha-layer:last-child .sha-body{padding-bottom:4px;}
.sha-layer-title{display:flex;align-items:baseline;gap:12px;margin:6px 0 14px;flex-wrap:wrap;}
.sha-layer-title h2{font-size:1.02rem;margin:0;letter-spacing:-.01em;font-weight:640;}
.sha-kicker{font-family:var(--mono);font-size:.68rem;letter-spacing:.16em;text-transform:uppercase;
  color:var(--ink-mute);}

.sha-cards{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));}
.sha-card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:13px 14px;
  min-width:0;transition:border-color .18s ease,transform .18s ease;}
.sha-card:hover{border-color:var(--signal-dim);transform:translateY(-2px);}
.sha-ct{display:flex;align-items:center;gap:9px;margin-bottom:5px;}
.sha-ico{font-size:1.02rem;line-height:1;}
.sha-card h3{font-size:.92rem;margin:0;font-weight:600;letter-spacing:-.005em;}
.sha-card p{margin:0;font-size:.78rem;color:var(--ink-dim);line-height:1.45;}
.sha-card code{font-family:var(--mono);font-size:.72rem;color:var(--data);word-break:break-word;}

.sha-brainband{background:linear-gradient(180deg,rgba(61,220,132,.05),transparent 70%),var(--panel);
  border:1px solid var(--signal-dim);border-radius:16px;padding:18px;display:grid;
  grid-template-columns:1.1fr 1fr;gap:18px;}
.sha-brain-core h3{margin:0 0 4px;font-size:1.15rem;letter-spacing:-.01em;}
.sha-sub{font-family:var(--mono);font-size:.72rem;color:var(--ink-mute);margin:0 0 14px;}
.sha-stat-row{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px;}
.sha-stat{background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:8px 12px;
  flex:1 1 auto;min-width:82px;}
.sha-n{font-size:1.35rem;font-weight:700;font-variant-numeric:tabular-nums;letter-spacing:-.02em;
  display:block;line-height:1.1;}
.sha-l{font-family:var(--mono);font-size:.64rem;letter-spacing:.1em;text-transform:uppercase;
  color:var(--ink-mute);}
.sha-rule{font-size:.82rem;color:var(--ink-dim);border-left:2px solid var(--signal);padding-left:12px;}
.sha-rule b{color:var(--signal);font-weight:600;}

.sha-feed{background:var(--bg);border:1px solid var(--line);border-radius:12px;padding:14px;position:relative;}
.sha-feed-h{font-family:var(--mono);font-size:.66rem;letter-spacing:.14em;text-transform:uppercase;
  color:var(--data);display:flex;align-items:center;gap:8px;margin-bottom:12px;}
.sha-feed-h::before{content:"→";font-size:.85rem;}
.sha-feed ul{list-style:none;margin:0;padding:0;display:grid;gap:9px;}
.sha-feed li{display:grid;grid-template-columns:18px 1fr;gap:9px;font-size:.8rem;align-items:start;}
.sha-fi{color:var(--data);font-size:.9rem;line-height:1.4;}
.sha-feed li b{font-weight:600;}
.sha-feed li span{color:var(--ink-mute);font-family:var(--mono);font-size:.68rem;display:block;}

.sha-group-label{display:inline-flex;align-items:center;gap:8px;font-family:var(--mono);font-size:.68rem;
  letter-spacing:.12em;text-transform:uppercase;color:var(--ink-dim);margin:18px 0 10px;}
.sha-group-label:first-child{margin-top:2px;}
.sha-sw{width:9px;height:9px;border-radius:3px;}

.sha-legend{margin-top:40px;background:var(--panel);border:1px solid var(--line);border-radius:16px;
  padding:20px clamp(16px,3vw,26px);}
.sha-legend h4{margin:0 0 4px;font-size:.95rem;font-weight:640;}
.sha-ls{font-family:var(--mono);font-size:.72rem;color:var(--ink-mute);margin:0 0 18px;}
.sha-bars{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;}
.sha-bar{background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:12px 14px;}
.sha-bh{display:flex;align-items:center;gap:9px;margin-bottom:6px;}
.sha-lamp{width:12px;height:12px;border-radius:50%;box-shadow:0 0 10px currentColor;}
.sha-bt{font-size:.86rem;font-weight:600;}
.sha-pv{font-family:var(--mono);font-size:.72rem;color:var(--ink-dim);}
.sha-bar p{margin:4px 0 0;font-size:.76rem;color:var(--ink-dim);}

.sha-footer{margin-top:36px;padding-top:20px;border-top:1px solid var(--line);display:flex;
  justify-content:space-between;flex-wrap:wrap;gap:10px;font-family:var(--mono);font-size:.7rem;
  color:var(--ink-mute);letter-spacing:.03em;}

@media (max-width:640px){
  .sha-flow{grid-template-columns:44px 1fr;}
  .sha-node{width:34px;height:34px;font-size:.72rem;}
  .sha-body{padding-left:14px;}
  .sha-brainband{grid-template-columns:1fr;}
}
@media (prefers-reduced-motion:no-preference){
  .sha-brain{animation:sha-pulse 3.2s ease-in-out infinite;}
  @keyframes sha-pulse{
    0%,100%{box-shadow:0 0 0 4px rgba(61,220,132,.10);}
    50%{box-shadow:0 0 0 7px rgba(61,220,132,.04);}
  }
}
`;
