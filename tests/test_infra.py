import pytest
import httpx
import redis.asyncio as aioredis
from src.config import settings


@pytest.mark.asyncio
async def test_health_endpoint():
    async with httpx.AsyncClient() as client:
        resp = await client.get("http://fastapi-1:8000/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_readiness_endpoint():
    async with httpx.AsyncClient() as client:
        resp = await client.get("http://fastapi-1:8000/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"


@pytest.mark.asyncio
async def test_redis_connection():
    r = aioredis.from_url(settings.REDIS_URL)
    await r.ping()
    await r.aclose()


@pytest.mark.asyncio
async def test_redis_stream_publish():
    r = aioredis.from_url(settings.REDIS_URL)
    msg_id = await r.xadd("test:stream", {"ping": "pong"})
    assert msg_id is not None
    await r.xdel("test:stream", msg_id)
    await r.delete("test:stream")
    await r.aclose()


@pytest.mark.asyncio
async def test_ollama_health():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{settings.OLLAMA_URL}/api/tags")
        assert resp.status_code == 200
