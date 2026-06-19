# Audio, Design Técnico

> Gerado pelo Writer — 2026-06-19

## Interface

| Símbolo | Assinatura | Retorno |
|---------|-----------|---------|
| `handle_forked_stream` | `(call_id: str, websocket: WebSocket)` | `None` |

### AudioChunk

| Campo | Tipo | Descrição |
|-------|------|-----------|
| call_id | str | ID da chamada |
| channel | str | "tx" (hardcoded) |
| data | bytes | Áudio bruto |
| timestamp | float | Timestamp do chunk |

## Fluxo Principal

1. FreeSWITCH fork do áudio e envia via WebSocket — evento CHANNEL_ANSWER
2. `handle_forked_stream()` é chamada com call_id e WebSocket — `src/audio/ingestor.py:30-40`
3. Metadados do stream são registrados — `src/audio/ingestor.py:63-68`
4. Chunks de áudio são recebidos em loop
5. Canal detectado como "tx" (🔴 hardcoded) — `src/audio/ingestor.py:70-71`
6. Chunks publicados no Redis Stream `call:events` — `src/audio/ingestor.py:45-55`

## Riscos e Lacunas

- 🔴 `_detect_channel()` retorna "tx" hardcoded — canal RX nunca identificado, torna impossível distinguir fala do agente vs cliente
- 🟡 Sem bufferização robusta — chunks pequenos podem causar sobrecarga de mensagens no Redis
