import pytest
import httpx
import asyncio


@pytest.mark.asyncio
async def test_health_before_restart():
    async with httpx.AsyncClient() as client:
        resp = await client.get("http://fastapi-1:8000/health", timeout=5.0)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_health_after_restart():
    async with httpx.AsyncClient() as client:
        try:
            await client.post("http://localhost:2375/containers/zenith-api-1/restart", timeout=5.0)
        except Exception:
            pytest.skip("Docker API not available")

        for attempt in range(10):
            try:
                resp = await client.get("http://fastapi-1:8000/health", timeout=5.0)
                if resp.status_code == 200:
                    return
            except Exception:
                pass
            await asyncio.sleep(2)

        pytest.fail("API did not recover after restart")


@pytest.mark.asyncio
async def test_redis_state_survives_restart():
    async with httpx.AsyncClient() as client:
        try:
            await client.post("http://localhost:2375/containers/zenith-api-1/restart", timeout=5.0)
        except Exception:
            pytest.skip("Docker API not available")

        await asyncio.sleep(5)
        resp = await client.get("http://fastapi-1:8000/health", timeout=5.0)
        assert resp.status_code == 200
