// energy.jsx — Экран «Энергия»
(function () {
  const { useState } = React;
  const { Card, Seg, Icon, tierColor, tierOf } = window;

  function Chart({ data, nowHour }) {
    const max = Math.max(...data, 1);
    return (
      <div>
        <div style={{ position: 'relative', height: 158, display: 'flex', alignItems: 'flex-end', gap: 2 }}>
          {/* grid */}
          {[0.25, 0.5, 0.75].map(g => (
            <div key={g} style={{ position: 'absolute', left: 0, right: 0, bottom: `${g * 100}%`, height: 1, background: 'var(--line)' }} />
          ))}
          {data.map((c, h) => (
            <div key={h} style={{ flex: 1, height: `${Math.max(4, (c / max) * 100)}%`, position: 'relative', borderRadius: '3px 3px 0 0',
              background: tierColor(c), opacity: h === nowHour ? 1 : 0.46,
              outline: h === nowHour ? '1.5px solid var(--text)' : 'none', outlineOffset: -1,
              transition: 'height .5s var(--ease), opacity .3s' }}>
              {h === nowHour && <span style={{ position: 'absolute', top: -17, left: '50%', transform: 'translateX(-50%)', fontSize: 9, fontWeight: 800, color: 'var(--text)' }} className="mono">{c.toFixed(1)}</span>}
            </div>
          ))}
        </div>
        <div className="spark-axis" style={{ marginTop: 6 }}>
          <span>00</span><span>06</span><span>12</span><span>18</span><span>23</span>
        </div>
      </div>
    );
  }

  function EnergyScreen({ data }) {
    const [period, setPeriod] = useState('1д');
    const p = data.price;
    const items = data.cost.items;
    const maxCost = Math.max(...items.map(i => i.cost), 0.01);
    return (
      <div className="screen stagger">
        <Card system="price" icon="activity" title="Nord Pool" sub="Цена за сегодня · ¢/кВт·ч">
          <Chart data={p.arr} nowHour={p.nowHour} />
          <div style={{ display: 'flex', gap: 10, marginTop: 12 }}>
            <div className="cell" style={{ flex: 1, textAlign: 'left', padding: '10px 12px' }}>
              <div className="l" style={{ marginBottom: 3 }}>Минимум</div>
              <div className="v mono" style={{ color: 'var(--ev)' }}>{p.min.toFixed(1)}¢ <span style={{ fontSize: 11, color: 'var(--text-2)' }}>в {String(p.minH).padStart(2, '0')}:00</span></div>
            </div>
            <div className="cell" style={{ flex: 1, textAlign: 'left', padding: '10px 12px' }}>
              <div className="l" style={{ marginBottom: 3 }}>Максимум</div>
              <div className="v mono" style={{ color: 'var(--sec)' }}>{p.max.toFixed(1)}¢ <span style={{ fontSize: 11, color: 'var(--text-2)' }}>в {String(p.maxH).padStart(2, '0')}:00</span></div>
            </div>
          </div>
        </Card>

        <Card icon="dollar" title="Потребление" sub={`Итого ${data.cost.total.toFixed(2)} € · ${data.cost.kwh.toFixed(1)} кВт·ч`}
          right={<span className="badge dim mono">{period}</span>}>
          <div style={{ marginTop: 2 }}>
            {items.map(i => (
              <div key={i.key} className="crow">
                <span className="cic" style={{ color: `var(--${i.system})` }}><Icon name={i.icon} size={18} /></span>
                <div>
                  <div className="cname">{i.name}</div>
                  <div className="bar" style={{ marginTop: 5, height: 4 }}><i style={{ width: `${(i.cost / maxCost) * 100}%`, background: `var(--${i.system})` }} /></div>
                </div>
                <span className="ckwh mono">{i.kwh.toFixed(1)} кВт·ч</span>
                <span className="ccost mono">{i.cost.toFixed(2)}€</span>
              </div>
            ))}
          </div>
          <div className="sep" />
          <Seg value={period} options={['1д', '3д', '7д', '30д'].map(v => ({ v, t: v }))} onChange={setPeriod} accent color="var(--price)" />
        </Card>
      </div>
    );
  }

  window.EnergyScreen = EnergyScreen;
})();
