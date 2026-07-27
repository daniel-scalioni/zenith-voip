---
spec:
  component: audio-ingestion
  layer: audio
  status: active
  version: 2.0.0
  language: python
  patterns: [singleton]
  inputs:
    - {name: audio_frame, type: bytes (PCM16 LE estéreo 8kHz), from: freeswitch/mod_audio_stream}
    - {name: stream_metadata, type: dict, from: telephony/esl_client}
  outputs:
    - {name: audio_chunk_event, type: dict, to: events/redis_streams}
    - {name: buffers, type: list[AudioChunk], to: telephony/esl_client}
  dependencies:
    - {component: redis_streams, layer: events}
    - {component: esl_client, layer: telephony}
  events_produced: [audio_chunk]
  updated_at: 2026-07-27
---

# Audio — Ingestão de Áudio

> Gerado pelo Writer — 2026-06-19
> **Revisado na re-extração incremental — 2026-07-27** (delta D-02)

## Visão Geral

Recebe o stream de áudio do FreeSWITCH via WebSocket (`/audio-stream/{call_id}`), separa os
dois canais de um frame PCM16 estéreo, bufferiza os chunks em memória e publica um evento por
canal no Redis Stream para processamento pelos workers.

O buffer é consumido no fim da chamada por `ESLClient._handle_channel_hangup()`, que o agrupa
por canal e enfileira o job de gravação.

## Responsabilidades

- Autorizar a conexão: só aceitar `call_id` previamente registrado por um `CHANNEL_ANSWER`
  real (senão fechar com código **4401**, antes do `accept()`)
- Receber o stream de áudio via WebSocket, tolerando o frame de texto de controle que o
  `mod_audio_stream` envia antes do binário
- Separar `tx` (agente) e `rx` (cliente) por de-interleaving PCM16
- Publicar chunks no Redis Stream `call:events`, um evento por canal
- Manter o buffer da chamada até o hangup e limpar o estado ao desconectar

## Requisitos Funcionais

| ID | Requisito | Prioridade | Status |
|----|-----------|-----------|--------|
| RF-01 | Receber stream de áudio via WebSocket | Must | ✅ |
| RF-02 | Publicar chunk de áudio no Redis Stream com metadados | Must | ✅ |
| RF-03 | Registrar metadados do stream no evento CHANNEL_ANSWER | Must | ✅ |
| RF-04 | Separar canal `tx` (agente) e `rx` (cliente) | Must | ✅ 2026-07 — de-interleaving real, era stub |
| RF-05 | 🆕 Rejeitar `call_id` não registrado via ESL (close 4401) | Must | ✅ 2026-07-12 |
| RF-06 | 🆕 Ignorar frames de texto de controle sem bufferizá-los como áudio | Must | ✅ |
| RF-07 | 🆕 Limpar `active_streams` e `stream_metadata` ao encerrar a conexão | Must | ✅ |

## Requisitos Não-Funcionais

| ID | Requisito | Status |
|----|-----------|--------|
| RNF-01 | O endpoint não deve ser alcançável de fora do host | ✅ portas publicadas em `127.0.0.1` |
| RNF-02 | Falha de um stream não pode derrubar outros | ✅ estado é por `call_id` |
| RNF-03 | Ordenação temporal dos chunks recuperável | 🔴 **não atendido** — `timestamp` fixo em `0.0` (GAP-RE-05) |

## Contrato do frame

| Propriedade | Valor |
|---|---|
| Codificação | PCM16 little-endian |
| Taxa | 8 kHz |
| Canais no fio | 2 (estéreo intercalado) |
| Canais após split | 2 × mono (`tx`, `rx`) |
| Origem | `uuid_audio_stream <call_id> start <ws_url> stereo 8k <metadata>` |

## Rastreabilidade

| Arquivo | Função | Cobertura |
|---------|--------|-----------|
| `src/audio/ingestor.py` | `handle_forked_stream()` | 🟢 |
| `src/audio/ingestor.py` | `_split_stereo_frame()` | 🟢 `tests/test_audio_ingestor.py` |
| `src/audio/ingestor.py` | `_publish_chunk_event()` | 🟢 |
| `src/audio/ingestor.py` | `register_stream_metadata()` | 🟢 |

## Lacunas

| ID | Descrição |
|---|---|
| GAP-RE-05 | `AudioChunk.timestamp` sempre `0.0` |
