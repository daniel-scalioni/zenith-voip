import asyncio
import os
import time
from datetime import datetime, timedelta, timezone
from arq import cron
from src.config import settings
from src.utils.telemetry import record_cleanup_deleted, record_cleanup_error, observe_cleanup_duration


async def cleanup_tenant_bucket(ctx, tenant_id: str) -> dict:
    start = time.monotonic()
    deleted_count = 0
    bytes_freed = 0

    tenant_dir = os.path.join(settings.RECORDINGS_PATH, tenant_id)
    if not os.path.isdir(tenant_dir):
        return {"tenant": tenant_id, "status": "skipped", "reason": "Tenant directory not found"}

    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=settings.AUDIO_RETENTION_DAYS)).timestamp()

        for root, _dirs, files in os.walk(tenant_dir):
            for name in files:
                path = os.path.join(root, name)
                stat = os.stat(path)
                if stat.st_mtime < cutoff:
                    bytes_freed += stat.st_size
                    os.remove(path)
                    deleted_count += 1

                    if deleted_count % 1000 == 0:
                        await asyncio.sleep(0)

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
