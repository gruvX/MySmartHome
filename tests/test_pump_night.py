# -*- coding: utf-8 -*-
"""Замок на ночную проверку гидрофора (2026-08-26/27).

Смысл этой пачки автоматизаций: понять, не пора ли подкачивать грушу
расширительного бака, по работе насоса в глухие ночные часы. Логика хрупкая в
трёх местах, и каждое уже один раз ломалось, поэтому проверяется тестом:

1. -1 значит «замера не было», а НЕ «насос стоял». Розетка офлайн ~78% времени,
   и подмена «нечем измерить» на ноль превратила бы отчёт во вранье о причине.
2. Окна, а не точное время. Первая версия мерила ровно в 01:00 и ровно в 04:00 и
   в первую же ночь не дала вердикта: розетки не было онлайн в эти секунды.
3. Порог считается НА ЧАС окна. Плоский порог врал бы: окно бывает 2.5 и 4.5 ч.

Тест читает YAML и НЕ трогает ни Home Assistant, ни сеть.
"""
from __future__ import annotations

from pathlib import Path

import re

import pytest
import yaml

FIXTURE = Path(__file__).parent / "fixtures" / "pump_night_automations.yaml"
RESET, VERDICT, DAILY, SNAPSHOT = (
    "1791200001001",
    "1791200001002",
    "1791200001003",
    "1791200001004",
)


@pytest.fixture(scope="module")
def autos():
    if not FIXTURE.exists():
        pytest.skip(f"нет фикстуры {FIXTURE}")
    data = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    return {str(a.get("id")): a for a in data}


def _dump(a) -> str:
    """YAML одной строкой с нормализованными пробелами.

    Шаблоны в файле свёрнуты в блочные скаляры, поэтому сравнивать с сырым текстом
    нельзя: перенос строки попадает в середину выражения. width=10**6 не даёт
    выгрузке ломать строки, а collapse убирает разницу в отступах.
    """
    return re.sub(r"\s+", " ", yaml.dump(a, allow_unicode=True, sort_keys=False, width=10**6))


def _has(a, needle: str) -> bool:
    return re.sub(r"\s+", " ", needle) in _dump(a)


def test_all_four_present(autos):
    for i in (RESET, VERDICT, DAILY, SNAPSHOT):
        assert i in autos, f"пропала автоматизация {i}"


def test_windows_not_exact_times(autos):
    """Снимок и вердикт живут в ОКНАХ и опрашиваются каждые 5 минут."""
    for i, after, before in ((SNAPSHOT, "00:05:00", "01:30:00"), (VERDICT, "04:00:00", "05:30:00")):
        a = autos[i]
        trig = a["triggers"][0]
        assert trig.get("trigger") == "time_pattern" and trig.get("minutes") == "/5", (
            f"{i}: нужен time_pattern /5, иначе вердикт снова будет требовать "
            f"розетку онлайн в одну конкретную секунду"
        )
        times = [c for c in a["conditions"] if c.get("condition") == "time"]
        assert times, f"{i}: нет временного окна"
        assert times[0]["after"] == after and times[0]["before"] == before


def test_snapshot_requires_numeric_counter(autos):
    """Снимок пишется только по числовому показанию — иначе в базу попадёт 0."""
    a = autos[SNAPSHOT]
    assert _has(a, "float(-1) >= 0")
    assert _has(a, "sensor.zigbee_plug_2_total_energy")


def test_verdict_is_guarded_three_ways(autos):
    a = autos[VERDICT]
    # снимок есть
    assert _has(a, "input_number.gidro_night_start') | float(-1) >= 0")
    # ещё не считали в эту ночь (идемпотентность)
    assert _has(a, "input_number.gidro_night_kwh') | float(-1) < 0")
    # счётчик читается
    assert _has(a, "sensor.zigbee_plug_2_total_energy') | float(-1) >= 0")
    # длина окна в разумных границах — защита от протухшего снимка
    assert _has(a, "1.5 <= (hours | float(0)) <= 6")


