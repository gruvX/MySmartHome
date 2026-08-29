#!/usr/bin/env python3
# EV best 2h charging window finder — Elering API (15-min LV prices)
# Runnable standalone: HA invokes `python3 /config/ev_best2h.py`.
# Shared logic lives in ev_common.py (must be deployed alongside this file).
import sys
import datetime

sys.stdout.reconfigure(encoding="utf-8")

from project_secrets import secret
import ev_common as ev

TOKEN = secret("HA_TOKEN")
HA = secret("HA_BASE_URL", "http://127.0.0.1:8123")
HDR = ev.make_headers(TOKEN)
TG = secret("HA_NOTIFY_ENTITY")

RIGA = ev.RIGA
DRY_RUN = "--dry-run" in sys.argv


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
    if not TOKEN:
        ev.log_err("missing HA_TOKEN")
        sys.exit(2)

    now_utc = datetime.datetime.now(datetime.timezone.utc)

    try:
        old_state = ev.ha_get(HA, "/api/states/input_datetime.ev_charge_start", HDR)
        old_val = old_state["state"]
    except Exception:
        old_val = ""

    try:
        prices = ev.fetch_lv_prices(now_utc)
    except Exception as e:
        ev.log_err(str(e))
        # Dedup/cooldown: one "недоступен" per incident (schedule untouched below).
        ev.notify_elering_failure(notify)
        sys.exit(1)

    # First success after an outage → one recovery notice; silent otherwise.
    ev.notify_elering_recovery(notify)

    best_utc, avg_price = ev.find_best_2h(prices, now_utc)

    if best_utc is None:
        ev.log("No genuine contiguous 2h window found")
        print(f"{ev.STATUS_NO_WINDOW}: no contiguous 2h window")
        sys.exit(0)

    best_local = best_utc.astimezone(RIGA)
    end_local = best_local + datetime.timedelta(hours=2)
    local_str = best_local.strftime("%Y-%m-%d %H:%M:%S")

    if DRY_RUN:
        print(f"[dry-run] would set input_datetime.ev_charge_start = {local_str}")
        print(f"[dry-run] plan: {best_local.strftime('%Y-%m-%d %H:%M')} - "
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

    if local_str != old_val:
        if best_utc > now_utc:
            lines = [
                "EV зарядка запланирована:",
                "  " + best_local.strftime("%Y-%m-%d"),
                "  " + best_local.strftime("%H:%M") + " - " + end_local.strftime("%H:%M") + " (2 часа)",
                "  Средн. цена: " + f"{avg_price:.4f}" + " EUR/kWh",
                "Ручная зарядка: кнопка EV ВКЛ в меню.",
            ]
        else:
            lines = [
                "EV: лучшее 2ч окно (" + best_local.strftime("%H:%M") + ", "
                + f"{avg_price:.4f}" + " EUR/kWh) уже прошло. Завтра обновится."
            ]
        notify("\n".join(lines))

    print(f"{ev.STATUS_OK}: {local_str}, avg={avg_price:.4f} EUR/kWh")


if __name__ == "__main__":
    main()
