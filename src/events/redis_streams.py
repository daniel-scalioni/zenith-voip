import json
import logging
from typing import Any
from redis.asyncio import Redis
from redis.exceptions import ResponseError
from src.config import settings

logger = logging.getLogger(__name__)


class RedisEventBus:
    def __init__(self, redis_url: str = settings.REDIS_URL):
        self.redis = Redis.from_url(redis_url)

    async def publish(self, stream: str, event: dict[str, Any]) -> str:
        try:
            return await self.redis.xadd(stream, {k: json.dumps(v) if not isinstance(v, (str, bytes)) else v for k, v in event.items()})
        except BaseException as error:
            logger.error("Redis publish failed: %s", error)
            raise

    async def consume(self, stream: str, group: str, consumer: str, count: int = 1, block: int = 5000) -> list[tuple[str, dict]]:
        try:
            messages = await self.redis.xreadgroup(group, consumer, {stream: ">"}, count=count, block=block)
        except BaseException as error:
            logger.error("Redis consume failed: %s", error)
            raise
        if not messages:
            return []
        result = []
        for stream_name, entries in messages:
            for msg_id, data in entries:
                decoded = {k.decode(): v.decode() if isinstance(v, bytes) else v for k, v in data.items()}
                result.append((msg_id.decode() if isinstance(msg_id, bytes) else msg_id, decoded))
        return result

    async def ack(self, stream: str, group: str, msg_id: str):
        try:
            await self.redis.xack(stream, group, msg_id)
        except BaseException as error:
            logger.error("Redis ack failed: %s", error)
            raise

    async def create_group(self, stream: str, group: str):
        try:
            await self.redis.xgroup_create(stream, group, mkstream=True)
        except ResponseError as error:
            if "BUSYGROUP" in str(error):
                return
            logger.error("Redis group creation failed: %s", error)
            raise
        except BaseException as error:
            logger.error("Redis group creation failed: %s", error)
            raise

    async def close(self):
        await self.redis.aclose()


event_bus = RedisEventBus()
