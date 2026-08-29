// status.jsx — Экран «Статус» (охрана, датчики, батареи)
(function () {
  const { Card, Seg, Icon } = window;

  function SensorRow({ icon, name, ok, value, alert }) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '11px 0', borderBottom: '1px solid var(--line)' }}>
        <span className={'dot ' + (ok ? 'ok' : 'err')} />
        <span style={{ color: 'var(--text-2)', display: 'grid', placeItems: 'center' }}><Icon name={icon} size={18} /></span>
        <span style={{ flex: 1, fontSize: 13.5, fontWeight: 600 }}>{name}</span>
        <span className="mono" style={{ fontWeight: 800, fontSize: 13, color: ok ? 'var(--text-2)' : 'var(--err)' }}>{value}</span>
      </div>
    );
  }

  function BatItem({ name, pct }) {
    const col = pct <= 15 ? 'var(--err)' : pct <= 30 ? 'var(--warn)' : 'var(--ok)';
    return (
      <div className="cell" style={{ textAlign: 'left', padding: '10px 12px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 7 }}>
          <span style={{ fontSize: 11.5, color: 'var(--text-2)', fontWeight: 600 }}>{name}</span>
          <span className="mono" style={{ fontSize: 12, fontWeight: 800, color: col }}>{pct}%</span>
        </div>
        <div className="bar" style={{ height: 5 }}><i style={{ width: pct + '%', background: col }} /></div>
      </div>
    );
  }

  function StatusScreen({ data, actions }) {
    const s = data.security;
    return (
      <div className="screen stagger">
        <Card system="sec" icon={s.armed ? 'lock' : 'shield'} title="Охрана"
          sub={s.armed ? 'Дом под охраной' : 'Охрана снята'}
          right={<span className="badge" style={{ background: s.armed ? 'color-mix(in oklab, var(--sec) 22%, transparent)' : 'var(--surface-3)', color: s.armed ? 'var(--sec)' : 'var(--text-2)' }}>
            {s.armed ? 'На охране' : 'Снята'}</span>}>
          <Seg value={s.armed ? 'arm' : 'dis'} accent color="var(--sec)"
            options={[{ v: 'arm', t: 'Поставить', icon: 'lock' }, { v: 'dis', t: 'Снять', icon: 'unlock' }]}
            onChange={(v) => actions.armSecurity(v === 'arm')} />
        </Card>

        <Card icon="wifi" title="Датчики" sub="Протечки · дверь · дым">
          <SensorRow icon="door" name="Входная дверь" ok={!data.sensors.door} value={data.sensors.door ? 'Открыта' : 'Закрыта'} />
          <SensorRow icon="smoke" name="Дым" ok={!data.sensors.smoke} value={data.sensors.smoke ? 'ДЫМ!' : 'Норма'} />
          <SensorRow icon="droplet" name="Ванная" ok={!data.sensors.bath} value={data.sensors.bath ? 'ТЕЧЬ!' : 'Сухо'} />
          <SensorRow icon="droplet" name="Душевая 1эт" ok={!data.sensors.shower} value={data.sensors.shower ? 'ТЕЧЬ!' : 'Сухо'} />
          <SensorRow icon="droplet" name="Кухня" ok={!data.sensors.kitchen} value={data.sensors.kitchen ? 'ТЕЧЬ!' : 'Сухо'} />
          <div style={{ height: 1 }} />
        </Card>

        <Card icon="battery" title="Батареи" sub="Беспроводные датчики">
          <div className="bento" style={{ gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            {data.batteries.map(b => <BatItem key={b.name} name={b.name} pct={b.pct} />)}
          </div>
        </Card>
      </div>
    );
  }

  window.StatusScreen = StatusScreen;
})();
