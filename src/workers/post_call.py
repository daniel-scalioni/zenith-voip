from arq import create_pool
from arq.connections import RedisSettings
from src.events.redis_streams import event_bus
from src.config import settings


async def analyze_sentiment(ctx, call_id: str, transcript: str) -> dict:
    return {"call_id": call_id, "sentiment": "neutral", "score": 0.0}


async def audit_procedure(ctx, call_id: str, transcript: str) -> dict:
    return {"call_id": call_id, "procedures_ok": True, "violations": []}


async def post_call_workflow(ctx, call_id: str, transcript: str) -> dict:
    sentiment = await analyze_sentiment(ctx, call_id, transcript)
    audit = await audit_procedure(ctx, call_id, transcript)

    await event_bus.publish(settings.REDIS_STREAM_POST_CALL, {
        "call_id": call_id,
        "event": "post_call_complete",
        "sentiment": sentiment,
        "audit": audit,
    })

    return {**sentiment, **audit}


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    functions = [post_call_workflow]
    max_jobs = 10
