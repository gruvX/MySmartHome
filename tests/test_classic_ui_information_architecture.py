from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TABLET = (ROOT / "tablet" / "tablet-panel.js").read_text(encoding="utf-8")
MINIAPP = (ROOT / "miniapp" / "smarthouse_v8.html").read_text(encoding="utf-8")


def _function_body(source: str, name: str, next_name: str) -> str:
    start = source.index(f"function {name}(")
    end = source.index(f"function {next_name}(", start)
    return source[start:end]


def test_tablet_primary_navigation_is_compact_and_task_based():
    nav = TABLET[TABLET.index("const NAV = [") : TABLET.index("];", TABLET.index("const NAV = ["))]
    expected = ["Центр", "Управление", "Климат", "Энергия", "Безопасность", "Server", "Система"]
    assert all(f"'{label}'" in nav for label in expected)
    assert nav.count("['") == 7
    assert "'Автоматика'" not in nav
    assert "'Сервис'" not in nav


def test_tablet_home_is_decision_first_and_moves_detail_below_fold():
    # Classic package 2 (2026-07-18): Главная = 4 priority zones (state, safety, cheap window,
    # active devices) + compact NAVIGATION summaries; detailed registries live on their own screens.
    body = _function_body(TABLET, "renderHome", "homeCardCheapWindow")
    expected = [
        "securityHomeCard()",          # zone (b): compact emergency card
        "homeCardActive()",            # zone (d): active/problem devices
        "homeCardCheapWindow()",       # zone (c): cheap Nord Pool window (no chart)
        "homeQuickActions()",
        "navTile('Отопление'",         # compact nav summaries → profile screens
        "navTile('Энергия'",
        "navTile('Сервер'",
        "navTile('Устройства'",
    ]
    assert all(item in body for item in expected)
    forbidden = [
        # detailed cards moved to their profile screens — not duplicated on Главная
        "homeCardEnergyToday()",
        "homeCardClimate()",
        "homeCardServer()",
        "homeCardElectricity()",
        "homeCardCost()",
        "homeCardTop3()",
        "homeCardUnavail()",
        "homeCardBatteries()",
        "homeCardAutoProtect()",
        "homeCardWater()",
        "priceBlock()",                # Nord Pool chart must live ONLY on Энергия
    ]
    assert all(item not in body for item in forbidden)


def test_tablet_nord_pool_chart_only_on_energy_screen():
    energy = _function_body(TABLET, "renderEnergy", "c1st")
    assert "priceBlock()" in energy
    # exactly one call site (definition + the single renderEnergy call)
    assert TABLET.count("priceBlock()") == 2


def test_system_screen_uses_live_health_not_stale_audit_cards():
    body = _function_body(TABLET, "renderService", "openWater")
    assert "Здоровье системы" in body
    assert "autoCounts()" in body
    assert "serviceAutoAudit()" not in body


def test_wall_tablet_touch_targets_are_at_least_44px():
    assert '".top-btn,.pill{min-height:44px}' in TABLET
    assert '.top-btn{min-width:44px}' in TABLET
    assert '.seg button{min-height:44px}' in TABLET


def test_navigation_exposes_current_page_semantics():
    assert 'aria-current="' in TABLET
    assert "setAttribute('aria-current',on?'page':'false')" in TABLET


def test_miniapp_home_has_no_duplicate_nord_pool_chart():
    body = _function_body(MINIAPP, "renderHome", "renderPriceChart")
    assert "renderPriceChart(" not in body
    assert "Статистика дома" not in body
    assert "home-actions" in body


def test_miniapp_converts_internal_cents_to_eur_for_display():
    # Prices are stored internally in cents (Nord Pool EUR/kWh * 100, see mapStates/normalizePrices).
    # Every display site must divide by 100 AND guard the missing case with «нет данных» — never
    # render raw cents (100x inflation) and never drop the guard. These assert the ACTUAL guarded
    # expressions shipped in smarthouse_v8.html, so they break if /100 or the guard is removed.
    assert 'pAvail?(p.now/100).toFixed(3):"нет данных"' in MINIAPP
    assert 'Number.isFinite(p.next)&&p.next>0?(p.next/100).toFixed(3):"нет данных"' in MINIAPP
    assert '${valid?(x/100).toFixed(3):"нет данных"}' in MINIAPP
    # raw cents must never be shown unscaled at a display site
    assert "${p.now}" not in MINIAPP
    assert "${p.next}" not in MINIAPP
    # real axis caption on the Energy price chart
    assert "Ось Y — EUR/кВт·ч · ось X — часы суток" in MINIAPP


def test_miniapp_accessibility_and_network_hardening_contract():
    assert 'role="status" aria-live="polite"' in MINIAPP
    assert 'role="dialog" aria-modal="true"' in MINIAPP
    assert 'role="switch" aria-checked=' in MINIAPP
    assert "AbortController" in MINIAPP
    assert "fetchPromise" in MINIAPP
