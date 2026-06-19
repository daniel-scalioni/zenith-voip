import pytest
from unittest.mock import AsyncMock, patch
from src.api.websockets import AgentAssistWebSocket


@pytest.mark.asyncio
async def test_websocket_session_link_by_ip():
    ws = AgentAssistWebSocket()

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value="4001")

    mock_ws = AsyncMock()
    mock_ws.client = ("192.168.1.100", 54321)

    with patch.object(ws, "active_connections", {}):
        await ws.connect("call-001", mock_ws)

    assert "call-001" in ws.active_connections


@pytest.mark.asyncio
async def test_websocket_disconnect_removes_session():
    ws = AgentAssistWebSocket()
    mock_ws = AsyncMock()
    mock_ws.client = ("192.168.1.100", 54321)

    await ws.connect("call-001", mock_ws)
    assert len(ws.active_connections["call-001"]) == 1

    ws.disconnect("call-001", mock_ws)
    assert "call-001" not in ws.active_connections


@pytest.mark.asyncio
async def test_broadcast_to_multiple_connections():
    ws = AgentAssistWebSocket()
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    await ws.connect("call-002", ws1)
    await ws.connect("call-002", ws2)
    assert len(ws.active_connections["call-002"]) == 2

    await ws.broadcast("call-002", {"type": "test", "data": "hello"})
    ws1.send_text.assert_called_once()
    ws2.send_text.assert_called_once()


@pytest.mark.asyncio
async def test_session_linked_event():
    ws = AgentAssistWebSocket()
    mock_ws = AsyncMock()

    await ws.connect("call-003", mock_ws)
    await ws.broadcast("call-003", {
        "event": "session_linked",
        "data": {
            "agent_uuid": "atend-123",
            "ramal_sip": "4001",
            "pbx_id": "771e8400-e29b-41d4-a716-446655440000",
            "pbx_name": "PABX-Matriz-SP",
            "strategy": "automatic_ip_matching",
        },
    })

    sent = mock_ws.send_text.call_args[0][0]
    assert "session_linked" in sent


@pytest.mark.asyncio
async def test_session_waiting_linkage_event():
    ws = AgentAssistWebSocket()
    mock_ws = AsyncMock()

    await ws.connect("call-004", mock_ws)
    await ws.broadcast("call-004", {
        "event": "session_waiting_linkage",
        "data": {
            "agent_uuid": "atend-456",
            "message": "Associação de ramal pendente. Digite *88 no seu softphone.",
        },
    })

    sent = mock_ws.send_text.call_args[0][0]
    assert "session_waiting_linkage" in sent


@pytest.mark.asyncio
async def test_manual_linkage_request():
    ws = AgentAssistWebSocket()
    mock_ws = AsyncMock()

    await ws.connect("call-005", mock_ws)
    await ws.broadcast("call-005", {
        "event": "manual_linkage_request",
        "data": {"agent_uuid": "atend-789"},
    })

    sent = mock_ws.send_text.call_args[0][0]
    assert "manual_linkage_request" in sent
