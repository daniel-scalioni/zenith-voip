import json
import logging
from unittest.mock import AsyncMock

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError

from src.events.redis_streams import RedisEventBus


@pytest.fixture
def redis_mock():
    redis = AsyncMock()
    redis.xadd = AsyncMock()
    redis.xreadgroup = AsyncMock()
    redis.xack = AsyncMock()
    redis.xgroup_create = AsyncMock()
    redis.aclose = AsyncMock()
    return redis


@pytest.fixture
def bus(redis_mock):
    event_bus = RedisEventBus.__new__(RedisEventBus)
    event_bus.redis = redis_mock
    return event_bus


@pytest.mark.asyncio
async def test_publish_preserves_plain_and_bytes_and_serializes_nested_json(bus, redis_mock):
    # Arrange
    redis_mock.xadd.return_value = "1-0"
    event = {
        "plain": "text",
        "binary": b"frame",
        "nested": {"enabled": True, "items": [1, 2]},
        "count": 42,
    }

    # Act
    result = await bus.publish("call:events", event)

    # Assert
    assert result == "1-0"
    redis_mock.xadd.assert_awaited_once_with(
        "call:events",
        {
            "plain": "text",
            "binary": b"frame",
            "nested": json.dumps({"enabled": True, "items": [1, 2]}),
            "count": json.dumps(42),
        },
    )


@pytest.mark.asyncio
async def test_consume_returns_empty_or_decoded_partial_messages(bus, redis_mock):
    # Arrange
    redis_mock.xreadgroup.side_effect = [
        [],
        [(b"call:events", [(b"1-0", {b"plain": b"text", b"count": b"42"})])],
    ]

    # Act
    empty = await bus.consume("call:events", "workers", "worker-1")
    partial = await bus.consume("call:events", "workers", "worker-1")

    # Assert
    assert empty == []
    assert partial == [("1-0", {"plain": "text", "count": "42"})]


@pytest.mark.asyncio
async def test_ack_delegates_exact_message_identity(bus, redis_mock):
    # Arrange
    redis_mock.xack.return_value = 1

    # Act
    await bus.ack("call:events", "workers", "1-0")

    # Assert
    redis_mock.xack.assert_awaited_once_with("call:events", "workers", "1-0")


@pytest.mark.asyncio
async def test_create_group_ignores_only_busygroup_response(bus, redis_mock):
    # Arrange
    redis_mock.xgroup_create.side_effect = ResponseError(
        "BUSYGROUP Consumer Group name already exists"
    )

    # Act
    await bus.create_group("call:events", "workers")

    # Assert
    redis_mock.xgroup_create.assert_awaited_once_with(
        "call:events", "workers", mkstream=True
    )


@pytest.mark.asyncio
async def test_create_group_propagates_and_logs_network_failure(
    bus,
    redis_mock,
    caplog,
):
    # Arrange
    redis_mock.xgroup_create.side_effect = RedisConnectionError("redis offline")
    caplog.set_level(logging.ERROR, logger="src.events.redis_streams")

    # Act
    with pytest.raises(RedisConnectionError, match="redis offline"):
        await bus.create_group("call:events", "workers")

    # Assert
    assert "redis offline" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["publish", "consume", "ack"])
async def test_stream_operations_propagate_network_failure(
    operation,
    bus,
    redis_mock,
    caplog,
):
    # Arrange
    error = RedisConnectionError("redis offline")
    redis_mock.xadd.side_effect = error
    redis_mock.xreadgroup.side_effect = error
    redis_mock.xack.side_effect = error
    caplog.set_level(logging.ERROR, logger="src.events.redis_streams")

    # Act
    with pytest.raises(RedisConnectionError, match="redis offline"):
        if operation == "publish":
            await bus.publish("call:events", {"event": "started"})
        elif operation == "consume":
            await bus.consume("call:events", "workers", "worker-1")
        else:
            await bus.ack("call:events", "workers", "1-0")

    # Assert
    called = {
        "publish": redis_mock.xadd,
        "consume": redis_mock.xreadgroup,
        "ack": redis_mock.xack,
    }
    called[operation].assert_awaited_once()
    assert "redis offline" in caplog.text
