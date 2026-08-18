import asyncio
import hashlib
import io
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path
from typing import Callable

from arq import cron
from arq.connections import RedisSettings
from smb.SMBConnection import SMBConnection
from smb.smb_structs import OperationFailure

from src.config import settings
from src.audio.recording_lifecycle import (
    LeaseBusyError,
    acquire_lease,
    has_valid_lease as lifecycle_has_valid_lease,
    release_lease,
    renew_lease,
)
from src.database.database import get_tenant_db
from src.database.models import Call
from src.services.base import Repository
from src.utils.telemetry import (
    observe_smb_latency,
    record_smb_failure,
    record_smb_success,
    set_smb_conversion_pending,
    set_smb_queue_size,
)
from src.workers.audio_uploader import _convert_to_wav
from src.workers.recording_consumers import mark_consumed

logger = logging.getLogger(__name__)

CHUNK_SIZE = 512 * 1024
SMB_QUEUE_NAME = "zenith:smb-sync"
LEASE_DURATION_SECONDS = settings.RECORDING_LEASE_TTL_SECONDS
LEASE_RENEWAL_SECONDS = settings.RECORDING_LEASE_HEARTBEAT_SECONDS
TRANSFER_TIMEOUT_SECONDS = 30
TRANSFER_LOG_RETENTION_DAYS = 7
RETRY_DELAYS_SECONDS = (1, 2, 4)
_cycle_lock = asyncio.Lock()


class RemoteCollisionError(RuntimeError):
    pass


class SMBConfigurationError(RuntimeError):
    pass


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, reset_seconds: int = 300):
        self.failure_threshold = failure_threshold
        self.reset_seconds = reset_seconds
        self.failures = 0
        self.opened_at: float | None = None

    def allows_request(self, now: float | None = None) -> bool:
        if self.opened_at is None:
            return True
        current = time.monotonic() if now is None else now
        if current - self.opened_at < self.reset_seconds:
            return False
        self.reset()
        return True

    def record_success(self) -> None:
        self.reset()

    def record_failure(self, now: float | None = None) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = time.monotonic() if now is None else now

    def reset(self) -> None:
        self.failures = 0
        self.opened_at = None


_circuit_breaker = CircuitBreaker()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sanitize_segment(value: str | None) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return "desconhecido"
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", normalized)
    return sanitized[:64] or "desconhecido"


def build_remote_directory(tenant_id: str, started_at: datetime) -> str:
    return f"{sanitize_segment(tenant_id)}/{started_at.astimezone(timezone.utc):%Y-%m-%d}"


