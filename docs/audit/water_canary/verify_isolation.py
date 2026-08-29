#!/usr/bin/env python
"""verify_isolation.py — prove the water canary package references ZERO production
entities / real device service calls.

Scans every file in this package directory (docs/audit/water_canary/) EXCEPT
this script itself, and asserts there are NO occurrences of forbidden production
identifiers. Exits non-zero (and prints each offending line) if any are found.

Run:  python docs/audit/water_canary/verify_isolation.py
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

PKG_DIR = os.path.dirname(os.path.abspath(__file__))
SELF = os.path.basename(__file__)

# --- Forbidden literal substrings (real entity ids) -------------------------
FORBIDDEN_LITERALS = [
    "switch.voda_kran_switch_1",          # real water valve
    "switch.zigbee_plug_2_socket_1",      # real hydrophore plug
    "binary_sensor.vannaia_moisture",     # real moisture sensors
    "binary_sensor.garazh_moisture",
    "binary_sensor.kukhnia_moisture",
    "binary_sensor.water_sensor_4_moisture",
    "input_boolean.security_armed",       # real security flag
    "input_boolean.ha_startup_grace",     # real grace flag
    "input_boolean.tuya_reconnect_grace", # real grace flag
    "notify.telegram_owner",               # real Telegram notifier
    "telegram_bot.",                       # real Telegram service
    "100000000",                          # real Telegram chat id
    "/leak_confirm",                      # real production callbacks
    "/moisture_false_alarm",
    "/siren_off",
]

# --- Forbidden regex patterns (real device domains / service calls) ---------
# Any *_moisture binary_sensor, any siren.*, any real security.* reference,
# and real device service calls on prod domains.
FORBIDDEN_PATTERNS = [
    (r"binary_sensor\.\w*moisture",        "real moisture binary_sensor reference"),
    (r"\bsiren\.\w+",                       "siren service/entity"),
    (r"\bsecurity_armed\b",                 "security_armed reference"),
    (r"\bswitch\.turn_o(n|ff)\b",           "real switch.turn_on/off service call"),
    (r"\bclimate\.\w+",                     "climate service/entity"),
    (r"\bselect\.select_option\b",          "select.select_option (alarm volume) call"),
    (r"\bnumber\.set_value\b",              "number.set_value (alarm time) call"),
    (r"\bnumber\.alarm_time\b",             "alarm_time entity"),
    (r"\bselect\.alarm_volume\b",           "alarm_volume entity"),
]


def scan_files():
    files = []
    for name in sorted(os.listdir(PKG_DIR)):
        path = os.path.join(PKG_DIR, name)
        if not os.path.isfile(path):
            continue
        if name == SELF:
            continue
        files.append(path)
    return files


def main():
    files = scan_files()
    if not files:
        print("ISOLATION CHECK: FAIL — no package files found to scan.")
        return 2

    violations = []
    for path in files:
        rel = os.path.relpath(path, PKG_DIR)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                lines = fh.readlines()
        except (UnicodeDecodeError, OSError):
            # binary / unreadable file -> skip content check (no text to match)
            continue
        for lineno, line in enumerate(lines, 1):
            for lit in FORBIDDEN_LITERALS:
                if lit in line:
                    violations.append((rel, lineno, f"literal '{lit}'", line.rstrip()))
            for pat, desc in FORBIDDEN_PATTERNS:
                if re.search(pat, line):
                    violations.append((rel, lineno, desc, line.rstrip()))

    print("=" * 72)
    print("WATER CANARY — ISOLATION VERIFICATION")
    print("=" * 72)
    print(f"Package dir : {PKG_DIR}")
    print(f"Files scanned: {', '.join(os.path.relpath(f, PKG_DIR) for f in files)}")
    print(f"Forbidden literals: {len(FORBIDDEN_LITERALS)} | patterns: {len(FORBIDDEN_PATTERNS)}")
    print("-" * 72)

    if violations:
        print(f"RESULT: FAIL — {len(violations)} production reference(s) found:\n")
        for rel, lineno, what, text in violations:
            print(f"  {rel}:{lineno}  [{what}]")
            print(f"      > {text}")
        print("\nISOLATION CHECK: FAIL")
        return 1

    print("RESULT: PASS — 0 production references.")
    print("  - no real valve (switch.voda_kran_switch_1)")
    print("  - no real moisture binary_sensor")
    print("  - no siren.* / security_armed")
    print("  - no real device service calls (switch/climate/select/number) or Telegram")
    print("\nISOLATION CHECK: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
