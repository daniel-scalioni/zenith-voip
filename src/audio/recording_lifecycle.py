import asyncio
import fcntl
import json
import os
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.config import settings


LEASE_STAGES = frozenset({"capture", "conversion", "smb", "transcription"})
LIFECYCLE_LOCK_FILE = ".recording-lifecycle.lock"


class LeaseBusyError(RuntimeError):
    pass


@dataclass(frozen=True)
class RecordingLease:
    stage: str
    call_id: str
    owner: str
    expires_at: datetime


@contextmanager
def locked_call_directory(call_dir: str | Path):
    directory = Path(call_dir)
    directory.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(directory / LIFECYCLE_LOCK_FILE, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _lease_path(call_dir: str | Path, stage: str) -> Path:
    if stage not in LEASE_STAGES:
        raise ValueError(f"Estágio de lease inválido: {stage}")
    return Path(call_dir) / f".{stage}-processing"


def _now(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    return current if current.tzinfo else current.replace(tzinfo=timezone.utc)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.new-{uuid.uuid4().hex}")
    try:
        temp.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _write_exclusive(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.new-{uuid.uuid4().hex}")
    try:
        temp.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        os.link(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _acquire_lease_unlocked(
    call_dir: str | Path,
    stage: str,
    call_id: str,
    *,
    owner: str | None = None,
    now: datetime | None = None,
    ttl_seconds: int | None = None,
) -> RecordingLease:
    current = _now(now)
    for active_stage in LEASE_STAGES:
        active = _read(_lease_path(call_dir, active_stage), active_stage)
        if (
            active is not None
            and active.expires_at > current
            and (owner is None or active.owner != owner)
        ):
            raise LeaseBusyError(
                f"Lease {active_stage} já está ativo por outra operação"
            )
    path = _lease_path(call_dir, stage)
    existing = _read(path, stage)
    if existing and existing.expires_at > current:
        if owner is None or existing.owner != owner:
            raise LeaseBusyError(f"Lease {stage} já está ativo")
    elif path.exists():
        path.unlink(missing_ok=True)
    lease = RecordingLease(
        stage=stage,
        call_id=call_id,
        owner=owner or str(uuid.uuid4()),
        expires_at=current + timedelta(seconds=ttl_seconds or settings.RECORDING_LEASE_TTL_SECONDS),
    )
    payload = {
        "version": 1,
        "stage": stage,
        "call_id": call_id,
        "owner": lease.owner,
        "expires_at": lease.expires_at.isoformat(),
    }
    if existing and existing.owner == lease.owner:
        _write(path, payload)
    else:
        try:
            _write_exclusive(path, payload)
        except FileExistsError as exc:
            raise LeaseBusyError(f"Lease {stage} adquirido concorrentemente") from exc
    return lease


def acquire_lease(
    call_dir: str | Path,
    stage: str,
    call_id: str,
    *,
    owner: str | None = None,
    now: datetime | None = None,
    ttl_seconds: int | None = None,
) -> RecordingLease:
    with locked_call_directory(call_dir):
        return _acquire_lease_unlocked(
            call_dir,
            stage,
            call_id,
            owner=owner,
            now=now,
            ttl_seconds=ttl_seconds,
        )


def _read(path: Path, expected_stage: str | None = None) -> RecordingLease | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        stage = payload.get("stage")
        owner = str(payload["owner"])
        call_id = str(payload["call_id"])
        uuid.UUID(owner)
        if (
            payload.get("version") != 1
            or stage not in LEASE_STAGES
            or (expected_stage is not None and stage != expected_stage)
            or not call_id
        ):
            return None
        expires_at = datetime.fromisoformat(payload["expires_at"])
        if expires_at.tzinfo is None:
            return None
        return RecordingLease(stage=stage, call_id=call_id, owner=owner, expires_at=expires_at)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def has_valid_lease(call_dir: str | Path, *, now: datetime | None = None) -> bool:
    current = _now(now)
    for stage in LEASE_STAGES:
        lease = _read(_lease_path(call_dir, stage), stage)
        if lease and lease.expires_at > current:
            return True
    return False


def renew_lease(
    call_dir: str | Path,
    stage: str,
    owner: str,
    *,
    now: datetime | None = None,
    ttl_seconds: int | None = None,
) -> bool:
    with locked_call_directory(call_dir):
        path = _lease_path(call_dir, stage)
        lease = _read(path, stage)
        if lease is None or lease.owner != owner:
            return False
        _acquire_lease_unlocked(
            call_dir,
            stage,
            lease.call_id,
            owner=owner,
            now=now,
            ttl_seconds=ttl_seconds,
        )
        return True


def release_lease(call_dir: str | Path, stage: str, owner: str) -> bool:
    with locked_call_directory(call_dir):
        path = _lease_path(call_dir, stage)
        lease = _read(path, stage)
        if lease is None or lease.owner != owner:
            return False
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False


async def heartbeat_lease(
    call_dir: str | Path,
    stage: str,
    owner: str,
    *,
    interval: float | None = None,
) -> bool:
    delay = settings.RECORDING_LEASE_HEARTBEAT_SECONDS if interval is None else interval
    if delay:
        await asyncio.sleep(delay)
    return renew_lease(call_dir, stage, owner)