def build_remote_name(
    started_at: datetime,
    call_id: str,
    caller_number: str | None,
    callee_number: str | None,
    *,
    extension: str = "wav",
    include_collision_suffix: bool = False,
) -> str:
    prefix = started_at.astimezone(timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")
    parts = [
        prefix,
        sanitize_segment(call_id[:6]),
        sanitize_segment(caller_number),
        sanitize_segment(callee_number),
    ]
    if include_collision_suffix:
        parts.append(sanitize_segment(call_id[6:10]))
    safe_extension = re.sub(r"[^A-Za-z0-9]", "", extension).lower()
    if not safe_extension:
        raise ValueError("remote extension must not be empty")
    return "-".join(parts) + f".{safe_extension}"


def load_transfer_log(path: str | Path) -> dict:
    log_path = Path(path)
    if not log_path.exists():
        return {}
    try:
        content = log_path.read_text(encoding="utf-8")
        state = json.loads(content)
        if not isinstance(state, dict):
            raise ValueError("transfer log root must be an object")
        return state
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        suffix = _utc_now().strftime("%Y%m%dT%H%M%S%fZ")
        corrupt_path = log_path.with_name(f"{log_path.name}.corrupt-{suffix}")
        try:
            os.replace(log_path, corrupt_path)
        except OSError:
            logger.exception("Could not preserve corrupt SMB transfer log")
        logger.warning("Recovered corrupt SMB transfer log: %s", type(exc).__name__)
        return {}


def save_transfer_log(path: str | Path, state: dict) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = log_path.with_suffix(log_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_path, log_path)


def prune_transfer_log(
    state: dict,
    retention_days: int = TRANSFER_LOG_RETENTION_DAYS,
    *,
    now: datetime | None = None,
) -> dict:
    cutoff = (now or _utc_now()) - timedelta(days=retention_days)
    result = {}
    for key, item in state.items():
        updated_at = _parse_datetime(item.get("updated_at"))
        if item.get("status") in {"done", "failed"} and updated_at and updated_at < cutoff:
            continue
        result[key] = item
    return result


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def write_lease(
    call_dir: str | Path,
    call_id: str,
    *,
    now: datetime | None = None,
) -> Path:
    lease = acquire_lease(call_dir, "smb", call_id, now=now)
    return Path(call_dir) / ".smb-processing"


def has_valid_lease(call_dir: str | Path, *, now: datetime | None = None) -> bool:
    valid = lifecycle_has_valid_lease(call_dir, now=now)
    if not valid and (Path(call_dir) / ".smb-processing").exists():
        logger.warning("Invalid or expired SMB lease treated as inactive")
    return valid


async def _renew_lease(call_dir: Path, call_id: str, owner: str | None = None) -> None:
    while True:
        await asyncio.sleep(LEASE_RENEWAL_SECONDS)
        try:
            if owner is None:
                write_lease(call_dir, call_id)
            elif not renew_lease(call_dir, "smb", owner):
                raise OSError("lease owner changed")
        except OSError as exc:
            logger.warning(
                "Failed to renew SMB lease call_id=%s error=%s",
                call_id,
                type(exc).__name__,
            )
            raise


class BandwidthLimiter:
    def __init__(
        self,
        megabytes_per_second: float,
        *,
        chunk_size: int = CHUNK_SIZE,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], object] = asyncio.sleep,
    ):
        if megabytes_per_second <= 0:
            raise ValueError("bandwidth limit must be positive")
        self.bytes_per_second = megabytes_per_second * 1024 * 1024
        self.chunk_size = chunk_size
        self.clock = clock
        self.sleep = sleep

    async def store(self, connection, share: str, remote_path: str, source) -> int:
        offset = 0
        started_at = self.clock()
        while True:
            chunk = source.read(self.chunk_size)
            if not chunk:
                break
            call = partial(
                connection.storeFileFromOffset,
                share,
                remote_path,
                io.BytesIO(chunk),
                offset=offset,
                truncate=offset == 0,
                timeout=30,
            )
            await asyncio.to_thread(call)
            offset += len(chunk)
            expected_elapsed = offset / self.bytes_per_second
            delay = expected_elapsed - (self.clock() - started_at)
            if delay > 0:
                await self.sleep(delay)
        return offset


def resolve_remote_name(
    base_name: str,
    collision_name: str,
    local_sha256: str,
    remote_sha256: Callable[[str], str | None],
) -> str:
    base_sha = remote_sha256(base_name)
    if base_sha is None or base_sha == local_sha256:
        return base_name
    collision_sha = remote_sha256(collision_name)
    if collision_sha is None or collision_sha == local_sha256:
        return collision_name
    raise RemoteCollisionError("remote name collision with divergent content")


