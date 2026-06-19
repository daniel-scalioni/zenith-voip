import os
import tempfile
from arq import create_pool
from arq.connections import RedisSettings
from src.config import settings
from src.events.redis_streams import event_bus


S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "")
S3_BUCKET_PREFIX = os.environ.get("S3_BUCKET_PREFIX", "zenith-audio")


async def upload_audio_chunk(ctx, tenant_id: str, call_id: str, channel: str, audio_data: bytes):
    if not S3_ENDPOINT:
        return {"status": "skipped", "reason": "S3 not configured"}

    try:
        import boto3
        from botocore.config import Config

        session = boto3.Session(
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
        )
        s3 = session.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            config=Config(signature_version="s3v4"),
        )

        bucket_name = f"{S3_BUCKET_PREFIX}-{tenant_id}"
        key = f"recordings/{call_id}/{channel}.raw"

        try:
            s3.head_bucket(Bucket=bucket_name)
        except Exception:
            s3.create_bucket(Bucket=bucket_name)

        s3.put_object(Bucket=bucket_name, Key=key, Body=audio_data)

        return {"status": "uploaded", "bucket": bucket_name, "key": key}
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
