"""App diagnostic logs: a paired phone uploads its own log (Ich -> Diagnose ->
"Protokoll an die Anlage senden"), so "my phone did not ring" can be traced without
a cable. Stored under /data/app-logs, newest MAX_PER_DEVICE per device."""
from __future__ import annotations

import re
import time
from pathlib import Path

from backend.voicemail_paths import data_dir

MAX_BYTES = 2 * 1024 * 1024
MAX_PER_DEVICE = 10
_NAME = re.compile(r"^ext\d{1,6}-dev\d{1,9}-\d{8}-\d{6}\.log$")


def logs_dir() -> Path:
    return data_dir() / "app-logs"


def save(ext_number: int, device_id: int, text: str, header: str, now: float | None = None) -> str:
    """Writes the log (header + text, cut to MAX_BYTES from the end) and prunes old ones."""
    d = logs_dir()
    d.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now if now is not None else time.time()))
    name = f"ext{ext_number}-dev{device_id}-{stamp}.log"
    body = text.encode("utf-8", "replace")
    if len(body) > MAX_BYTES:
        body = body[-MAX_BYTES:]  # the newest lines matter
    (d / name).write_bytes(header.encode("utf-8", "replace") + b"\n" + body)
    own = sorted(d.glob(f"ext{ext_number}-dev{device_id}-*.log"))
    for old in own[:-MAX_PER_DEVICE]:
        old.unlink(missing_ok=True)
    return name


def listing() -> list[dict]:
    d = logs_dir()
    if not d.is_dir():
        return []
    files = sorted((p for p in d.iterdir() if _NAME.match(p.name)), key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"name": p.name, "size": p.stat().st_size, "mtime": p.stat().st_mtime} for p in files]


def path_of(name: str) -> Path | None:
    """Only names this module wrote (no path traversal)."""
    if not _NAME.match(name):
        return None
    p = logs_dir() / name
    return p if p.is_file() else None
