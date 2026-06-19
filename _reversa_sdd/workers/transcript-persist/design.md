# Persistência de Transcrições, Design

**Interface:** `persist_transcripts() → None`
**Fluxo:** Buffer Redis `transcripts:batch:{call_id}` → flush a cada BATCH_INSERT_INTERVAL_SECONDS (5s) → batch insert PostgreSQL
**Origem:** `src/workers/transcript_persist.py` 🟢
