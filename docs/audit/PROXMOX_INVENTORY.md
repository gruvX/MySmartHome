# Proxmox VE — инвентаризация в Home Assistant

_Агент: proxmox-inventory-agent · Дата: 2026-07-17 · Репозиторий: `/home/user/projects/MySmartHome`_
_Режим: READ-ONLY. Только чтение HA REST/WebSocket. Проксмокс API не вызывался, устройства/VM не менялись, секреты/IP/токены не раскрываются._

## 1. Итог (evidence-based)

| Показатель | Значение |
|---|---|
| Интеграция | `proxmoxve` (config entry `01HAENTRYIDPLACEHOLDER0000`, state `loaded`, source `user`) |
| Хост узла | `[REDACTED node host IP]` (title config entry — не раскрывается) |
| Узлов (nodes) | **1** — `mylab` (model `Node`) |
| Гостей всего | **6 — все типа VM** (model `VM`). **LXC-контейнеров нет.** |
| VM running / stopped | **5 running / 1 stopped** |
| Хранилищ (storages) | 3 (`nas`, `local-btrfs`, `local`) |
| Устройств в реестре | 10 (1 node + 6 VM + 3 storage) |
| Сущностей в реестре | **159** (17 binary_sensor + 89 sensor + 53 button) |
| Отключённых (disabled_by) | 0 |
| Бэкап-данные | **Есть** (только на уровне узла) |
| Ссылки в tablet-panel.js / miniapp / dashboards | **Нет** (ни одна сущность не используется в UI) |

Данные свежие: `sensor.mylab_cpu_usage` 627 точек истории, узел online, uptime ~108 ч. Recorder пишет эти сущности.

## 2. Узел `mylab`

| Метрика | Сущность | Значение | Ед. | dc / sc |
|---|---|---|---|---|
| Статус (binary) | `binary_sensor.mylab_status` | on | — | running |
| Статус (enum) | `sensor.mylab_status` | online | — | enum / — |
| CPU | `sensor.mylab_cpu_usage` | 11.78 | % | — / measurement |
| CPU ядер | `sensor.mylab_max_cpu` | 8 | — | — |
| RAM использ. | `sensor.mylab_memory_usage` | 25.23 | GiB | data_size / measurement |
| RAM всего | `sensor.mylab_max_memory_usage` | 31.20 | GiB | data_size / measurement |
| RAM % | `sensor.mylab_memory_usage_percentage` | 80.86 | % | — / measurement |
| Диск использ. | `sensor.mylab_disk_usage` | 171.22 | GiB | data_size / measurement |
| Диск всего | `sensor.mylab_max_disk_usage` | 474.00 | GiB | data_size / measurement |
| Uptime | `sensor.mylab_uptime` | 108.40 | h | duration / measurement |
| Бэкап (проблема?) | `binary_sensor.mylab_backup_status` | off (= OK) | — | problem |
| Последний бэкап | `sensor.mylab_last_backup` | 2026-07-17T00:13:07Z | — | timestamp |
| Длит. бэкапа | `sensor.mylab_backup_duration` | 13.08 | min | duration / measurement |
| Кнопки (R2/R3) | `button.mylab_restart / _shut_down / _start_all / _stop_all / _suspend_all` | unknown | — | — |

Диск узла (171 GiB / 474 GiB) совпадает с `local-btrfs` — корень узла на btrfs. Нет: load average, температуры, SMART/health, обновлений, сетевого throughput на узле.

## 3. Гости (все VM; LXC нет)