class SMBBackupStrategy:
    def __init__(self, connection_factory=SMBConnection):
        self.connection_factory = connection_factory
        self.limiter = BandwidthLimiter(settings.SMB_BANDWIDTH_LIMIT_MBS)

    def _connect(self):
        connection = self.connection_factory(
            settings.SMB_USERNAME,
            settings.SMB_PASSWORD,
            settings.SMB_CLIENT_NAME,
            settings.SMB_SERVER_NAME,
            domain=settings.SMB_DOMAIN,
            use_ntlm_v2=settings.SMB_USE_NTLM_V2,
            sign_options=settings.SMB_SIGN_OPTIONS,
            is_direct_tcp=settings.SMB_IS_DIRECT_TCP,
        )
        if not connection.connect(settings.SMB_HOST, settings.SMB_PORT, timeout=10):
            raise ConnectionError("SMB connection rejected")
        return connection

    @staticmethod
    def _join_path(*parts: str) -> str:
        return "/".join(part.strip("/\\") for part in parts if part.strip("/\\"))

    def _ensure_directories(self, connection, remote_dir: str) -> None:
        current = ""
        for segment in remote_dir.split("/"):
            current = self._join_path(current, segment)
            try:
                connection.createDirectory(settings.SMB_SHARE, current, timeout=30)
            except Exception:
                connection.listPath(settings.SMB_SHARE, current, timeout=30)

    def _list_names(self, connection, remote_dir: str) -> set[str]:
        return {
            item.filename
            for item in connection.listPath(settings.SMB_SHARE, remote_dir, timeout=30)
            if item.filename not in {".", ".."}
        }

    def _remote_sha(self, connection, remote_dir: str, name: str) -> str | None:
        if name not in self._list_names(connection, remote_dir):
            return None
        target = io.BytesIO()
        connection.retrieveFile(
            settings.SMB_SHARE,
            self._join_path(remote_dir, name),
            target,
            timeout=30,
        )
        return hashlib.sha256(target.getvalue()).hexdigest()

    async def list_names(self, remote_dir: str) -> set[str]:
        connection = await asyncio.to_thread(self._connect)
        try:
            full_remote_dir = self._join_path(settings.SMB_PATH, remote_dir)
            await asyncio.to_thread(self._ensure_directories, connection, full_remote_dir)
            return await asyncio.to_thread(self._list_names, connection, full_remote_dir)
        finally:
            await asyncio.to_thread(connection.close)

    async def publish(
        self,
        local_path: Path,
        remote_dir: str,
        base_name: str,
        collision_name: str,
    ) -> dict:
        connection = await asyncio.to_thread(self._connect)
        tmp_path = ""
        try:
            full_remote_dir = self._join_path(settings.SMB_PATH, remote_dir)
            await asyncio.to_thread(self._ensure_directories, connection, full_remote_dir)
            local_sha = await asyncio.to_thread(_sha256_file, local_path)
            remote_name = await asyncio.to_thread(
                resolve_remote_name,
                base_name,
                collision_name,
                local_sha,
                lambda name: self._remote_sha(connection, full_remote_dir, name),
            )
            existing_sha = await asyncio.to_thread(
                self._remote_sha, connection, full_remote_dir, remote_name
            )
            if existing_sha == local_sha:
                return {"sha256": local_sha, "remote_name": remote_name, "idempotent": True}

            remote_path = self._join_path(full_remote_dir, remote_name)
            tmp_path = remote_path + ".tmp"
            with local_path.open("rb") as source:
                bytes_written = await self.limiter.store(
                    connection, settings.SMB_SHARE, tmp_path, source
                )
            await verify_remote_temporary_and_rename(
                connection,
                settings.SMB_SHARE,
                tmp_path,
                remote_path,
                local_sha,
            )
            remote_sha = await asyncio.to_thread(
                self._remote_sha, connection, full_remote_dir, remote_name
            )
            if remote_sha != local_sha:
                await asyncio.to_thread(
                    connection.deleteFiles, settings.SMB_SHARE, remote_path, False, 30
                )
                raise OSError("remote checksum mismatch")
            return {
                "sha256": local_sha,
                "remote_name": remote_name,
                "bytes": bytes_written,
                "idempotent": False,
            }
        except Exception:
            if tmp_path:
                try:
                    await asyncio.to_thread(
                        connection.deleteFiles,
                        settings.SMB_SHARE,
                        tmp_path,
                        False,
                        10,
                    )
                except Exception:
                    logger.warning("Could not remove temporary SMB object after failure")
            raise
        finally:
            await asyncio.to_thread(connection.close)

    async def cleanup_remote_temporaries(
        self,
        remote_dir: str,
        expected_names: list[str],
        candidates: dict,
        *,
        now: datetime | None = None,
    ) -> dict:
        current = now or _utc_now()
        connection = await asyncio.to_thread(self._connect)
        try:
            full_remote_dir = self._join_path(settings.SMB_PATH, remote_dir)
            await asyncio.to_thread(self._ensure_directories, connection, full_remote_dir)
            names = await asyncio.to_thread(self._list_names, connection, full_remote_dir)
            updated = {}
            for name in expected_names:
                temporary_name = name + ".tmp"
                if temporary_name not in names:
                    continue
                first_seen = _parse_datetime(candidates.get(temporary_name))
                if first_seen is None:
                    updated[temporary_name] = current.isoformat()
                    continue
                if (current - first_seen).total_seconds() < settings.RECORDING_CLEANUP_ROUND_SECONDS:
                    updated[temporary_name] = first_seen.isoformat()
                    continue
                await asyncio.to_thread(
                    connection.deleteFiles,
                    settings.SMB_SHARE,
                    self._join_path(full_remote_dir, temporary_name),
                    False,
                    30,
                )
            return updated
        finally:
            await asyncio.to_thread(connection.close)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _has_stable_mono_input(call_dir: str | Path) -> bool:
    directory = Path(call_dir)
    return all(
        (directory / f"{channel}.wav").is_file()
        or (directory / f"{channel}.raw").is_file()
        for channel in ("tx", "rx")
    )


