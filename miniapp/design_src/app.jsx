// app.jsx — каркас приложения: данные, навигация, шапка, тревоги, Tweaks
(function () {
  const { useState, useEffect, useRef } = React;
  const { Icon, tierOf } = window;
  const { useTweaks, TweaksPanel, TweakSection, TweakColor, TweakToggle, TweakRadio } = window;

  // ── 24h Nord Pool кривая (¢/кВт·ч) ──────────────────────
  const PRICE = [5.2,4.6,4.1,3.8,4.0,5.5,9.8,14.2,17.6,15.1,11.3,8.4,6.2,5.1,5.6,7.8,11.4,16.2,20.8,22.3,19.1,14.6,10.2,7.1];

  function cheapWindow(arr, from) {
    for (let i = 0; i < 24; i++) {
      const h = (from + i) % 24;
      if (arr[h] < 8) {
        let end = h;
        while (arr[(end + 1) % 24] < 10 && ((end + 1) % 24) !== from) end = (end + 1) % 24;
        return `${String(h).padStart(2,'0')}:00–${String((end+1)%24).padStart(2,'0')}:00`;
      }
    }
    return '—';
  }

  function makeData(nowHour) {
    const arr = PRICE;
    const min = Math.min(...arr), max = Math.max(...arr);
    const items = [
      { key: 'ev',    name: 'EV зарядка',    system: 'ev',    icon: 'car',     kwh: 22.6, cost: 1.42 },
      { key: 'boil',  name: 'Котёл',         system: 'boil',  icon: 'flame',   kwh: 8.4,  cost: 0.71 },
      { key: 'akv',   name: 'Аквариум',      system: 'plug',  icon: 'plug',    kwh: 1.2,  cost: 0.13 },
      { key: 'rec',   name: 'Рециркуляция',  system: 'water', icon: 'refresh', kwh: 0.8,  cost: 0.09 },
      { key: 'hyd',   name: 'Гидрофор',      system: 'water', icon: 'droplet', kwh: 0.6,  cost: 0.06 },
    ];
    return {
      outside: 7.4,
      price: {
        now: arr[nowHour], next: arr[(nowHour + 1) % 24], arr, nowHour,
        min, max, minH: arr.indexOf(min), maxH: arr.indexOf(max),
        cheapWindow: cheapWindow(arr, nowHour),
      },
      cost: { total: items.reduce((s, i) => s + i.cost, 0), kwh: items.reduce((s, i) => s + i.kwh, 0), items },
      ev: { pct: 0.62, kwh: 14.2, short: 'Заряжается', sub: 'Заряжается · план 02:00', sched: '02:00', manual: false },
      boiler: { mode: 'work', co: 64, coSet: 68, cwu: 49, cwuSet: 50, ret: 52, fan: 42, power: true, pumpCo: true, pumpCwu: false, pumpCirc: true },
      floor: [{ name: 'Ванная', temp: 24, mode: 'auto' }, { name: 'Душевая 1эт', temp: 23, mode: 'auto' }],
      lights: [
        { id: 'entr', name: 'Фонарь',      icon: 'bulb', on: false },
        { id: 'isl',  name: 'Остров',      icon: 'bulb', on: true },
        { id: 'tbl',  name: 'Стол',        icon: 'bulb', on: false },
        { id: 'hall', name: 'Коридор 2эт', icon: 'bulb', on: false },
        { id: 'sauna',name: 'Баня',        icon: 'bulb', on: false },
        { id: 'ver',  name: 'Веранда',     icon: 'bulb', on: false },
      ],
      plugs: [
        { id: 'akv',   name: 'Аквариум',  icon: 'plug',    on: true },
        { id: 'rec',   name: 'Рециркул.', icon: 'refresh', on: true },
        { id: 'hyd',   name: 'Гидрофор',  icon: 'droplet', on: false },
        { id: 'cal',   name: 'Полотенцесушитель', icon: 'fan',     on: false },
      ],
      water: { open: true },
      security: { armed: false },
      sensors: { door: false, smoke: false, bath: false, shower: false, kitchen: false },
      batteries: [
        { name: 'Дверь', pct: 84 }, { name: 'Дым', pct: 92 }, { name: 'Ванная', pct: 61 },
        { name: 'Душевая', pct: 28 }, { name: 'Кухня', pct: 73 }, { name: 'Гараж', pct: 12 },
      ],
    };
  }

  const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
    "dark": true,
    "accent": "#5fe0a6",
    "home": "B",
    "demoLeak": false
  }/*EDITMODE-END*/;

  const NAV = [
    { t: 'Главная', icon: 'home' },
    { t: 'Управление', icon: 'sliders' },
    { t: 'Энергия', icon: 'activity' },
    { t: 'Статус', icon: 'shield' },
  ];

  function App() {
    const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
    const nowHour = new Date().getHours();
    const [data, setData] = useState(() => makeData(nowHour));
    const [tab, setTab] = useState(0);
    const [home, setHome] = useState(t.home);
    const [clock, setClock] = useState('');
    const [toastMsg, setToastState] = useState(null);
    const [spin, setSpin] = useState(false);
    const [dismissed, setDismissed] = useState(false);
    const toastTmr = useRef(null);

    useEffect(() => { setHome(t.home); }, [t.home]);

    // demo leak toggle
    useEffect(() => {
      setData(d => ({ ...d, sensors: { ...d.sensors, bath: t.demoLeak } }));
      if (t.demoLeak) setDismissed(false);
    }, [t.demoLeak]);

    // clock
    useEffect(() => {
      const tick = () => {
        const n = new Date(), p = x => String(x).padStart(2, '0');
        setClock(`${p(n.getHours())}:${p(n.getMinutes())}`);
      };
      tick(); const id = setInterval(tick, 10000); return () => clearInterval(id);
    }, []);

    const dateStr = (() => {
      const n = new Date();
      const days = ['воскресенье','понедельник','вторник','среда','четверг','пятница','суббота'];
      const mon = ['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'];
      return `${days[n.getDay()]}, ${n.getDate()} ${mon[n.getMonth()]}`;
    })();

    function toast(msg, color) {
      setToastState({ msg, color });
      clearTimeout(toastTmr.current);
      toastTmr.current = setTimeout(() => setToastState(null), 2400);
    }

    // alerts
    const alerts = [];
    if (data.sensors.smoke) alerts.push('Обнаружен дым');
    if (data.sensors.bath) alerts.push('Утечка: Ванная');
    if (data.sensors.shower) alerts.push('Утечка: Душевая 1эт');
    if (data.sensors.kitchen) alerts.push('Утечка: Кухня');
    if (data.sensors.door && data.security.armed) alerts.push('Дверь открыта (охрана)');
    const security = { ...data.security, alerts };

    const actions = {
      scene(k) {
        if (k === 'night') { setData(d => ({ ...d, lights: d.lights.map(l => ({ ...l, on: false })), water: { open: false } })); toast('Ночной режим активирован', 'var(--floor)'); }
        if (k === 'away')  { setData(d => ({ ...d, lights: d.lights.map(l => ({ ...l, on: false })), security: { armed: true } })); toast('Ушли · охрана включена', 'var(--sec)'); }
        if (k === 'eco')   { setData(d => ({ ...d, floor: d.floor.map(f => ({ ...f, mode: 'auto' })) })); toast('Режим экономии активирован', 'var(--ev)'); }
      },
      closeValve() { setData(d => ({ ...d, water: { open: false } })); toast('Кран закрыт', 'var(--water)'); },
      armSecurity(v) { setData(d => ({ ...d, security: { armed: v } })); toast(v ? 'Охрана поставлена' : 'Охрана снята', 'var(--sec)'); },
      setCwu(temp) { setData(d => ({ ...d, boiler: { ...d.boiler, cwuSet: temp } })); toast(`ГВС уставка ${temp}°`, 'var(--boil)'); },
      setCo(temp) { setData(d => ({ ...d, boiler: { ...d.boiler, coSet: temp } })); toast(`CO уставка ${temp}°`, 'var(--boil)'); },
      boilerPower(on) { setData(d => ({ ...d, boiler: { ...d.boiler, power: on, mode: on ? 'work' : 'off' } })); toast(`Котёл ${on ? 'включён' : 'выключен'}`, 'var(--boil)'); },
      evStart() { setData(d => ({ ...d, ev: { ...d.ev, short: 'Заряжается', sub: 'Заряжается · ручной' } })); toast('Зарядка запущена', 'var(--ev)'); },
      evStop() { setData(d => ({ ...d, ev: { ...d.ev, short: 'Остановлено', sub: 'Остановлено' } })); toast('Зарядка остановлена', 'var(--ev)'); },
      evManual() { setData(d => ({ ...d, ev: { ...d.ev, manual: !d.ev.manual } })); },
      setFloor(i, mode) { setData(d => ({ ...d, floor: d.floor.map((f, idx) => idx === i ? { ...f, mode, temp: mode === 'manual' ? 30 : f.temp } : f) })); toast(`${data.floor[i].name}: ${mode === 'manual' ? 'ручной 30°' : 'авто'}`, 'var(--floor)'); },
      toggleLight(id) { setData(d => ({ ...d, lights: d.lights.map(l => l.id === id ? { ...l, on: !l.on } : l) })); },
      togglePlug(id) { setData(d => ({ ...d, plugs: d.plugs.map(p => p.id === id ? { ...p, on: !p.on } : p) })); },
      allLightsOff() { setData(d => ({ ...d, lights: d.lights.map(l => ({ ...l, on: false })) })); toast('Весь свет выключен', 'var(--light)'); },
    };

    const go = (i) => setTab(i);
    function refresh() { setSpin(true); setTimeout(() => setSpin(false), 750); toast('Данные обновлены'); }

    const dataF = { ...data, price: { ...data.price, nowHour: data.price.nowHour }, security };

    return (
      <IOSDevice dark={t.dark} width={390} height={844}>
        <div className="app" data-theme={t.dark ? 'dark' : 'light'} style={{ '--accent': t.accent }}>

          {/* Telegram context bar */}
          <div className="tg-bar" style={{ paddingTop: 50 }}>
            <div className="tg-title"><span className="tg-logo"><Icon name="home" size={15} /></span>Умный дом</div>
            <div className="tg-actions">
              <button className="icon-btn" style={{ width: 34, height: 34 }} onClick={() => setTweak('dark', !t.dark)}>
                <Icon name={t.dark ? 'sun' : 'moon'} size={18} />
              </button>
            </div>
          </div>

          {/* Header */}
          <div className="hdr">
            <div className="hdr-l">
              <div className="hdr-clock mono">{clock}</div>
              <div className="hdr-date">{dateStr}</div>
            </div>
            <div className="hdr-r">
              <div className="chip-out"><Icon name="temp" size={15} /><span className="mono">{data.outside.toFixed(1)}°</span></div>
              <button className={'icon-btn' + (spin ? ' spin' : '')} onClick={refresh}><Icon name="refresh" size={18} /></button>
            </div>
          </div>

          {/* Scroll */}
          <div className="scroll">
            {alerts.length > 0 && !dismissed && (
              <div className="alert" style={{ marginTop: 6 }}>
                <div className="alert-hd"><Icon name="bell" size={18} />Тревога</div>
                <ul>{alerts.map((a, i) => <li key={i}>{a}</li>)}</ul>
                <div className="alert-btns">
                  <button className="abtn solid" onClick={actions.closeValve}>Закрыть кран</button>
                  <button className="abtn out" onClick={() => toast('Сирена выключена')}>Выкл. сирену</button>
                  <button className="abtn out" onClick={() => setDismissed(true)}>Ложная</button>
                </div>
              </div>
            )}

            {tab === 0 && <window.HomeScreen data={dataF} actions={actions} go={go} layout={home} setLayout={setHome} />}
            {tab === 1 && <window.ControlScreen data={dataF} actions={actions} />}
            {tab === 2 && <window.EnergyScreen data={dataF} />}
            {tab === 3 && <window.StatusScreen data={dataF} actions={actions} />}
          </div>

          {/* Toast */}
          <div className={'toast' + (toastMsg ? ' show' : '')}>
            {toastMsg && <><span className="tdot" style={{ background: toastMsg.color || 'var(--accent)' }} />{toastMsg.msg}</>}
          </div>

          {/* Bottom nav */}
          <nav className="nav">
            {NAV.map((n, i) => (
              <button key={i} className={'nav-btn' + (tab === i ? ' on' : '')} onClick={() => setTab(i)}>
                <span className="ni"><Icon name={n.icon} size={23} stroke={tab === i ? 2 : 1.7} /></span>{n.t}
              </button>
            ))}
          </nav>

          <TweaksPanel title="Tweaks">
            <TweakSection label="Тема" />
            <TweakToggle label="Тёмная тема" value={t.dark} onChange={v => setTweak('dark', v)} />
            <TweakColor label="Акцент" value={t.accent} options={['#5fe0a6', '#56b8f5', '#b98cff', '#ffb259']} onChange={v => setTweak('accent', v)} />
            <TweakSection label="Главный экран" />
            <TweakRadio label="Раскладка" value={t.home} options={[{ value: 'A', label: 'Лента' }, { value: 'B', label: 'Панель' }, { value: 'C', label: 'Фокус' }]} onChange={v => setTweak('home', v)} />
            <TweakSection label="Демо" />
            <TweakToggle label="Тревога: протечка" value={t.demoLeak} onChange={v => setTweak('demoLeak', v)} />
          </TweaksPanel>
        </div>
      </IOSDevice>
    );
  }

  window.App = App;
})();