| VMID | Имя | Статус | CPU % | ядра | RAM исп. GiB | RAM % | Диск исп. / всего GiB | Uptime ч | Net in/out GiB |
|---|---|---|---|---|---|---|---|---|---|
| 100 | homelab-staging | running | 4.97 | 4 | 6.60 | 82.5 | 0.0 / 40 | 108.4 | 1.98 / 0.10 |
| 101 | homelab-dev | running | 8.85 | 4 | 7.89 | **98.6** | 0.0 / 60 | 108.4 | 10.13 / 7.81 |
| 102 | ssh-tool | running | 2.54 | 2 | 1.67 | 83.7 | 0.0 / 20 | 108.4 | 1.94 / 1.43 |
| 200 | homeassistant | running | 2.85 | 2 | 3.58 | 59.6 | 0.0 / 32 | 108.4 | 1.26 / 1.33 |
| 9000 | homelab-clean-ubuntu-2404 | **stopped** | 0 | 2 | 0.0 | 0.0 | 0.0 / 80 | 0.0 | 0.0 / 0.0 |
| 9001 | homelab-ci-runner | running | 2.29 | 4 | 3.45 | 86.3 | 0.0 / 120 | 40.7 | 35.79 / 8.58 |

Каждая VM имеет: `binary_sensor.<slug>_status` (dc `running`), `sensor.<slug>_status` (enum running/stopped/suspended), `_cpu_usage`, `_max_cpu`, `_memory_usage`, `_max_memory_usage`, `_memory_usage_percentage`, `_uptime`, `_disk_usage`, `_max_disk_usage`, `_network_input`, `_network_output`, плюс 8 кнопок управления (`_start _stop _restart _hibernate _reset _shut_down _create_snapshot` и bare `button.<slug>`).

**Диск VM (`_disk_usage`) у всех = 0.0 GiB** — гостевой агент (qemu-guest-agent) не отдаёт использование; `_max_disk_usage` = выделенный объём. Реальное использование диска VM **недоступно**.

## 4. Хранилища

| Storage | active | enabled | shared | Использ. GiB | Всего GiB | Доступно GiB | % |
|---|---|---|---|---|---|---|---|
| nas | on | on | on | 1162.43 | 1826.22 | 663.79 | 63.7 |
| local-btrfs | on | on | off | 171.22 | 474.00 | 301.90 | 36.1 |
| local | **off** | **off** | off | 0.0 | 0.0 | 0.0 | **unknown** |

`local` неактивно/выключено — все значения 0/unknown (1 точка истории). Это не сбой сбора, а состояние хранилища в PVE.

## 5. Доступность по категориям метрик

| Категория | Есть в HA? | Источник / примечание |
|---|---|---|
| Статус узла | ДА | `binary_sensor.mylab_status` + `sensor.mylab_status` (enum) |
| CPU узла | ДА | `sensor.mylab_cpu_usage` (%) + `_max_cpu` (ядра) |
| Память узла used/total/% | ДА | `_memory_usage` / `_max_memory_usage` / `_memory_usage_percentage` |
| Хранилище узла used/total/% | ДА | через per-storage сущности; на узле есть disk_used/max, но нет node-level % |
| Uptime узла | ДА | `sensor.mylab_uptime` (h) |
| Load average узла | **НЕТ ДАННЫХ** | сенсора нагрузки нет |
| Температура | **НЕТ ДАННЫХ** | сенсора температуры нет |
| Статус VM | ДА | binary + enum на каждую VM |
| Статус LXC | **НЕТ ДАННЫХ** | LXC-гостей нет |
| CPU VM/LXC | ДА (VM) | `_cpu_usage` (%) + `_max_cpu` (ядра) |
| RAM VM/LXC | ДА (VM) | `_memory_usage` / `_max` / `_percentage` |
| Диск VM/LXC (использование) | **НЕТ ДАННЫХ** | сенсоры есть, но = 0 (нет guest agent); только выделенный размер |
| Статус хранилища | ДА | `_storage_active / _enabled / _shared` на каждое |
| Хранилище used/total/% | ДА | `_used_/_total_/_available_/_usage_percentage` (кроме неактивного `local`) |
| Статус бэкапа | ДА | `binary_sensor.mylab_backup_status` (dc problem; off=OK) — только узел |
| Последний успешный бэкап | ДА | `sensor.mylab_last_backup` (timestamp) — только узел |
| Возраст бэкапа | ДА (вычислимо) | из timestamp last_backup; выделенного сенсора возраста нет |
| Cluster / quorum | **НЕТ ДАННЫХ** | один узел, кластер-сенсора нет |
| Сетевой throughput (rate) | **НЕТ ДАННЫХ** | есть только накопительные счётчики (см. ниже) |
| Сетевые счётчики (кумулятивные) | ДА | `_network_input/_output` (GiB, total_increasing) на каждую VM; на узле нет |
| Диск / SMART health | **НЕТ ДАННЫХ** | нет |
| Доступность обновлений | **НЕТ ДАННЫХ** | нет (обновления HA — отдельная интеграция `version`) |
| Сама HA VM/LXC | ДА | VM 200 `homeassistant` мониторится (оговорка — см. §6) |
| Инфра-сервисы | **НЕТ ДАННЫХ (частично)** | только через webhook-автоматизацию (внешний push), не через сущности proxmoxve |

