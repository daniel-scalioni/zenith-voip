import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.events.redis_streams import RedisEventBus


@pytest.fixture
def redis_mock():
    return AsyncMock()


@pytest.fixture
def bus(redis_mock):
    with patch.object(RedisEventBus, "__init__", lambda self, **kw: None):
        b = RedisEventBus.__new__(RedisEventBus)
        b.redis = redis_mock
        return b


@pytest.mark.asyncio
async def test_publish_adds_event_to_stream(bus, redis_mock):
    # Arrange
    redis_mock.xadd = AsyncMock(return_value="1-0")
    event = {"call_id": "abc", "event": "started"}

    # Act
    result = await bus.publish("call:events", event)

    # Assert
    assert result == "1-0"
    redis_mock.xadd.assert_awaited_once()
    args = redis_mock.xadd.await_args
    assert args.args[0] == "call:events"


@pytest.mark.asyncio
async def test_publish_serializes_non_string_values(bus, redis_mock):
    # Arrange
    redis_mock.xadd = AsyncMock(return_value="1-0")
    event = {"count": 42, "nested": {"key": "val"}, "plain": "text"}

    # Act
    await bus.publish("stream", event)

    # Assert
    sent = redis_mock.xadd.await_args.kwargs
    data = sent.get("mapping", sent.get(1, {}))
    if not data:
        data = redis_mock.xadd.await_args.args[1] if len(redis_mock.xadd.await_args.args) > 1 else {}
    assert data.get("count") == "42" or data.get("count") == 42


@pytest.mark.asyncio
async def test_consume_returns_empty_list_when_no_messages(bus, redis_mock):
    # Arrange
    redis_mock.xreadgroup = AsyncMock(return_value=[])

    # Act
    result = await bus.consume("stream", "group", "consumer")

    # Assert
    assert result == []


@pytest.mark.asyncio
async def test_consume_decodes_messages(bus, redis_mock):
    # Arrange
    redis_mock.xreadgroup = AsyncMock(
        return_value=[
            (
                b"stream",
                [
                    (b"1-0", {b"call_id": b"abc", b"event": b"started"}),
                    (b"2-0", {b"call_id": b"def", b"event": b"ended"}),
                ],
            )
        ]
    )

    # Act
    result = await bus.consume("stream", "group", "consumer", count=2)

    # Assert
    assert len(result) == 2
    assert result[0] == ("1-0", {"call_id": "abc", "event": "started"})
    assert result[1] == ("2-0", {"call_id": "def", "event": "ended"})


@pytest.mark.asyncio
async def test_consume_handles_partial_entries(bus, redis_mock):
    # Arrange
    redis_mock.xreadgroup = AsyncMock(
        return_value=[(b"stream", [(b"1-0", {b"key": b"val"})])]
    )

    # Act
    result = await bus.consume("stream", "group", "consumer", count=1)

    # Assert
    assert len(result) == 1
    assert result[0][1] == {"key": "val"}


@pytest.mark.asyncio
async def test_ack_delegates_to_xack(bus, redis_mock):
    # Arrange
    redis_mock.xack = AsyncMock(return_value=1)

    # Act
    await bus.ack("stream", "group", "1-0")

    # Assert
    redis_mock.xack.assert_awaited_once_with("stream", "group", "1-0")


@pytest.mark.asyncio
async def test_consume_propagates_redis_error(bus, redis_mock):
    # Arrange
    redis_mock.xreadgroup = AsyncMock(side_effect=Exception("connection lost"))

    # Act / Assert
    with pytest.raises(Exception, match="connection lost"):
        await bus.consume("stream", "group", "consumer")


@pytest.mark.asyncio
async def test_publish_propagates_redis_error(bus, redis_mock):
    # Arrange
    redis_mock.xadd = AsyncMock(side_effect=Exception("timeout"))

    # Act / Assert
    with pytest.raises(Exception, match="timeout"):
        await bus.publish("stream", {"key": "val"})


@pytest.mark.asyncio
async def test_create_group_delegates_to_xgroup_create(bus, redis_mock):
    # Arrange
    redis_mock.xgroup_create = AsyncMock()

    # Act
    await bus.create_group("stream", "group")

    # Assert
    redis_mock.xgroup_create.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_group_ignores_existing_group_error(bus, redis_mock):
    # Arrange
    redis_mock.xgroup_create = AsyncMock(side_effect=Exception("BUSYGROUP"))

    # Act
    await bus.create_group("stream", "group")

    # Assert
    assert redis_mock.xgroup_create.await_count == 1


@pytest.mark.asyncio
async def test_close_delegates_to_aclose(bus, redis_mock):
    # Arrange
    redis_mock.aclose = AsyncMock()

    # Act
    await bus.close()

    # Assert
    redis_mock.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_consume_with_block_zero_returns_empty(bus, redis_mock):
    # Arrange
    redis_mock.xreadgroup = AsyncMock(return_value=[])

    # Act
    result = await bus.consume("stream", "group", "consumer", block=0)

    # Assert
    assert result == []
