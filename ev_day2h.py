#!/usr/bin/env python3
# EV daytime 2h charging window finder (08:00-20:00 local).
# Runnable standalone: HA invokes `python3 /config/ev_day2h.py`.
# Shared logic lives in ev_common.py (must be deployed alongside this file).
import sys
import datetime

sys.stdout.reconfigure(encoding="utf-8")

from project_secrets import secret
import ev_common as ev

TOKEN = secret("HA_TOKEN", required=True)
HA = secret("HA_BASE_URL", "http://127.0.0.1:8123")
HDR = ev.make_headers(TOKEN)
TG = secret("HA_NOTIFY_ENTITY")

START_H = 8
END_H = 20
LABEL = "Дневная"
WINDOW_LABEL = "08:00-20:00"

RIGA = ev.RIGA
DRY_RUN = "--dry-run" in sys.argv


def in_window(hour):
    return START_H <= hour < END_H


def notify(message):
    if DRY_RUN:
        print(f"[dry-run] would notify: {message.splitlines()[0]}")
        return True
    ok, status = ev.ha_post(
        HA, "/api/services/notify/send_message",
        {"entity_id": TG, "message": message}, HDR,
    )
    if not ok:
        ev.log_err(f"notify failed (status={status})")
    return ok


def main():
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    try:
        old_val = ev.ha_get(HA, "/api/states/input_datetime.ev_charge_start", HDR)["state"]
    except Exception:
        old_val = ""

    try:
        prices = ev.fetch_lv_prices(now_utc)
    except Exception as exc:
        ev.log_err(str(exc))
        # Dedup/cooldown: one "недоступен" per incident (schedule untouched below).
        ev.notify_elering_failure(
            notify,
            message=(f"⚠️ EV {LABEL}: Elering API недоступен (сервис временно не отвечает). "
                     "Расписание не изменено, попробуй позже."),
        )
        sys.exit(1)

    # First success after an outage → one recovery notice; silent otherwise.
    ev.notify_elering_recovery(notify)

    best_utc, avg_price = ev.find_best_2h(prices, now_utc, hour_filter=in_window)
    if best_utc is None:
        ev.log(f"No genuine contiguous 2h window in {WINDOW_LABEL}")
        notify(f"EV {LABEL}: Нет дешёвого 2ч окна в {WINDOW_LABEL} на сегодня. Попробуй завтра.")
        print(f"{ev.STATUS_NO_WINDOW}: no contiguous 2h window in {WINDOW_LABEL}")
        sys.exit(0)

    best_local = best_utc.astimezone(RIGA)
    end_local = best_local + datetime.timedelta(hours=2)
    local_str = best_local.strftime("%Y-%m-%d %H:%M:%S")

    if DRY_RUN:
        print(f"[dry-run] would set input_datetime.ev_charge_start = {local_str}")
        print(f"[dry-run] would clear input_boolean.ev_manual_mode")
        print(f"[dry-run] plan ({LABEL}): {best_local.strftime('%d.%m %H:%M')} -> "
              f"{end_local.strftime('%H:%M')}, avg={avg_price:.4f} EUR/kWh")
        return

    ok, status = ev.ha_post(
        HA, "/api/services/input_datetime/set_datetime",
        {"entity_id": "input_datetime.ev_charge_start", "datetime": local_str}, HDR,
    )
    if not ok:
        ev.log_err(f"set_datetime failed (status={status})")
        print(f"{ev.STATUS_HA_ERROR}: set_datetime status={status}")
        sys.exit(1)

    ok, status = ev.ha_post(
        HA, "/api/services/input_boolean/turn_off",
        {"entity_id": "input_boolean.ev_manual_mode"}, HDR,
    )
    if not ok:
        ev.log_err(f"turn_off ev_manual_mode failed (status={status})")

    if local_str != old_val:
        msg = "\n".join([
            f"🚗 EV {LABEL} запланирована:",
            "  " + best_local.strftime("%d.%m %H:%M") + " → " + end_local.strftime("%H:%M"),
            "  Средн. цена: " + f"{avg_price:.4f}" + " EUR/кВт·ч",
        ])
        notify(msg)

    print(f"{ev.STATUS_OK}: {local_str}, avg={avg_price:.4f} EUR/kWh")


if __name__ == "__main__":
    main()
