from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MINIAPP = (ROOT / "miniapp" / "smarthouse_luxury_candidate.html").read_text()
TABLET = (ROOT / "tablet" / "tablet-panel.luxury.js").read_text()


def test_miniapp_uses_eur_per_kwh_as_canonical_unit():
    """HA sensors and today_prices.json already expose EUR/kWh."""
    assert "Number(v)*100" not in MINIAPP
    assert "v*100" not in MINIAPP
    assert "p.now/100" not in MINIAPP
    assert "p.next/100" not in MINIAPP
    assert "d.price.now/100" not in MINIAPP
    assert 'v.toFixed(3)} €' in MINIAPP
    assert 'v<=0.04' in MINIAPP
    assert 'v<=0.10' in MINIAPP


def test_nord_pool_chart_exists_only_on_energy_screens():
    assert MINIAPP.count("renderPriceChart(p.arr") == 1
    assert TABLET.count("+priceBlock()+") == 1
    mini_energy = MINIAPP.index("function renderEnergy()")
    mini_chart_call = MINIAPP.index("renderPriceChart(p.arr")
    assert mini_chart_call > mini_energy
    tablet_energy = TABLET.index("function renderEnergy()")
    tablet_chart_call = TABLET.index("+priceBlock()+")
    assert tablet_chart_call > tablet_energy


def test_miniapp_control_is_grouped_by_rooms():
    assert 'Устройства собраны по помещениям' in MINIAPP
    for room in ("Кухня", "Гостиная", "Прихожая и двор", "Баня", "Аквариум и техника"):
        assert f'name:"{room}"' in MINIAPP


def test_navigation_contracts():
    assert 'const nav=[["home","Дом","home"],["control","Управление","bulb"],["energy","Энергия","bolt"],["events","События","shield"]]' in MINIAPP
    for label in ("Дом", "Комнаты", "Энергия", "Безопасность", "Системы"):
        assert f"'{label}'" in TABLET


def test_water_open_requires_confirmation_and_readback():
    assert 'if(name==="openWater"){app.modal="confirmOpenWater"' in MINIAPP
    assert 'app.data.water.open!==open' in MINIAPP
    assert 'состояние крана не подтвердилось' in MINIAPP
