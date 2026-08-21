---
spec:
  component: workers
  layer: workers
  status: active
  version: 3.0.0
  language: python
  updated_at: 2026-08-14
---

# Workers, Design Técnico

> Gerado pelo Writer — 2026-06-19
> **Revisado na re-extração incremental — 2026-07-27** (deltas D-03/D-04)

## Interface

| Worker | Função | Gatilho | Fila exclusiva | Container |
|--------|--------|---------|----------------|-----------|
| audio_uploader | `upload_recording_batch(tenant_id, call_id)` | Job arq enfileirado na finalização da captura | `zenith:audio-upload` | `zenith-arq-uploader` |
| audio_cleanup | `run_cleanup()` | Cron ARQ a cada 15 min | `zenith:audio-cleanup` | `zenith-arq-cleanup` |
| smb_sync | `run_smb_sync()` | Cron ARQ a cada 5 min | `zenith:smb-sync` | `zenith-smb-sync` |
| post_call | `run_post_call(call_id)` | Evento `CHANNEL_HANGUP` | fora desta decisão | — |
| transcript_persist | `persist_transcripts()` | Batch a cada 5s | fora desta decisão | — |

## Isolamento de filas ARQ

Contrato aprovado após o E2E de 2026-07-29:

1. Cada `WorkerSettings` operacional define `queue_name` igual à sua fila exclusiva.
2. `enqueue_recording_upload()` publica `upload_recording_batch` explicitamente em
   `zenith:audio-upload`, usando `default_queue_name` no pool ou `_queue_name` no enqueue.
3. Os crons de cleanup e SMB são materializados somente nas filas dos próprios workers.
4. A fila default `arq:queue` não é usada por uploader, cleanup ou SMB sync.
5. Nomes de função permanecem distintos; não registrar todas as funções em todos os workers.
6. Jobs falhos anteriores à correção não são reenfileirados: o E2E deve usar uma nova chamada.

### Motivo

ARQ usa uma fila Redis compartilhada por padrão. Ter containers separados não isola consumo:
qualquer worker pode retirar qualquer job da fila. Em chamada real, `upload_recording_batch` foi
retirado por um worker que não registra essa função, produzindo `JobExecutionFailed: function
'upload_recording_batch' not found`. Também foram observadas colisões equivalentes com
`cron:run_cleanup` e `cron:run_smb_sync`.

## Fluxo Principal (Gravação WAV 16 kHz)

1. `AudioIngestor.finalize_stream()` publica `.tmp.raw` como `.raw` e chama
   `enqueue_recording_upload(tenant_id, call_id)` sem bytes no Redis.
2. `enqueue_recording_upload` obtém um pool arq lazy (`_get_pool()`, singleton de módulo) associado
   à fila `zenith:audio-upload` e enfileira `upload_recording_batch` nessa fila.
3. `zenith-arq-uploader` adquire `.conversion-processing` e descobre os raws finalizados.
4. Para cada canal:
   - `os.makedirs(RECORDINGS_PATH/<tenant>/<call_id>)`
   - lê `<channel>.raw` (PCM16 16 kHz mono)
   - `ffmpeg -f s16le -ar 16000 -ac 1 -i <raw> -codec:a pcm_s16le <tmp.wav>` via
     `asyncio.create_subprocess_exec`
   - em sucesso, publica `.wav` por `os.replace` e preserva o `.raw`
   - em falha do ffmpeg, mantém o `.raw` e descarta o temporário incompleto
   - em falha da **escrita**, retorna `failed` sem tentar converter

### Por que WAV mono por canal

`tx` e `rx` ficam separados por decisão de produto: o uso pretendido é auditoria humana, e o
canal isolado permite avaliar o atendente sem o ruído do outro lado. Áudio misturado
inviabilizaria isso. Ver ADR-009.

## Fluxo Principal (Cleanup)

1. Cron ARQ dispara `run_cleanup()` nos minutos 0, 15, 30 e 45 — `audio_cleanup.py:59-62`
2. `SELECT` dos tenants ativos no schema public
3. Para cada tenant, `cleanup_tenant_bucket()`:
   - se `RECORDINGS_PATH/<tenant>` não existe → `skipped`
   - `cutoff = now - AUDIO_RETENTION_DAYS`
   - remove finais plenamente consumidos; o cutoff continua como segurança
   - temporários locais allowlisted entram em `.cleanup-candidates.json` na primeira rodada
   - na rodada seguinte, após 900 s, lease e fingerprint são revalidados antes da exclusão
   - `await asyncio.sleep(0)` a cada 1000 remoções, cedendo o event loop
4. Registra `deleted_count`, `bytes_freed`, `duration`

O cron e as funções de cleanup são consumidos exclusivamente de `zenith:audio-cleanup`.

### Por que 15 minutos

Com retenção de ~1 hora, um cron diário às 03:00 deixaria arquivos vivos por até 24 h antes
da primeira avaliação — o TTL não seria respeitado de verdade.

### Correções de configuração do arq (2026-07-10)

| Item | Antes | Agora |
|---|---|---|
| `redis_settings` | `settings.REDIS_URL` (string crua, inválida) | `RedisSettings.from_dsn(settings.REDIS_URL)` |
| Parâmetro do cron | `run_on_startup` (kwarg inexistente, ignorado) | `run_at_startup` |

Antes disso o `arq-cleanup` ficava em crash loop e nunca executou uma limpeza.

## Fluxo Principal (Transcript Persist)

1. Transcripts bufferizados no Redis em lista `transcripts:batch:{call_id}`
2. A cada 5s (`BATCH_INSERT_INTERVAL_SECONDS`), flush para PostgreSQL
3. Insert em lote na tabela `transcripts`

## Armazenamento

| Propriedade | Valor |
|---|---|
| Caminho | `RECORDINGS_PATH/<tenant_id>/<call_id>/<channel>.mp3` |
| Backing | volume `zenith_recordings_tmpfs`, **tmpfs de 512 MB (RAM)** |
| Montado por | `zenith-api-1`, `zenith-api-2`, `zenith-arq-uploader`, `zenith-arq-cleanup` |
| TTL em produção | `AUDIO_RETENTION_DAYS=0.0417` (~1 h) |
| Persistência | ❌ zerado no restart do container |

## Lacunas

- 🔴 `analyze_sentiment()` e `audit_procedure()` — stubs, `src/workers/post_call.py:7-12`
- 🔴 GAP-RE-04: tmpfs sem backpressure. Enchendo o volume, cada gravação falha
  individualmente (`failed`) sem alarme agregado e sem descarte do mais antigo
- 🔴 Retenção é global, não por tenant
- 🟡 Sem monitoramento de workers (dead letters, retry)
- 🟡 `ffmpeg` é dependência de runtime da imagem, sem verificação no boot do container
- 🟡 GAP-ARQ-01: isolamento de filas especificado após falha E2E; código e redeploy pendentes
