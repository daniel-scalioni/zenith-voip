import os

import httpx
import pytest


def _bunkerweb_url() -> str:
    return os.environ.get("BUNKERWEB_URL", "http://bunkerweb:80")


@pytest.fixture
def bunkerweb_url() -> str:
    return _bunkerweb_url()


@pytest.fixture
def require_bunkerweb_url() -> str:
    url = os.environ.get("BUNKERWEB_URL")

    if not url:
        pytest.skip("BUNKERWEB_URL não definida: teste de integração requer BunkerWeb real acessível")

    return url


class TestUnitStickyForwarding:
    """Testes unitários sem rede, usando httpx.MockTransport para provar o contrato de encaminhamento."""

    @pytest.mark.asyncio
    async def test_forwards_x_call_id_header(self, bunkerweb_url):
        # Arrange
        received_headers = {}

        def handler(request: httpx.Request) -> httpx.Response:
            received_headers.update(request.headers)
            return httpx.Response(200, json={"status": "ok"})

        transport = httpx.MockTransport(handler)

        # Act
        async with httpx.AsyncClient(transport=transport, base_url=bunkerweb_url) as client:
            resp = await client.get("/health", headers={"X-Call-ID": "test-call-001"})

        # Assert
        assert resp.status_code == 200
        assert received_headers.get("x-call-id") == "test-call-001"

    @pytest.mark.asyncio
    async def test_raises_explicit_error_on_http_failure(self, bunkerweb_url):
        # Arrange
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(502, json={"error": "bad gateway"})

        transport = httpx.MockTransport(handler)

        # Act
        async with httpx.AsyncClient(transport=transport, base_url=bunkerweb_url) as client:
            resp = await client.get("/health", headers={"X-Call-ID": "test-call-002"})

        # Assert
        assert resp.status_code == 502
        with pytest.raises(httpx.HTTPStatusError):
            resp.raise_for_status()

    @pytest.mark.asyncio
    async def test_raises_explicit_error_on_connection_failure(self, bunkerweb_url):
        # Arrange
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        transport = httpx.MockTransport(handler)

        # Act / Assert
        async with httpx.AsyncClient(transport=transport, base_url=bunkerweb_url) as client:
            with pytest.raises(httpx.ConnectError):
                await client.get("/health", headers={"X-Call-ID": "test-call-003"})


@pytest.mark.integration
class TestIntegrationBunkerWeb:
    """Testes reais opt-in: exigem BUNKERWEB_URL apontando para uma instância BunkerWeb acessível."""

    @pytest.mark.asyncio
    async def test_bunkerweb_health(self, require_bunkerweb_url):
        # Arrange
        client = httpx.AsyncClient(base_url=require_bunkerweb_url)

        # Act
        async with client:
            resp = await client.get("/health", timeout=10.0)

        # Assert
        assert resp.status_code in (200, 302)

    @pytest.mark.asyncio
    async def test_sticky_session_header(self, require_bunkerweb_url):
        # Arrange
        client = httpx.AsyncClient(base_url=require_bunkerweb_url)
        headers = {"X-Call-ID": "test-call-001"}

        # Act
        async with client:
            resp = await client.get("/health", headers=headers, timeout=10.0)

        # Assert
        assert resp.status_code in (200, 302)

    @pytest.mark.asyncio
    async def test_bunker_reverse_proxy(self, require_bunkerweb_url):
        # Arrange
        client = httpx.AsyncClient(base_url=require_bunkerweb_url)

        # Act
        async with client:
            resp = await client.get("/health", headers={"Host": "zenith.local"}, timeout=10.0)

        # Assert
        assert resp.status_code == 200
