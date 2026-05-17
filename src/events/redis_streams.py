import json
from typing import Any
from redis.asyncio import Redis
from src.config import settings


class RedisEventBus:
    def __init__(self, redis_url: str = settings.REDIS_URL):
        self.redis = Redis.from_url(redis_url)

    async def publish(self, stream: str, event: dict[str, Any]) -> str:
        return await self.redis.xadd(stream, {k: json.dumps(v) if not isinstance(v, (str, bytes)) else v for k, v in event.items()})

    async def consume(self, stream: str, group: str, consumer: str, count: int = 1, block: int = 5000) -> list[tuple[str, dict]]:
        messages = await self.redis.xreadgroup(group, consumer, {stream: ">"}, count=count, block=block)
        if not messages:
            return []
        result = []
        for stream_name, entries in messages:
            for msg_id, data in entries:
                decoded = {k.decode(): v.decode() if isinstance(v, bytes) else v for k, v in data.items()}
                result.append((msg_id.decode() if isinstance(msg_id, bytes) else msg_id, decoded))
        return result

    async def ack(self, stream: str, group: str, msg_id: str):
        await self.redis.xack(stream, group, msg_id)

    async def create_group(self, stream: str, group: str):
        try:
            await self.redis.xgroup_create(stream, group, mkstream=True)
        except Exception:
            pass

    async def close(self):
        await self.redis.aclose()


event_bus = RedisEventBus()
