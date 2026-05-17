import json
from fastapi import WebSocket, WebSocketDisconnect
from collections import defaultdict
from src.events.redis_streams import event_bus
from src.config import settings


class AudioChunk:
    def __init__(self, call_id: str, channel: str, data: bytes, timestamp: float):
        self.call_id = call_id
        self.channel = channel
        self.data = data
        self.timestamp = timestamp


class AudioIngestor:
    def __init__(self):
        self.active_streams: dict[str, dict[str, WebSocket | None]] = defaultdict(
            lambda: {"tx": None, "rx": None}
        )
        self.buffers: dict[str, list[AudioChunk]] = defaultdict(list)

    async def handle_forked_stream(self, call_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_streams[call_id]

        try:
            while True:
                raw = await websocket.receive_bytes()
                if not raw:
                    continue

                channel = self._detect_channel(raw)
                self.active_streams[call_id][channel] = websocket
                chunk = AudioChunk(call_id, channel, raw, 0.0)

                self.buffers[call_id].append(chunk)

                await event_bus.publish(
                    settings.REDIS_STREAM_CALL_EVENTS,
                    {
                        "call_id": call_id,
                        "channel": channel,
                        "event": "audio_chunk",
                        "size_bytes": len(raw),
                    },
                )
        except WebSocketDisconnect:
            pass
        finally:
            if call_id in self.active_streams:
                del self.active_streams[call_id]

    def _detect_channel(self, raw: bytes) -> str:
        return "tx"


audio_ingestor = AudioIngestor()
