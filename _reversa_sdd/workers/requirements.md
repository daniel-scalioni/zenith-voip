---
spec:
  component: workers
  layer: workers
  status: active
  version: 3.0.0
  language: python
  patterns: [singleton]
  inputs:
    - {name: upload_recording_batch, type: arq job, from: audio-ingestion}
    - {name: cron_trigger, type: schedule, from: arq}
  outputs:
    - {name: recording_wav, type: file, to: tmpfs RECORDINGS_PATH}
    - {name: transcripts, type: rows, to: database}
  dependencies:
    - {component: config, layer: root}
    - {component: database, layer: database}
  events_produced: []
  updated_at: 2026-08-21
---

# Workers — Background Jobs

> Gerado pelo Writer — 2026-06-19
> **Revisado na re-extração incremental — 2026-07-27** (deltas D-03/D-04)
> ⚠️ **S3 foi removido do projeto** (ADR-009). Os requisitos RF-01 a RF-03 da versão 1.0.0
> descreviam um subsistema que não existe mais.

## Visão Geral

Workers ARQ para processamento assíncrono: **gravação local de áudio com conversão para WAV**,
limpeza por TTL, workflow pós-chamada e persistência de transcrições em lote.

Os workers operacionais de áudio usam filas Redis exclusivas. Um worker nunca pode retirar da
fila um job cuja função não registra. Este isolamento é parte do contrato de confiabilidade, não
uma otimização de deploy.

## Responsabilidades

- Consumir o job idempotente `upload_recording_batch` enfileirado na finalização da captura
- Converter cada `.raw` final em WAV PCM16 mono 16 kHz, preservando o raw
- Remover finais após confirmação dos consumidores ou pelo TTL de segurança
- Coletar temporários locais órfãos somente após duas rodadas de 15 min
- Executar workflow pós-chamada (sentimento, auditoria) — 🔴 continuam stubs
- Persistir transcrições em lote no PostgreSQL
- Rotear upload, cleanup e sincronização SMB para filas ARQ distintas

## Regras de Negócio

| Regra | Confiança |
|---|---|
| Cleanup roda a cada 15 minutos (`minute={0,15,30,45}`) | 🟢 |
| Retenção em produção: ~1 hora (`AUDIO_RETENTION_DAYS=0.0417`); default do código: 90 dias | 🟢 |
| Gravação vive em tmpfs de 2 GiB (RAM), nunca em disco durável | 🟢 decisão 2026-08-14 |
| Cada canal vira WAV PCM16 mono 16 kHz separado; o SMB publica WAV estéreo | 🟢 |
| Falha de conversão preserva o `.raw` (`uploaded_raw_only`) | 🟢 |
| Consumidores exigidos vêm de `RECORDING_REQUIRED_CONSUMERS` (inicialmente `smb`) | 🟢 |
| Leases duram 120 s, heartbeat 30 s; cleanup reobserva órfão após 900 s | 🟢 |
| Admissão reserva chamada de 300 s e usa margens livres 20/30% + headroom | 🟢 |
| Cleanup cede o event loop a cada 1000 arquivos removidos | 🟢 |
| Uploader consome exclusivamente `zenith:audio-upload` | 🟢 decisão SDD 2026-07-29 |
| Cleanup consome exclusivamente `zenith:audio-cleanup` | 🟢 decisão SDD 2026-07-29 |
| SMB sync consome exclusivamente `zenith:smb-sync` | 🟢 decisão SDD 2026-07-29 |

## Requisitos Funcionais

| ID | Requisito | Prioridade | Status |
|----|-----------|-----------|--------|
| RF-01 | Gravar cada canal em `RECORDINGS_PATH/<tenant>/<call_id>/<channel>.raw` | Must | ✅ |
| RF-02 | Converter cada `.raw` para MP3 mono 8 kHz e remover o `.raw` | Must | ✅ |
| RF-03 | Preservar o `.raw` se a conversão falhar (`uploaded_raw_only`) | Must | ✅ |
| RF-04 | Remover gravações com `mtime` além do TTL, por tenant | Must | ✅ |
| RF-05 | Rodar o cleanup a cada 15 min, não uma vez ao dia | Must | ✅ |
| RF-06 | Expor `enqueue_recording_upload()` como produtor da fila | Must | ✅ |
| RF-07 | ~~Executar análise de sentimento pós-chamada~~ | Should | 🗑️ removido (2026-08-21, GAP-02) — stub sem worker registrado nem produtor de job |
| RF-08 | ~~Executar auditoria pós-chamada~~ | Should | 🗑️ removido (2026-08-21, GAP-02) — idem |
| RF-09 | Persistir transcrições em lote no PostgreSQL | Must | ✅ `transcript_batch.py` (feature 013) — a rastreabilidade abaixo apontava por engano para `transcript_persist.py`, código morto desde o commit inicial e removido em 2026-08-21 (GAP-04) |
| RF-10 | Isolar uploader, cleanup e SMB sync em filas ARQ exclusivas; produtores devem publicar explicitamente na fila do consumidor | Must | 🟡 especificado, implementação pendente |

## Requisitos Não-Funcionais

| ID | Requisito | Status |
|----|-----------|--------|
| RNF-01 | Áudio sensível não deve persistir em mídia durável | ✅ tmpfs + TTL curto |
| RNF-02 | Cleanup não pode bloquear o event loop com muitos arquivos | ✅ `sleep(0)` a cada 1000 |
| RNF-03 | Falha de gravação de uma chamada não afeta as demais | ✅ tratamento por chunk |
| RNF-04 | Backpressure quando o tmpfs encher | 🔴 **não atendido** (GAP-RE-04) |
| RNF-05 | Retenção configurável por tenant | 🔴 não atendido — TTL é global |
| RNF-06 | Um worker não pode consumir job de função desconhecida pertencente a outro worker | 🟡 especificado, implementação pendente |

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
| `src/workers/smb_sync.py` | `run_smb_sync()` | 🟢 testes focados; isolamento de fila pendente |
| `src/workers/transcript_batch.py` | `run_transcript_cycle()`, `process_call()` | 🟢 `src/workers/test_transcript_batch.py` |

## Lacunas

| ID | Descrição |
|---|---|
| GAP-RE-04 | tmpfs de 512 MB sem backpressure nem política de descarte |
| GAP-RE-08 | Métricas Prometheus de S3 medem subsistema inexistente |
| GAP-ARQ-01 | Uploader, cleanup e SMB compartilham `arq:queue`; em chamada real, outro worker consumiu `upload_recording_batch` e retornou `function not found`. Filas exclusivas especificadas, implementação pendente |