async def verify_remote_temporary_and_rename(
    connection,
    share: str,
    temporary_path: str,
    final_path: str,
    expected_sha256: str,
) -> None:
    target = io.BytesIO()
    await asyncio.to_thread(
        connection.retrieveFile,
        share,
        temporary_path,
        target,
        30,
    )
    remote_sha = hashlib.sha256(target.getvalue()).hexdigest()
    if remote_sha != expected_sha256:
        await asyncio.to_thread(
            connection.deleteFiles,
            share,
            temporary_path,
            False,
            30,
        )
        raise OSError("remote temporary checksum mismatch")
    await asyncio.to_thread(connection.rename, share, temporary_path, final_path, 30)


async def ensure_mono_pair(
    call_dir: str | Path,
    *,
    lease_owner: str | None = None,
) -> tuple[Path, Path] | None:
    directory = Path(call_dir)
    needs_conversion = any(
        not (directory / f"{channel}.wav").exists()
        and (directory / f"{channel}.raw").exists()
        for channel in ("tx", "rx")
    )
    if needs_conversion:
        try:
            lease = acquire_lease(
                directory,
                "conversion",
                directory.name,
                owner=lease_owner,
            )
        except LeaseBusyError:
            return None
        try:
            for channel in ("tx", "rx"):
                wav_path = directory / f"{channel}.wav"
                raw_path = directory / f"{channel}.raw"
                if not wav_path.exists() and raw_path.exists():
                    await _convert_to_wav(str(raw_path))
        finally:
            release_lease(directory, "conversion", lease.owner)
    tx_path = directory / "tx.wav"
    rx_path = directory / "rx.wav"
    if not tx_path.exists() or not rx_path.exists():
        return None
    return tx_path, rx_path


async def generate_stereo(tx_path: str | Path, rx_path: str | Path) -> Path:
    tx = Path(tx_path)
    rx = Path(rx_path)
    if not tx.exists() or not rx.exists():
        raise FileNotFoundError("both mono channels are required")
    final_path = tx.parent / "stereo.wav"
    tmp_path = tx.parent / "stereo.tmp.wav"
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-i",
        str(tx),
        "-i",
        str(rx),
        "-filter_complex",
        "[0:a][1:a]amerge=inputs=2[a]",
        "-map",
        "[a]",
        "-ac",
        "2",
        "-ar",
        "16000",
        "-codec:a",
        "pcm_s16le",
        str(tmp_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await process.communicate()
    except asyncio.CancelledError:
        if process.returncode is None:
            process.kill()
            await process.wait()
        tmp_path.unlink(missing_ok=True)
        raise
    if process.returncode != 0:
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"ffmpeg stereo failed (exit {process.returncode}): "
            f"{stderr.decode(errors='replace')[-500:]}"
        )
    os.replace(tmp_path, final_path)
    return final_path


async def _load_call_metadata(tenant_id: str, call_id: str) -> dict | None:
    async for session in get_tenant_db(f"tenant_{tenant_id}"):
        repository = Repository(session, Call)
        matches = await repository.find_by(call_id=call_id)
        if not matches:
            return None
        call = matches[0]
        return {
            "started_at": call.started_at,
            "caller_number": call.caller_number,
            "callee_number": call.callee_number,
        }
    return None


