import json
import struct
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.audio.ingestor import AudioIngestor


def make_stereo_frame(tx_samples: list[int], rx_samples: list[int]) -> bytes:
    # Arrange
    interleaved = [sample for pair in zip(tx_samples, rx_samples) for sample in pair]

    # Act / Assert
    return struct.pack(f"<{len(interleaved)}h", *interleaved)


def test_split_stereo_frame_deinterleaves_channels():
    # Arrange
    ingestor = AudioIngestor()
    frame = make_stereo_frame([100, 300, 500], [200, 400, 600])

    # Act
    tx_bytes, rx_bytes = ingestor._split_stereo_frame(frame)

    # Assert
    assert struct.unpack("<3h", tx_bytes) == (100, 300, 500)
    assert struct.unpack("<3h", rx_bytes) == (200, 400, 600)


@pytest.mark.asyncio
async def test_stream_appends_temp_raw_and_finalizes_to_paths(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setattr("src.audio.ingestor.settings.RECORDINGS_PATH", str(tmp_path))
    ingestor = AudioIngestor()
    call_id = "call-stereo-001"
    ingestor.register_stream_metadata(call_id, "tenant-1", "pbx-1", "1001")
    frame = make_stereo_frame([111, 222], [333, 444])
    websocket = AsyncMock()
    websocket.receive.side_effect = [
        {"type": "websocket.receive", "bytes": frame},
        {"type": "websocket.disconnect", "code": 1000},
    ]

    # Act
    with patch("src.audio.ingestor.event_bus.publish", new=AsyncMock()) as publish, patch(
        "src.audio.ingestor.enqueue_recording_upload", new=AsyncMock()
    ) as enqueue:
        await ingestor.handle_forked_stream(call_id, websocket)

    # Assert
    call_dir = tmp_path / "tenant-1" / call_id
    assert struct.unpack("<2h", (call_dir / "tx.raw").read_bytes()) == (111, 222)
    assert struct.unpack("<2h", (call_dir / "rx.raw").read_bytes()) == (333, 444)
    assert not list(call_dir.glob("*.tmp.raw"))
    assert not (call_dir / ".capture-processing").exists()
    assert publish.await_count == 2
    enqueue.assert_awaited_once_with("tenant-1", call_id)


@pytest.mark.asyncio
async def test_control_frame_creates_no_audio_or_job(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setattr("src.audio.ingestor.settings.RECORDINGS_PATH", str(tmp_path))
    ingestor = AudioIngestor()
    call_id = "call-control"
    ingestor.register_stream_metadata(call_id, "tenant-1", "pbx-1", "1001")
    websocket = AsyncMock()
    websocket.receive.side_effect = [
        {"type": "websocket.receive", "text": json.dumps({"event": "start"})},
        {"type": "websocket.disconnect", "code": 1000},
    ]

    # Act
    with patch("src.audio.ingestor.event_bus.publish", new=AsyncMock()) as publish, patch(
        "src.audio.ingestor.enqueue_recording_upload", new=AsyncMock()
    ) as enqueue:
        await ingestor.handle_forked_stream(call_id, websocket)

    # Assert
    publish.assert_not_awaited()
    enqueue.assert_not_awaited()
    assert call_id not in ingestor.active_streams
    assert call_id not in ingestor.stream_metadata


@pytest.mark.asyncio
async def test_unknown_and_capacity_blocked_streams_are_refused(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setattr("src.audio.ingestor.settings.RECORDINGS_PATH", str(tmp_path))
    ingestor = AudioIngestor()
    unknown = AsyncMock()
    blocked = AsyncMock()
    ingestor.register_stream_metadata("known", "tenant", "pbx", "1001")
    ingestor.capacity_guard.reserve = AsyncMock(return_value=False)

    # Act
    await ingestor.handle_forked_stream("unknown", unknown)
    await ingestor.handle_forked_stream("known", blocked)

    # Assert
    unknown.close.assert_awaited_once_with(code=4401)
    blocked.close.assert_awaited_once_with(code=4403)
    blocked.accept.assert_not_awaited()
    assert "known" not in ingestor.stream_metadata


@pytest.mark.asyncio
async def test_finalize_is_idempotent_and_late_chunk_does_not_reopen(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setattr("src.audio.ingestor.settings.RECORDINGS_PATH", str(tmp_path))
    ingestor = AudioIngestor()
    ingestor.register_stream_metadata("call", "tenant", "pbx", "1001")
    await ingestor._start_recording("call")
    ingestor._write_channel("call", "tx", b"\x01\x00")

    # Act
    with patch("src.audio.ingestor.enqueue_recording_upload", new=AsyncMock()) as enqueue:
        first = await ingestor.finalize_stream("call")
        second = await ingestor.finalize_stream("call")
        late = ingestor._write_channel("call", "tx", b"\x02\x00")

    # Assert
    assert first
    assert not second
    assert not late
    enqueue.assert_awaited_once_with("tenant", "call")
    assert (tmp_path / "tenant" / "call" / "tx.raw").read_bytes() == b"\x01\x00"


@pytest.mark.asyncio
async def test_instances_do_not_share_recording_state(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setattr("src.audio.ingestor.settings.RECORDINGS_PATH", str(tmp_path))
    first = AudioIngestor()
    second = AudioIngestor()
    first.register_stream_metadata("call", "tenant", "pbx", "1001")

    # Act
    await first._start_recording("call")

    # Assert
    assert "call" in first.recordings
    assert "call" not in second.recordings


@pytest.mark.asyncio
async def test_write_failure_preserves_healthy_channel_and_discards_failed_channel(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setattr("src.audio.ingestor.settings.RECORDINGS_PATH", str(tmp_path))
    ingestor = AudioIngestor()
    ingestor.register_stream_metadata("call", "tenant", "pbx", "1001")
    await ingestor._start_recording("call")
    assert ingestor._write_channel("call", "tx", b"ok")

    class FullDisk:
        def write(self, _data):
            raise OSError(28, "No space left")

        def close(self):
            pass

    ingestor.recordings["call"].handles["rx"] = FullDisk()

    # Act
    with patch("src.audio.ingestor.enqueue_recording_upload", new=AsyncMock()) as enqueue:
        assert not ingestor._write_channel("call", "rx", b"fail")
        await ingestor.finalize_stream("call")

    # Assert
    call_dir = tmp_path / "tenant" / "call"
    enqueue.assert_awaited_once_with("tenant", "call")
    assert (call_dir / "tx.raw").read_bytes() == b"ok"
    assert not (call_dir / "rx.raw").exists()


@pytest.mark.asyncio
async def test_finalize_without_started_recording_cleans_metadata():
    # Arrange
    ingestor = AudioIngestor()
    ingestor.register_stream_metadata("call", "tenant", "pbx", "1001")

    # Act
    result = await ingestor.finalize_stream("call")

    # Assert
    assert not result
    assert "call" not in ingestor.stream_metadata


@pytest.mark.asyncio
async def test_concurrent_finalize_claims_state_only_once(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setattr("src.audio.ingestor.settings.RECORDINGS_PATH", str(tmp_path))
    ingestor = AudioIngestor()
    ingestor.register_stream_metadata("call", "tenant", "pbx", "1001")
    await ingestor._start_recording("call")
    ingestor._write_channel("call", "tx", b"audio")

    # Act
    with patch("src.audio.ingestor.enqueue_recording_upload", new=AsyncMock()) as enqueue:
        results = await asyncio.gather(
            ingestor.finalize_stream("call"),
            ingestor.finalize_stream("call"),
        )

    # Assert
    assert sorted(results) == [False, True]
    enqueue.assert_awaited_once_with("tenant", "call")


@pytest.mark.asyncio
async def test_capture_heartbeat_failure_closes_ws_and_finalizes_state(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setattr("src.audio.ingestor.settings.RECORDINGS_PATH", str(tmp_path))
    ingestor = AudioIngestor()
    ingestor.register_stream_metadata("call", "tenant", "pbx", "1001")
    await ingestor._start_recording("call")
    state = ingestor.recordings["call"]
    state.heartbeat_task.cancel()
    await asyncio.gather(state.heartbeat_task, return_exceptions=True)
    state.websocket = AsyncMock()
    monkeypatch.setattr("src.audio.ingestor.asyncio.sleep", AsyncMock())
    monkeypatch.setattr("src.audio.ingestor.renew_lease", lambda *_args: False)

    # Act
    await ingestor._heartbeat_capture(state)

    # Assert
    state.websocket.close.assert_awaited_once_with(code=1011)
    assert "call" not in ingestor.recordings
    assert "call" not in ingestor.stream_metadata
