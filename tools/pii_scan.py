#!/usr/bin/env python3
"""Поиск личных данных в том, что уходит в публичный репозиторий.

ЗАЧЕМ ОТДЕЛЬНО ОТ secret_scan.py. Тот ищет секреты — токены, ключи, пароли.
Личные данные устроены иначе: это не «строка известного вида», а имя, адрес
почты, координаты, логин. Искать их по списку известных значений бесполезно —
такой поиск находит только то, что ты уже знаешь. Именно так 2026-08-29 трижды
подряд пропускались: почта на gmail, id аккаунта Xiaomi, имя машины.

ПОЭТОМУ ЗДЕСЬ ДРУГОЙ ПОДХОД: перечисление. Скрипт выписывает ВСЕ строки,
похожие на идентификатор (почта, координаты, MAC, логин перед @, домашний путь),
и сверяет их с явным белым списком разрешённых значений. Всё, чего в списке
нет, — находка, даже если инструмент видит её впервые.

Запуск: python3 tools/pii_scan.py [--all]
  без флага  — только файлы в индексе (для pre-commit)
  --all      — весь репозиторий
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# Значения, которые публиковать МОЖНО. Всё остальное — находка.
ALLOWED_EMAILS = {"owner@example.com", "BOILER_PASSWORD@ecoNET300.local"}
ALLOWED_COORDS = {"56.9496", "24.1052"}          # центр Риги, не дом
ALLOWED_MACS = {"aa:bb:cc:dd:ee:ff"}
ALLOWED_LOGINS = {"root", "owner", "user", "postgres", "homeassistant"}
ALLOWED_HOME_PATHS = {"user", "root"}
# Локальные адреса: 192.168.1.x — обобщённый пример, .18.x — настоящая сеть дома.
FORBIDDEN_NETS = (re.compile(r"\b192\.168\.18\.\d+\b"),)

CHECKS = [
    ("почта", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), ALLOWED_EMAILS),
    ("координаты", re.compile(r'(?i)"?(?:latitude|longitude)"?\s*[:=]\s*(-?\d+\.\d{3,})'), ALLOWED_COORDS),
    ("MAC-адрес", re.compile(r"\b(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b"), ALLOWED_MACS),
    ("логин перед @", re.compile(r"\b([a-z][a-z0-9_.-]{2,})@(?:\d{1,3}\.){3}\d{1,3}"), ALLOWED_LOGINS),
    # Именно "/home/<логин>/" со слэшем на конце: без него правило ловило пути
    # чужих API вида /v1.0/m/life/ha/home/devices и давало ложные срабатывания.
    ("домашний путь", re.compile(r"/(?:home|Users)/([A-Za-z0-9._-]+)/"), ALLOWED_HOME_PATHS),
]

SKIP_SUFFIX = (".png", ".jpg", ".jpeg", ".webp", ".ico", ".woff", ".woff2", ".ttf")


def files_to_check(scan_all: bool) -> list[str]:
    cmd = ["git", "ls-files"] if scan_all else ["git", "diff", "--cached", "--name-only"]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout.split()
    return [f for f in out if Path(f).is_file()]


def main() -> int:
    scan_all = "--all" in sys.argv
    findings: list[str] = []
    for f in files_to_check(scan_all):
        if f.endswith(SKIP_SUFFIX):
            continue
        try:
            text = Path(f).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for label, rx, allowed in CHECKS:
            for m in rx.finditer(text):
                value = m.group(1) if m.groups() else m.group(0)
                if value in allowed:
                    continue
                line = text[: m.start()].count("\n") + 1
                findings.append(f"  {label}: {value}  ({f}:{line})")
        for rx in FORBIDDEN_NETS:
            for m in rx.finditer(text):
                line = text[: m.start()].count("\n") + 1
                findings.append(f"  адрес домашней сети: {m.group(0)}  ({f}:{line})")

    if findings:
        print("Найдены личные данные (или новое значение, которого нет в белом списке):")
        for x in sorted(set(findings)):
            print(x)
        print("\nЕсли значение безопасно — добавь его в белый список в tools/pii_scan.py.")
        return 1
    print("Личных данных не найдено.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