async def resolve_call_metadata(tenant_id: str, call_id: str, call_dir: Path) -> dict:
    metadata = await _load_call_metadata(tenant_id, call_id) or {}
    started_at = metadata.get("started_at")
    if started_at is None:
        started_at = datetime.fromtimestamp(call_dir.stat().st_mtime, tz=timezone.utc)
    elif started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    return {
        "started_at": started_at,
        "caller_number": metadata.get("caller_number") or "desconhecido",
        "callee_number": metadata.get("callee_number") or "desconhecido",
    }


async def _publish_with_retry(strategy, *args):
    delays = RETRY_DELAYS_SECONDS
    for attempt in range(len(delays) + 1):
        try:
            return await strategy.publish(*args)
        except RemoteCollisionError:
            raise
        except (ConnectionError, OSError, TimeoutError):
            if attempt == len(delays):
                raise
            await asyncio.sleep(delays[attempt])


async def _process_call_unbounded(
    strategy,
    tenant_id: str,
    call_id: str,
    call_dir: Path,
    metadata: dict,
    lease_owner: str | None = None,
) -> dict:
    pair = await ensure_mono_pair(call_dir, lease_owner=lease_owner)
    if pair is None:
        set_smb_conversion_pending(1)
        return {"status": "pending", "reason": "mono_pair_incomplete"}
    stereo_path = await generate_stereo(*pair)
    started_at = metadata.get("started_at") or datetime.fromtimestamp(
        call_dir.stat().st_mtime, tz=timezone.utc
    )
    remote_dir = build_remote_directory(tenant_id, started_at)
    base_name = build_remote_name(
        started_at,
        call_id,
        metadata.get("caller_number"),
        metadata.get("callee_number"),
    )
    collision_name = build_remote_name(
        started_at,
        call_id,
        metadata.get("caller_number"),
        metadata.get("callee_number"),
        include_collision_suffix=True,
    )
    candidates = await strategy.cleanup_remote_temporaries(
        remote_dir,
        [base_name, collision_name],
        metadata.get("remote_tmp_candidates", {}),
    )
    if not isinstance(candidates, dict):
        candidates = {}
    try:
        published = await _publish_with_retry(
            strategy, stereo_path, remote_dir, base_name, collision_name
        )
    except Exception as exc:
        exc.remote_tmp_candidates = candidates
        raise
    mark_consumed(call_dir, "smb")
    stereo_path.unlink(missing_ok=True)
    return {"status": "done", "remote_tmp_candidates": candidates, **published}


async def process_call(
    strategy,
    *,
    tenant_id: str,
    call_id: str,
    call_dir: str | Path,
    metadata: dict,
    timeout_seconds: float = TRANSFER_TIMEOUT_SECONDS,
) -> dict:
    directory = Path(call_dir)
    try:
        lease = acquire_lease(directory, "smb", call_id)
    except LeaseBusyError:
        return {"status": "pending", "reason": "already_processing"}
    renewer = asyncio.create_task(_renew_lease(directory, call_id, lease.owner))
    operation = asyncio.create_task(
        _process_call_unbounded(
            strategy,
            tenant_id,
            call_id,
            directory,
            metadata,
            lease.owner,
        )
    )
    try:
        done, _ = await asyncio.wait(
            {operation, renewer}, timeout=timeout_seconds, return_when=asyncio.FIRST_COMPLETED
        )
        if not done:
            logger.warning("SMB backup timed out tenant=%s call_id=%s", tenant_id, call_id)
            return {"status": "pending", "reason": "timeout"}
        if renewer in done:
            operation.cancel()
            await asyncio.gather(operation, return_exceptions=True)
            record_lease_failure("smb")
            return {"status": "pending", "reason": "lease_lost"}
        return await operation
    finally:
        operation.cancel()
        renewer.cancel()
        await asyncio.gather(operation, renewer, return_exceptions=True)
        release_lease(directory, "smb", lease.owner)


