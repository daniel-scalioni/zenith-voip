import json
import struct
import pytest
from unittest.mock import AsyncMock, patch
from src.audio.ingestor import AudioIngestor


def make_stereo_frame(tx_samples: list[int], rx_samples: list[int]) -> bytes:
    assert len(tx_samples) == len(rx_samples)
    interleaved = []
    for tx, rx in zip(tx_samples, rx_samples):
        interleaved.append(tx)
        interleaved.append(rx)
    return struct.pack(f"<{len(interleaved)}h", *interleaved)


def test_split_stereo_frame_deinterleaves_channels():
    ingestor = AudioIngestor()
    frame = make_stereo_frame([100, 300, 500], [200, 400, 600])

    tx_bytes, rx_bytes = ingestor._split_stereo_frame(frame)

    assert struct.unpack("<3h", tx_bytes) == (100, 300, 500)
    assert struct.unpack("<3h", rx_bytes) == (200, 400, 600)


@pytest.mark.asyncio
async def test_handle_forked_stream_splits_stereo_binary_frame_into_tx_rx_chunks():
    # Arrange
    ingestor = AudioIngestor()
    call_id = "call-stereo-001"
    ingestor.register_stream_metadata(call_id, tenant_id="tenant-1", pbx_id="pbx-1", agent_extension="1001")
    frame = make_stereo_frame([111, 222], [333, 444])
    mock_ws = AsyncMock()
    mock_ws.receive = AsyncMock(side_effect=[
        {"type": "websocket.receive", "bytes": frame},
        {"type": "websocket.disconnect", "code": 1000},
    ])

    # Act
    with patch("src.audio.ingestor.event_bus.publish", new=AsyncMock()) as mock_publish:
        await ingestor.handle_forked_stream(call_id, mock_ws)

    # Assert
    chunks = ingestor.buffers[call_id]
    channels = {chunk.channel for chunk in chunks}
    assert channels == {"tx", "rx"}
    tx_chunk = next(c for c in chunks if c.channel == "tx")
    rx_chunk = next(c for c in chunks if c.channel == "rx")
    assert struct.unpack("<2h", tx_chunk.data) == (111, 222)
    assert struct.unpack("<2h", rx_chunk.data) == (333, 444)
    assert mock_publish.await_count == 2


@pytest.mark.asyncio
async def test_handle_forked_stream_ignores_control_frame_without_buffering_audio():
    # Arrange
    ingestor = AudioIngestor()
    call_id = "call-control-001"
    ingestor.register_stream_metadata(call_id, tenant_id="tenant-1", pbx_id="pbx-1", agent_extension="1001")
    control_frame = {"type": "websocket.receive", "text": json.dumps({"event": "start", "streamSid": "abc"})}
    mock_ws = AsyncMock()
    mock_ws.receive = AsyncMock(side_effect=[
        control_frame,
        {"type": "websocket.disconnect", "code": 1000},
    ])

    # Act
    with patch("src.audio.ingestor.event_bus.publish", new=AsyncMock()) as mock_publish:
        await ingestor.handle_forked_stream(call_id, mock_ws)

    # Assert
    assert call_id not in ingestor.buffers
    mock_publish.assert_not_called()


@pytest.mark.asyncio
async def test_handle_forked_stream_disconnect_ends_loop_and_cleans_active_stream_state():
    # Arrange
    ingestor = AudioIngestor()
    call_id = "call-disconnect-001"
    ingestor.register_stream_metadata(call_id, tenant_id="tenant-1", pbx_id="pbx-1", agent_extension="1001")
    mock_ws = AsyncMock()
    mock_ws.receive = AsyncMock(side_effect=[
        {"type": "websocket.disconnect", "code": 1000},
    ])

    # Act
    with patch("src.audio.ingestor.event_bus.publish", new=AsyncMock()):
        await ingestor.handle_forked_stream(call_id, mock_ws)

    # Assert
    assert call_id not in ingestor.active_streams
    assert call_id not in ingestor.stream_metadata
    mock_ws.receive.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_forked_stream_does_not_leak_state_between_instances():
    # Arrange
    ingestor_a = AudioIngestor()
    ingestor_b = AudioIngestor()
    call_id = "call-shared-id-001"
    ingestor_a.register_stream_metadata(call_id, tenant_id="tenant-a", pbx_id="pbx-a", agent_extension="1001")
    frame = make_stereo_frame([1, 2], [3, 4])
    mock_ws = AsyncMock()
    mock_ws.receive = AsyncMock(side_effect=[
        {"type": "websocket.receive", "bytes": frame},
        {"type": "websocket.disconnect", "code": 1000},
    ])

    # Act
    with patch("src.audio.ingestor.event_bus.publish", new=AsyncMock()):
        await ingestor_a.handle_forked_stream(call_id, mock_ws)

    # Assert
    assert ingestor_a.buffers[call_id] != []
    assert call_id not in ingestor_b.stream_metadata
    assert ingestor_b.buffers[call_id] == []
    assert call_id not in ingestor_b.active_streams
