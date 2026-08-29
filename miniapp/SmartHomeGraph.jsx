import React, { useCallback, useLayoutEffect, useMemo, useRef, useState } from "react";

/**
 * SmartHomeGraph — full interactive node-graph of ALL 38 Home Assistant
 * automations: triggers → conditions → actions → devices, with cross-links
 * (interlocks, grace blocking, Telegram routing), animated "flowing" wires,
 * and hover highlight (hover a node → light up its connections, dim the rest).
 *
 * Zero external dependencies (only React). Pan (drag background),
 * zoom (wheel / buttons), drag nodes by header. Data-driven — edit NODES/EDGES.
 *
 *   import SmartHomeGraph from "./SmartHomeGraph";
 *   <div style={{position:"relative",width:"100%",height:"100vh"}}><SmartHomeGraph/></div>
 */

const HEADER = 32, PADY = 8, ROW = 24, NODE_W = 172;
const COLX = [40, 310, 580, 850, 1120, 1390, 1660, 1930, 2200];
const EB = 40, EVB = 560, SB = 830, CB = 1480, SCB = 1720;
const cx = (c) => COLX[c];
const cy = (b, s) => b + s * 128;

const KIND_COLOR = { trigger: "#2E9BE6", data: "#F2C230", cond: "#E8862E", action: "#D64545", device: "#7C5CFF", util: "#39424f" };
const LEGEND = [
  ["trigger", "Триггеры / события"], ["data", "Данные / API"], ["cond", "Условия / логика"],
  ["action", "Действия"], ["device", "Устройства"], ["util", "Утилиты / таймеры"],
];
const B = "#3A9BD6", P = "#8B6CFF", Y = "#E8B32E", R = "#e06868";

