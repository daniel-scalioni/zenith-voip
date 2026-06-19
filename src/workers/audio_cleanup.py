import asyncio
import time
from datetime import datetime, timedelta, timezone
from arq import cron
from src.config import settings
from src.utils.telemetry import record_cleanup_deleted, record_cleanup_error, observe_cleanup_duration


async def cleanup_tenant_bucket(ctx, tenant_id: str) -> dict:
    if not settings.S3_ENDPOINT:
        return {"tenant": tenant_id, "status": "skipped", "reason": "S3 not configured"}

    start = time.monotonic()
    deleted_count = 0
    bytes_freed = 0

    try:
        import boto3
        from botocore.config import Config

        session = boto3.Session(
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
        )
        s3 = session.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            config=Config(signature_version="s3v4"),
        )

        bucket_name = f"{settings.S3_BUCKET_PREFIX}-{tenant_id}"
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.AUDIO_RETENTION_DAYS)

        try:
            s3.head_bucket(Bucket=bucket_name)
        except Exception:
            return {"tenant": tenant_id, "status": "skipped", "reason": "Bucket not found"}

        paginator = s3.get_paginator("list_objects_v2")
        objects_to_delete = []

        for page in paginator.paginate(Bucket=bucket_name):
            if "Contents" not in page:
                continue
            for obj in page["Contents"]:
                last_mod = obj["LastModified"].replace(tzinfo=timezone.utc)
                if last_mod < cutoff:
                    objects_to_delete.append({"Key": obj["Key"]})
                    bytes_freed += obj.get("Size", 0)

                    if len(objects_to_delete) >= 1000:
                        s3.delete_objects(Bucket=bucket_name, Delete={"Objects": objects_to_delete})
                        deleted_count += len(objects_to_delete)
                        objects_to_delete = []

        if objects_to_delete:
            s3.delete_objects(Bucket=bucket_name, Delete={"Objects": objects_to_delete})
            deleted_count += len(objects_to_delete)

        duration = time.monotonic() - start
        record_cleanup_deleted(tenant_id, deleted_count, bytes_freed)
        observe_cleanup_duration(duration)

        return {
            "tenant": tenant_id,
            "status": "ok",
            "deleted": deleted_count,
            "bytes_freed": bytes_freed,
            "duration_seconds": round(duration, 2),
        }

    except Exception as e:
        record_cleanup_error(tenant_id)
        return {"tenant": tenant_id, "status": "failed", "error": str(e)}


async def run_cleanup(ctx):
    from src.database.database import engine
    from sqlalchemy import text

    if not settings.S3_ENDPOINT:
        return {"status": "skipped", "reason": "S3 not configured"}

    results = []

    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT schema_name FROM public.tenants WHERE status = 'active'"))
        tenants = [row[0] for row in result]

    for schema_name in tenants:
        tenant_id = schema_name.replace("tenant_", "", 1)
        res = await cleanup_tenant_bucket(ctx, tenant_id)
        results.append(res)

    return {"status": "completed", "tenants_processed": len(results), "results": results}


class WorkerSettings:
    redis_settings = settings.REDIS_URL
    cron_jobs = [
        cron(run_cleanup, hour=3, minute=0, run_on_startup=False),
    ]
    functions = [run_cleanup, cleanup_tenant_bucket]
