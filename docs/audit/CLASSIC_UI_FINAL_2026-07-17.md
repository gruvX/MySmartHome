# Улучшенный Classic — итог разработки и деплоя

Дата: 2026-07-17  
Подсистемы: планшет, Mini App, frontend Home Assistant  
Риск: R1 разработка + R2 frontend-деплой  
Физические устройства: не управлялись

## 1. Результат

Классический визуальный язык сохранён. Перестроена информационная архитектура, устранена перегрузка главных экранов, добавлены адаптивность, accessibility и сетевое hardening.

Планшет:

- семь разделов: Центр, Управление, Климат, Энергия, Безопасность, Server, Система;
- на Центре видны активные нагрузки и четыре быстрых режима;
- подробные энергия, Server и диагностика перенесены на профильные экраны;
- Автоматика и Сервис объединены в живой экран Система;
- Nord Pool-график находится только в Энергии и имеет оси, легенду, границу дней и пустое состояние;
- touch targets верхних действий и сегментов увеличены до 44 px;
- навигация получила `aria-current` и видимый focus.

Mini App:

- компактная главная до 1–1,5 мобильного экрана;
- safety показывается только при проблеме;
- одна краткая Nord Pool-сводка, активные системы, четыре действия и климат;
- подробный график только в Энергии;
- внутренняя цена в центах корректно преобразуется в EUR/kWh;
- добавлены оси X/Y графика;
- custom switches стали семантическими кнопками;
- добавлены ARIA, Escape/initial focus для диалогов и live-region для сообщений;
- запросы имеют timeout, AbortController и single-flight;
- вода, EV и охрана подтверждают фактическое состояние перед сообщением об успехе.

## 2. Изменённые файлы

- `tablet/tablet-panel.js`
- `tablet/tablet-panel.dev.html`
- `miniapp/smarthouse_v8.html`
- `tests/test_classic_ui_information_architecture.py`
- `docs/audit/DESIGN_AUDIT_CLASSIC_2026-07-17.md`
- `docs/audit/classic_improved_2026-07-17/*`

Production:

- `/config/www/tablet-panel.js`
- `/config/www/smarthouse.html`
- `/config/www/design-review/classic-final/*`

## 3. Проверки

- независимый первичный UX-review: BLOCK, 5 блокеров;
- все 5 блокеров исправлены;
- независимый повторный UX-review: PASS;
- полный pytest: 408 passed, 8 skipped, 1 xpassed;
- Python py_compile обязательных файлов: PASS;
- Tablet JavaScript syntax: PASS;
- Mini App inline JavaScript syntax: PASS;
- contract/auth/server tests: PASS;
- screenshots: Tablet 1024/1280/1366; Energy populated/empty 1024; System 1024; Mini App 390/430;
- HTTP production: 200, SHA-256 совпадает с локальными кандидатами;
- invalid Mini App auth: 401;
- staged secret scan: clean;
- full-tree scan показывает только санкционированный `local_secrets.json` и синтетическую Telegram-фикстуру теста; в изменённых frontend-файлах секретов нет;
- Impeccable detector: два неблокирующих предупреждения — старое `transition: width` meter-анимации и сохранённый classic dark glow;
- общий `git diff --check HEAD` содержит существующий whitespace в `docs/audit/ev_notify_surgical.diff`, не относящийся к этому пакету; scoped diff чист.

## 4. Влияние на работающий дом

Изменено только отображение и безопасная обработка frontend-команд. Новых backend-команд или allow-list действий не добавлено. Вода, котёл, отопление, охрана, EV, сирена и розетки во время тестов не переключались.

После деплоя подтверждены состояния:

- датчики дыма/протечки: off;
- главный кран: открыт;
- сирена: off;
- охрана: off;
- EV: off;
- электрический бойлер: off.

HA restart/reload не выполнялся.

## 5. Остаточные риски

- уже открытая вкладка планшета держит загруженный JS до обновления страницы; production-файл обновлён, но физический экран может потребовать reload/hard refresh;
- полный циклический focus trap Mini App ещё не реализован, хотя dialog semantics, initial focus и Escape есть;
- не все некритические команды Mini App сравнивают ожидаемое состояние; вода, EV и охрана сравнивают;
- два визуальных detector-warning оставлены ради сохранения familiar classic.

## 6. Откат

Production backup:

`/config/backups/pre_classic_ui_20260717_213948/`

В нём находятся прежние `tablet-panel.js` и `smarthouse.html` с правами 0600. Откат: атомарно вернуть оба файла в `/config/www/`; restart HA не требуется, браузеру потребуется обновление страницы. Устройства и конфигурация HA при откате не меняются.

## 7. Визуальный результат

Gallery в Home Assistant:

`/local/design-review/classic-final/index.html`

Локальные артефакты: `docs/audit/classic_improved_2026-07-17/`.