const RAW = [
  // ENERGY
  { id: "nordpool", k: "data", c: 0, b: EB, s: 0, t: "Nord Pool LV", gl: "⚡", out: [["price", "цена"]] },
  { id: "econet", k: "data", c: 0, b: EB, s: 2, t: "ecoNET24 котёл", gl: "🔥", out: [["o", "REST"]] },
  { id: "thr", k: "data", c: 1, b: EB, s: 1, t: "порог 0.04 €", out: [["v", ""]] },
  { id: "priceCond", k: "cond", c: 2, b: EB, s: 0, t: "Цена ≤ 0.04 €?", in: [["value", "value"], ["cmp", "compare"]], out: [["true", "ДА"], ["false", "НЕТ"]] },
  { id: "turboBath", k: "action", c: 2, b: EB, s: 2, t: "Турбо ванная", in: [["i", ""]], out: [["o", ""]] },
  { id: "turboShower", k: "action", c: 2, b: EB, s: 3, t: "Турбо душевая", in: [["i", ""]], out: [["o", ""]] },
  { id: "boilerOn", k: "action", c: 3, b: EB, s: 0, t: "Бойлер ВКЛ", in: [["t", ""]], out: [["o", ""]] },
  { id: "boilerOff", k: "action", c: 3, b: EB, s: 1, t: "Бойлер ВЫКЛ", in: [["t", ""]], out: [["o", ""]] },
  { id: "floorMan", k: "action", c: 3, b: EB, s: 2, t: "Пол manual/auto", in: [["t", ""]], out: [["o", ""]] },
  { id: "boilerDHW", k: "action", c: 3, b: EB, s: 3, t: "Котёл ГВС 40/55", in: [["i", ""]], out: [["o", ""]] },
  { id: "boiler", k: "device", c: 4, b: EB, s: 0, t: "Бойлер", gl: "♨️", in: [["i", ""]] },
  { id: "floor", k: "device", c: 4, b: EB, s: 2, t: "Тёплый пол ×2", gl: "🌡️", in: [["i", ""]] },
  // EV
  { id: "elering", k: "data", c: 0, b: EVB, s: 0, t: "Elering API", gl: "📈", out: [["p", "15-мин"]] },
  { id: "tuya", k: "data", c: 0, b: EVB, s: 1, t: "Tuya Cloud", gl: "☁️", out: [["o", "3.5"]] },
  { id: "evPlan", k: "cond", c: 1, b: EVB, s: 0, t: "EV планировщик", in: [["p", "цены"]], out: [["w", "окно 2ч"]] },
  { id: "evDT", k: "util", c: 2, b: EVB, s: 0, t: "ev_charge_start", gl: "🕒", in: [["i", ""]], out: [["o", ""]] },
  { id: "evTrig", k: "trigger", c: 3, b: EVB, s: 0, t: "Триггер: время", in: [["i", ""]], out: [["o", ""]] },
  { id: "evManual", k: "cond", c: 4, b: EVB, s: 0, t: "ev_manual_mode?", in: [["i", ""]], out: [["run", "авто"], ["skip", "пропуск"]] },
  { id: "evReset", k: "action", c: 4, b: EVB, s: 1, t: "EV сброс режима", in: [["i", ""]], out: [["o", ""]] },
  { id: "evCharge", k: "action", c: 5, b: EVB, s: 0, t: "EV зарядка 2ч", in: [["i", ""]], out: [["o", ""]] },
  { id: "interlock", k: "cond", c: 5, b: EVB, s: 1, t: "EV ↔ Бойлер", in: [["a", "EV"], ["b", "бойл"]], out: [["o", ""]] },
  { id: "evDev", k: "device", c: 6, b: EVB, s: 0, t: "EV зарядка", gl: "🚗", in: [["i", ""]] },
  // SAFETY
  { id: "moist", k: "trigger", c: 0, b: SB, s: 0, t: "Влага ×4", gl: "💦", out: [["w", "мокро"]] },
  { id: "grace", k: "data", c: 0, b: SB, s: 1, t: "Grace-период", gl: "🛡️", out: [["o", "блок"]] },
  { id: "smoke", k: "trigger", c: 0, b: SB, s: 2, t: "Дым", gl: "🔥", out: [["o", ""]] },
  { id: "door", k: "trigger", c: 0, b: SB, s: 3, t: "Дверь", gl: "🚪", out: [["o", ""]] },
  { id: "startupGrace", k: "trigger", c: 0, b: SB, s: 4, t: "HA старт", gl: "🔄", out: [["o", ""]] },
  { id: "leakWait", k: "util", c: 1, b: SB, s: 0, t: "Подтвердить 3мин", gl: "⏳", in: [["i", ""]], out: [["o", ""]] },
  { id: "tuyaGrace", k: "util", c: 1, b: SB, s: 1, t: "Tuya reconnect ×2", gl: "🔁", in: [["i", ""]], out: [["o", ""]] },
  { id: "armed", k: "cond", c: 1, b: SB, s: 3, t: "Охрана вкл?", in: [["i", ""]], out: [["o", "да"]] },
  { id: "graceCk", k: "cond", c: 2, b: SB, s: 0, t: "Grace активен?", in: [["i", ""], ["g", "grace"]], out: [["pass", "нет"], ["block", "да"]] },
  { id: "siren", k: "action", c: 2, b: SB, s: 2, t: "Сирена", in: [["i", ""]], out: [["o", ""]] },
  { id: "alarm", k: "action", c: 2, b: SB, s: 3, t: "Тревога охраны", in: [["i", ""]], out: [["o", ""]] },
  { id: "closeValve", k: "action", c: 3, b: SB, s: 0, t: "Закрыть кран", in: [["i", ""]], out: [["o", ""]] },
  { id: "leakAlert", k: "action", c: 3, b: SB, s: 1, t: "Тревога +кнопки", in: [["i", ""]], out: [["o", ""]] },
  { id: "valve", k: "device", c: 4, b: SB, s: 0, t: "Кран воды", gl: "🚰", in: [["i", ""]] },
  // CONTROL
  { id: "tgCmd", k: "trigger", c: 0, b: CB, s: 0, t: "Telegram команда", gl: "💬", out: [["o", ""]] },
  { id: "gemini", k: "data", c: 0, b: CB, s: 1, t: "Gemini AI", gl: "🤖", out: [["o", ""]] },
  { id: "menu", k: "util", c: 1, b: CB, s: 0, t: "Меню + inline", in: [["i", ""]], out: [["o", ""]] },
  { id: "socketNotif", k: "action", c: 1, b: CB, s: 1, t: "Уведомл. розеток", in: [["i", ""]], out: [["o", ""]] },
  { id: "btn", k: "cond", c: 2, b: CB, s: 0, t: "Обработчик кнопок", in: [["i", ""]], out: [["dev", "устр"], ["ev", "EV"], ["sec", "охрана"]] },
  { id: "actDev", k: "action", c: 3, b: CB, s: 0, t: "Вкл / Выкл", in: [["i", ""]], out: [["o", ""]] },
  { id: "plugs", k: "device", c: 4, b: CB, s: 0, t: "Розетки · свет", gl: "🔌", in: [["i", ""]] },
  // SCHEDULED + ALERTS
  { id: "t07", k: "trigger", c: 0, b: SCB, s: 0, t: "07:00", gl: "⏰", out: [["o", ""]] },
  { id: "t23", k: "trigger", c: 0, b: SCB, s: 1, t: "23:00", gl: "⏰", out: [["o", ""]] },
  { id: "t2330", k: "trigger", c: 0, b: SCB, s: 2, t: "23:30", gl: "🌙", out: [["o", ""]] },
  { id: "t0001", k: "trigger", c: 0, b: SCB, s: 3, t: "00:01", gl: "🕛", out: [["o", ""]] },
  { id: "t09", k: "trigger", c: 0, b: SCB, s: 4, t: "09:00", gl: "⏰", out: [["o", ""]] },
  { id: "t10", k: "trigger", c: 0, b: SCB, s: 5, t: "10:00", gl: "⏰", out: [["o", ""]] },
  { id: "t03", k: "trigger", c: 0, b: SCB, s: 6, t: "03:00", gl: "⏰", out: [["o", ""]] },
  { id: "t1519", k: "trigger", c: 0, b: SCB, s: 7, t: "11/15/19:00", gl: "⏰", out: [["o", ""]] },
  { id: "tDate", k: "trigger", c: 0, b: SCB, s: 8, t: "01.11.2026", gl: "📅", out: [["o", ""]] },
  { id: "brief", k: "action", c: 1, b: SCB, s: 0, t: "Утренний брифинг", in: [["i", ""]], out: [["o", ""]] },
  { id: "report", k: "action", c: 1, b: SCB, s: 1, t: "Отчёт потребления", in: [["i", ""]], out: [["o", ""]] },
  { id: "patrol", k: "action", c: 1, b: SCB, s: 2, t: "Ночной патруль", in: [["i", ""]], out: [["o", ""]] },
  { id: "snap", k: "action", c: 1, b: SCB, s: 3, t: "Снимок энергии", in: [["i", ""]], out: [["o", ""]] },
  { id: "battAlert", k: "action", c: 1, b: SCB, s: 4, t: "Батареи <30%", in: [["i", ""]], out: [["o", ""]] },
  { id: "haUpd", k: "action", c: 1, b: SCB, s: 5, t: "Проверка обновл.", in: [["i", ""]], out: [["o", ""]] },
  { id: "haInstall", k: "action", c: 1, b: SCB, s: 6, t: "Авто-установка", in: [["i", ""]], out: [["o", ""]] },
  { id: "selfDiag", k: "action", c: 1, b: SCB, s: 7, t: "Самодиагностика", in: [["i", ""]], out: [["o", ""]] },
  { id: "tailscale", k: "action", c: 1, b: SCB, s: 8, t: "Tailscale ключ", in: [["i", ""]], out: [["o", ""]] },
  { id: "priceFcst", k: "action", c: 1, b: SCB, s: 9, t: "Прогноз цен", in: [["i", ""]], out: [["o", ""]] },
  { id: "cheapSoon", k: "action", c: 1, b: SCB, s: 10, t: "Скоро дёшево", in: [["i", ""]], out: [["o", ""]] },
  { id: "boilerNotif", k: "action", c: 1, b: SCB, s: 11, t: "Котёл: уведомл.", in: [["i", ""]], out: [["o", ""]] },
  { id: "inums", k: "util", c: 2, b: SCB, s: 3, t: "input_number ×6", gl: "💾", in: [["i", ""]] },
  // CONVERGENCE
  { id: "tgOut", k: "device", x: 1660, y: 1120, t: "Telegram → Пользователь", gl: "📲", in: [["i", ""]] },
];
const NODES = RAW.map((n) => ({ ...n, x: n.x !== undefined ? n.x : cx(n.c), y: n.y !== undefined ? n.y : cy(n.b, n.s) }));

