# Persistência de Transcrições (workers/transcript-persist)

**Responsabilidades:** Buffer de transcrições no Redis + batch insert no PostgreSQL
**RF:** Persistir em lote a cada 5s
**Origem:** `src/workers/transcript_persist.py`
