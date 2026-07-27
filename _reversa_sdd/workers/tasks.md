---
spec:
  component: workers
  layer: workers
  status: active
  version: 2.0.0
  updated_at: 2026-07-27
---

# Workers, Tarefas de Implementação

> Gerado pelo Writer — 2026-06-19
> **Revisado na re-extração incremental — 2026-07-27** (deltas D-03/D-04)

## Tarefas implementadas

- [x] T-01, Worker de gravação local com conversão MP3
  - Origem: `src/workers/audio_uploader.py`
  - Critério: cada canal gravado em `RECORDINGS_PATH/<tenant>/<call_id>/<channel>.mp3`
  - Confiança: 🟢 — `tests/test_audio_uploader.py`

- [x] T-02, Produtor da fila de gravação (`enqueue_recording_upload`)
  - Origem: `src/workers/audio_uploader.py:66-76`
  - Critério: job `upload_recording_batch` enfileirado no `CHANNEL_HANGUP`
  - Confiança: 🟢

- [x] T-03, Worker de cleanup por `mtime` (cron a cada 15 min)
  - Origem: `src/workers/audio_cleanup.py`
  - Critério: arquivos além do TTL removidos por tenant, sem bloquear o event loop
  - Confiança: 🟢

- [x] T-04, Worker de persistência de transcrições (batch)
  - Origem: `src/workers/transcript_persist.py`
  - Critério: transcripts bufferizados no Redis e persistidos em lote a cada 5s
  - Confiança: 🟢

- [x] T-05, Container `zenith-arq-uploader` no compose
  - Origem: `docker-compose.app.yml`
  - Critério: alguém consome `upload_recording_batch` (antes ninguém consumia — GAP-14)
  - Confiança: 🟢

## Tarefas obsoletas (v1.0.0 — S3 removido, ADR-009)

- [~] ~~T-01 v1, Implementar worker de cleanup S3 (cron 03:00)~~
- [~] ~~T-02 v1, Implementar worker de upload S3~~

## Tarefas pendentes

- [ ] T-06, Implementar worker pós-chamada
  - Origem: `src/workers/post_call.py:7-12`
  - Critério: sentimento e auditoria executados de fato (resolver 🔴 stubs)
  - Confiança: 🔴 — GAP-02

- [ ] T-07, Backpressure quando o tmpfs encher
  - Critério: alarme agregado e/ou descarte da gravação mais antiga em vez de falhar por chamada
  - Prioridade: alta — GAP-RE-04

- [ ] T-08, Retenção configurável por tenant
  - Critério: TTL lido da configuração do tenant, não de variável global

- [ ] T-09, Verificar `ffmpeg` disponível no boot do worker
  - Critério: falhar cedo e explicitamente, em vez de descobrir na primeira conversão

- [ ] T-10, Remover ou reapontar as métricas Prometheus de S3
  - Critério: `observability` deixa de expor métricas de subsistema inexistente — GAP-RE-08

- [ ] T-11, Monitoramento de workers (dead letters, retry)
  - Confiança: 🟡

## Tarefas de Teste

- [x] TT-01, Testar gravação e conversão MP3 (`tests/test_audio_uploader.py`)
- [ ] TT-02, Testar cleanup por `mtime` com TTL curto
- [ ] TT-03, Testar comportamento com tmpfs cheio
- [x] TT-04, Testar batch persist de transcrições
- [ ] TT-05, Testar worker pós-chamada (bloqueado por T-06)
