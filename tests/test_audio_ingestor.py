import struct
import pytest
from unittest.mock import AsyncMock, patch
from fastapi import WebSocketDisconnect
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
async def test_handle_forked_stream_produces_both_channel_chunks():
    ingestor = AudioIngestor()
    frame = make_stereo_frame([111, 222], [333, 444])

    mock_ws = AsyncMock()
    mock_ws.receive_bytes = AsyncMock(side_effect=[frame, WebSocketDisconnect()])

    with patch("src.audio.ingestor.event_bus.publish", new=AsyncMock()):
        await ingestor.handle_forked_stream("call-stereo-001", mock_ws)

    chunks = ingestor.buffers["call-stereo-001"]
    channels = {chunk.channel for chunk in chunks}
    assert channels == {"tx", "rx"}

    tx_chunk = next(c for c in chunks if c.channel == "tx")
    rx_chunk = next(c for c in chunks if c.channel == "rx")
    assert struct.unpack("<2h", tx_chunk.data) == (111, 222)
    assert struct.unpack("<2h", rx_chunk.data) == (333, 444)
