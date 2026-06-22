import os
from arq import create_pool
from arq.connections import RedisSettings
from src.config import settings


async def upload_audio_chunk(ctx, tenant_id: str, call_id: str, channel: str, audio_data: bytes):
    try:
        call_dir = os.path.join(settings.RECORDINGS_PATH, tenant_id, call_id)
        os.makedirs(call_dir, exist_ok=True)
        path = os.path.join(call_dir, f"{channel}.raw")

        with open(path, "wb") as f:
            f.write(audio_data)

        return {"status": "uploaded", "path": path}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


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
