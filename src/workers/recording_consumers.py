import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


_CONSUMER_RE = re.compile(r"^[a-z0-9_-]+$")


def _marker(call_dir: str | Path, consumer: str) -> Path:
    if not _CONSUMER_RE.fullmatch(consumer):
        raise ValueError(f"Nome de consumidor inválido: {consumer}")
    return Path(call_dir) / f".consumed-{consumer}"


def mark_consumed(call_dir: str | Path, consumer: str) -> Path:
    marker = _marker(call_dir, consumer)
    marker.parent.mkdir(parents=True, exist_ok=True)
    temp = marker.with_name(f".{marker.name}.new-{uuid.uuid4().hex}")
    try:
        temp.write_text(json.dumps({
            "version": 1,
            "consumer": consumer,
            "consumed_at": datetime.now(timezone.utc).isoformat(),
        }, sort_keys=True), encoding="utf-8")
        os.replace(temp, marker)
    finally:
        temp.unlink(missing_ok=True)
    return marker


def is_fully_consumed(call_dir: str | Path, required: Iterable[str]) -> bool:
    consumers = list(required)
    return bool(consumers) and all(_marker(call_dir, consumer).is_file() for consumer in consumers)