async def _run_cycle(_ctx) -> dict:
    if not settings.SMB_ENABLED:
        return {"status": "disabled"}
    if not _circuit_breaker.allows_request():
        return {"status": "circuit_open"}
    started = time.monotonic()
    log_path = Path(settings.SMB_TRANSFER_LOG_PATH)
    state = prune_transfer_log(load_transfer_log(log_path))
    strategy = SMBBackupStrategy()
    call_dirs = sorted(
        path
        for path in Path(settings.RECORDINGS_PATH).glob("*/*")
        if path.is_dir()
    )
    set_smb_queue_size(len(call_dirs))
    completed = 0
    failed = 0
    for call_dir in call_dirs:
        if not _circuit_breaker.allows_request():
            break
        tenant_id = call_dir.parent.name
        call_id = call_dir.name
        key = f"{tenant_id}/{call_id}"
        if state.get(key, {}).get("status") == "done":
            continue
        if lifecycle_has_valid_lease(call_dir) or not _has_stable_mono_input(call_dir):
            continue
        previous = state.get(key, {})
        try:
            metadata = await resolve_call_metadata(tenant_id, call_id, call_dir)
            metadata["remote_tmp_candidates"] = previous.get("remote_tmp_candidates", {})
            result = await process_call(
                strategy,
                tenant_id=tenant_id,
                call_id=call_id,
                call_dir=call_dir,
                metadata=metadata,
            )
            if result.get("reason") in {"already_processing", "mono_pair_incomplete"}:
                continue
            status = result["status"]
            completed += status == "done"
            state[key] = {
                "tenant_id": tenant_id,
                "call_id": call_id,
                "caller_number": metadata["caller_number"],
                "callee_number": metadata["callee_number"],
                "started_at": metadata["started_at"].isoformat(),
                "tx_path": str(call_dir / "tx.wav"),
                "rx_path": str(call_dir / "rx.wav"),
                "stereo_path": str(call_dir / "stereo.wav"),
                "status": status,
                "attempts": previous.get("attempts", 0) + 1,
                "sha256": result.get("sha256"),
                "remote_name": result.get("remote_name"),
                "created_at": previous.get("created_at", _utc_now().isoformat()),
                "transferred_at": _utc_now().isoformat() if status == "done" else None,
                "updated_at": _utc_now().isoformat(),
                "last_error": result.get("reason"),
                "remote_tmp_candidates": result.get("remote_tmp_candidates", {}),
            }
            if status == "done":
                record_smb_success()
                _circuit_breaker.record_success()
            elif result.get("reason") == "timeout":
                record_smb_failure()
                _circuit_breaker.record_failure()
        except RemoteCollisionError as exc:
            failed += 1
            record_smb_failure()
            state[key] = {
                "tenant_id": tenant_id,
                "call_id": call_id,
                "status": "failed",
                "updated_at": _utc_now().isoformat(),
                "last_error": type(exc).__name__,
                "remote_tmp_candidates": getattr(
                    exc, "remote_tmp_candidates", previous.get("remote_tmp_candidates", {})
                ),
            }
        except (ConnectionError, OSError, TimeoutError, RuntimeError, OperationFailure) as exc:
            failed += 1
            _circuit_breaker.record_failure()
            record_smb_failure()
            logger.warning(
                "SMB backup pending tenant=%s call_id=%s error=%s",
                tenant_id,
                call_id,
                type(exc).__name__,
            )
            state[key] = {
                "tenant_id": tenant_id,
                "call_id": call_id,
                "status": "pending",
                "updated_at": _utc_now().isoformat(),
                "last_error": type(exc).__name__,
                "remote_tmp_candidates": getattr(
                    exc, "remote_tmp_candidates", previous.get("remote_tmp_candidates", {})
                ),
            }
        save_transfer_log(log_path, state)
    observe_smb_latency(time.monotonic() - started)
    return {
        "status": "completed",
        "calls_seen": len(call_dirs),
        "completed": completed,
        "failed": failed,
    }


async def run_smb_sync(ctx):
    if _cycle_lock.locked():
        return {"status": "already_running"}
    async with _cycle_lock:
        return await _run_cycle(ctx)


class WorkerSettings:
    queue_name = SMB_QUEUE_NAME
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    cron_jobs = [
        cron(
            run_smb_sync,
            minute=set(range(0, 60, settings.SMB_SYNC_INTERVAL_MINUTES)),
            run_at_startup=False,
            unique=True,
            job_id="zenith-smb-sync-cycle",
        )
    ]
    functions = [run_smb_sync]
