"""Local secret loading helpers.

Values are read from environment variables first, then from a local JSON file.
Do not commit local_secrets.json.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


_CACHE: dict[str, str] | None = None


def _candidate_files() -> list[Path]:
    here = Path(__file__).resolve().parent
    return [
        here / "local_secrets.json",
        Path.cwd() / "local_secrets.json",
        Path("/config/local_secrets.json"),
    ]


def _load_file_secrets() -> dict[str, str]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    data: dict[str, str] = {}
    for path in _candidate_files():
        try:
            if path.exists():
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data.update({str(k): str(v) for k, v in loaded.items()})
        except Exception:
            continue
    _CACHE = data
    return data


def secret(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.environ.get(name) or _load_file_secrets().get(name) or default
    if required and not value:
        raise RuntimeError(f"Missing required secret: {name}")
    return value or ""
