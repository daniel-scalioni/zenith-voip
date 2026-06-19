from fastapi import WebSocket, WebSocketDisconnect, Depends
from typing import Any
from src.api.auth import verify_token
from src.extraction.regex_layer import RegexExtractor
from src.extraction.llm_layer import LocalLLMExtractor
from src.config import settings
from src.events.redis_streams import event_bus
import json
import asyncio


class AgentAssistWebSocket:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
        self.extractor = RegexExtractor()
        self.llm = LocalLLMExtractor()

    async def connect(self, call_id: str, ws: WebSocket):
        await ws.accept()
        if call_id not in self.active_connections:
            self.active_connections[call_id] = []
        self.active_connections[call_id].append(ws)

        client_ip = ws.client.host if ws.client else ""
        await self._try_auto_link(call_id, ws, client_ip)

    def disconnect(self, call_id: str, ws: WebSocket):
        if call_id in self.active_connections:
            self.active_connections[call_id].remove(ws)
            if not self.active_connections[call_id]:
                del self.active_connections[call_id]

    async def _try_auto_link(self, agent_uuid: str, ws: WebSocket, client_ip: str):
        extension = await event_bus.redis.get(f"zenith:sip:ip_to_extension:{client_ip}")
        if extension:
            ext_str = extension.decode() if isinstance(extension, bytes) else extension
            pbx_id = await event_bus.redis.get(f"zenith:sip:extension_to_pbx:{ext_str}")

            await self.broadcast(agent_uuid, {
                "event": "session_linked",
                "data": {
                    "agent_uuid": agent_uuid,
                    "ramal_sip": ext_str,
                    "pbx_id": pbx_id.decode() if pbx_id else "",
                    "pbx_name": "",
                    "strategy": "automatic_ip_matching",
                },
            })
        else:
            await self.broadcast(agent_uuid, {
                "event": "session_waiting_linkage",
                "data": {
                    "agent_uuid": agent_uuid,
                    "message": "Associação de ramal pendente. Digite *88 no seu softphone corporativo para vincular este widget ao seu ramal.",
                },
            })

    async def broadcast(self, call_id: str, event: dict[str, Any]):
        if call_id not in self.active_connections:
            return
        payload = json.dumps(event)
        stale = []
        for ws in self.active_connections[call_id]:
            try:
                await ws.send_text(payload)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(call_id, ws)

    async def handle_message(self, agent_uuid: str, ws: WebSocket, raw: str):
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return

        event_type = msg.get("event", "")
        if event_type == "manual_linkage_request":
            await self._on_manual_linkage_request(agent_uuid, ws, msg.get("data", {}))

    async def _on_manual_linkage_request(self, agent_uuid: str, ws: WebSocket, data: dict):
        agent_uuid = data.get("agent_uuid", agent_uuid)
        session_key = f"zenith:ws:agent_session:{agent_uuid}"
        await event_bus.redis.hset(session_key, mapping={
            "agent_uuid": agent_uuid,
            "status": "awaiting_linkage",
            "ip": ws.client.host if ws.client else "",
        })
        await event_bus.redis.expire(session_key, 120)

        await self.broadcast(agent_uuid, {
            "event": "session_waiting_linkage",
            "data": {
                "agent_uuid": agent_uuid,
                "message": "Vinculação solicitada. Disque *88 do seu ramal corporativo.",
            },
        })

    async def handle_transcript(self, call_id: str, text: str, speaker: str):
        entities = await self.extractor.extract(text)
        await self.broadcast(call_id, {
            "type": "transcript",
            "speaker": speaker,
            "text": text,
        })
        if entities:
            await self.broadcast(call_id, {
                "type": "entities",
                "data": entities,
            })

    async def handle_alert(self, call_id: str, alert_type: str, message: str, severity: str = "info"):
        await self.broadcast(call_id, {
            "type": "alert",
            "alert_type": alert_type,
            "message": message,
            "severity": severity,
        })


agent_assist_ws = AgentAssistWebSocket()
