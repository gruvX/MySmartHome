# Откат «Пульта v2» с 20260818-v2-photo-2 на 20260817-v2-ctl-1

Вербатимные байты предыдущей сборки. Проверенные md5:

| файл | md5 | назначение |
|---|---|---|
| `tablet-panel-v2.js.20260817-v2-ctl-1` | `9f2e536b53863816c623784cadbf0e48` | `/config/www/tablet-panel-v2.js` (222 007 B) |
| `tablet-v2-version.json.20260817-v2-ctl-1` | `d8efc4ba63c050cddda24779cb37d2e0` | `/config/www/tablet-v2-version.json` |

Порядок откатa — ОБРАТНЫЙ деплою: сначала сайдкар (чтобы планшеты узнали о смене сборки),
потом JS. Затем вернуть `?v=` в `panel_custom` и перезапустить HA.

```
# 1. сайдкар
cat rollback/tablet-v2-version.json.20260817-v2-ctl-1 | ssh <user>@192.168.1.45 'cat > /tmp/s.json'
ssh <user>@192.168.1.45 "echo <sudo> | sudo -S cp /tmp/s.json /config/www/tablet-v2-version.json"
# 2. JS
cat rollback/tablet-panel-v2.js.20260817-v2-ctl-1 | ssh <user>@192.168.1.45 'cat > /tmp/p.js'
ssh <user>@192.168.1.45 "echo <sudo> | sudo -S cp /tmp/p.js /config/www/tablet-panel-v2.js"
# 3. проверить md5 на диске, затем вернуть в /config/configuration.yaml:
#      module_url: /local/tablet-panel-v2.js?v=20260817-v2-ctl-1
#    и перезапустить HA (предварительно проверив: нет moisture=on, дым off,
#    sensor.leak_protection_status != leak).
```

Резервная копия конфигурации до правки `?v=` лежит на HA:
`/config/configuration.yaml.bak_photo_20260818` (md5 `eaaa8aad4524735ca76dd8a04c166b44`, 40 530 B).
