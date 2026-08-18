import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from arq import cron
from arq.connections import RedisSettings

from src.audio.recording_lifecycle import has_valid_lease, locked_call_directory
from src.config import settings
from src.utils.telemetry import (
    observe_cleanup_duration,
    record_cleanup_deleted,
    record_cleanup_error,
    record_temporary_cleanup,
)
from src.workers.recording_consumers import is_fully_consumed


CLEANUP_QUEUE_NAME = "zenith:audio-cleanup"
LOCAL_TEMPORARIES = frozenset({
    "tx.tmp.raw", "rx.tmp.raw", "tx.tmp.wav", "rx.tmp.wav", "stereo.tmp.wav",
})
CANDIDATES_FILE = ".cleanup-candidates.json"
CONSUMABLE_FILES = frozenset({"tx.wav", "rx.wav", "tx.raw", "rx.raw"})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _fingerprint(path: Path) -> dict:
    stat = path.stat()
    return {"inode": stat.st_ino, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def _load_candidates(call_dir: Path) -> dict:
    try:
        value = json.loads((call_dir / CANDIDATES_FILE).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError):
        return {}


def _save_candidates(call_dir: Path, candidates: dict) -> None:
    marker = call_dir / CANDIDATES_FILE
    if not candidates:
        marker.unlink(missing_ok=True)
        return
    temporary = marker.with_name(f".{marker.name}.new-{uuid.uuid4().hex}")
    try:
        temporary.write_text(json.dumps(candidates, sort_keys=True), encoding="utf-8")
        os.replace(temporary, marker)
    finally:
        temporary.unlink(missing_ok=True)


def _delete(path: Path) -> tuple[bool, int]:
    try:
        size = path.stat().st_size
        path.unlink()
        return True, size
    except FileNotFoundError:
        return False, 0


def _cleanup_call_directory(call_dir: Path, cutoff: float, now: datetime) -> tuple[int, int, int, int]:
    with locked_call_directory(call_dir):
        return _cleanup_locked_call_directory(call_dir, cutoff, now)


def _cleanup_locked_call_directory(call_dir: Path, cutoff: float, now: datetime) -> tuple[int, int, int, int]:
    if has_valid_lease(call_dir, now=now):
        # Um lease reaparecido invalida observações feitas antes da atividade atual.
        (call_dir / CANDIDATES_FILE).unlink(missing_ok=True)
        return 0, 0, 0, 0
    deleted = 0
    bytes_freed = 0
    fully_consumed = is_fully_consumed(call_dir, settings.RECORDING_REQUIRED_CONSUMERS)
    candidates = _load_candidates(call_dir)
    next_candidates = {}
    temporary_candidates = 0
    temporary_deleted = 0

    for path in list(call_dir.iterdir()):
        if not path.is_file() or path.name == CANDIDATES_FILE:
            continue
        if path.name in LOCAL_TEMPORARIES:
            temporary_candidates += 1
            try:
                fingerprint = _fingerprint(path)
            except FileNotFoundError:
                continue
            previous = candidates.get(path.name, {})
            if not isinstance(previous, dict):
                previous = {}
            first_seen = previous.get("first_seen")
            same = previous.get("fingerprint") == fingerprint
            try:
                elapsed = (now - datetime.fromisoformat(first_seen)).total_seconds() if first_seen else 0
            except (TypeError, ValueError):
                elapsed = 0
            if same and elapsed >= settings.RECORDING_CLEANUP_ROUND_SECONDS:
                if has_valid_lease(call_dir, now=now):
                    continue
                was_deleted, size = _delete(path)
                bytes_freed += size
                deleted += was_deleted
                temporary_deleted += was_deleted
            else:
                next_candidates[path.name] = {
                    "first_seen": first_seen if same and first_seen else now.isoformat(),
                    "fingerprint": fingerprint,
                }
            continue
        if path.name.startswith(".") or path.name.endswith(".wav.tmp"):
            continue
        try:
            expired = path.stat().st_mtime < cutoff
        except FileNotFoundError:
            continue
        if (fully_consumed and path.name in CONSUMABLE_FILES) or expired:
            was_deleted, size = _delete(path)
            bytes_freed += size
            deleted += was_deleted

    _save_candidates(call_dir, next_candidates)
    return deleted, bytes_freed, temporary_candidates, temporary_deleted


async def cleanup_tenant_bucket(ctx, tenant_id: str) -> dict:
    started = time.monotonic()
    tenant_dir = Path(settings.RECORDINGS_PATH) / tenant_id
    if not tenant_dir.is_dir():
        return {"tenant": tenant_id, "status": "skipped", "reason": "Tenant directory not found"}
    deleted = 0
    bytes_freed = 0
    temporary_candidates = 0
    temporary_deleted = 0
    try:
        now = _utc_now()
        cutoff = (now - timedelta(days=settings.AUDIO_RETENTION_DAYS)).timestamp()
        call_dirs = (path for path in tenant_dir.iterdir() if path.is_dir())
        for index, call_dir in enumerate(call_dirs, 1):
            call_deleted, call_bytes, call_candidates, call_temp_deleted = _cleanup_call_directory(call_dir, cutoff, now)
            deleted += call_deleted
            bytes_freed += call_bytes
            temporary_candidates += call_candidates
            temporary_deleted += call_temp_deleted
            if index % 1000 == 0:
                await asyncio.sleep(0)
        duration = time.monotonic() - started
        record_cleanup_deleted(tenant_id, deleted, bytes_freed)
        record_temporary_cleanup(candidates=temporary_candidates, deleted=temporary_deleted)
        observe_cleanup_duration(duration)
        return {
            "tenant": tenant_id,
            "status": "ok",
            "deleted": deleted,
            "bytes_freed": bytes_freed,
            "temporary_candidates": temporary_candidates,
            "duration_seconds": round(duration, 2),
        }
    except Exception as exc:
        record_cleanup_error(tenant_id)
        return {"tenant": tenant_id, "status": "failed", "error": str(exc)}


async def run_cleanup(ctx):
    from sqlalchemy import text
    from src.database.database import engine

    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT schema_name FROM public.tenants WHERE status = 'active'"))
        tenants = [row[0] for row in result]
    results = []
    for schema_name in tenants:
        results.append(await cleanup_tenant_bucket(ctx, schema_name.replace("tenant_", "", 1)))
    return {"status": "completed", "tenants_processed": len(results), "results": results}


class WorkerSettings:
    queue_name = CLEANUP_QUEUE_NAME
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    cron_jobs = [
        cron(
            run_cleanup,
            minute={0, 15, 30, 45},
            run_at_startup=False,
            unique=True,
            job_id="zenith-audio-cleanup-cycle",
        ),
    ]
    functions = [run_cleanup, cleanup_tenant_bucket]