const EDGES = [
  ["nordpool:price", "priceCond:value", Y], ["thr:v", "priceCond:cmp", Y],
  ["priceCond:true", "boilerOn:t", B], ["priceCond:true", "floorMan:t", B], ["priceCond:false", "boilerOff:t", B],
  ["priceCond:true", "turboBath:i", B], ["priceCond:true", "turboShower:i", B],
  ["turboBath:o", "floor:i", R], ["turboShower:o", "floor:i", R],
  ["boilerOn:o", "boiler:i", R], ["boilerOff:o", "boiler:i", R], ["floorMan:o", "floor:i", R],
  ["boilerOn:o", "boilerDHW:i", P], ["boilerDHW:o", "boiler:i", R],
  ["econet:o", "boiler:i", P], ["econet:o", "floor:i", P], ["econet:o", "boilerNotif:i", P], ["boilerNotif:o", "tgOut:i", R],
  ["elering:p", "evPlan:p", Y], ["evPlan:w", "evDT:i", B], ["evDT:o", "evTrig:i", B], ["evTrig:o", "evManual:i", B],
  ["evManual:run", "evCharge:i", B], ["tuya:o", "evCharge:i", Y], ["evCharge:o", "evDev:i", R],
  ["evCharge:o", "interlock:a", P], ["boilerOn:o", "interlock:b", P], ["interlock:o", "evCharge:i", P], ["evReset:o", "evManual:i", P],
  ["moist:w", "leakWait:i", B], ["leakWait:o", "graceCk:i", B], ["grace:o", "graceCk:g", P],
  ["startupGrace:o", "grace:o", P], ["tuyaGrace:o", "grace:o", P],
  ["graceCk:pass", "closeValve:i", B], ["graceCk:pass", "leakAlert:i", B],
  ["closeValve:o", "valve:i", R], ["leakAlert:o", "tgOut:i", R],
  ["smoke:o", "siren:i", B], ["siren:o", "tgOut:i", R], ["door:o", "armed:i", B], ["armed:o", "alarm:i", B], ["alarm:o", "tgOut:i", R],
  ["tgCmd:o", "menu:i", B], ["gemini:o", "menu:i", Y], ["menu:o", "btn:i", B],
  ["btn:dev", "actDev:i", B], ["actDev:o", "plugs:i", R], ["btn:ev", "evCharge:i", P], ["btn:sec", "alarm:i", P],
  ["actDev:o", "socketNotif:i", B], ["socketNotif:o", "tgOut:i", R],
  ["t07:o", "brief:i", B], ["brief:o", "tgOut:i", R],
  ["t23:o", "report:i", B], ["report:o", "tgOut:i", R],
  ["t2330:o", "patrol:i", B], ["patrol:o", "tgOut:i", R],
  ["t0001:o", "snap:i", B], ["snap:o", "inums:i", R],
  ["t09:o", "battAlert:i", B], ["battAlert:o", "tgOut:i", R],
  ["t10:o", "haUpd:i", B], ["haUpd:o", "tgOut:i", R],
  ["t03:o", "haInstall:i", B], ["haInstall:o", "tgOut:i", R],
  ["t1519:o", "selfDiag:i", B], ["selfDiag:o", "tgOut:i", R],
  ["tDate:o", "tailscale:i", B], ["tailscale:o", "tgOut:i", R],
  ["nordpool:price", "priceFcst:i", Y], ["priceFcst:o", "tgOut:i", R],
  ["nordpool:price", "cheapSoon:i", Y], ["cheapSoon:o", "tgOut:i", R],
];

