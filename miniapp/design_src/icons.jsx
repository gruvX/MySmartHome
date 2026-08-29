// icons.jsx — линейный набор иконок (stroke, currentColor)
// <Icon name="bolt" size={20} />
(function () {
  const P = {
    home: <path d="M3 10.5 12 3l9 7.5M5.5 9.5V20h13V9.5M9.5 20v-5h5v5" />,
    sliders: <g><path d="M4 7h10M18 7h2M4 17h2M10 17h10" /><circle cx="16" cy="7" r="2.2" /><circle cx="8" cy="17" r="2.2" /></g>,
    activity: <path d="M3 13h3l2.5-7 4 14 3-9 1.6 2H21" />,
    shield: <path d="M12 3 5 5.5V11c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V5.5L12 3Z" />,
    bolt: <path d="M13 2 5 13h6l-1 9 8-12h-6l1-8Z" />,
    car: <g><path d="M3 13.5 4.8 8a3 3 0 0 1 2.8-2h8.8a3 3 0 0 1 2.8 2l1.8 5.5" /><path d="M3 13.5h18V18a1 1 0 0 1-1 1h-1.5a1 1 0 0 1-1-1v-1H6.5v1a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-4.5Z" /><path d="M6.5 16h.5M17 16h.5" /></g>,
    flame: <path d="M12 3c.6 3-2 4-2 7a2.2 2.2 0 0 0 4.3.6c1.4 1 2.2 2.6 2.2 4.4a4.5 4.5 0 1 1-9 0c0-3.2 2.5-4.6 2.5-7.5C10 8 11 6 12 3Z" />,
    droplet: <path d="M12 3c3 4 6 6.8 6 10.5a6 6 0 0 1-12 0C6 9.8 9 7 12 3Z" />,
    thermo: <g><path d="M10 13.5V5a2 2 0 0 1 4 0v8.5a4 4 0 1 1-4 0Z" /><circle cx="12" cy="17" r="1.4" fill="currentColor" stroke="none" /></g>,
    plug: <g><path d="M9 2v5M15 2v5M6 7h12v3a6 6 0 0 1-12 0V7Z" /><path d="M12 16v6" /></g>,
    bulb: <g><path d="M9 17h6M10 21h4M8.5 14a5.5 5.5 0 1 1 7 0c-.7.6-1 1.3-1 2.2H9.5c0-.9-.3-1.6-1-2.2Z" /></g>,
    moon: <path d="M20 14.5A8 8 0 1 1 9.5 4 6.5 6.5 0 0 0 20 14.5Z" />,
    sun: <g><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M19 5l-1.5 1.5M6.5 17.5 5 19" /></g>,
    refresh: <path d="M20 11a8 8 0 1 0-.8 4.5M20 6v5h-5" />,
    chevR: <path d="M9 6l6 6-6 6" />,
    chevD: <path d="M6 9l6 6 6-6" />,
    leaf: <path d="M5 19c0-8 6-13 14-13 0 8-5 14-13 14-1 0-2-.3-2-.3M9 15c2.5-3 5-4.5 8-5.5" />,
    battery: <g><rect x="2.5" y="8" width="16" height="8" rx="2" /><path d="M21 11v2" /></g>,
    door: <g><path d="M5 21V4a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v17M4 21h14" /><circle cx="13" cy="12" r="1" fill="currentColor" stroke="none" /></g>,
    smoke: <g><circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="2.2" /><path d="M12 3.5v2M12 18.5v2M3.5 12h2M18.5 12h2" /></g>,
    gauge: <g><path d="M4 16a8 8 0 1 1 16 0" /><path d="M12 16l4-4" /><circle cx="12" cy="16" r="1.4" fill="currentColor" stroke="none" /></g>,
    clock: <g><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></g>,
    plus: <path d="M12 5v14M5 12h14" />,
    minus: <path d="M5 12h14" />,
    power: <g><path d="M12 3v8" /><path d="M6.5 7a8 8 0 1 0 11 0" /></g>,
    play: <path d="M7 4.5 19 12 7 19.5v-15Z" />,
    stop: <rect x="6" y="6" width="12" height="12" rx="2" />,
    x: <path d="M6 6l12 12M18 6 6 18" />,
    bell: <path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4l2-2ZM9.5 20a2.5 2.5 0 0 0 5 0" />,
    walk: <g><circle cx="13" cy="4.5" r="1.6" /><path d="M11 9l3-1 2 3 2 1M11 9l-1.5 4 2 2 .5 5M9.5 13 7 16" /></g>,
    check: <path d="M5 12.5 10 17.5 19.5 6.5" />,
    snow: <path d="M12 2v20M3.5 7l17 10M20.5 7l-17 10M12 5l-3 2 3 2 3-2-3-2ZM12 19l3-2-3-2-3 2 3 2Z" />,
    fan: <g><circle cx="12" cy="12" r="2" /><path d="M12 10c0-4 1-7 0-8-2 1-3 4-2 6M14 12c4 0 7 1 8 0-1-2-4-3-6-2M12 14c0 4-1 7 0 8 2-1 3-4 2-6M10 12c-4 0-7-1-8 0 1 2 4 3 6 2" /></g>,
    arrowUR: <path d="M7 17 17 7M9 7h8v8" />,
    wifi: <path d="M5 12.5a10 10 0 0 1 14 0M8 15.5a6 6 0 0 1 8 0M12 18.5h.01" />,
    temp: <g><path d="M14 13.5V5a2 2 0 0 0-4 0v8.5a4 4 0 1 0 4 0Z" /></g>,
    dollar: <g><path d="M12 3v18" /><path d="M16 7.5C16 5.5 14.2 4.5 12 4.5S8 5.5 8 7.5 9.8 10.5 12 10.5s4 1 4 3-1.8 3-4 3-4-1-4-3" /></g>,
    eco: <path d="M5 19c0-8 6-13 14-13 0 8-5 14-13 14-1 0-2-.3-2-.3M9 15c2.5-3 5-4.5 8-5.5" />,
    lock: <g><rect x="5" y="10.5" width="14" height="10" rx="2.5" /><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" /><circle cx="12" cy="15.2" r="1.2" fill="currentColor" stroke="none" /></g>,
    unlock: <g><rect x="5" y="10.5" width="14" height="10" rx="2.5" /><path d="M8 10.5V8a4 4 0 0 1 7.8-1.2" /><circle cx="12" cy="15.2" r="1.2" fill="currentColor" stroke="none" /></g>,
    valve: <g><circle cx="12" cy="12" r="4" /><path d="M12 8V3M9 3h6M12 16v5M9 21h6M16 12h5M21 9v6M8 12H3M3 9v6" /></g>,
  };

  function Icon({ name, size = 22, stroke = 1.7, style, className }) {
    const node = P[name];
    if (!node) return null;
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
        stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round"
        style={{ display: 'block', ...style }} className={className}>
        {node}
      </svg>
    );
  }

  window.Icon = Icon;
})();
