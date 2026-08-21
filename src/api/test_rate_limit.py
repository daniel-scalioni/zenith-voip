from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from redis.exceptions import ConnectionError as RedisConnectionError, ResponseError

from src.api import rate_limit


def _make_request(ip: str | None = "203.0.113.5"):
    request = MagicMock()
    request.client = MagicMock(host=ip) if ip is not None else None
    return request


@pytest.mark.asyncio
async def test_allows_request_when_under_threshold(monkeypatch):
    # Arrange
    redis = AsyncMock()
    redis.zcard = AsyncMock(return_value=5)
    monkeypatch.setattr(rate_limit.event_bus, "redis", redis)
    call_next = AsyncMock(return_value="response")
    request = _make_request()

    # Act
    result = await rate_limit.rate_limit_middleware(request, call_next)

    # Assert
    assert result == "response"
    call_next.assert_awaited_once_with(request)


@pytest.mark.asyncio
async def test_blocks_request_when_at_threshold(monkeypatch):
    # Arrange: GAP-03 regressão — estado precisa sobreviver a restart e ser
    # compartilhado entre zenith-api-1/zenith-api-2, não mais um dict local
    redis = AsyncMock()
    redis.zcard = AsyncMock(return_value=rate_limit.RATE_LIMIT_REQUESTS)
    monkeypatch.setattr(rate_limit.event_bus, "redis", redis)
    call_next = AsyncMock()
    request = _make_request()

    # Act / Assert
    with pytest.raises(HTTPException) as exc_info:
        await rate_limit.rate_limit_middleware(request, call_next)

    assert exc_info.value.status_code == 429
    call_next.assert_not_awaited()
    redis.zadd.assert_not_awaited()


@pytest.mark.asyncio
async def test_prunes_expired_entries_before_counting(monkeypatch):
    # Arrange
    redis = AsyncMock()
    redis.zcard = AsyncMock(return_value=0)
    monkeypatch.setattr(rate_limit.event_bus, "redis", redis)
    fixed_now = 1_000_000.0
    monkeypatch.setattr(rate_limit.time, "time", lambda: fixed_now)
    call_next = AsyncMock(return_value="ok")
    request = _make_request()

    # Act
    await rate_limit.rate_limit_middleware(request, call_next)

    # Assert
    redis.zremrangebyscore.assert_awaited_once_with(
        "zenith:ratelimit:203.0.113.5", 0, fixed_now - rate_limit.RATE_LIMIT_WINDOW
    )


@pytest.mark.asyncio
async def test_records_request_and_sets_ttl_after_allowing(monkeypatch):
    # Arrange
    redis = AsyncMock()
    redis.zcard = AsyncMock(return_value=0)
    monkeypatch.setattr(rate_limit.event_bus, "redis", redis)
    call_next = AsyncMock(return_value="ok")
    request = _make_request()

    # Act
    await rate_limit.rate_limit_middleware(request, call_next)

    # Assert
    redis.zadd.assert_awaited_once()
    key = redis.zadd.await_args.args[0]
    assert key == "zenith:ratelimit:203.0.113.5"
    redis.expire.assert_awaited_once_with(key, rate_limit.RATE_LIMIT_WINDOW)


@pytest.mark.asyncio
async def test_uses_unknown_key_when_client_absent(monkeypatch):
    # Arrange
    redis = AsyncMock()
    redis.zcard = AsyncMock(return_value=0)
    monkeypatch.setattr(rate_limit.event_bus, "redis", redis)
    call_next = AsyncMock(return_value="ok")
    request = _make_request(ip=None)

    # Act
    await rate_limit.rate_limit_middleware(request, call_next)

    # Assert
    redis.zremrangebyscore.assert_awaited_once()
    assert redis.zremrangebyscore.await_args.args[0] == "zenith:ratelimit:unknown"


@pytest.mark.asyncio
async def test_fails_open_when_redis_unavailable(monkeypatch):
    # Arrange: rate limiter é defesa em profundidade -- se falhar fechado quando o
    # Redis cai, um blip de infra derruba a API inteira, pior que o problema original.
    # redis.exceptions.ConnectionError NÃO herda do ConnectionError builtin do Python
    # -- usar a exceção real que o cliente redis-py lança.
    redis = AsyncMock()
    redis.zremrangebyscore = AsyncMock(side_effect=RedisConnectionError("redis down"))
    monkeypatch.setattr(rate_limit.event_bus, "redis", redis)
    call_next = AsyncMock(return_value="ok")
    request = _make_request()

    # Act
    result = await rate_limit.rate_limit_middleware(request, call_next)

    # Assert
    assert result == "ok"
    call_next.assert_awaited_once_with(request)


@pytest.mark.asyncio
async def test_does_not_fail_open_for_non_connection_redis_errors(monkeypatch):
    # Arrange: ResponseError (comando malformado, WRONGTYPE etc.) é bug real, não blip
    # de infra -- não deve ser engolido como "Redis indisponível, deixa passar"
    redis = AsyncMock()
    redis.zremrangebyscore = AsyncMock(side_effect=ResponseError("WRONGTYPE"))
    monkeypatch.setattr(rate_limit.event_bus, "redis", redis)
    call_next = AsyncMock()
    request = _make_request()

    # Act / Assert
    with pytest.raises(ResponseError):
        await rate_limit.rate_limit_middleware(request, call_next)
    call_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_different_client_ips_use_isolated_keys(monkeypatch):
    # Arrange
    redis = AsyncMock()
    redis.zcard = AsyncMock(return_value=0)
    monkeypatch.setattr(rate_limit.event_bus, "redis", redis)
    call_next = AsyncMock(return_value="ok")

    # Act
    await rate_limit.rate_limit_middleware(_make_request("10.0.0.1"), call_next)
    await rate_limit.rate_limit_middleware(_make_request("10.0.0.2"), call_next)

    # Assert
    keys = [call.args[0] for call in redis.zremrangebyscore.await_args_list]
    assert keys == ["zenith:ratelimit:10.0.0.1", "zenith:ratelimit:10.0.0.2"]