const nodeH = (n) => (n.k === "data" ? 34 : HEADER + PADY * 2 + Math.max((n.in || []).length, (n.out || []).length, 1) * ROW);

export default function SmartHomeGraph() {
  const vpRef = useRef(null);
  const widths = useRef({});
  const [nodes, setNodes] = useState(NODES);
  const [view, setView] = useState({ tx: 0, ty: 0, sc: 1 });
  const [focus, setFocus] = useState(null);

  const map = useMemo(() => Object.fromEntries(nodes.map((n) => [n.id, n])), [nodes]);
  const adj = useMemo(() => {
    const a = Object.fromEntries(NODES.map((n) => [n.id, new Set()]));
    EDGES.forEach(([f, t]) => { const x = f.split(":")[0], y = t.split(":")[0]; a[x].add(y); a[y].add(x); });
    return a;
  }, []);

  const port = useCallback((ref, side) => {
    const [id, pid] = ref.split(":");
    const n = map[id], w = widths.current[id] || NODE_W;
    if (n.k === "data") return { x: side === "out" ? n.x + w : n.x, y: n.y + 17 };
    const list = side === "out" ? n.out || [] : n.in || [];
    let i = list.findIndex((p) => p[0] === pid); if (i < 0) i = 0;
    return { x: side === "out" ? n.x + w : n.x, y: n.y + HEADER + PADY + i * ROW + ROW / 2 };
  }, [map]);

  const bounds = useMemo(() => {
    let mx = 0, my = 0;
    nodes.forEach((n) => { mx = Math.max(mx, n.x + (widths.current[n.id] || NODE_W)); my = Math.max(my, n.y + nodeH(n)); });
    return { mx, my };
  }, [nodes]);

  const fit = useCallback(() => {
    const vp = vpRef.current; if (!vp) return;
    const pad = 70, vw = vp.clientWidth, vh = vp.clientHeight;
    const sc = Math.max(0.12, Math.min((vw - pad * 2) / bounds.mx, (vh - pad * 2) / bounds.my, 1));
    setView({ sc, tx: (vw - bounds.mx * sc) / 2, ty: pad });
  }, [bounds]);

  useLayoutEffect(() => { fit(); /* eslint-disable-next-line */ }, []);

  const drag = useRef(null);
  const onPointerDown = (e) => {
    const h = e.target.closest("[data-handle]"), ne = e.target.closest("[data-node]");
    if (h && ne) { const n = map[ne.getAttribute("data-node")]; drag.current = { t: "node", id: n.id, sx: e.clientX, sy: e.clientY, ox: n.x, oy: n.y }; }
    else drag.current = { t: "pan", sx: e.clientX, sy: e.clientY, ox: view.tx, oy: view.ty };
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const onPointerMove = (e) => {
    const d = drag.current; if (!d) return;
    if (d.t === "node") setNodes((ns) => ns.map((n) => n.id === d.id ? { ...n, x: d.ox + (e.clientX - d.sx) / view.sc, y: d.oy + (e.clientY - d.sy) / view.sc } : n));
    else setView((v) => ({ ...v, tx: d.ox + (e.clientX - d.sx), ty: d.oy + (e.clientY - d.sy) }));
  };
  const onPointerUp = (e) => { drag.current = null; try { e.currentTarget.releasePointerCapture(e.pointerId); } catch {} };
  const onWheel = (e) => {
    e.preventDefault();
    const r = vpRef.current.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top, f = e.deltaY < 0 ? 1.12 : 1 / 1.12;
    setView((v) => { const ns = Math.min(2.2, Math.max(0.12, v.sc * f)); return { sc: ns, tx: mx - (mx - v.tx) * (ns / v.sc), ty: my - (my - v.ty) * (ns / v.sc) }; });
  };
  const zoom = (f) => setView((v) => ({ ...v, sc: Math.min(2.2, Math.max(0.12, v.sc * f)) }));

  const edgePath = (e) => {
    const a = port(e[0], "out"), b = port(e[1], "in"), dx = Math.max(45, Math.abs(b.x - a.x) * 0.45);
    return `M ${a.x} ${a.y} C ${a.x + dx} ${a.y}, ${b.x - dx} ${b.y}, ${b.x} ${b.y}`;
  };
  const edgeState = (f0, t0) => {
    if (!focus) return "";
    const on = f0.split(":")[0] === focus || t0.split(":")[0] === focus;
    return on ? "hl" : "dim";
  };

  return (
    <div ref={vpRef} className="shg-vp" style={S.vp} onPointerDown={onPointerDown} onPointerMove={onPointerMove}
         onPointerUp={onPointerUp} onWheel={onWheel}>
      <style>{CSS}</style>
      <div className="shg-world" style={{ ...S.world, transform: `translate(${view.tx}px,${view.ty}px) scale(${view.sc})` }}>
        <svg width={bounds.mx + 80} height={bounds.my + 80} style={S.wires}>
          {EDGES.map((e, i) => {
            const st = edgeState(e[0], e[1]), dpath = edgePath(e);
            return (
              <g key={i}>
                <path className={"base " + st} d={dpath} stroke={e[2]} fill="none" />
                <path className={"flow " + st} d={dpath} stroke={e[2]} fill="none" />
              </g>
            );
          })}
        </svg>

        {nodes.map((n) => {
          const dim = focus && n.id !== focus && !adj[focus].has(n.id);
          return (
            <div key={n.id} data-node={n.id}
                 className={"shg-node k-" + n.k + (dim ? " dim" : "") + (focus === n.id ? " focus" : "")}
                 ref={(el) => { if (el) widths.current[n.id] = el.offsetWidth; }}
                 style={{ left: n.x, top: n.y }}
                 onMouseEnter={() => setFocus(n.id)} onMouseLeave={() => setFocus(null)}>
              {n.k === "data" ? (
                <div className="shg-pill" data-handle>
                  {n.gl && <span className="gl">{n.gl}</span>}<span>{n.t}</span><span className="dpin">▸</span>
                </div>
              ) : (
                <>
                  <div className="shg-hd" data-handle>{n.gl && <span className="gl">{n.gl}</span>}<span>{n.t}</span></div>
                  <div className="shg-bd">
                    <div className="ins">{(n.in || []).map((p) => <div className="port" key={p[0]}><span className="pin">▸</span><span className="plabel">{p[1]}</span></div>)}</div>
                    <div className="outs">{(n.out || []).map((p) => <div className="port" key={p[0]}><span className="pin">▸</span><span className="plabel">{p[1]}</span></div>)}</div>
                  </div>
                </>
              )}
            </div>
          );
        })}
      </div>

      <div className="shg-tl">
        <div className="shg-title"><div className="t1">Home Assistant</div><div className="t2">SMART&nbsp;HOME</div><div className="t3">полный граф · 38 автоматизаций</div></div>
        <div className="shg-legend">
          {LEGEND.map(([k, l]) => <div className="lr" key={k}><span className="sq" style={{ background: KIND_COLOR[k] }} />{l}</div>)}
          <div className="hint">наведи на ноду — подсветит связи<br />тяни за шапку · фон = панорама · колесо = зум</div>
        </div>
      </div>
      <div className="shg-br">
        <button className="shg-btn" onClick={() => zoom(1 / 1.18)} title="Отдалить">−</button>
        <button className="shg-btn" onClick={() => zoom(1.18)} title="Приблизить">+</button>
        <button className="shg-btn" onClick={fit} title="Показать всё">⤢</button>
      </div>
    </div>
  );
}

const S = {
  vp: { position: "absolute", inset: 0, overflow: "hidden", touchAction: "none", cursor: "grab" },
  world: { position: "absolute", top: 0, left: 0, transformOrigin: "0 0" },
  wires: { position: "absolute", top: 0, left: 0, overflow: "visible", pointerEvents: "none" },
};

const CSS = `
.shg-vp{background:
  linear-gradient(#151b24 1px, transparent 1px) 0 0/26px 26px,
  linear-gradient(90deg,#151b24 1px, transparent 1px) 0 0/26px 26px,
  radial-gradient(1100px 700px at 70% 8%, rgba(124,92,255,.10), transparent 60%),
  radial-gradient(900px 600px at 12% 92%, rgba(46,155,230,.09), transparent 55%), #0C0F14;
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif; color:#E7ECF2; -webkit-font-smoothing:antialiased;}
.shg-vp svg path{fill:none;}
.shg-vp svg path.base{stroke-width:2.2; opacity:.22; transition:opacity .2s;}
.shg-vp svg path.flow{stroke-width:2.4; stroke-dasharray:4 10; opacity:.85; transition:opacity .2s,stroke-width .2s; animation:shg-dash 1.1s linear infinite;}
@keyframes shg-dash{to{stroke-dashoffset:-28;}}
@media (prefers-reduced-motion:reduce){.shg-vp svg path.flow{animation:none; stroke-dasharray:none; opacity:.55;}}
.shg-vp svg path.dim{opacity:.05 !important;}
.shg-vp svg path.hl{opacity:1 !important; stroke-width:3.4 !important;}
.shg-node{position:absolute; width:172px; background:#1B222D; border:1px solid #2c3543; border-radius:9px;
  box-shadow:0 10px 22px rgba(0,0,0,.45); font-size:12px; user-select:none; transition:opacity .2s,box-shadow .2s;}
.shg-node.dim{opacity:.2;}
.shg-node.focus{box-shadow:0 0 0 2px #7C5CFF,0 14px 30px rgba(0,0,0,.5);}
.shg-hd{height:32px; display:flex; align-items:center; gap:7px; padding:0 10px; border-radius:8px 8px 0 0;
  font-weight:600; color:#fff; cursor:grab; line-height:1.1;}
.shg-hd .gl{font-size:13px;}
.shg-bd{display:flex; justify-content:space-between; padding:8px 0;}
.shg-bd .ins,.shg-bd .outs{display:flex; flex-direction:column;}
.shg-bd .port{height:24px; display:flex; align-items:center; gap:6px; font-size:11px; color:#94A2B3;}
.shg-bd .outs .port{flex-direction:row-reverse;}
.shg-bd .pin{width:15px; height:15px; border-radius:4px; background:#2E9BE6; display:grid; place-items:center; flex:0 0 auto; color:#fff; font-size:9px; line-height:1;}
.shg-bd .ins .pin{margin-left:-8px;} .shg-bd .outs .pin{margin-right:-8px;}
.shg-bd .plabel{white-space:nowrap; max-width:112px; overflow:hidden; text-overflow:ellipsis;}
.shg-bd .outs .plabel{text-align:right;}
.k-trigger .shg-hd{background:linear-gradient(180deg,#3aa6ee,#2E9BE6);}
.k-cond .shg-hd{background:linear-gradient(180deg,#f0902f,#E8862E);}
.k-action .shg-hd{background:linear-gradient(180deg,#e05252,#D64545);}
.k-device .shg-hd{background:linear-gradient(180deg,#8a6bff,#7C5CFF);}
.k-util .shg-hd{background:linear-gradient(180deg,#46515f,#39424f);}
.k-cond .pin{background:#E8862E !important;} .k-action .pin{background:#D64545 !important;}
.k-device .ins .pin{background:#7C5CFF !important;} .k-util .pin{background:#39424f !important;}
.shg-node.k-data{width:auto; min-width:96px; border:none; border-radius:8px;
  background:linear-gradient(180deg,#f6cf4b,#F2C230); box-shadow:0 8px 18px rgba(242,194,48,.22);}
.shg-pill{display:flex; align-items:center; gap:8px; padding:8px 10px 8px 12px; color:#20170a; font-weight:700; font-size:12px; white-space:nowrap; cursor:grab;}
.shg-pill .gl{font-size:13px;}
.shg-pill .dpin{width:16px; height:16px; border-radius:4px; background:#20170a; color:#F2C230; display:grid; place-items:center; font-size:10px; margin-right:-9px; flex:0 0 auto;}
.shg-tl{position:absolute; top:16px; left:16px; z-index:20; display:flex; flex-direction:column; gap:10px; max-width:250px;}
.shg-title{font-family:ui-monospace,"Cascadia Code",Menlo,Consolas,monospace; pointer-events:none;}
.shg-title .t1{font-size:13px; letter-spacing:.32em; color:#E8862E; text-transform:uppercase;}
.shg-title .t2{font-size:28px; letter-spacing:.12em; color:transparent; -webkit-text-stroke:1.4px #6f7cff; font-weight:700; margin-top:2px;}
.shg-title .t3{font-size:12px; letter-spacing:.18em; color:#94A2B3; margin-top:6px;}
.shg-legend{background:rgba(18,23,31,.8); border:1px solid #2c3543; border-radius:11px; padding:12px 14px; backdrop-filter:blur(8px); font-size:11.5px; color:#94A2B3;}
.shg-legend .lr{display:flex; align-items:center; gap:8px; margin:5px 0;}
.shg-legend .sq{width:12px; height:12px; border-radius:3px; flex:0 0 auto;}
.shg-legend .hint{margin-top:9px; padding-top:9px; border-top:1px solid #2c3543; font-family:ui-monospace,Menlo,Consolas,monospace; font-size:10.5px; color:#5f6b7a; line-height:1.6;}
.shg-br{position:absolute; bottom:16px; right:16px; z-index:20; display:flex; gap:6px;}
.shg-btn{width:38px; height:38px; border-radius:9px; background:rgba(27,34,45,.8); color:#E7ECF2; border:1px solid #2c3543; font-size:17px; cursor:pointer; backdrop-filter:blur(6px); display:grid; place-items:center;}
.shg-btn:hover{border-color:#7C5CFF;}
.shg-btn:focus-visible{outline:2px solid #2E9BE6; outline-offset:2px;}
`;
