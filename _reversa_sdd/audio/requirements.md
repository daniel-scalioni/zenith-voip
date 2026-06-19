# Audio — Ingestão de Áudio

> Gerado pelo Writer — 2026-06-19

## Visão Geral

Recebe streams de áudio forked do FreeSWITCH via WebSocket, bufferiza chunks e publica eventos no Redis Stream para processamento pelos workers.

## Responsabilidades

- Receber stream de áudio forked via WebSocket do FreeSWITCH
- Detectar canal de áudio (tx/rx) — 🔴 stub retorna "tx" hardcoded
- Publicar chunks de áudio no Redis Stream `call:events`

## Requisitos Funcionais

| ID | Requisito | Prioridade |
|----|-----------|-----------|
| RF-01 | Receber stream de áudio forked via WebSocket | Must |
| RF-02 | Publicar chunk de áudio no Redis Stream com metadados | Must |
| RF-03 | Registrar metadados do stream no evento CHANNEL_ANSWER | Must |
| RF-04 | Detectar canal de áudio (tx = agente, rx = cliente) | Should |

## Rastreabilidade

| Arquivo | Função | Cobertura |
|---------|--------|-----------|
| `src/audio/ingestor.py` | `handle_forked_stream()` | 🟢 |
