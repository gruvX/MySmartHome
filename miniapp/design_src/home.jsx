// home.jsx — Главный экран: 3 направления раскладки
(function () {
  const { Card, Tile, Spark, PriceClock, Ring, Icon, tierOf } = window;

  function PriceBadge({ c }) {
    const t = tierOf(c);
    return <span className={'badge ' + t.key}>{t.label}</span>;
  }

  // мини-разбивка расхода (горизонтальные бары)
  function CostBars({ items }) {
    const max = Math.max(...items.map(i => i.cost), 0.01);
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 9, marginTop: 13 }}>
        {items.map(i => (
          <div key={i.key} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ color: `var(--${i.system})`, display: 'grid', placeItems: 'center', width: 18 }}><Icon name={i.icon} size={16} /></span>
            <span style={{ width: 66, fontSize: 12, fontWeight: 600 }}>{i.name}</span>
            <div className="bar" style={{ flex: 1 }}><i style={{ width: `${(i.cost / max) * 100}%`, background: `var(--${i.system})` }} /></div>
            <span className="mono" style={{ fontSize: 12.5, fontWeight: 800, width: 44, textAlign: 'right' }}>{i.cost.toFixed(2)}€</span>
          </div>
        ))}
      </div>
    );
  }

  function StatusChip({ system, icon, label, value, dot, onClick }) {
    return (
      <div className="tile tint" style={{ '--c': `var(--${system})`, minHeight: 0, padding: 11, cursor: 'pointer' }} onClick={onClick}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color: `var(--${system})` }}><Icon name={icon} size={17} /></span>
          <span style={{ fontSize: 10.5, fontWeight: 800, letterSpacing: '.4px', color: 'var(--text-3)', textTransform: 'uppercase' }}>{label}</span>
          {dot && <span className={'dot ' + dot} style={{ marginLeft: 'auto' }} />}
        </div>
        <div className="mono" style={{ fontSize: 14, fontWeight: 800, marginTop: 7 }}>{value}</div>
      </div>
    );
  }

  function Scenes({ actions }) {
    const list = [
      { k: 'night', t: 'Ночь', icon: 'moon' },
      { k: 'away', t: 'Ушли', icon: 'walk' },
      { k: 'eco', t: 'Экономия', icon: 'leaf' },
    ];
    return (
      <div className="scenes">
        {list.map(s => (
          <button key={s.k} className="scene" onClick={() => actions.scene(s.k)}>
            <span className="si"><Icon name={s.icon} size={22} /></span>{s.t}
          </button>
        ))}
      </div>
    );
  }

  // ════════════════ Direction A — Лента ════════════════
  function DirA({ data, actions, go }) {
    const p = data.price, t = tierOf(p.now);
    return (
      <div className="stagger">
        <Card system="price" icon="bolt" title="Электричество" sub="Nord Pool · Латвия"
          right={<PriceBadge c={p.now} />}>
          <div className="readout" style={{ marginTop: 4 }}>
            <span className="num mono" style={{ color: 'var(--price)' }}>{p.now.toFixed(1)}</span>
            <span className="unit">¢/кВт·ч</span>
          </div>
          <div style={{ margin: '13px 0 2px' }}><Spark data={p.arr} nowHour={p.nowHour} onClick={() => go(2)} /></div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 11, padding: '9px 11px', background: 'var(--surface-2)', borderRadius: 12 }}>
            <span style={{ color: 'var(--ev)' }}><Icon name="leaf" size={16} /></span>
            <span style={{ fontSize: 12.5, fontWeight: 600 }}>Дешёвое окно: <b className="mono">{p.cheapWindow}</b></span>
            <span className="mono" style={{ marginLeft: 'auto', fontWeight: 800, color: 'var(--text-2)' }}>след {p.next.toFixed(1)}¢</span>
          </div>
        </Card>

        <Card>
          <div className="card-row">
            <div>
              <div className="eyebrow">Расход сегодня</div>
              <div className="readout" style={{ marginTop: 6 }}>
                <span className="num mono">{data.cost.total.toFixed(2)}</span>
                <span className="unit">€</span>
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div className="mono" style={{ fontSize: 18, fontWeight: 800 }}>{data.cost.kwh.toFixed(1)}</div>
              <div className="t-sub">кВт·ч</div>
            </div>
          </div>
          <CostBars items={data.cost.items.slice(0, 4)} />
        </Card>

        <div className="bento" style={{ gridTemplateColumns: '1fr 1fr' }}>
          <StatusChip system="sec" icon={data.security.armed ? 'lock' : 'unlock'} label="Охрана"
            value={data.security.armed ? 'На охране' : 'Снята'} dot={data.security.alerts.length ? 'err' : 'ok'} onClick={() => go(3)} />
          <StatusChip system="ev" icon="car" label="Зарядка" value={data.ev.short} onClick={() => go(1)} />
          <StatusChip system="boil" icon="flame" label="Котёл" value={`${data.boiler.co}° / ${data.boiler.cwu}°`} onClick={() => go(1)} />
          <StatusChip system="water" icon="valve" label="Кран" value={data.water.open ? 'Открыт' : 'Закрыт'} onClick={() => actions.closeValve()} />
        </div>

        <div className="sec-lbl">Быстрые сцены</div>
        <Scenes actions={actions} />
      </div>
    );
  }

  // ════════════════ Direction B — Приборная панель ════════════════
  function DirB({ data, actions, go }) {
    const p = data.price, t = tierOf(p.now);
    return (
      <div>
        <div className="bento stagger">
          {/* price wide */}
          <Tile system="price" icon="bolt" tag="Nord Pool" span2 onClick={() => go(2)}>
            <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginTop: 10 }}>
              <div>
                <div className="readout"><span className="num mono" style={{ color: 'var(--price)', fontSize: 40 }}>{p.now.toFixed(1)}</span><span className="unit">¢</span></div>
                <div style={{ marginTop: 8 }}><PriceBadge c={p.now} /></div>
              </div>
              <div style={{ width: 130 }}><Spark data={p.arr} nowHour={p.nowHour} height={42} /></div>
            </div>
          </Tile>

          {/* cost */}
          <Tile system="ev" icon="dollar" tag="Сегодня" onClick={() => go(2)}>
            <div className="tile-val mono" style={{ fontSize: 26 }}>{data.cost.total.toFixed(2)}€</div>
            <div className="tile-sub">{data.cost.kwh.toFixed(1)} кВт·ч</div>
          </Tile>

          {/* EV ring */}
          <Tile system="ev" icon="car" tag="EV" onClick={() => go(1)}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 10 }}>
              <Ring size={54} value={data.ev.pct} color="var(--ev)" thickness={6}>
                <span className="mono" style={{ fontSize: 13, fontWeight: 800 }}>{Math.round(data.ev.pct * 100)}</span>
              </Ring>
              <div>
                <div className="mono" style={{ fontWeight: 800, fontSize: 15 }}>{data.ev.kwh.toFixed(1)}</div>
                <div className="tile-sub">кВт·ч · {data.ev.short}</div>
              </div>
            </div>
          </Tile>

          {/* boiler */}
          <Tile system="boil" icon="flame" tag="Котёл" onClick={() => go(1)}>
            <div style={{ display: 'flex', gap: 14, marginTop: 12 }}>
              <div><div className="mono" style={{ fontWeight: 800, fontSize: 18, color: 'var(--boil)' }}>{data.boiler.co}°</div><div className="tile-sub">CO</div></div>
              <div><div className="mono" style={{ fontWeight: 800, fontSize: 18, color: 'var(--boil)' }}>{data.boiler.cwu}°</div><div className="tile-sub">ГВС</div></div>
            </div>
          </Tile>

          {/* security */}
          <Tile system="sec" icon={data.security.armed ? 'lock' : 'shield'} tag="Охрана" onClick={() => go(3)}>
            <div className="tile-val" style={{ fontSize: 16 }}>{data.security.armed ? 'На охране' : 'Снята'}</div>
            <div className="tile-sub" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span className={'dot ' + (data.security.alerts.length ? 'err' : 'ok')} />{data.security.alerts.length ? `${data.security.alerts.length} тревоги` : 'Всё ОК'}
            </div>
          </Tile>

          {/* floor */}
          <Tile system="floor" icon="thermo" tag="Пол" onClick={() => go(1)}>
            <div className="tile-val mono" style={{ fontSize: 18, color: 'var(--floor)' }}>{data.floor[0].temp}°</div>
            <div className="tile-sub">{data.floor[0].name} · авто</div>
          </Tile>
        </div>

        <div className="sec-lbl">Быстрые сцены</div>
        <Scenes actions={actions} />
      </div>
    );
  }

  // ════════════════ Direction C — Фокус ════════════════
  function DirC({ data, actions, go }) {
    const p = data.price, t = tierOf(p.now);
    return (
      <div className="stagger">
        <div className="card" style={{ '--c': 'var(--price)', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '20px 16px 18px' }}>
          <div className="eyebrow" style={{ marginBottom: 12 }}>Цена · 24 часа</div>
          <div style={{ position: 'relative', display: 'grid', placeItems: 'center' }}>
            <PriceClock data={p.arr} nowHour={p.nowHour} size={232} />
            <div style={{ position: 'absolute', textAlign: 'center' }}>
              <div className="mono" style={{ fontSize: 44, fontWeight: 800, letterSpacing: '-2px', color: 'var(--price)', lineHeight: .9 }}>{p.now.toFixed(1)}</div>
              <div className="t-sub" style={{ fontWeight: 700 }}>¢/кВт·ч</div>
              <div style={{ marginTop: 8 }}><PriceBadge c={p.now} /></div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 16, marginTop: 14, fontSize: 11, fontWeight: 700, color: 'var(--text-2)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}><i style={{ width: 9, height: 9, borderRadius: 3, background: 'var(--ev)' }} />дёшево</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}><i style={{ width: 9, height: 9, borderRadius: 3, background: 'var(--plug)' }} />средне</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}><i style={{ width: 9, height: 9, borderRadius: 3, background: 'var(--sec)' }} />дорого</span>
          </div>
          <div style={{ marginTop: 14, padding: '10px 14px', background: 'var(--surface-2)', borderRadius: 12, fontSize: 12.5, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: 'var(--ev)' }}><Icon name="leaf" size={16} /></span>Дешёвое окно <b className="mono">{p.cheapWindow}</b>
          </div>
        </div>

        <div className="card card-row">
          <div>
            <div className="eyebrow">Расход сегодня</div>
            <div className="readout" style={{ marginTop: 5 }}><span className="num mono" style={{ fontSize: 32 }}>{data.cost.total.toFixed(2)}</span><span className="unit">€</span></div>
          </div>
          <button className="icon-btn" style={{ width: 44, height: 44 }} onClick={() => go(2)}><Icon name="arrowUR" size={20} /></button>
        </div>

        <div className="sec-lbl">Быстрые сцены</div>
        <Scenes actions={actions} />
      </div>
    );
  }

  function HomeScreen({ data, actions, go, layout, setLayout }) {
    const opts = [{ v: 'A', t: 'Лента' }, { v: 'B', t: 'Панель' }, { v: 'C', t: 'Фокус' }];
    const { Seg } = window;
    return (
      <div className="screen">
        <div style={{ margin: '2px 0 14px' }}>
          <Seg value={layout} options={opts} onChange={setLayout} />
        </div>
        {layout === 'A' && <DirA data={data} actions={actions} go={go} />}
        {layout === 'B' && <DirB data={data} actions={actions} go={go} />}
        {layout === 'C' && <DirC data={data} actions={actions} go={go} />}
      </div>
    );
  }

  window.HomeScreen = HomeScreen;
})();
