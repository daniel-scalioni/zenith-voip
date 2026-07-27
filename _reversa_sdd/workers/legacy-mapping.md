# Módulo: workers

> Gerado pelo Archaeologist — 2026-06-19
> **Re-extração incremental — 2026-07-27** (base `48da5b1` → `0658157`, deltas D-03/D-04)
> Confiança: 🟢 CONFIRMADO

## Arquivos

| Arquivo | Propósito | Linhas |
|---------|-----------|--------|
| `src/workers/audio_cleanup.py` | Limpeza de gravações locais (cron a cada 15 min) | 78 |
| `src/workers/audio_uploader.py` | Persistência local de gravações + conversão MP3 | 76 |
| `src/workers/post_call.py` | Workflow pós-chamada (sentiment + audit) | 32 |
| `src/workers/transcript_persist.py` | Persistência em lote de transcrições | 45 |

## ⚠️ Mudança estruturante: S3 foi removido

A extração de 2026-06-19 documentava os dois workers de áudio como clientes S3
(`boto3`, buckets `{prefix}-{tenant_id}`, `put_object`, `delete_objects`). **Isso não existe
mais.** `boto3` saiu do `requirements.txt` e todo o armazenamento passou a ser **filesystem
local** sob `settings.RECORDINGS_PATH` (`/data/recordings`), montado como **tmpfs de 512 MB**
(volume `zenith_recordings_tmpfs`) — ou seja, a gravação vive em RAM, não em disco.

## Fluxo de Controle

### audio_uploader.py (🔄 reescrito)
- `upload_audio_chunk(ctx, tenant_id, call_id, channel, audio_data)`:
  1. Cria `RECORDINGS_PATH/<tenant_id>/<call_id>/` e grava `<channel>.raw` (PCM16 bruto).
  2. `_convert_to_mp3()` → `ffmpeg -f s16le -ar 8000 -ac 1 -i <raw> -codec:a libmp3lame <mp3>`
     via `asyncio.create_subprocess_exec`; remove o `.raw` em caso de sucesso.
  3. Se o `ffmpeg` falhar, retorna `uploaded_raw_only` — o áudio bruto já está salvo,
     nada se perde. Se a **escrita** falhar, retorna `failed`.
- `upload_recording_batch(ctx, tenant_id, call_id, recordings)` → itera os canais.
- 🆕 `enqueue_recording_upload(tenant_id, call_id, recordings)` → produtor: obtém um pool arq
  lazy (`_get_pool()`, singleton de módulo) e enfileira `upload_recording_batch`. É o ponto
  chamado por `ESLClient._handle_channel_hangup()`.
- Formato de saída: **MP3 mono 8 kHz por canal** (`tx.mp3`, `rx.mp3`) — decisão explícita de
  não misturar nem manter estéreo.

### audio_cleanup.py (🔄 reescrito)
- Worker ARQ com cron **a cada 15 minutos** (`minute={0,15,30,45}`), não mais 03:00 diário:
  com retenção de ~1 h, uma varredura diária deixaria arquivos vivos por até 24 h.
- `run_cleanup(ctx)` → lista tenants ativos do DB e executa cleanup por tenant.
- `cleanup_tenant_bucket(ctx, tenant_id)` → `os.walk` em `RECORDINGS_PATH/<tenant_id>`,
  remove arquivos com `st_mtime` anterior ao cutoff; cede o event loop (`await asyncio.sleep(0)`)
  a cada 1000 arquivos. Retorna `skipped` se o diretório do tenant não existir.
- `WorkerSettings.redis_settings` agora usa `RedisSettings.from_dsn(settings.REDIS_URL)`
  (antes passava a string crua, que o arq não aceita) e `run_at_startup` (nome correto do
  parâmetro; o anterior `run_on_startup` era ignorado silenciosamente).
- Métricas mantidas: `deleted_count`, `bytes_freed`, `duration`.

### post_call.py
- Worker ARQ: `post_call_workflow()` executa sentiment + audit.
- **Continua stub** (retorna valores fixos) — lacuna não endereçada nesta re-extração.
- Publica resultado no Redis Stream `call:post`.

### transcript_persist.py
- `TranscriptPersister` faz buffer de transcrições no Redis (lista) e flush em lote.
- `buffer_transcript()` → `rpush`; `flush_batch()` → lê, cria `Transcript`, insere, apaga.

## Deploy

Serviço `zenith-arq-uploader` 🆕 no `docker-compose.app.yml`
(`arq src.workers.audio_uploader.WorkerSettings`), montando o mesmo tmpfs de gravações que
`fastapi-1`, `fastapi-2` e `zenith-arq-cleanup`. Sem esse container, `enqueue_recording_upload`
enfileira e ninguém consome.

## Regras de Negócio

| Regra | Local | Confiança |
|-------|-------|-----------|
| 🔄 Cleanup roda a cada 15 minutos (era 03:00 diário) | `audio_cleanup.py:59-62` | 🟢 |
| 🔄 Retenção padrão de produção: **~1 hora** (`AUDIO_RETENTION_DAYS=0.0417`) | `docker-compose.app.yml` | 🟢 |
| 🔄 Default do código continua 90 dias (`float`) | `config.py` | 🟢 |
| 🆕 Gravação é salva em tmpfs (RAM), não em disco nem em S3 | `docker-compose.app.yml` | 🟢 |
| 🆕 Cada canal vira um MP3 mono 8 kHz separado | `audio_uploader.py:11,25-33` | 🟢 |
| 🆕 Falha de conversão preserva o `.raw` (`uploaded_raw_only`) | `audio_uploader.py:52-55` | 🟢 |
| 🆕 Cleanup cede o event loop a cada 1000 arquivos | `audio_cleanup.py:40-41` | 🟢 |
| Transcrições bufferizadas no Redis e persistidas em lote | `transcript_persist.py:14-42` | 🟢 |
| Post-call workflow (stub) | `post_call.py:7-13` | 🔴 LACUNA |

## Regras que deixaram de existir

| Regra (2026-06-19) | Situação |
|---|---|
| Retenção de áudio: 90 dias | Substituída por ~1 h em produção |
| Delete em lotes de 1000 objetos S3 | S3 removido; hoje é `os.remove` arquivo a arquivo |
| Bucket naming `{prefix}-{tenant_id}` | Substituído por `RECORDINGS_PATH/<tenant>/<call_id>/<channel>.mp3` |
| Skip quando `S3_ENDPOINT` vazio | Removido — não há mais configuração de S3 |
