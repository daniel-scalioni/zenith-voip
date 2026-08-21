import asyncio
import logging
import os
import re
import tempfile
import time
import wave
from datetime import datetime, timezone
from pathlib import Path

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import delete, select, text
from sqlalchemy.exc import SQLAlchemyError
from smb.smb_structs import OperationFailure

from src.audio.recording_lifecycle import (
    LeaseBusyError,
    acquire_lease,
    locked_call_directory,
    release_lease,
    renew_lease,
)
from src.config import settings
from src.database.database import get_tenant_db
from src.database.models import Call, Transcript
from src.services.stt_whisper import WhisperCppSTT
from src.utils.telemetry import (
    observe_transcript_latency,
    record_lease_failure,
    record_transcript_failure,
    record_transcript_success,
    set_transcript_queue_size,
)
from src.workers.recording_consumers import mark_consumed
from src.workers.smb_sync import (
    SMBBackupStrategy,
    build_remote_directory,
    build_remote_name,
    load_transfer_log,
)


logger = logging.getLogger(__name__)
TRANSCRIPT_QUEUE_NAME = "zenith:transcript"
MIN_WAV_BYTES = 44
_cycle_lock = asyncio.Lock()
_TENANT_ID_PATTERN = re.compile(r"^[a-z0-9_]+$")
_REMOTE_WAV_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}-[A-Za-z0-9._-]+\.wav$"
)


def _tenant_schema(tenant_id: str) -> str:
    if not _TENANT_ID_PATTERN.fullmatch(tenant_id):
        raise ValueError("invalid tenant directory")
    return f"tenant_{tenant_id}"


def is_ready_call(call_dir: str | Path) -> bool:
    directory = Path(call_dir)
    try:
        if any(path.is_file() for path in directory.glob("*.tmp*")):
            return False
        return all(_is_supported_wav(directory / f"{channel}.wav") for channel in ("tx", "rx"))
    except (OSError, EOFError, wave.Error):
        return False


