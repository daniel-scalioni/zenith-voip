import asyncio
import contextlib
import logging
import os
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

from fastapi import WebSocket, WebSocketDisconnect

from src.audio.capacity import RecordingCapacityGuard
from src.audio.recording_lifecycle import LeaseBusyError, acquire_lease, release_lease, renew_lease
from src.config import settings
from src.events.redis_streams import event_bus
from src.workers.audio_uploader import enqueue_recording_upload
from src.utils.telemetry import record_lease_failure


logger = logging.getLogger(__name__)


@dataclass
class RecordingState:
    call_id: str
    tenant_id: str
    call_dir: Path
    lease_owner: str
    handles: dict[str, BinaryIO] = field(default_factory=dict)
    websocket: WebSocket | None = None
    heartbeat_task: asyncio.Task | None = None
    failed_channels: set[str] = field(default_factory=set)


class AudioIngestor:
    def __init__(self):
        self.active_streams: dict[str, dict[str, WebSocket | None]] = {}
        self.stream_metadata: dict[str, dict[str, str]] = {}
        self.recordings: dict[str, RecordingState] = {}
        self.capacity_guard = RecordingCapacityGuard(settings.RECORDINGS_PATH)

    async def handle_forked_stream(self, call_id: str, websocket: WebSocket):
        if call_id not in self.stream_metadata:
            await websocket.close(code=4401)
            return
        if not await self._start_recording(call_id):
            self.stream_metadata.pop(call_id, None)
            await websocket.close(code=4403)
            return

        await websocket.accept()
        state = self.recordings[call_id]
        state.websocket = websocket
        self.active_streams[call_id] = {"tx": websocket, "rx": websocket}

        try:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    raise WebSocketDisconnect(message.get("code", 1000))
                raw = message.get("bytes")
                if raw is None:
                    continue
                tx_bytes, rx_bytes = self._split_stereo_frame(raw)
                for channel, data in (("tx", tx_bytes), ("rx", rx_bytes)):
                    if self._write_channel(call_id, channel, data):
                        await self._publish_chunk_event(call_id, channel, len(data))
        except WebSocketDisconnect:
            pass
        finally:
            self.active_streams.pop(call_id, None)
            await self.finalize_stream(call_id)

    async def _start_recording(self, call_id: str) -> bool:
        if call_id in self.recordings:
            return True
        metadata = self.stream_metadata.get(call_id)
        if metadata is None:
            return False
        root = Path(settings.RECORDINGS_PATH)
        root.mkdir(parents=True, exist_ok=True)
        self.capacity_guard.path = root
        if not await self.capacity_guard.reserve(call_id):
            logger.warning("recording_refused_capacity call_id=%s", call_id)
            return False
        call_dir = root / metadata["tenant_id"] / call_id
        call_dir.mkdir(parents=True, exist_ok=True)
        try:
            lease = acquire_lease(call_dir, "capture", call_id)
        except (OSError, LeaseBusyError):
            await self.capacity_guard.release(call_id)
            logger.exception("capture_lease_create_failed call_id=%s", call_id)
            record_lease_failure("capture")
            return False
        state = RecordingState(call_id, metadata["tenant_id"], call_dir, lease.owner)
        self.recordings[call_id] = state
        state.heartbeat_task = asyncio.create_task(self._heartbeat_capture(state))
        return True

    async def _heartbeat_capture(self, state: RecordingState) -> None:
        while self.recordings.get(state.call_id) is state:
            await asyncio.sleep(settings.RECORDING_LEASE_HEARTBEAT_SECONDS)
            if not renew_lease(state.call_dir, "capture", state.lease_owner):
                logger.error("capture_lease_renewal_failed call_id=%s", state.call_id)
                record_lease_failure("capture")
                if state.websocket is not None:
                    await state.websocket.close(code=1011)
                await self.finalize_stream(state.call_id)
                return

    def _write_channel(self, call_id: str, channel: str, data: bytes) -> bool:
        state = self.recordings.get(call_id)
        if state is None or channel not in {"tx", "rx"}:
            logger.warning("late_audio_chunk_discarded call_id=%s channel=%s", call_id, channel)
            return False
        try:
            handle = state.handles.get(channel)
            if handle is None:
                handle = open(state.call_dir / f"{channel}.tmp.raw", "ab", buffering=0)
                state.handles[channel] = handle
            handle.write(data)
            return True
        except OSError:
            state.failed_channels.add(channel)
            logger.exception("recording_write_failed call_id=%s channel=%s", call_id, channel)
            return False

    async def finalize_stream(self, call_id: str) -> bool:
        state = self.recordings.pop(call_id, None)
        if state is None:
            self.stream_metadata.pop(call_id, None)
            return False
        task = state.heartbeat_task
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        published = False
        try:
            for channel, handle in state.handles.items():
                handle.close()
                temporary = state.call_dir / f"{channel}.tmp.raw"
                final = state.call_dir / f"{channel}.raw"
                if channel not in state.failed_channels and temporary.exists():
                    os.replace(temporary, final)
                    published = True
            if published:
                await enqueue_recording_upload(state.tenant_id, call_id)
        finally:
            release_lease(state.call_dir, "capture", state.lease_owner)
            await self.capacity_guard.release(call_id)
            self.active_streams.pop(call_id, None)
            self.stream_metadata.pop(call_id, None)
        return True

    async def _publish_chunk_event(self, call_id: str, channel: str, size_bytes: int):
        metadata = self.stream_metadata.get(call_id, {})
        await event_bus.publish(settings.REDIS_STREAM_CALL_EVENTS, {
            "call_id": call_id,
            "channel": channel,
            "event": "audio_chunk",
            "size_bytes": size_bytes,
            "tenant_id": metadata.get("tenant_id", ""),
            "pbx_id": metadata.get("pbx_id", ""),
            "agent_extension": metadata.get("agent_extension", ""),
        })

    def register_stream_metadata(self, call_id: str, tenant_id: str, pbx_id: str, agent_extension: str):
        self.stream_metadata[call_id] = {
            "tenant_id": tenant_id,
            "pbx_id": pbx_id,
            "agent_extension": agent_extension,
        }

    def _split_stereo_frame(self, raw: bytes) -> tuple[bytes, bytes]:
        sample_count = len(raw) // 2
        samples = struct.unpack(f"<{sample_count}h", raw[: sample_count * 2])
        tx_samples = samples[0::2]
        rx_samples = samples[1::2]
        return (
            struct.pack(f"<{len(tx_samples)}h", *tx_samples),
            struct.pack(f"<{len(rx_samples)}h", *rx_samples),
        )


audio_ingestor = AudioIngestor()
