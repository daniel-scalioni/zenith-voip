# Módulo: audio

> Gerado pelo Archaeologist — 2026-06-19
> **Re-extração incremental — 2026-07-27** (base `48da5b1` → `0658157`, delta D-02)
> Confiança: 🟢 CONFIRMADO

## Arquivos

| Arquivo | Propósito | Linhas |
|---------|-----------|--------|
| `src/audio/ingestor.py` | Ingestão de streams de áudio via WebSocket | 95 |

## Fluxo de Controle

- `AudioIngestor` gerencia streams ativos (dict por `call_id`, canais `tx`/`rx`)
- `handle_forked_stream(call_id, websocket)`:
  1. 🆕 **Guard de autorização** — se `call_id` não estiver em `stream_metadata`, fecha a
     conexão com código **4401** *antes* do `accept()`. Só um `call_id` registrado por um
     `CHANNEL_ANSWER` real do FreeSWITCH (via `register_stream_metadata`) é aceito.
  2. Aceita o WebSocket e entra no loop de leitura.
  3. 🆕 Usa `websocket.receive()` (não `receive_bytes()`): o `mod_audio_stream` envia um
     frame **de texto** (JSON de controle) antes do áudio binário; frames sem `bytes` são
     ignorados, e `websocket.disconnect` é convertido em `WebSocketDisconnect`.
  4. 🆕 Cada frame binário passa por `_split_stereo_frame()` e gera **dois** `AudioChunk`
     (um `tx`, um `rx`), cada um publicado como evento próprio no Redis Stream.
- `_publish_chunk_event(call_id, channel, size_bytes)` 🆕 → extraído do loop; monta o payload
  com os metadados do stream e publica em `settings.REDIS_STREAM_CALL_EVENTS`.
- `register_stream_metadata()` → associa metadados (`tenant_id`, `pbx_id`, `agent_extension`)
  ao `call_id`. **É também o registro de autorização** do endpoint (ver guard acima).
- No `finally`, `active_streams` e `stream_metadata` são limpos para o `call_id`.

## Algoritmos

**De-interleaving PCM16 estéreo** (`_split_stereo_frame`, `ingestor.py:86-94`) 🆕 —
substitui o antigo `_detect_channel()`, que retornava `"tx"` hardcoded (lacuna 🔴 da extração
anterior, agora **fechada**):

```
samples = struct.unpack("<{n}h", raw)   # PCM16 little-endian
tx = samples[0::2]                      # canal par  → agente
rx = samples[1::2]                      # canal ímpar → cliente
```

O FreeSWITCH envia o frame estéreo intercalado (`uuid_audio_stream ... stereo 8k`); a
separação por índice par/ímpar é o que torna `tx` e `rx` gravações mono independentes.

## Estruturas

### AudioChunk
| Campo | Tipo | Descrição |
|-------|------|-----------|
| call_id | str | ID da chamada |
| channel | str | Canal (`tx` = agente, `rx` = cliente) |
| data | bytes | Áudio bruto PCM16 mono 8kHz |
| timestamp | float | Timestamp (sempre `0.0` hoje — 🔴 nunca populado) |

### active_streams
`dict[str, dict[str, WebSocket | None]]` — `call_id` → `{tx: WS, rx: WS}`.
Como os dois canais chegam pelo mesmo socket, `tx` e `rx` apontam para o **mesmo**
objeto WebSocket.

### buffers
`dict[str, list[AudioChunk]]` — consumido e esvaziado por
`ESLClient._handle_channel_hangup()`, que agrupa por canal e enfileira o upload.

## Regras de Negócio

| Regra | Local | Confiança |
|-------|-------|-----------|
| 🆕 WebSocket de áudio exige `call_id` previamente registrado via ESL (senão fecha 4401) | `ingestor.py:27-36` | 🟢 |
| 🆕 Frame estéreo é dividido em `tx` (pares) e `rx` (ímpares) | `ingestor.py:86-94` | 🟢 |
| 🆕 Frame de texto do `mod_audio_stream` é ignorado, não bufferizado | `ingestor.py:44-48` | 🟢 |
| Metadados do stream registrados no CHANNEL_ANSWER | `ingestor.py:78-84` | 🟢 |
| Chunks publicados no Redis Stream `call:events` (um evento por canal) | `ingestor.py:65-76` | 🟢 |
| `AudioChunk.timestamp` sempre `0.0` | `ingestor.py:59` | 🔴 LACUNA |

## Lacunas resolvidas nesta re-extração

| Lacuna (2026-06-19) | Status |
|---|---|
| `channel_detection: _detect_channel() retorna tx hardcoded` | ✅ **RESOLVIDA** — `_split_stereo_frame()` faz a separação real |

## Lacunas abertas

| Lacuna | Impacto |
|---|---|
| `AudioChunk.timestamp` nunca é populado (fixo em `0.0`) | Impossível reconstruir o eixo temporal do áudio a partir do buffer; a ordenação depende da ordem de chegada na lista |
| Endpoint publicado no host | Mitigado: `docker-compose.app.yml` agora publica `8001`/`8002` apenas em `127.0.0.1`, e o guard 4401 fecha o vetor de `call_id` inventado |
