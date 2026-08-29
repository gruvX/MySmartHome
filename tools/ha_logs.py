#!/usr/bin/env python3
"""Read-only Home Assistant log reader for this box.

Why this exists
---------------
There is no single obvious way to read HA logs on this installation, and every
session used to re-derive it. The access paths, in the order this tool tries
them:

1. ``api``     -- ``GET {HA_BASE_URL}/api/error_log`` with ``HA_TOKEN``.
                  Returns the whole current ``/config/home-assistant.log``.
                  Only answers 200 while the Supervisor core option
                  ``duplicate_log_file`` is true (see 3.); otherwise 404.
2. ``file``    -- SSH + ``cat /config/home-assistant.log`` (and ``.log.1``
                  with ``--rotated``). Same data as 1., works when the HA HTTP
                  API is down. NB: HA rotates this file only at startup and
                  keeps a single backup, so its depth is
                  "current run + previous run", not a time window.
3. ``journal`` -- SSH + Supervisor ``GET http://supervisor/core/logs``
                  (token from ``/run/s6/container_environment/SUPERVISOR_TOKEN``,
                  needs root). This is the persistent systemd journal: it
                  survives restarts and reaches back weeks, but it only carries
                  what HA wrote to stdout.

Everything here is read-only: HTTP GETs and read-only shell commands. No
service is called, no device is touched, nothing is written to the HA box.

Secrets are never printed: every emitted line goes through ``redact()``, which
masks inline URL credentials, bearer tokens, JWTs, bot tokens and any literal
value found in ``local_secrets.json``. The HA log genuinely does contain
credentials (the ecoNET boiler REST resources embed basic-auth in the URL, so
every boiler connection error carries the password), which is exactly why
redaction is unconditional rather than opt-in.

Examples
--------
    python3 tools/ha_logs.py -n 50
    python3 tools/ha_logs.py --level error -n 200
    python3 tools/ha_logs.py --logger tuya
    python3 tools/ha_logs.py --grep "sign invalid" --source journal
    python3 tools/ha_logs.py --top 15 --source journal
    python3 tools/ha_logs.py --top 15 --level error
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
import urllib.error
import urllib.request
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from project_secrets import secret  # noqa: E402

LOG_PATH = "/config/home-assistant.log"
ROTATED_PATH = "/config/home-assistant.log.1"
SUPERVISOR_LOGS = "http://supervisor/core/logs"
TOKEN_FILE = "/run/s6/container_environment/SUPERVISOR_TOKEN"

LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LEVEL_RANK = {name: i for i, name in enumerate(LEVELS)}

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
# A record starts with "2026-08-17 13:09:14.139 LEVEL (Thread) [logger] message".
RECORD_RE = re.compile(
    r"^(?P<ts>\d{4}-\d\d-\d\d[ T]\d\d:\d\d:\d\d(?:\.\d+)?)\s+"
    r"(?P<level>[A-Z]+)\s+"
    r"(?:\((?P<thread>[^)]*)\)\s+)?"
    r"(?:\[(?P<logger>[^\]]+)\]\s*)?"
    r"(?P<msg>.*)$"
)


# --------------------------------------------------------------------------
# redaction
# --------------------------------------------------------------------------

_URL_CREDS_RE = re.compile(r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*://)[^/\s:@]+:[^/\s@]+@")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
_BOT_RE = re.compile(r"\b\d{8,10}:AA[A-Za-z0-9_-]{30,}\b")
_BEARER_RE = re.compile(r"(?i)\b(bearer|token|authorization)\b(\s*[:=]?\s*)(\S{8,})")
_QUERY_SECRET_RE = re.compile(
    r"(?i)\b(password|passwd|pwd|api_?key|secret|access_token|auth)"
    r"(=|%3D)([^&\s\"'<>]{3,})"
)


def _local_secret_values() -> list[tuple[str, str]]:
    """(name, value) pairs from local_secrets.json, longest value first."""
    out: list[tuple[str, str]] = []
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "local_secrets.json")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return out
    if not isinstance(data, dict):
        return out
    for name, value in data.items():
        value = str(value)
        # Short values (ports, usernames, hostnames) are not secrets and
        # blanket-masking them would mangle every line.
        if len(value) >= 8 and not value.isdigit():
            out.append((str(name), value))
    out.sort(key=lambda kv: len(kv[1]), reverse=True)
    return out


_SECRET_VALUES = _local_secret_values()


def redact(text: str) -> str:
    """Mask credentials. Applied to every line this tool prints."""
    for name, value in _SECRET_VALUES:
        if value in text:
            text = text.replace(value, f"<secret:{name}>")
    text = _URL_CREDS_RE.sub(lambda m: m.group("scheme") + "<redacted>:<redacted>@", text)
    text = _JWT_RE.sub("<jwt-redacted>", text)
    text = _BOT_RE.sub("<bot-token-redacted>", text)
    text = _QUERY_SECRET_RE.sub(lambda m: m.group(1) + m.group(2) + "<redacted>", text)
    text = _BEARER_RE.sub(lambda m: m.group(1) + m.group(2) + "<redacted>", text)
    return text


# --------------------------------------------------------------------------
# sources
# --------------------------------------------------------------------------


def fetch_api() -> str:
    base = secret("HA_BASE_URL") or "http://{}:{}".format(
        secret("HA_HOST", ""), secret("HA_PORT", "8123")
    )
    token = secret("HA_TOKEN", required=True)
    req = urllib.request.Request(
        base.rstrip("/") + "/api/error_log", headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def _ssh():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, root)
    from ha_ssh import ssh_connect  # noqa: PLC0415

    return ssh_connect()


def _ssh_read(client, cmd: str) -> str:
    _, out, err = client.exec_command(cmd)
    data = out.read().decode("utf-8", "replace")
    if not data.strip():
        problem = err.read().decode("utf-8", "replace").strip()
        if problem:
            raise RuntimeError(problem.splitlines()[0])
    return data


def fetch_file(rotated: bool = False) -> str:
    client = _ssh()
    try:
        text = _ssh_read(client, f"cat {shlex.quote(LOG_PATH)}")
        if rotated:
            older = _ssh_read(client, f"cat {shlex.quote(ROTATED_PATH)} 2>/dev/null || true")
            text = older + text
        return text
    finally:
        client.close()


def fetch_journal(lines: int) -> str:
    """Supervisor journal for the core container (persistent, survives restarts)."""
    client = _ssh()
    try:
        sudo = secret("HA_SUDO_PASSWORD", required=True)
        inner = (
            f"T=$(cat {TOKEN_FILE}); "
            f'curl -s -m 120 -H "Authorization: Bearer $T" '
            f'"{SUPERVISOR_LOGS}?lines={int(lines)}"'
        )
        cmd = (
            "printf '%s\\n' " + shlex.quote(sudo) + " | sudo -S sh -c " + shlex.quote(inner)
        )
        return _ssh_read(client, cmd)
    finally:
        client.close()


def load(source: str, journal_lines: int, rotated: bool) -> tuple[str, str]:
    """Return (source_used, text). ``auto`` tries api -> file -> journal."""
    order = [source] if source != "auto" else ["api", "file", "journal"]
    problems = []
    for name in order:
        try:
            if name == "api":
                return name, fetch_api()
            if name == "file":
                return name, fetch_file(rotated)
            if name == "journal":
                return name, fetch_journal(journal_lines)
        except Exception as exc:  # noqa: BLE001 - fall through to next source
            problems.append(f"{name}: {type(exc).__name__}: {redact(str(exc))}")
    raise SystemExit("no log source worked:\n  " + "\n  ".join(problems))


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------


class Record:
    __slots__ = ("ts", "level", "logger", "msg", "raw")

    def __init__(self, ts, level, logger, msg, raw):
        self.ts = ts
        self.level = level
        self.logger = logger
        self.msg = msg
        self.raw = raw

    def append(self, line: str) -> None:
        self.raw += "\n" + line
        self.msg += "\n" + line


def parse(text: str) -> list[Record]:
    records: list[Record] = []
    for line in text.splitlines():
        line = ANSI_RE.sub("", line.rstrip("\n"))
        match = RECORD_RE.match(line)
        if match:
            records.append(
                Record(
                    match.group("ts"),
                    match.group("level"),
                    match.group("logger") or "-",
                    match.group("msg"),
                    line,
                )
            )
        elif records:
            records[-1].append(line)  # traceback / continuation
        elif line.strip():
            records.append(Record("", "", "-", line, line))
    return records


_NUM_RE = re.compile(r"\d+")
_HEX_RE = re.compile(r"\b[0-9a-f]{8,}\b", re.IGNORECASE)


def signature(rec: Record) -> str:
    """Collapse a record to a countable shape (numbers/ids normalised)."""
    head = rec.msg.split("\n", 1)[0]
    head = _HEX_RE.sub("<hex>", head)
    head = _NUM_RE.sub("#", head)
    words = head.split()
    return f"[{rec.logger}] " + " ".join(words[:14])


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Read-only HA log reader (never prints secrets).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples\n--------\n")[-1],
    )
    p.add_argument("-n", "--lines", type=int, default=40, help="last N records (default 40)")
    p.add_argument(
        "--level",
        choices=[lv.lower() for lv in LEVELS],
        help="minimum severity to show (e.g. --level error keeps ERROR+CRITICAL)",
    )
    p.add_argument("--only-level", action="store_true", help="match --level exactly")
    p.add_argument("--logger", help="substring match on the logger name, e.g. tuya")
    p.add_argument("--grep", help="substring match anywhere in the record (case-insensitive)")
    p.add_argument(
        "--top",
        nargs="?",
        type=int,
        const=15,
        default=None,
        metavar="N",
        help="summarise the top N recurring records with counts instead of listing them",
    )
    p.add_argument(
        "--source",
        choices=["auto", "api", "file", "journal"],
        default="auto",
        help="where to read from (default auto: api -> file -> journal)",
    )
    p.add_argument(
        "--journal-lines",
        type=int,
        default=50000,
        help="how many journal entries to pull when source is journal (default 50000)",
    )
    p.add_argument(
        "--rotated",
        action="store_true",
        help="with --source file, also read home-assistant.log.1 (previous HA run)",
    )
    p.add_argument("--stats", action="store_true", help="print level/logger counts and exit")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source, text = load(args.source, args.journal_lines, args.rotated)
    records = parse(text)

    if args.level:
        want = args.level.upper()
        if args.only_level:
            records = [r for r in records if r.level == want]
        else:
            floor = LEVEL_RANK[want]
            records = [
                r for r in records if LEVEL_RANK.get(r.level, LEVEL_RANK["CRITICAL"]) >= floor
            ]
    if args.logger:
        needle = args.logger.lower()
        records = [r for r in records if needle in r.logger.lower()]
    if args.grep:
        needle = args.grep.lower()
        records = [r for r in records if needle in r.raw.lower()]

    print(f"# source={source}  records={len(records)}", file=sys.stderr)
    if records:
        print(f"# span {records[0].ts or '?'} .. {records[-1].ts or '?'}", file=sys.stderr)

    if args.stats:
        levels = Counter(r.level or "-" for r in records)
        loggers = Counter(r.logger for r in records)
        print("levels:")
        for lv, count in sorted(levels.items(), key=lambda kv: -kv[1]):
            print(f"  {count:7d}  {lv}")
        print("loggers (top 25):")
        for name, count in loggers.most_common(25):
            print(f"  {count:7d}  {redact(name)}")
        return 0

    if args.top is not None:
        groups: dict[str, list[Record]] = {}
        for rec in records:
            groups.setdefault(signature(rec), []).append(rec)
        ranked = sorted(groups.items(), key=lambda kv: -len(kv[1]))[: args.top]
        print(f"top {len(ranked)} recurring records (of {len(groups)} distinct shapes):")
        for sig, group in ranked:
            first, last = group[0], group[-1]
            print(f"\n  {len(group):6d}x  {first.level:8s} {redact(sig)}")
            print(f"          first {first.ts or '?'}   last {last.ts or '?'}")
            print(f"          e.g. {redact(last.msg.splitlines()[0])[:220]}")
        return 0

    for rec in records[-args.lines :] if args.lines > 0 else records:
        print(redact(rec.raw))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None
