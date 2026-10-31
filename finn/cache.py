"""A tiny disk cache. Filings never change once filed, so most entries live forever.

Keys are hashed so any string (a URL, a prompt) is a valid key. Values are JSON,
or raw bytes for PDFs.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable

from .config import CACHE_DIR


def _path(namespace: str, key: str, ext: str) -> Path:
    digest = hashlib.sha256(key.encode()).hexdigest()[:24]
    folder = CACHE_DIR / namespace
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{digest}.{ext}"


def get_json(namespace: str, key: str, max_age: float | None = None) -> Any | None:
    p = _path(namespace, key, "json")
    if not p.exists():
        return None
    if max_age is not None and time.time() - p.stat().st_mtime > max_age:
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def put_json(namespace: str, key: str, value: Any) -> None:
    _path(namespace, key, "json").write_text(json.dumps(value, ensure_ascii=False))


def cached_json(namespace: str, key: str, fn: Callable[[], Any], max_age: float | None = None) -> Any:
    hit = get_json(namespace, key, max_age)
    if hit is not None:
        return hit
    value = fn()
    if value is not None:
        put_json(namespace, key, value)
    return value


def cached_bytes(namespace: str, key: str, fn: Callable[[], bytes | None]) -> bytes | None:
    p = _path(namespace, key, "bin")
    if p.exists():
        return p.read_bytes()
    data = fn()
    if data:
        p.write_bytes(data)
    return data


HOUR = 3600
DAY = 24 * HOUR
