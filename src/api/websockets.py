from fastapi import WebSocket, WebSocketDisconnect, Depends
from typing import Any
from src.api.auth import verify_token
from src.extraction.regex_layer import RegexExtractor
from src.extraction.llm_layer import LocalLLMExtractor
from src.config import settings
import json


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

    def disconnect(self, call_id: str, ws: WebSocket):
        if call_id in self.active_connections:
            self.active_connections[call_id].remove(ws)
            if not self.active_connections[call_id]:
                del self.active_connections[call_id]

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
