# Módulo: audio

> Gerado pelo Archaeologist — 2026-06-19
> Confiança: 🟢 CONFIRMADO

## Arquivos

| Arquivo | Propósito | Linhas |
|---------|-----------|--------|
| `src/audio/ingestor.py` | Ingestão de streams de áudio via WebSocket | 74 |

## Fluxo de Controle

- `AudioIngestor` gerencia streams ativos (dict por call_id, canais tx/rx)
- `handle_forked_stream(call_id, websocket)` → aceita WS, lê chunks de áudio em loop
- Cada chunk é identificado por canal (tx = transmissão, rx = recepção)
- `_detect_channel()` → sempre retorna "tx" (hardcoded, 🟡 INFERIDO)
- Chunks são bufferizados em memória e publicados no Redis Stream
- `register_stream_metadata()` → associa metadados (tenant_id, pbx_id, agent_extension) ao call_id

## Estruturas

### AudioChunk
| Campo | Tipo | Descrição |
|-------|------|-----------|
| call_id | str | ID da chamada |
| channel | str | Canal (tx/rx) |
| data | bytes | Áudio bruto |
| timestamp | float | Timestamp |

### active_streams
`dict[str, dict[str, WebSocket | None]]` — call_id → {tx: WS, rx: WS}

## Regras de Negócio

| Regra | Local | Confiança |
|-------|-------|-----------|
| Canal de áudio detectado como "tx" por padrão | `ingestor.py:70-71` | 🟡 INFERIDO |
| Metadados do stream registrados no CHANNEL_ANSWER | `ingestor.py:63-68` | 🟢 |
| Chunks publicados no Redis Stream call:events | `ingestor.py:52-55` | 🟢 |
