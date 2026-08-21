# Persistência de Transcrições, Design

**Interface:** `TranscriptPersister.buffer_transcript()` / `.flush_batch()` (não `persist_transcripts()` — a spec original nomeava uma função que nunca existiu no código)
**Fluxo:** Buffer Redis `transcripts:batch:{call_id}` → flush sob demanda → batch insert PostgreSQL
**Origem:** `src/workers/transcript_persist.py` 🔴 — módulo **órfão desde o commit inicial do
projeto** (`cfd12b5`, nunca mais tocado; confirmado via `git log --follow`), sem nenhum chamador
em `src/` e sem arquivo de teste. Foi **superado pela feature `013-transcricao-persistida`**:
`src/workers/transcript_batch.py` é o worker real de persistência de transcrições — está
registrado em `docker-compose.app.yml` (`arq src.workers.transcript_batch.WorkerSettings`) e
`Dockerfile.transcript`, lê WAV de `recording_lifecycle` e grava em `Transcript` via
`get_tenant_db()`. `transcript_persist.py` é scaffold morto do MVP inicial, não uma
implementação concorrente ativa. Ver GAP-04 (`gaps.md`).