## 6. Пограничные случаи, коллизии, качество данных

- **Один узел** — кластера/кворума нет; `_start_all/_stop_all/_suspend_all` есть на узле как кнопки.
- **Только VM, ноль LXC.** Все 6 гостей model `VM`. Категория «статус LXC» — нет данных.
- **Коллизий имён VM/LXC нет** — все имена уникальны, entity_id с префиксом слага.
- **VM `homeassistant` (200)** — имя пересекается по смыслу с самой HA. Это НЕ обязательно тот HA, который опрашивался: опрос идёт на HA-хост из CLAUDE.md (Hyper-V на Windows-хосте), а узел Proxmox — другой, отдельный хост. Является ли VM 200 этим же инстансом HA — **не подтверждено**; фиксирую как факт, требующий проверки владельцем.
- **VM 9000 `homelab-clean-ubuntu-2404` — stopped, вероятно намеренно**: vmid из 9000-серии (конвенция шаблонов/базовых образов), имя «clean-...-2404» = чистый базовый образ; метрики 0 (cpu/ram/uptime/net). Не выглядит аварией. `binary_sensor.*_status` dc=`running`, состояние off — корректно (не запущена).
- **VM 9001 `homelab-ci-runner` — running** (uptime 40.7 ч, короче остальных ~108 ч → перезапускалась/поднята позже). CI-runner в 9000-серии, но активна.
- **Диск всех VM = 0.0 GiB** — вводит в заблуждение при отображении; нужен qemu-guest-agent. Показывать «использование диска VM» в UI нельзя без оговорки.
- **`sensor.*_network_input/_output` — накопительные (total_increasing), а не скорость.** Для throughput нужна производная (derivative). Как есть — это счётчики трафика с момента старта VM.
- **Хранилище `local`**: active/enabled/shared = off, значения 0, `_usage_percentage` = `unknown`. Состояние PVE, не ошибка сбора; в UI выводить не стоит.
- **RAM homelab-dev 98.6%** — высокая утилизация (данные валидны, не сбой сенсора).
- **Кнопки (53 шт.)** — все `button.*` в состоянии `unknown` (нормально для stateless-кнопок). Это управляющие действия уровня **R2/R3** (start/stop/restart/reset/shutdown/hibernate/create_snapshot/start_all/stop_all/suspend_all). Только инвентаризованы; **не вызывались**.
- **Бэкап — только узловой.** Пер-VM сенсоров бэкапа нет. `mylab_last_backup` = сегодня 00:13Z, длительность 13 мин, `backup_status` off (проблем нет) → бэкап свежий и здоровый.

## 7. Использование в UI / автоматизациях

- В `tablet/` и `miniapp/` **нет ссылок** на proxmox-сущности (grep пусто).
- Существует `automation.proxmox_infrastructure_alerts` (`proxmox_infra_alerts_v1`, ON, last_triggered 2026-07-16): триггер — **local webhook** (push из Proxmox), `notify.send_message`, без действий над устройствами. Она **не ссылается на сущности proxmoxve** — это независимый канал алертов от самого Proxmox.

## 8. Выходные файлы

- `docs/audit/PROXMOX_INVENTORY.md` (этот файл)
- `docs/audit/proxmox_inventory.json` (машиночитаемо: entities[], nodes[], guests[] с type/status/refs, storages[], backup{}, metrics_available{})