def _is_supported_wav(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size <= MIN_WAV_BYTES:
        return False
    with wave.open(str(path), "rb") as audio:
        return (
            audio.getcomptype() == "NONE"
            and audio.getnchannels() == 1
            and audio.getsampwidth() == 2
            and audio.getframerate() == 16_000
            and audio.getnframes() > 0
        )


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as audio:
        return audio.getnframes() / audio.getframerate()


def normalize_segments(
    channel: str,
    segments: list[dict],
    *,
    chunk_offset: float,
    chunk_index: int,
) -> list[dict]:
    speaker = {"tx": "atendente", "rx": "cliente"}[channel]
    normalized = []
    for segment in segments:
        content = str(segment.get("text", "")).strip()
        if not content:
            continue
        start = max(0.0, float(segment.get("start", 0.0))) + chunk_offset
        end = max(float(segment.get("end", start - chunk_offset)), start - chunk_offset) + chunk_offset
        confidence = min(1.0, max(0.0, float(segment.get("confidence", 0.0))))
        normalized.append({
            "channel": channel,
            "speaker": speaker,
            "text": content,
            "confidence": confidence,
            "start_time": start,
            "end_time": end,
            "is_final": True,
            "extra_metadata": {"chunk_index": chunk_index},
        })
    return normalized


def _format_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def render_markdown(metadata: dict, segments: list[dict]) -> str:
    started_at = metadata["started_at"]
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    lines = [
        f"# Transcrição — {metadata['call_id']}",
        "",
        (
            f"> Tenant: {metadata['tenant_id']} · Data: {started_at:%Y-%m-%d %H:%M:%S} · "
            f"Origem: {metadata['caller_number']} → Destino: {metadata['callee_number']}"
        ),
        "",
    ]
    for segment in sorted(segments, key=lambda item: (item["start_time"], item.get("channel", ""))):
        text_content = str(segment.get("text", "")).strip()
        if not text_content:
            continue
        speaker = str(segment["speaker"]).capitalize()
        lines.extend([
            (
                f"[{_format_timestamp(segment['start_time'])} → "
                f"{_format_timestamp(segment['end_time'])}] **{speaker}** "
                f"(confidence: {segment['confidence']:.2f})"
            ),
            text_content,
            "",
        ])
    if not segments:
        lines.extend(["_Nenhuma fala detectada._", ""])
    return "\n".join(lines).rstrip() + "\n"


def build_transcript_remote_names(tenant_id: str, metadata: dict) -> tuple[str, str, str]:
    started_at = metadata["started_at"]
    arguments = (
        started_at,
        metadata["call_id"],
        metadata.get("caller_number"),
        metadata.get("callee_number"),
    )
    return (
        build_remote_directory(tenant_id, started_at),
        build_remote_name(*arguments, extension="md"),
        build_remote_name(*arguments, extension="md", include_collision_suffix=True),
    )


def load_smb_audio_reference(
    log_path: str | Path, tenant_id: str, call_id: str
) -> dict | None:
    item = load_transfer_log(log_path).get(f"{tenant_id}/{call_id}")
    if (
        not isinstance(item, dict)
        or item.get("status") != "done"
        or item.get("tenant_id") != tenant_id
        or item.get("call_id") != call_id
    ):
        return None
    remote_name = item.get("remote_name")
    if (
        not isinstance(remote_name, str)
        or "/" in remote_name
        or "\\" in remote_name
        or not _REMOTE_WAV_PATTERN.fullmatch(remote_name)
    ):
        return None
    try:
        started_at = datetime.fromisoformat(item["started_at"])
    except (KeyError, TypeError, ValueError):
        return None
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    return {
        "remote_dir": build_remote_directory(tenant_id, started_at),
        "remote_wav_name": remote_name,
        "remote_md_name": remote_name[:-4] + ".md",
    }


async def chunk_audio(source: Path, output_dir: Path, channel: str) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    pattern = output_dir / f"{channel}-%04d.wav"
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-v", "error",
        "-i", str(source),
        "-map", "0:a:0",
        "-c:a", "copy",
        "-f", "segment",
        "-segment_time", str(settings.TRANSCRIPT_CHUNK_SECONDS),
        "-reset_timestamps", "1",
        str(pattern),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await process.communicate()
    except asyncio.CancelledError:
        if process.returncode is None:
            process.kill()
            await process.wait()
        raise
    if process.returncode != 0:
        raise RuntimeError(f"ffmpeg chunk failed: {stderr.decode(errors='replace')[-500:]}")
    chunks = sorted(output_dir.glob(f"{channel}-*.wav"))
    if not chunks:
        raise RuntimeError(f"ffmpeg did not create chunks for {channel}")
    return chunks


async def transcribe_pair(call_dir: Path, strategy: WhisperCppSTT | None = None) -> list[dict]:
    stt = strategy or WhisperCppSTT(
        model_path=settings.WHISPER_CPP_MODEL_PATH,
        binary=settings.WHISPER_CPP_BINARY,
        timeout_seconds=settings.TRANSCRIPT_CALL_TIMEOUT_SECONDS,
        language=settings.WHISPER_CPP_LANGUAGE,
        threads=settings.WHISPER_CPP_THREADS,
    )
    segments = []
    with tempfile.TemporaryDirectory(prefix="zenith-transcript-") as temporary:
        output_dir = Path(temporary)
        for channel in ("tx", "rx"):
            chunks = await chunk_audio(call_dir / f"{channel}.wav", output_dir, channel)
            chunk_offset = 0.0
            for index, chunk in enumerate(chunks):
                result = await stt.transcribe(await asyncio.to_thread(chunk.read_bytes))
                if result.get("error"):
                    raise RuntimeError(f"whisper failed for {channel}: {result['error']}")
                segments.extend(normalize_segments(
                    channel,
                    result.get("segments", []),
                    chunk_offset=chunk_offset,
                    chunk_index=index,
                ))
                chunk_offset += await asyncio.to_thread(_wav_duration, chunk)
    return sorted(segments, key=lambda item: (item["start_time"], item["channel"]))


async def resolve_call_metadata(tenant_id: str, call_id: str) -> dict | None:
    async for session in get_tenant_db(_tenant_schema(tenant_id)):
        result = await session.execute(select(Call).where(Call.call_id == call_id))
        call = result.scalar_one_or_none()
        if call is None:
            return None
        started_at = call.started_at or datetime.now(timezone.utc)
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        return {
            "tenant_id": tenant_id,
            "call_id": call_id,
            "database_id": call.id,
            "started_at": started_at,
            "caller_number": call.caller_number or "desconhecido",
            "callee_number": call.callee_number or "desconhecido",
        }
    return None


async def transcripts_exist(tenant_id: str, database_id) -> bool:
    async for session in get_tenant_db(_tenant_schema(tenant_id)):
        result = await session.execute(
            select(Transcript.id).where(Transcript.call_id == database_id).limit(1)
        )
        return result.scalar_one_or_none() is not None
    return False


async def persist_segments(tenant_id: str, database_id, call_id: str, segments: list[dict]) -> None:
    async for session in get_tenant_db(_tenant_schema(tenant_id)):
        await session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:call_id))"), {"call_id": call_id})
        await session.execute(delete(Transcript).where(Transcript.call_id == database_id))
        session.add_all(Transcript(call_id=database_id, **segment) for segment in segments)
        await session.flush()


async def markdown_exists(publisher, remote_dir: str, base_name: str, collision_name: str) -> bool:
    names = await publisher.list_names(remote_dir)
    return base_name in names or collision_name in names


async def _lease_heartbeat(call_dir: Path, owner: str) -> None:
    while True:
        await asyncio.sleep(settings.RECORDING_LEASE_HEARTBEAT_SECONDS)
        if not renew_lease(call_dir, "transcription", owner):
            record_lease_failure("transcription")
            raise OSError("transcription lease lost")


