// control.jsx — Экран управления (котёл / EV / пол / свет / розетки)
(function () {
  const { Card, Seg, Stepper, Pill, Icon, Ring } = window;

  function ModeBadge({ mode }) {
    const map = {
      work:  { t: 'Работа',  c: 'var(--ev)' },
      watch: { t: 'Надзор',  c: 'var(--plug)' },
      off:   { t: 'Выключен',c: 'var(--text-2)' },
      alarm: { t: 'Авария',  c: 'var(--sec)' },
    };
    const m = map[mode] || map.off;
    return <span className="badge" style={{ background: `color-mix(in oklab, ${m.c} 20%, transparent)`, color: m.c }}>
      <span className="dot" style={{ background: m.c, width: 6, height: 6 }} />{m.t}</span>;
  }

  function ControlScreen({ data, actions }) {
    const b = data.boiler, ev = data.ev;
    return (
      <div className="screen stagger">

        {/* ───── Котёл ───── */}
        <Card system="boil" icon="flame" title="Котёл ecoNET24" sub={`CO ${b.co}°→${b.coSet}° · ГВС ${b.cwu}°→${b.cwuSet}°`}
          right={<ModeBadge mode={b.mode} />}>
          <div className="cells c3" style={{ marginTop: 2 }}>
            <div className="cell"><div className="v mono" style={{ color: 'var(--boil)' }}>{b.co}°</div><div className="l">CO темп</div></div>
            <div className="cell"><div className="v mono">{b.coSet}°</div><div className="l">CO задано</div></div>
            <div className="cell"><div className="v mono">{b.ret}°</div><div className="l">Обратка</div></div>
            <div className="cell"><div className="v mono" style={{ color: 'var(--boil)' }}>{b.cwu}°</div><div className="l">ГВС темп</div></div>
            <div className="cell"><div className="v mono">{b.cwuSet}°</div><div className="l">ГВС задано</div></div>
            <div className="cell"><div className="v mono">{b.fan}%</div><div className="l">Вентилятор</div></div>
          </div>

          <div className="leds" style={{ marginTop: 11 }}>
            <span className={'led' + (b.pumpCo ? ' on' : '')}><i />CO насос</span>
            <span className={'led' + (b.pumpCwu ? ' on' : '')}><i />ГВС насос</span>
            <span className={'led' + (b.pumpCirc ? ' on' : '')}><i />Циркуляция</span>
          </div>

          <div className="sep" />

          <Seg value={b.power ? 'on' : 'off'} accent color="var(--boil)"
            options={[{ v: 'on', t: 'Включён', icon: 'power' }, { v: 'off', t: 'Выключен' }]}
            onChange={(v) => actions.boilerPower(v === 'on')} />

          <div className="sec-lbl" style={{ marginLeft: 0 }}>ГВС уставка</div>
          <div className="presets" style={{ '--c': 'var(--boil)' }}>
            {[40, 45, 50, 55, 60].map(t => (
              <button key={t} className={'preset' + (b.cwuSet === t ? ' cur' : '')} onClick={() => actions.setCwu(t)}>{t}°</button>
            ))}
          </div>

          <div className="sec-lbl" style={{ marginLeft: 0 }}>CO уставка</div>
          <div className="presets" style={{ '--c': 'var(--boil)' }}>
            {[50, 60, 68, 75].map(t => (
              <button key={t} className={'preset' + (b.coSet === t ? ' cur' : '')} onClick={() => actions.setCo(t)}>{t}°</button>
            ))}
          </div>
        </Card>

        {/* ───── EV ───── */}
        <Card system="ev" icon="car" title="EV зарядка" sub={ev.sub}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <Ring size={84} value={ev.pct} color="var(--ev)" thickness={8}>
              <div style={{ textAlign: 'center' }}>
                <div className="mono" style={{ fontSize: 18, fontWeight: 800 }}>{Math.round(ev.pct * 100)}<span style={{ fontSize: 11 }}>%</span></div>
              </div>
            </Ring>
            <div style={{ flex: 1 }}>
              <div className="cells c2">
                <div className="cell"><div className="v mono" style={{ color: 'var(--ev)' }}>{ev.kwh.toFixed(1)}</div><div className="l">кВт·ч сессия</div></div>
                <div className="cell"><div className="v mono">{ev.sched}</div><div className="l">старт по плану</div></div>
              </div>
            </div>
          </div>
          <div className="sep" />
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="pill" style={{ '--c': 'var(--ev)', flex: 1, justifyContent: 'center' }} onClick={actions.evStart}>
              <span className="pi" style={{ color: 'var(--ev)' }}><Icon name="play" size={16} /></span>Зарядить</button>
            <button className="pill" style={{ flex: 1, justifyContent: 'center' }} onClick={actions.evStop}>
              <span className="pi"><Icon name="stop" size={16} /></span>Стоп</button>
          </div>
          <div style={{ marginTop: 8 }}>
            <Pill on={ev.manual} color="var(--ev)" icon="sliders" knob onClick={actions.evManual}>Ручной режим</Pill>
          </div>
        </Card>

        {/* ───── Тёплый пол ───── */}
        <Card system="floor" icon="thermo" title="Тёплый пол" sub={data.floor.map(f => `${f.name} ${f.temp}°`).join(' · ')}>
          {data.floor.map((f, i) => (
            <div key={i} style={{ marginBottom: i === 0 ? 12 : 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <span className="t-name">{f.name}</span>
                <span className="mono" style={{ fontWeight: 800, fontSize: 17, color: 'var(--floor)' }}>{f.temp}°</span>
              </div>
              <Seg value={f.mode} color="var(--floor)" accent
                options={[{ v: 'auto', t: 'Авто', icon: 'refresh' }, { v: 'manual', t: 'Ручной 30°', icon: 'flame' }]}
                onChange={(v) => actions.setFloor(i, v)} />
            </div>
          ))}
        </Card>

        {/* ───── Освещение ───── */}
        <Card system="light" icon="bulb" title="Освещение" sub={`${data.lights.filter(l => l.on).length} включено`}>
          <div className="bento" style={{ gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            {data.lights.map(l => (
              <Pill key={l.id} on={l.on} color="var(--light)" icon={l.icon} onClick={() => actions.toggleLight(l.id)}>{l.name}</Pill>
            ))}
          </div>
          <button className="scene" style={{ width: '100%', flexDirection: 'row', gap: 9, marginTop: 10 }} onClick={actions.allLightsOff}>
            <span style={{ color: 'var(--text-2)' }}><Icon name="moon" size={18} /></span>Выключить весь свет
          </button>
        </Card>

        {/* ───── Розетки ───── */}
        <Card system="plug" icon="plug" title="Розетки" sub="Аквариум · Рециркуляция · Гидрофор · Полотенцесушитель">
          <div className="bento" style={{ gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            {data.plugs.map(p => (
              <Pill key={p.id} on={p.on} color="var(--plug)" icon={p.icon} onClick={() => actions.togglePlug(p.id)}>{p.name}</Pill>
            ))}
          </div>
        </Card>

      </div>
    );
  }

  window.ControlScreen = ControlScreen;
})();
