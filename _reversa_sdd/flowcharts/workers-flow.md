# Fluxograma — Módulo Workers

> Atualizado na re-extração incremental de **2026-07-27** (deltas D-03/D-04).
> **S3 foi removido do projeto** — os fluxos anteriores baseados em `boto3` não valem mais.

## Gravação de chamada (produtor → consumidor) 🆕

```mermaid
flowchart TD
    A[ESLClient._handle_channel_hangup] --> B[Agrupa AudioChunks por canal]
    B --> C[enqueue_recording_upload]
    C --> D[(Fila arq / Redis)]
    D --> E[zenith-arq-uploader<br/>upload_recording_batch]
    E --> F[Para cada canal: upload_audio_chunk]
    F --> G["mkdir RECORDINGS_PATH/{tenant}/{call_id}/"]
    G --> H["grava {channel}.raw — PCM16 8kHz mono"]
    H --> I{Escrita OK?}
    I -->|Não| J[retorna failed]
    I -->|Sim| K[ffmpeg -f s16le -ar 8000 -ac 1<br/>-codec:a libmp3lame]
    K --> L{exit code 0?}
    L -->|Sim| M[remove .raw → retorna uploaded]
    L -->|Não| N[mantém .raw → uploaded_raw_only]
```

> O destino é o volume **tmpfs** `zenith_recordings_tmpfs` (512 MB, em RAM) montado em
> `/data/recordings`. Sai um MP3 mono por canal: `tx.mp3` (agente) e `rx.mp3` (cliente).

## Audio Cleanup (cron a cada 15 min) 🔄

```mermaid
flowchart TD
    A["Cron minute={0,15,30,45}"] --> B[run_cleanup]
    B --> C[SELECT tenants ativos]
    C --> D[Para cada tenant: cleanup_tenant_bucket]
    D --> E{RECORDINGS_PATH/tenant existe?}
    E -->|Não| F[skipped: Tenant directory not found]
    E -->|Sim| G[cutoff = now - AUDIO_RETENTION_DAYS]
    G --> H[os.walk no diretório do tenant]
    H --> I{st_mtime < cutoff?}
    I -->|Não| H
    I -->|Sim| J[os.remove + soma bytes_freed]
    J --> K{deleted % 1000 == 0?}
    K -->|Sim| L[await asyncio.sleep 0<br/>cede o event loop]
    K -->|Não| H
    L --> H
    H --> M[Registra métricas: deleted, bytes, duration]
    M --> D
```

> Retenção em produção: `AUDIO_RETENTION_DAYS=0.0417` (~1 hora). A frequência de 15 min
> existe porque um cron diário deixaria arquivos vivos por até 24 h antes da primeira
> avaliação — o TTL não seria respeitado de verdade.

## Transcript Persist

```mermaid
flowchart TD
    A[Novo transcript] --> B[buffer_transcript: rpush Redis]
    B --> C[call: flush_batch]
    C --> D[lrange Redis lista]
    D --> E{Lista vazia?}
    E -->|Sim| F[Retorna 0]
    E -->|Não| G[Cria Transcript objects]
    G --> H[Insere no DB via session]
    H --> I[delete Redis key]
    I --> J[Retorna count]
```

## Post-call (🔴 ainda stub)

```mermaid
flowchart TD
    A[post_call_workflow] --> B[analyze_sentiment — stub]
    B --> C[audit_procedure — stub]
    C --> D[Publica em Redis Stream call:post]
```