async def _process_owned_call(publisher, call_dir: Path, metadata: dict) -> dict:
    if not is_ready_call(call_dir):
        return {"status": "pending", "reason": "audio_incomplete"}
    remote_dir = metadata["remote_dir"]
    remote_names = await publisher.list_names(remote_dir)
    if metadata["remote_wav_name"] not in remote_names:
        return {"status": "pending", "reason": "audio_remote_missing"}
    remote_name = metadata["remote_md_name"]
    segments = await transcribe_pair(call_dir)
    await persist_segments(
        metadata["tenant_id"], metadata["database_id"], metadata["call_id"], segments
    )
    content = render_markdown(metadata, segments)
    descriptor, local_name = tempfile.mkstemp(prefix="zenith-transcript-", suffix=".md")
    local_path = Path(local_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as target:
            target.write(content)
        published = await publisher.publish(local_path, remote_dir, remote_name, remote_name)
    finally:
        local_path.unlink(missing_ok=True)
    mark_consumed(call_dir, "transcription")
    return {"status": "done", "segments": len(segments), **published}


async def process_call(publisher, call_dir: str | Path, metadata: dict) -> dict:
    directory = Path(call_dir)
    try:
        lease = acquire_lease(directory, "transcription", metadata["call_id"])
    except LeaseBusyError:
        return {"status": "pending", "reason": "already_processing"}
    heartbeat = asyncio.create_task(_lease_heartbeat(directory, lease.owner))
    operation = asyncio.create_task(_process_owned_call(publisher, directory, metadata))
    try:
        done, _ = await asyncio.wait(
            {operation, heartbeat},
            timeout=settings.TRANSCRIPT_CALL_TIMEOUT_SECONDS,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if not done:
            return {"status": "pending", "reason": "timeout"}
        if heartbeat in done:
            operation.cancel()
            await asyncio.gather(operation, return_exceptions=True)
            heartbeat.result()
        return await operation
    finally:
        operation.cancel()
        heartbeat.cancel()
        await asyncio.gather(operation, heartbeat, return_exceptions=True)
        release_lease(directory, "transcription", lease.owner)


async def _run_cycle(_ctx) -> dict:
    if not settings.TRANSCRIPT_ENABLED:
        return {"status": "disabled"}
    started = time.monotonic()
    publisher = SMBBackupStrategy()
    call_dirs = sorted(path for path in Path(settings.RECORDINGS_PATH).glob("*/*") if path.is_dir())
    set_transcript_queue_size(len(call_dirs))
    completed = 0
    failed = 0
    for call_dir in call_dirs:
        if not is_ready_call(call_dir):
            continue
        tenant_id = call_dir.parent.name
        call_id = call_dir.name
        try:
            reference = load_smb_audio_reference(
                settings.SMB_TRANSFER_LOG_PATH, tenant_id, call_id
            )
            if reference is None:
                continue
            metadata = await resolve_call_metadata(tenant_id, call_id)
            if metadata is None:
                continue
            metadata.update(reference)
            remote_dir = reference["remote_dir"]
            remote_name = reference["remote_md_name"]
            remote_names = await publisher.list_names(remote_dir)
            if reference["remote_wav_name"] not in remote_names:
                continue
            if (
                (call_dir / ".consumed-transcription").is_file()
                and remote_name in remote_names
            ):
                continue
            if await transcripts_exist(tenant_id, metadata["database_id"]):
                if remote_name not in remote_names:
                    result = await process_call(publisher, call_dir, metadata)
                else:
                    if not (call_dir / ".consumed-transcription").is_file():
                        with locked_call_directory(call_dir):
                            if is_ready_call(call_dir):
                                mark_consumed(call_dir, "transcription")
                    continue
            else:
                result = await process_call(publisher, call_dir, metadata)
            if result["status"] == "done":
                completed += 1
                record_transcript_success()
            elif result.get("reason") not in {"already_processing", "audio_incomplete"}:
                failed += 1
                record_transcript_failure(result.get("reason", "pending"))
        except (
            ConnectionError, OSError, RuntimeError, TimeoutError, ValueError,
            SQLAlchemyError, OperationFailure,
        ) as exc:
            failed += 1
            record_transcript_failure(type(exc).__name__)
            logger.warning(
                "transcription_pending tenant_id=%s call_id=%s error=%s",
                tenant_id, call_id, type(exc).__name__,
            )
    observe_transcript_latency(time.monotonic() - started)
    return {"status": "completed", "calls_seen": len(call_dirs), "completed": completed, "failed": failed}


async def run_transcript_cycle(ctx):
    if _cycle_lock.locked():
        return {"status": "already_running"}
    async with _cycle_lock:
        return await _run_cycle(ctx)


class WorkerSettings:
    queue_name = TRANSCRIPT_QUEUE_NAME
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 1
    job_timeout = settings.TRANSCRIPT_CYCLE_TIMEOUT_SECONDS
    cron_jobs = [
        cron(
            run_transcript_cycle,
            minute=set(range(0, 60, settings.TRANSCRIPT_SYNC_INTERVAL_MINUTES)),
            run_at_startup=False,
            unique=True,
            job_id="zenith-transcript-cycle",
        )
    ]
    functions = [run_transcript_cycle]
