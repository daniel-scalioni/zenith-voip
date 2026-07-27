---
spec:
  component: workers
  layer: workers
  status: active
  version: 2.0.0
  language: python
  patterns: [singleton]
  inputs:
    - {name: upload_recording_batch, type: arq job, from: telephony/esl_client}
    - {name: cron_trigger, type: schedule, from: arq}
  outputs:
    - {name: recording_mp3, type: file, to: tmpfs RECORDINGS_PATH}
    - {name: transcripts, type: rows, to: database}
  dependencies:
    - {component: config, layer: root}
    - {component: database, layer: database}
  events_produced: [call:post]
  updated_at: 2026-07-27
---

# Workers — Background Jobs

> Gerado pelo Writer — 2026-06-19
> **Revisado na re-extração incremental — 2026-07-27** (deltas D-03/D-04)
> ⚠️ **S3 foi removido do projeto** (ADR-009). Os requisitos RF-01 a RF-03 da versão 1.0.0
> descreviam um subsistema que não existe mais.

## Visão Geral

Workers ARQ para processamento assíncrono: **gravação local de áudio com conversão para MP3**,
limpeza por TTL, workflow pós-chamada e persistência de transcrições em lote.

## Responsabilidades

- Consumir o job `upload_recording_batch` enfileirado no `CHANNEL_HANGUP`
- Gravar cada canal em `RECORDINGS_PATH/<tenant_id>/<call_id>/<channel>.raw` e convertê-lo
  para MP3 mono 8 kHz via `ffmpeg`
- Remover gravações cujo `mtime` ultrapassou `AUDIO_RETENTION_DAYS`
- Executar workflow pós-chamada (sentimento, auditoria) — 🔴 continuam stubs
- Persistir transcrições em lote no PostgreSQL

## Regras de Negócio

| Regra | Confiança |
|---|---|
| Cleanup roda a cada 15 minutos (`minute={0,15,30,45}`) | 🟢 |
| Retenção em produção: ~1 hora (`AUDIO_RETENTION_DAYS=0.0417`); default do código: 90 dias | 🟢 |
| Gravação vive em tmpfs de 512 MB (RAM), nunca em disco durável | 🟢 |
| Cada canal vira um MP3 mono 8 kHz separado — nunca misturado nem estéreo | 🟢 |
| Falha de conversão preserva o `.raw` (`uploaded_raw_only`) | 🟢 |
| Cleanup cede o event loop a cada 1000 arquivos removidos | 🟢 |

## Requisitos Funcionais

| ID | Requisito | Prioridade | Status |
|----|-----------|-----------|--------|
| RF-01 | Gravar cada canal em `RECORDINGS_PATH/<tenant>/<call_id>/<channel>.raw` | Must | ✅ |
| RF-02 | Converter cada `.raw` para MP3 mono 8 kHz e remover o `.raw` | Must | ✅ |
| RF-03 | Preservar o `.raw` se a conversão falhar (`uploaded_raw_only`) | Must | ✅ |
| RF-04 | Remover gravações com `mtime` além do TTL, por tenant | Must | ✅ |
| RF-05 | Rodar o cleanup a cada 15 min, não uma vez ao dia | Must | ✅ |
| RF-06 | Expor `enqueue_recording_upload()` como produtor da fila | Must | ✅ |
| RF-07 | Executar análise de sentimento pós-chamada | Should | 🔴 stub |
| RF-08 | Executar auditoria pós-chamada | Should | 🔴 stub |
| RF-09 | Persistir transcrições em lote no PostgreSQL | Must | ✅ |

## Requisitos Não-Funcionais

| ID | Requisito | Status |
|----|-----------|--------|
| RNF-01 | Áudio sensível não deve persistir em mídia durável | ✅ tmpfs + TTL curto |
| RNF-02 | Cleanup não pode bloquear o event loop com muitos arquivos | ✅ `sleep(0)` a cada 1000 |
| RNF-03 | Falha de gravação de uma chamada não afeta as demais | ✅ tratamento por chunk |
| RNF-04 | Backpressure quando o tmpfs encher | 🔴 **não atendido** (GAP-RE-04) |
| RNF-05 | Retenção configurável por tenant | 🔴 não atendido — TTL é global |

## Requisitos removidos (versão 1.0.0)

| ID antigo | Requisito | Motivo |
|---|---|---|
| RF-01 v1 | Limpar áudio do S3 com mais de 90 dias | S3 removido (ADR-009) |
| RF-02 v1 | Deletar objetos S3 em lotes de 1000 | idem |
| RF-03 v1 | Fazer upload de áudio para S3 | idem |

## Rastreabilidade

| Arquivo | Função | Cobertura |
|---------|--------|-----------|
| `src/workers/audio_uploader.py` | `upload_audio_chunk()`, `_convert_to_mp3()` | 🟢 `tests/test_audio_uploader.py` |
| `src/workers/audio_uploader.py` | `enqueue_recording_upload()` | 🟢 |
| `src/workers/audio_cleanup.py` | `run_cleanup()`, `cleanup_tenant_bucket()` | 🟢 |
| `src/workers/post_call.py` | `analyze_sentiment()`, `audit_procedure()` | 🔴 stubs |
| `src/workers/transcript_persist.py` | batch persist | 🟢 |

## Lacunas

| ID | Descrição |
|---|---|
| GAP-02 | `analyze_sentiment()` e `audit_procedure()` continuam stubs |
| GAP-RE-04 | tmpfs de 512 MB sem backpressure nem política de descarte |
| GAP-RE-08 | Métricas Prometheus de S3 medem subsistema inexistente |
