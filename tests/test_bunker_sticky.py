"""Contrato do BunkerWeb real e integração opt-in de afinidade."""

import os
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
import pytest


COMPOSE_PATH = Path(__file__).parents[1] / "docker-compose.app.yml"


def _bunkerweb_environment() -> dict[str, str]:
    lines = COMPOSE_PATH.read_text(encoding="utf-8").splitlines()
    in_service = False
    in_environment = False
    environment = {}
    for line in lines:
        if line == "  bunkerweb:":
            in_service = True
            continue
        if in_service and line.startswith("  ") and not line.startswith("    "):
            break
        if not in_service:
            continue
        if line == "    environment:":
            in_environment = True
            continue
        if in_environment and line.startswith("    ") and not line.startswith("      "):
            in_environment = False
        if in_environment and line.startswith("      - "):
            key, value = line.removeprefix("      - ").split("=", 1)
            environment[key] = value
    return environment


def _integration_url() -> str:
    url = os.getenv("BUNKERWEB_URL", "")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        pytest.skip("integração exige BUNKERWEB_URL HTTP(S) explícita")
    return url


def test_t070_compose_configures_real_reverse_proxy_and_sticky_key():
    # Arrange
    environment = _bunkerweb_environment()

    # Act
    proxy_enabled = environment.get("USE_REVERSE_PROXY")
    upstream = environment.get("REVERSE_PROXY_HOST", "")
    sticky_enabled = environment.get("STICKY_SESSION")
    sticky_name = environment.get("STICKY_SESSION_NAME")

    # Assert
    assert proxy_enabled == "yes"
    assert upstream.startswith("http://fastapi-") and upstream.endswith(":8000")
    assert sticky_enabled == "yes"
    assert sticky_name == "X-Call-ID"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t070_real_response_preserves_cookie_and_backend_affinity():
    # Arrange
    endpoint = _integration_url()
    path = os.getenv("BUNKERWEB_AFFINITY_PATH", "/health")
    backend_header = os.getenv("BUNKERWEB_UPSTREAM_HEADER", "X-Upstream-ID")
    call_id = f"t070-{uuid4().hex}"

    # Act
    async with httpx.AsyncClient(base_url=endpoint, follow_redirects=True) as client:
        first = await client.get(path, headers={"X-Call-ID": call_id}, timeout=10)
        first.raise_for_status()
        first_backend = first.headers.get(backend_header)
        first_cookies = dict(client.cookies)
        second = await client.get(path, headers={"X-Call-ID": call_id}, timeout=10)
        second.raise_for_status()
        second_backend = second.headers.get(backend_header)
        second_cookies = dict(client.cookies)
    observed_backends = set()
    for _index in range(12):
        distinct_call_id = f"t070-{uuid4().hex}"
        async with httpx.AsyncClient(base_url=endpoint, follow_redirects=True) as client:
            response = await client.get(
                path, headers={"X-Call-ID": distinct_call_id}, timeout=10
            )
            response.raise_for_status()
            observed_backends.add(response.headers.get(backend_header))

    # Assert
    assert first_backend, f"resposta não expôs {backend_header}"
    assert second_backend == first_backend
    assert first_cookies, "BunkerWeb não emitiu cookie de afinidade"
    assert second_cookies == first_cookies
    assert None not in observed_backends
    assert len(observed_backends) >= 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t070_real_proxy_error_is_never_reported_as_success():
    # Arrange
    endpoint = _integration_url()
    missing_path = f"/__t070_missing__/{uuid4().hex}"

    # Act
    async with httpx.AsyncClient(base_url=endpoint, follow_redirects=False) as client:
        response = await client.get(missing_path, timeout=10)

    # Assert
    assert response.status_code >= 400
    with pytest.raises(httpx.HTTPStatusError):
        response.raise_for_status()
