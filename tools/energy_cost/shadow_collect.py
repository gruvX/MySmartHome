#!/usr/bin/env python3
"""Shadow energy/cost collector (SHADOW — does NOT touch production cost_month_*).

Every run appends ONE JSON snapshot line to /config/shadow_snapshots.jsonl:
  timestamp, Nord Pool prices (EUR/kWh), and per-device cumulative energy (kWh) +
  availability. Interval cost (Δ kWh × price of that 15-min interval) is derived
  OFFLINE from consecutive snapshots at checkpoint time — so the raw 15-min data
  is preserved and cannot be lost to recorder purge.

Read-only against HA (localhost REST). Missing/unavailable -> null, never 0.
Deployed to /config/shadow_energy_collect.py, run every 15 min by an automation.
"""
import json, os, sys, urllib.request
from datetime import datetime, timezone

BASE = "http://127.0.0.1:8123"
LEDGER = "/config/shadow_snapshots.jsonl"
SECRETS = "/config/local_secrets.json"

PRICE = {
    "current": "sensor.nord_pool_lv_current_price",
    "next": "sensor.nord_pool_lv_next_price",
    "lowest": "sensor.nord_pool_lv_lowest_price",
    "highest": "sensor.nord_pool_lv_highest_price",
}
ENERGY = {
    "ev": "sensor.ev_charger_energy",
    "boiler_ten": "sensor.boiler_total_energy",
    "towel": "sensor.terarium_total_energy",
    "aquarium": "sensor.akvarium_svet_total_energy",
    "recirc": "sensor.cherepakha_total_energy",
    "hydrophore": "sensor.zigbee_plug_2_total_energy",
    "bed_backlight": "sensor.zigbee_plug_total_energy",
    "tv": "sensor.75_qled_energy",
}
CONTEXT = {  # extra context, not billed
    "boiler_mode": "sensor.boiler_mode",
    "ev_status": "sensor.ev_charger_status",
}

def token():
    m = __import__("re").search(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}", open(SECRETS).read())
    return m.group(0) if m else ""

def num(v):
    try:
        if v in (None, "", "unknown", "unavailable"):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None

def main():
    tok = token()
    if not tok:
        print("ERROR: no HA_TOKEN", file=sys.stderr); return 1
    req = urllib.request.Request(BASE + "/api/states", headers={"Authorization": "Bearer " + tok})
    states = {s["entity_id"]: s for s in json.load(urllib.request.urlopen(req, timeout=15))}
    def slot(eid):
        s = states.get(eid)
        if not s:
            return {"v": None, "avail": False, "raw": "missing"}
        avail = s["state"] not in ("unknown", "unavailable", "")
        return {"v": num(s["state"]), "avail": avail, "raw": s["state"],
                "updated": s.get("last_updated")}
    snap = {
        "ts": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "price": {k: {**slot(e),
                      "start": (states.get(e, {}).get("attributes", {}) or {}).get("start")}
                  for k, e in PRICE.items()},
        "energy_kwh": {k: slot(e) for k, e in ENERGY.items()},
        "context": {k: (states.get(e, {}) or {}).get("state") for k, e in CONTEXT.items()},
    }
    # atomic-ish append
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(snap, ensure_ascii=False) + "\n")
    try:
        os.chmod(LEDGER, 0o644)
    except OSError:
        pass
    n_avail = sum(1 for v in snap["energy_kwh"].values() if v["avail"])
    print(f"OK snapshot ts={snap['ts']} price={snap['price']['current']['v']} energy_avail={n_avail}/{len(ENERGY)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
