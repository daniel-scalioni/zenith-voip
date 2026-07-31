import json
import pytest
from unittest.mock import AsyncMock
from starlette.datastructures import Address
from src.api.websockets import AgentAssistWebSocket


@pytest.fixture
def fake_redis(monkeypatch):
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    monkeypatch.setattr("src.api.websockets.event_bus.redis", redis)
    return redis


def make_ws(host: str = "192.168.1.100", port: int = 54321) -> AsyncMock:
    ws = AsyncMock()
    ws.client = Address(host, port)
    return ws


@pytest.mark.asyncio
async def test_connect_awaits_accept_and_registers_connection_by_call_id(fake_redis):
    # Arrange
    agent_ws = AgentAssistWebSocket()
    mock_ws = make_ws()

    # Act
    await agent_ws.connect("call-001", mock_ws)

    # Assert
    mock_ws.accept.assert_awaited_once()
    assert agent_ws.active_connections["call-001"] == [mock_ws]


@pytest.mark.asyncio
async def test_connect_appends_multiple_connections_under_same_call_id(fake_redis):
    # Arrange
    agent_ws = AgentAssistWebSocket()
    ws_one = make_ws("192.168.1.100", 54321)
    ws_two = make_ws("192.168.1.101", 54322)

    # Act
    await agent_ws.connect("call-002", ws_one)
    await agent_ws.connect("call-002", ws_two)

    # Assert
    assert agent_ws.active_connections["call-002"] == [ws_one, ws_two]


@pytest.mark.asyncio
async def test_disconnect_removes_only_target_connection(fake_redis):
    # Arrange
    agent_ws = AgentAssistWebSocket()
    ws_one = make_ws("192.168.1.100", 54321)
    ws_two = make_ws("192.168.1.101", 54322)
    await agent_ws.connect("call-003", ws_one)
    await agent_ws.connect("call-003", ws_two)

    # Act
    agent_ws.disconnect("call-003", ws_one)

    # Assert
    assert agent_ws.active_connections["call-003"] == [ws_two]


@pytest.mark.asyncio
async def test_disconnect_last_connection_removes_call_id_key(fake_redis):
    # Arrange
    agent_ws = AgentAssistWebSocket()
    mock_ws = make_ws()
    await agent_ws.connect("call-004", mock_ws)

    # Act
    agent_ws.disconnect("call-004", mock_ws)

    # Assert
    assert "call-004" not in agent_ws.active_connections


@pytest.mark.asyncio
async def test_broadcast_delivers_semantically_correct_json_to_all_active_connections(fake_redis):
    # Arrange
    agent_ws = AgentAssistWebSocket()
    ws_one = make_ws("192.168.1.100", 54321)
    ws_two = make_ws("192.168.1.101", 54322)
    await agent_ws.connect("call-005", ws_one)
    await agent_ws.connect("call-005", ws_two)
    ws_one.send_text.reset_mock()
    ws_two.send_text.reset_mock()
    event = {"type": "alert", "alert_type": "silence", "message": "Silêncio prolongado", "severity": "warning"}

    # Act
    await agent_ws.broadcast("call-005", event)

    # Assert
    payload_one = json.loads(ws_one.send_text.await_args.args[0])
    payload_two = json.loads(ws_two.send_text.await_args.args[0])
    assert payload_one == event
    assert payload_two == event


@pytest.mark.asyncio
async def test_connect_without_redis_association_emits_session_waiting_linkage(fake_redis):
    # Arrange
    agent_ws = AgentAssistWebSocket()
    mock_ws = make_ws()

    # Act
    await agent_ws.connect("call-006", mock_ws)

    # Assert
    payload = json.loads(mock_ws.send_text.await_args.args[0])
    assert payload["event"] == "session_waiting_linkage"
    assert payload["data"]["agent_uuid"] == "call-006"
    assert "message" in payload["data"]


@pytest.mark.asyncio
async def test_connect_propagates_redis_port_error_leaving_connection_registered(fake_redis):
    """Caracteriza o comportamento atual: não há try/except em connect/_try_auto_link,
    então erro da porta Redis propaga e a conexão já aceita permanece registrada."""
    # Arrange
    agent_ws = AgentAssistWebSocket()
    mock_ws = make_ws()
    fake_redis.get.side_effect = ConnectionError("redis unavailable")

    # Act & Assert
    with pytest.raises(ConnectionError):
        await agent_ws.connect("call-007", mock_ws)

    mock_ws.accept.assert_awaited_once()
    assert agent_ws.active_connections["call-007"] == [mock_ws]
    mock_ws.send_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_broadcast_skips_failed_connection_and_removes_only_stale_one(fake_redis):
    # Arrange
    agent_ws = AgentAssistWebSocket()
    ws_healthy = make_ws("192.168.1.100", 54321)
    ws_failing = make_ws("192.168.1.101", 54322)
    await agent_ws.connect("call-008", ws_healthy)
    await agent_ws.connect("call-008", ws_failing)
    ws_healthy.send_text.reset_mock()
    ws_failing.send_text.reset_mock()
    ws_failing.send_text.side_effect = RuntimeError('Cannot call "send" once a close message has been sent.')
    event = {"type": "alert", "alert_type": "test", "message": "ping", "severity": "info"}

    # Act
    await agent_ws.broadcast("call-008", event)

    # Assert
    payload_healthy = json.loads(ws_healthy.send_text.await_args.args[0])
    assert payload_healthy == event
    assert agent_ws.active_connections["call-008"] == [ws_healthy]


@pytest.mark.asyncio
async def test_broadcast_removes_call_id_key_when_all_connections_fail(fake_redis):
    # Arrange
    agent_ws = AgentAssistWebSocket()
    ws_one = make_ws("192.168.1.100", 54321)
    ws_two = make_ws("192.168.1.101", 54322)
    await agent_ws.connect("call-009", ws_one)
    await agent_ws.connect("call-009", ws_two)
    ws_one.send_text.side_effect = RuntimeError('Cannot call "send" once a close message has been sent.')
    ws_two.send_text.side_effect = RuntimeError('Cannot call "send" once a close message has been sent.')
    event = {"type": "alert", "alert_type": "test", "message": "ping", "severity": "info"}

    # Act
    await agent_ws.broadcast("call-009", event)

    # Assert
    assert "call-009" not in agent_ws.active_connections


@pytest.mark.asyncio
async def test_broadcast_to_unknown_call_id_is_noop(fake_redis):
    # Arrange
    agent_ws = AgentAssistWebSocket()
    event = {"type": "alert", "alert_type": "test", "message": "ping", "severity": "info"}

    # Act
    await agent_ws.broadcast("call-inexistente", event)

    # Assert
    assert agent_ws.active_connections == {}
