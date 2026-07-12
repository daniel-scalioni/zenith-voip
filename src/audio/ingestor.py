import json
import struct
from fastapi import WebSocket, WebSocketDisconnect
from collections import defaultdict
from src.events.redis_streams import event_bus
from src.config import settings
from src.telephony.esl_client import esl_client


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
        self.stream_metadata: dict[str, dict] = {}

    async def handle_forked_stream(self, call_id: str, websocket: WebSocket):
        # Só aceita stream para um call_id que o FreeSWITCH já registrou via
        # evento ESL CHANNEL_ANSWER real (register_stream_metadata). Sem isso,
        # qualquer conexão WebSocket com um call_id inventado era aceita e
        # bufferizada como se fosse uma chamada real (achado de segurança,
        # revisão 2026-07-12) — o endpoint fica exposto na porta publicada do
        # host (docker-compose.app.yml), não só em loopback.
        if call_id not in self.stream_metadata:
            await websocket.close(code=4401)
            return

        await websocket.accept()
        self.active_streams[call_id]

        try:
            while True:
                raw = await websocket.receive_bytes()
                if not raw:
                    continue

                tx_bytes, rx_bytes = self._split_stereo_frame(raw)
                self.active_streams[call_id]["tx"] = websocket
                self.active_streams[call_id]["rx"] = websocket

                for channel, data in (("tx", tx_bytes), ("rx", rx_bytes)):
                    self.buffers[call_id].append(AudioChunk(call_id, channel, data, 0.0))
                    await self._publish_chunk_event(call_id, channel, len(data))
        except WebSocketDisconnect:
            pass
        finally:
            if call_id in self.active_streams:
                del self.active_streams[call_id]
            self.stream_metadata.pop(call_id, None)

    async def _publish_chunk_event(self, call_id: str, channel: str, size_bytes: int):
        metadata = self.stream_metadata.get(call_id, {})
        event_payload = {
            "call_id": call_id,
            "channel": channel,
            "event": "audio_chunk",
            "size_bytes": size_bytes,
            "tenant_id": metadata.get("tenant_id", ""),
            "pbx_id": metadata.get("pbx_id", ""),
            "agent_extension": metadata.get("agent_extension", ""),
        }
        await event_bus.publish(settings.REDIS_STREAM_CALL_EVENTS, event_payload)

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
        tx_bytes = struct.pack(f"<{len(tx_samples)}h", *tx_samples)
        rx_bytes = struct.pack(f"<{len(rx_samples)}h", *rx_samples)
        return tx_bytes, rx_bytes


audio_ingestor = AudioIngestor()
