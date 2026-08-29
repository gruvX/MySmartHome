#!/usr/bin/env python
"""Scan for obvious secrets.

Default mode scans git-staged files (intended as a pre-commit guard).
``--all`` scans the entire working tree, including git-ignored runtime
files (agent logs, backups, caches), which is where real credentials
tend to accumulate.

Never prints secret values: findings report path, line number, secret
type and a short sha256 fingerprint (first 12 hex chars) only.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys


PATTERNS = [
    (re.compile(r"-----BEGIN " + r"OPENSSH PRIVATE KEY-----"), "private SSH key"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b"), "JWT token"),
    (re.compile(r"\b\d{8,10}:AA[A-Za-z0-9_-]{30,}\b"), "Telegram bot token"),
    (re.compile(r"\bBoiler_\w+_\d{4}\b"), "boiler password"),
    (re.compile(r"\bDUCK_TOKEN\b\s*=\s*['\"][^'\"]+['\"]"), "DuckDNS token assignment"),
    (re.compile(r"\bBOT_TOKEN\b\s*=\s*['\"][^'\"]+['\"]"), "Telegram bot token assignment"),
    (re.compile(r"\bCLIENT_SECRET\b\s*=\s*['\"][^'\"]+['\"]"), "client secret assignment"),
    (re.compile(r"\bpass(?:word|wd)\b\s*[=:]\s*['\"][^'\"]+['\"]", re.IGNORECASE), "password assignment"),
]

IGNORED_WORDS = {
    "paste-home-assistant-token-here",
    "paste-sudo-password-here",
    "paste-tuya-client-secret-here",
    # Dummy tokens used only by the unit tests (never real credentials).
    "123456:TEST-BOT-TOKEN",
    "999:OTHER",
}

# Directories never worth scanning in --all mode.
EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache"}

# Skip obvious binaries by extension (content still guarded by a null-byte check).
BINARY_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".pdf", ".zip",
    ".gz", ".tar", ".7z", ".woff", ".woff2", ".ttf", ".otf", ".mp4", ".mov",
    ".mp3", ".jar", ".so", ".pyc", ".pyo",
}

MAX_BYTES = 5 * 1024 * 1024  # skip very large files (>5 MB)


def fingerprint(value: str) -> str:
    """Short, non-reversible fingerprint of a secret value (never the value)."""
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()[:12]


def scan_content(path: str, content: str, findings: list[str]) -> None:
    for lineno, line in enumerate(content.splitlines(), 1):
        if any(word in line for word in IGNORED_WORDS):
            continue
        for regex, label in PATTERNS:
            match = regex.search(line)
            if match:
                findings.append(f"{path}:{lineno}: {label} [fp={fingerprint(match.group(0))}]")


def staged_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
        capture_output=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def staged_content(path: str) -> str:
    result = subprocess.run(
        ["git", "show", f":{path}"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def iter_all_files(root: str = ".") -> "list[str]":
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for name in filenames:
            if os.path.splitext(name)[1].lower() in BINARY_EXT:
                continue
            yield os.path.join(dirpath, name)


def read_text(path: str) -> str:
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return ""
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError:
        return ""
    if b"\x00" in raw[:4096]:  # binary
        return ""
    return raw.decode("utf-8", "replace")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all",
        action="store_true",
        help="scan the entire working tree (incl. git-ignored runtime files)",
    )
    args = parser.parse_args()

    findings: list[str] = []
    if args.all:
        scope = "working tree"
        for path in iter_all_files("."):
            rel = path[2:] if path.startswith("./") else path
            scan_content(rel, read_text(path), findings)
    else:
        scope = "staged files"
        for path in staged_files():
            content = staged_content(path)
            if content:
                scan_content(path, content, findings)

    if findings:
        print(f"Possible secrets found in {scope}:", file=sys.stderr)
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        return 1

    print(f"No obvious secrets found in {scope}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
