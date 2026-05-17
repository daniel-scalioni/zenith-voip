from redis.asyncio import Redis
from src.config import settings
import json


class POPsCache:
    def __init__(self):
        self.redis = Redis.from_url(settings.REDIS_URL)
        self.cache_ttl = 3600

    async def get_pops(self, tenant_id: str) -> list[dict]:
        key = f"pops:{tenant_id}"
        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)
        return []

    async def set_pops(self, tenant_id: str, pops: list[dict]):
        key = f"pops:{tenant_id}"
        await self.redis.setex(key, self.cache_ttl, json.dumps(pops))

    async def invalidate(self, tenant_id: str):
        await self.redis.delete(f"pops:{tenant_id}")

    async def close(self):
        await self.redis.aclose()


pops_cache = POPsCache()
