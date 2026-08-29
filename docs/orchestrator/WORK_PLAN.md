# План развития и стабилизации MySmartHome

План составлен по результатам статического аудита. Оркестратор выполняет этапы по порядку;
переход к следующему этапу допускается после выполнения exit criteria предыдущего.

## P0 — немедленная защита credentials

- [ ] Отозвать HA-токен, который попал в `.claude/settings.local.json` и исторические команды.
- [ ] Удалить секреты из Claude/Ruflo permissions и локальных одноразовых скриптов.
- [ ] Проверить `tablet/*.bak*`, `scripts/`, `backups/`, agent logs и screenshots.
- [ ] Добавить `*.bak*`, browser profiles и agent runtime state в ignore/изоляцию.
- [ ] Ввести full-tree и staged secret scan; проверить Git history.
- [ ] Хранить runtime/backups вне рабочего дерева репозитория.

Exit criteria: действующие credentials отсутствуют в исходниках, настройках агентов, командах,
логах и web-root; скомпрометированные значения отозваны.

## P1 — восстановление корректного управления

- [ ] Синхронизировать Mini App actions с backend allow-list.
- [ ] Добавить недостающие `STATE_IDS` или удалить неподдерживаемые данные из UI.
- [ ] Убрать оптимистический успех; ждать ответ и подтверждать HA state.
- [ ] Для воды, охраны, EV и отопления добавить confirm + post-action verification.
- [ ] Исправить обработку некорректной температуры без HTTP 500.
- [ ] Добавить единый декларативный контракт entities/actions.

Exit criteria: каждая видимая кнопка либо подтверждённо работает, либо явно недоступна; тест
контракта доказывает отсутствие frontend-команд вне allow-list.

## P1 — усиление Telegram auth

- [ ] Ограничить возраст `initData` и отклонять дату из будущего.
- [ ] Определить короткую серверную сессию или nonce/replay policy.
- [ ] Ограничить размер body и частоту запросов.
- [ ] Сузить calendar allow-list и убрать внутренний HTTP с административным HA-токеном.
- [ ] Добавить тесты подписи, UID, старой/будущей даты и изменённых параметров.

Exit criteria: auth имеет негативные тесты, ограничение replay и минимальные права.

## P1 — надёжность EV и Tuya

- [ ] Удалить fallback одного 15-минутного слота как «2 часа».
- [ ] Проверять результат каждого HA POST и не печатать `OK` при ошибке.
- [ ] Объединить общую логику трёх EV scheduler в один модуль с параметрами.
- [ ] Добавить тесты непрерывности, неполных цен, DST и границ дня/ночи.
- [ ] Сделать Tuya cache атомарным, с lock и правами `0600`.
- [ ] Добавить безопасное диагностическое логирование и единый набор статусов.

Exit criteria: unit tests покрывают сбои Elering/HA/Tuya; старое подтверждённое расписание не
повреждается при внешнем отказе.

## P2 — воспроизводимая конфигурация Home Assistant

- [ ] Создать обезличенные templates automations, scripts, shell_commands, rest_commands и helpers.
- [ ] Убрать ссылки документации на отсутствующие tracked-файлы.
- [ ] Создать inventory entity IDs с назначением, владельцем и критичностью.
- [ ] Зафиксировать совместимые версии HA и integrations.
- [ ] Сделать validate/deploy/rollback scripts без встроенных credentials.

Exit criteria: чистый clone можно настроить по документации без приватных historical scripts.

## P2 — frontend pipeline

- [ ] Выбрать один source of truth: `design_src` или автономный HTML.
- [ ] Добавить воспроизводимую сборку V8.
- [ ] Убрать персональный hostname, имя бота и адреса в конфигурацию deploy-time.
- [ ] Отделить mock/preview от production и явно маркировать его.
- [ ] Перевести graph/livemap на proxy auth либо оставить только локальными инструментами.
- [ ] Добавить CSP и правила iframe.

Exit criteria: runtime HTML воспроизводится одной командой, не содержит credentials и проходит
автоматическую проверку.

## P2 — CI и качество

- [ ] Добавить `pyproject.toml`, formatter/linter и test runner.
- [ ] Добавить CI: Python compile, tests, JS syntax, contract test, secret scan, diff check.
- [ ] Нормализовать окончания строк через `.gitattributes`.
- [ ] Разделить unit, integration и live-device tests.
- [ ] Запретить live-device tests по умолчанию.

Exit criteria: pull request не принимается при нарушении контракта, утечке секрета или ошибке
синтаксиса.

## P3 — наблюдаемость и эксплуатация

- [ ] Ввести health dashboard: stale data, unavailable entities, automation failures.
- [ ] Добавить correlation ID и безопасные структурированные логи Mini App proxy.
- [ ] Документировать runbooks воды, дыма, котла, EV, Tuya quota и HA restart.
- [ ] Ввести журнал изменений production и регулярную проверку backup restore.
- [ ] Добавить мониторинг расхождения Git/deployed configuration.

Exit criteria: отказ обнаруживается, диагностируется и откатывается по документированному runbook.

## Рекомендуемый первый спринт

1. P0 credentials и изоляция runtime-файлов.
2. Контракт Mini App/backend и исправление ложного успеха.
3. Unit tests Telegram auth.
4. Unit tests и безопасный fallback EV.
5. Минимальный CI.

