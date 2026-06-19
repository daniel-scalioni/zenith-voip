# WebSocket Agent Assist, Design

**Interface:** WSS `/ws/{call_id}`, mensagens JSON bidirecionais
**Fluxo:** connect → _try_auto_link (Redis IP→extension) → handle_transcript → handle_alert → broadcast
**Caching:** Sessões Redis `zenith:ws:agent_session:{uuid}` TTL 30-120s
**Origem:** `src/api/websockets.py:33-118` 🟢
