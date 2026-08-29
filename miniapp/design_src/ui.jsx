// ui.jsx — общие компоненты приборной панели
(function () {
  const { useState } = React;

  // ── price tier ──────────────────────────────────────────
  function tierOf(c) {
    if (c < 8) return { key: 'cheap', label: 'ДЁШЕВО', v: 'var(--ev)' };
    if (c < 16) return { key: 'mid', label: 'СРЕДНЕ', v: 'var(--plug)' };
    return { key: 'high', label: 'ДОРОГО', v: 'var(--sec)' };
  }
  const tierColor = (c) => c < 8 ? '#5fe0a6' : c < 16 ? '#ffd84d' : '#ff5d57';

  // ── Ring gauge ──────────────────────────────────────────
  function Ring({ size = 92, value = 0, color = 'var(--accent)', thickness = 8, track, children, cap = true }) {
    const r = (size - thickness) / 2;
    const c = 2 * Math.PI * r;
    const off = c * (1 - Math.max(0, Math.min(1, value)));
    return (
      <div className="ring-wrap" style={{ width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={track || 'var(--surface-3)'} strokeWidth={thickness} />
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={thickness}
          strokeDasharray={c} strokeDashoffset={off} strokeLinecap={cap ? 'round' : 'butt'}
          style={{ transition: 'stroke-dashoffset .7s cubic-bezier(.4,0,.2,1)' }} />
        </svg>
        {children && <div className="ring-center">{children}</div>}
      </div>);

  }

  // ── 24h sparkline ───────────────────────────────────────
  function Spark({ data, nowHour, height = 46, onClick }) {
    const max = Math.max(...data, 1);
    return (
      <div onClick={onClick} style={{ cursor: onClick ? 'pointer' : 'default' }}>
        <div className="spark" style={{ height }}>
          {data.map((c, h) =>
          <div key={h} className={'b' + (h === nowHour ? ' now' : '')}
          style={{ height: `${Math.max(8, c / max * 100)}%`, background: tierColor(c) }} />
          )}
        </div>
        <div className="spark-axis"><span>00</span><span>06</span><span>12</span><span>18</span><span>23</span></div>
      </div>);

  }

  // ── radial 24h price clock (direction C) ────────────────
  function PriceClock({ data, nowHour, size = 230 }) {
    const cx = size / 2,cy = size / 2;
    const rOut = size / 2 - 6,rIn = size / 2 - 26;
    const max = Math.max(...data, 1);
    const seg = [];
    for (let h = 0; h < 24; h++) {
      const a0 = h / 24 * 2 * Math.PI - Math.PI / 2 + 0.012;
      const a1 = (h + 1) / 24 * 2 * Math.PI - Math.PI / 2 - 0.012;
      const lvl = 0.45 + 0.55 * (data[h] / max);
      const ri = rIn,ro = rIn + (rOut - rIn) * lvl;
      const p = (a, r) => [cx + Math.cos(a) * r, cy + Math.sin(a) * r];
      const [x0, y0] = p(a0, ri),[x1, y1] = p(a1, ri);
      const [x2, y2] = p(a1, ro),[x3, y3] = p(a0, ro);
      seg.push(
        <path key={h}
        d={`M${x0} ${y0} A${ri} ${ri} 0 0 1 ${x1} ${y1} L${x2} ${y2} A${ro} ${ro} 0 0 0 ${x3} ${y3} Z`}
        fill={tierColor(data[h])} opacity={h === nowHour ? 1 : 0.42}
        style={{ transition: 'opacity .4s' }} />
      );
    }
    // hand
    const ha = nowHour / 24 * 2 * Math.PI - Math.PI / 2;
    const hx = cx + Math.cos(ha) * (rOut - 1),hy = cy + Math.sin(ha) * (rOut - 1);
    return (
      <svg width={size} height={size}>
        {seg}
        <line x1={cx} y1={cy} x2={hx} y2={hy} stroke="var(--text)" strokeWidth="2.5" strokeLinecap="round" />
        <circle cx={cx} cy={cy} r="4" fill="var(--text)" />
      </svg>);

  }

  // ── Switch ───────────────────────────────────────────────
  function Switch({ on, onChange, color = 'var(--accent)' }) {
    return <div className={'sw' + (on ? ' on' : '')} style={{ '--c': color }}
    onClick={(e) => {e.stopPropagation();onChange(!on);}} />;
  }

  // ── Pill toggle (icon + label, glows when on) ────────────
  // knob: показывать тумблер (для широких строк). В сетках knob не нужен —
  // состояние читается по подсветке, иконке и маленькому индикатору.
  function Pill({ on, onClick, color, icon, children, knob }) {
    const { Icon } = window;
    return (
      <button className={'pill' + (on ? ' on' : '')} style={{ '--c': color }} onClick={onClick}>
        {icon && <span className="pi"><Icon name={icon} size={18} /></span>}
        <span className="pill-lbl">{children}</span>
        {knob
          ? <Switch on={on} onChange={() => onClick()} color={color} />
          : <span className={'pill-led' + (on ? ' on' : '')} />}
      </button>);

  }

  // ── Segmented ────────────────────────────────────────────
  function Seg({ value, options, onChange, accent, color = 'var(--accent)' }) {
    return (
      <div className={'seg' + (accent ? ' accent' : '')} style={{ '--c': color }}>
        {options.map((o) =>
        <button key={o.v} className={value === o.v ? 'on' : ''} onClick={() => onChange(o.v)}>
            {o.icon && window.Icon && <window.Icon name={o.icon} size={15} />}{o.t}
          </button>
        )}
      </div>);

  }

  // ── Stepper ──────────────────────────────────────────────
  function Stepper({ value, unit = '°', step = 1, min = 0, max = 99, onChange, color = 'var(--accent)' }) {
    const { Icon } = window;
    return (
      <div className="stepper">
        <button className="step-btn" onClick={() => onChange(Math.max(min, value - step))}><Icon name="minus" size={20} /></button>
        <div className="step-val mono" style={{ color }}>{value}<span style={{ fontSize: 15, color: 'var(--text-2)' }}>{unit}</span></div>
        <button className="step-btn" onClick={() => onChange(Math.min(max, value + step))}><Icon name="plus" size={20} /></button>
      </div>);

  }

  // ── Card ─────────────────────────────────────────────────
  function Card({ system, icon, title, sub, right, children, onClick, style }) {
    const { Icon } = window;
    const sysVar = system ? `var(--${system})` : undefined;
    return (
      <div className={'card' + (system ? ' tint' : '')} style={{ '--c': sysVar, marginBottom: 12, ...style }} onClick={onClick}>
        {(title || icon) &&
        <div className="card-hd">
            {icon && <div className="ic"><Icon name={icon} size={18} /></div>}
            <div style={{ flex: 1 }}>
              <div className="tt">{title}</div>
              {sub && <div className="ss">{sub}</div>}
            </div>
            {right}
          </div>
        }
        {children}
      </div>);

  }

  // ── Bento tile ───────────────────────────────────────────
  function Tile({ system, icon, tag, value, sub, onClick, children, span2, valueColor }) {
    const { Icon } = window;
    const sysVar = system ? `var(--${system})` : undefined;
    return (
      <div className={'tile tint' + (span2 ? ' span2' : '')} style={{ '--c': sysVar }} onClick={onClick}>
        <div className="tile-hd">
          <div className="tile-ic"><Icon name={icon} size={18} /></div>
          {tag && <span className="tile-tag">{tag}</span>}
        </div>
        {children || <>
          <div className="tile-val mono" style={{ color: valueColor }}>{value}</div>
          {sub && <div className="tile-sub">{sub}</div>}
        </>}
      </div>);

  }

  Object.assign(window, { tierOf, tierColor, Ring, Spark, PriceClock, Switch, Pill, Seg, Stepper, Card, Tile });
})();