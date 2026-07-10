import os
import asyncio
from arq import create_pool
from arq.connections import RedisSettings
from src.config import settings

# mod_audio_stream envia PCM16 mono 8kHz por canal (ver freeswitch/conf/dialplan/default.xml,
# "uuid_audio_stream ... stereo 8k"). Conversão para mp3 mantém tx/rx separados
# (decisão do usuário: mono por canal, não misturado nem estéreo).
_FFMPEG_INPUT_ARGS = ["-f", "s16le", "-ar", "8000", "-ac", "1"]


async def _convert_to_mp3(raw_path: str) -> str:
    mp3_path = raw_path[: -len(".raw")] + ".mp3"
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", *_FFMPEG_INPUT_ARGS, "-i", raw_path, "-codec:a", "libmp3lame", mp3_path,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou (exit {proc.returncode}): {stderr.decode(errors='replace')[-500:]}")
    return mp3_path


async def upload_audio_chunk(ctx, tenant_id: str, call_id: str, channel: str, audio_data: bytes):
    try:
        call_dir = os.path.join(settings.RECORDINGS_PATH, tenant_id, call_id)
        os.makedirs(call_dir, exist_ok=True)
        raw_path = os.path.join(call_dir, f"{channel}.raw")

        with open(raw_path, "wb") as f:
            f.write(audio_data)
    except Exception as e:
        return {"status": "failed", "error": str(e)}

    try:
        mp3_path = await _convert_to_mp3(raw_path)
        os.remove(raw_path)
        return {"status": "uploaded", "path": mp3_path}
    except Exception as e:
        # Áudio bruto já está salvo — conversão falhou, mas nada foi perdido.
        return {"status": "uploaded_raw_only", "path": raw_path, "conversion_error": str(e)}


async def upload_recording_batch(ctx, tenant_id: str, call_id: str, recordings: list[dict]):
    results = []
    for rec in recordings:
        result = await upload_audio_chunk(
            ctx,
            tenant_id=tenant_id,
            call_id=call_id,
            channel=rec.get("channel", "unknown"),
            audio_data=rec.get("data", b""),
        )
        results.append(result)
    return results


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    functions = [upload_audio_chunk, upload_recording_batch]


_pool = None


async def _get_pool():
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    return _pool


async def enqueue_recording_upload(tenant_id: str, call_id: str, recordings: list[dict]):
    pool = await _get_pool()
    await pool.enqueue_job("upload_recording_batch", tenant_id, call_id, recordings)