def test_threshold_is_per_hour_not_flat(autos):
    """max(0.06; 0.03 x часы). Замеренная норма дома — ~1 Вт·ч в час."""
    assert _has(autos[VERDICT], "[0.06, 0.03 * (hours | float(0))] | max")


@pytest.mark.parametrize(
    "kwh,hours,should_alert",
    [
        (0.01, 3.42, False),   # норма этого дома
        (0.05, 3.42, False),
        (0.09, 3.42, False),   # порог при 3.42 ч = 0.103
        (0.15, 3.42, True),
        (0.05, 2.00, False),   # порог не опускается ниже 0.06
        (0.07, 2.00, True),
        (0.13, 4.50, False),   # порог при 4.5 ч = 0.135
        (0.20, 4.50, True),
    ],
)
def test_threshold_arithmetic(kwh, hours, should_alert):
    """Та же формула, что в YAML: тревога, если расход выше порога на окно."""
    assert (kwh > max(0.06, 0.03 * hours)) is should_alert


def test_reset_clears_to_minus_one(autos):
    """Без сброса ночь без единого чтения унаследовала бы вчерашний снимок,
    и вердикт принял бы суточный расход за ночной."""
    body = _dump(autos[RESET])
    for ent in ("gidro_night_start", "gidro_night_kwh", "gidro_night_hours"):
        assert ent in body
    assert body.count("value: -1") >= 2, "снимок и результат должны обнуляться в -1, не в 0"
    assert autos[RESET]["triggers"][0]["at"] == "00:00:00"


def test_daily_runs_before_midnight_snapshot(autos):
    """23:59 намеренно: в 00:01 полуночный снимок обнуляет разницу."""
    assert autos[DAILY]["triggers"][0]["at"] == "23:59:00"


def test_daily_has_no_notification(autos):
    """Суточный рост — это чаще всего законный полив (июнь 230 мин/сут против
    65 в августе). Алерт на него был бы шумом; алерт только ночной."""
    body = _dump(autos[DAILY])
    assert "telegram_bot" not in body and "notify." not in body


def test_only_the_night_check_notifies(autos):
    for i in (RESET, SNAPSHOT, DAILY):
        assert "telegram_bot" not in _dump(autos[i]), f"{i} не должна уведомлять"
    assert "telegram_bot.send_message" in _dump(autos[VERDICT])


def test_alert_message_is_html_and_actionable(autos):
    """parse_mode html обязателен (markdown в этом боте ломает сообщения),
    и в тексте должна быть конкретная инструкция, а не просто «проверь»."""
    body = _dump(autos[VERDICT])
    assert "parse_mode: html" in body
    assert "0.2 бар" in body and "золотник" in body

# --- Протухшая база отсчёта (найдено 27.08 на первой же проверке) -------------
# Полуночный снимок в 00:01 при офлайне розетки штатно СОХРАНЯЕТ прежнее значение
# (ноль соврал бы про причину). Тогда «за сутки» покрывает больше суток: 27.08 было
# 112 мин при возрасте базы 27.3 ч. Такое число нельзя ни впускать в недельное
# среднее, ни называть суточным в отчёте.
REPORT = "1778700001003"


def test_daily_skips_stale_baseline(autos):
    a = autos[DAILY]
    assert _has(a, "baseline_age_h"), "нет проверки возраста базы — среднее будет расти само"
    assert _has(a, "<= 26")
    assert len(a["conditions"]) == 2, "должно быть два условия: число есть И база свежая"


def test_report_does_not_call_stale_number_daily(autos):
    """В отчёте протухшее число подписывается «за N ч», и со средним НЕ сравнивается:
    сравнивать интервалы разной длины — значит вводить в заблуждение."""
    if REPORT not in autos:
        pytest.skip("вечернего отчёта нет в фикстуре")
    body = _dump(autos[REPORT])
    assert "baseline_age_h" in body
    assert "b_age > 26" in body
    assert "полуночный снимок не прошёл" in body
    # ветка со средним должна быть в else, то есть после проверки возраста
    assert body.index("b_age > 26") < body.index("gidro_minutes_avg7")
