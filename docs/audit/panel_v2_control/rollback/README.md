# Откат «Пульта v2» на сборку 20260816-v2-lux-1

Байты, которые лежали на HA до деплоя сборки **20260817-v2-ctl-1** (реструктуризация
навигации + автоматизации). Сняты по SSH прямо из `/config/www/` и сверены по md5.

| Файл здесь | Куда кладётся | Размер | md5 |
|---|---|---|---|
| `tablet-panel-v2.js.20260816-v2-lux-1` | `/config/www/tablet-panel-v2.js` | 184 450 | `894843347368d107a7a776ad70ecaae9` |
| `tablet-v2-version.json.20260816-v2-lux-1` | `/config/www/tablet-v2-version.json` | 29 | `7b0e98c8b55102f7a9049e04a6c797c4` |

## Как откатить

Порядок обратный деплою: **сначала JS, сайдкар — последним.** Пока сайдкар ещё
рекламирует новую сборку, планшет никуда не уедет; как только сайдкар меняется, поллер
перезагружает страницу один раз и подхватывает старый JS. Перезапуск HA не нужен.

```python
import sys; sys.path.insert(0, '/home/user/projects/MySmartHome')
from ha_ssh import ssh_connect, run, write_remote
c = ssh_connect()
d = '/home/user/projects/MySmartHome/docs/audit/panel_v2_control/rollback/'
write_remote(c, open(d + 'tablet-panel-v2.js.20260816-v2-lux-1', 'rb').read(),
             '/config/www/tablet-panel-v2.js')
print(run(c, 'md5sum /config/www/tablet-panel-v2.js'))   # ждём 894843347368d107a7a776ad70ecaae9
write_remote(c, open(d + 'tablet-v2-version.json.20260816-v2-lux-1', 'rb').read(),
             '/config/www/tablet-v2-version.json')
print(run(c, 'md5sum /config/www/tablet-v2-version.json'))  # ждём 7b0e98c8b55102f7a9049e04a6c797c4
```

После откатa вернуть в репозитории `tablet/tablet-panel-v2.js` и
`tablet/tablet-v2-version.json` на эти же байты — иначе `tests/test_panel_v2_build_marker.py`
покажет расхождение сборки (это его работа).

Ограничение поллера: не больше одной перезагрузки на КАЖДОЕ уникальное значение `build`
и не больше 3 за сессию браузера. Если планшет уже перезагружался на
`20260816-v2-lux-1` в этой же сессии, повторной перезагрузки не будет — тогда обновить
страницу на планшете руками.
