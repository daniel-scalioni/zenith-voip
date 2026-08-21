import asyncio
import logging
import os
from pathlib import Path

from arq import create_pool
from arq.connections import RedisSettings

from src.audio.recording_lifecycle import LeaseBusyError, acquire_lease, release_lease, renew_lease
from src.config import settings
from src.utils.telemetry import record_lease_failure


logger = logging.getLogger(__name__)
_FFMPEG_INPUT_ARGS = ["-f", "s16le", "-ar", "16000", "-ac", "1"]
UPLOAD_QUEUE_NAME = "zenith:audio-upload"


async def _convert_to_wav(raw_path: str) -> str:
    raw = Path(raw_path)
    wav = raw.with_suffix(".wav")
    temporary = raw.with_name(f"{raw.stem}.tmp.wav")
    temporary.unlink(missing_ok=True)
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", *_FFMPEG_INPUT_ARGS, "-i", str(raw),
        "-codec:a", "pcm_s16le", "-ar", "16000", "-ac", "1", str(temporary),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await proc.communicate()
    except asyncio.CancelledError:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
        temporary.unlink(missing_ok=True)
        raise
    if proc.returncode != 0:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            f"ffmpeg falhou (exit {proc.returncode}): "
            f"{stderr.decode(errors='replace')[-500:]}"
        )
    os.replace(temporary, wav)
    return str(wav)


async def _conversion_heartbeat(call_dir: Path, owner: str) -> None:
    while True:
        await asyncio.sleep(settings.RECORDING_LEASE_HEARTBEAT_SECONDS)
        if not renew_lease(call_dir, "conversion", owner):
            record_lease_failure("conversion")
            raise OSError("conversion lease renewal failed")


async def _convert_while_lease_is_valid(raw: Path, heartbeat: asyncio.Task) -> str:
    conversion = asyncio.create_task(_convert_to_wav(str(raw)))
    done, _ = await asyncio.wait({conversion, heartbeat}, return_when=asyncio.FIRST_COMPLETED)
    if heartbeat in done:
        conversion.cancel()
        await asyncio.gather(conversion, return_exceptions=True)
        heartbeat.result()
    return await conversion


async def upload_audio_chunk(
    ctx,
    tenant_id: str,
    call_id: str,
    channel: str | None = None,
    audio_data: bytes | None = None,
):
    # Compatibilidade de função registrada: payload binário antigo não é regravado.
    return {"status": "legacy_payload_ignored", "tenant_id": tenant_id, "call_id": call_id}


async def upload_recording_batch(
    ctx,
    tenant_id: str,
    call_id: str,
    recordings: list[dict] | None = None,
):
    call_dir = Path(settings.RECORDINGS_PATH) / tenant_id / call_id
    if not call_dir.is_dir():
        return []
    try:
        lease = acquire_lease(call_dir, "conversion", call_id)
    except LeaseBusyError:
        return [{"status": "already_processing"}]
    results = []
    heartbeat = asyncio.create_task(_conversion_heartbeat(call_dir, lease.owner))
    try:
        for channel in ("tx", "rx"):
            raw = call_dir / f"{channel}.raw"
            if not raw.is_file():
                continue
            try:
                output = await _convert_while_lease_is_valid(raw, heartbeat)
                results.append({"status": "uploaded", "path": output, "channel": channel})
            except OSError as exc:
                if heartbeat.done():
                    logger.error("conversion_lease_lost tenant_id=%s call_id=%s", tenant_id, call_id)
                    return [{"status": "lease_lost"}]
                logger.exception("wav_conversion_failed tenant_id=%s call_id=%s channel=%s", tenant_id, call_id, channel)
                results.append({
                    "status": "uploaded_raw_only",
                    "path": str(raw),
                    "channel": channel,
                    "conversion_error": str(exc),
                })
            except Exception as exc:
                logger.exception("wav_conversion_failed tenant_id=%s call_id=%s channel=%s", tenant_id, call_id, channel)
                results.append({
                    "status": "uploaded_raw_only",
                    "path": str(raw),
                    "channel": channel,
                    "conversion_error": str(exc),
                })
        return results
    finally:
        heartbeat.cancel()
        await asyncio.gather(heartbeat, return_exceptions=True)
        release_lease(call_dir, "conversion", lease.owner)


class WorkerSettings:
    queue_name = UPLOAD_QUEUE_NAME
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    functions = [upload_audio_chunk, upload_recording_batch]


_pool = None


async def _get_pool():
    global _pool
    if _pool is None:
        _pool = await create_pool(
            RedisSettings.from_dsn(settings.REDIS_URL),
            default_queue_name=UPLOAD_QUEUE_NAME,
        )
    return _pool


async def enqueue_recording_upload(tenant_id: str, call_id: str):
    pool = await _get_pool()
    await pool.enqueue_job(
        "upload_recording_batch",
        tenant_id,
        call_id,
        _job_id=f"recording-upload:{tenant_id}:{call_id}",
    )
