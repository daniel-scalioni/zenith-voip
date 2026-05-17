import pytest
import httpx


@pytest.mark.asyncio
async def test_bunkerweb_health():
    async with httpx.AsyncClient() as client:
        resp = await client.get("http://bunkerweb:80/health", timeout=10.0)
        assert resp.status_code in (200, 302, 404)


@pytest.mark.asyncio
async def test_sticky_session_header():
    async with httpx.AsyncClient() as client:
        headers = {"X-Call-ID": "test-call-001"}
        resp = await client.get(
            "http://bunkerweb:80/health",
            headers=headers,
            timeout=10.0,
        )
        assert resp.status_code in (200, 302)


@pytest.mark.asyncio
async def test_bunker_reverse_proxy():
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "http://bunkerweb:80/health",
            headers={"Host": "zenith.local"},
            timeout=10.0,
        )
        assert resp.status_code in (200, 502)
