# Regression Watch — Feature 013

Monitorar após rollout:

- `transcript_failed_total{reason=...}` e ausência prolongada de `transcript_success_total`;
- `transcript_backlog_dropped_total{tenant_id=...}` maior que zero;
- crescimento de `transcript_queue_size` além da vazão medida;
- leases `.transcription-processing` vencidos ou perda recorrente de heartbeat;
- `.md` sem WAV de mesmo nome-base ou divergência com `remote_name` do transfer log;
- queda de espaço livre do tmpfs abaixo de `RECORDING_RESUME_FREE_PERCENT`;
- latência de ciclo próxima de `TRANSCRIPT_CYCLE_TIMEOUT_SECONDS`.

Rollback funcional: parar somente `zenith-arq-transcript` e restaurar
`RECORDING_REQUIRED_CONSUMERS=["smb"]`; captura e backup SMB permanecem operacionais.

## W001 — DATABASE_URL desviado da porta real do Postgres

Origem: descoberto durante T036 (checkpoint de produção, 2026-08-19). O `.env` do host
(`10.10.10.11:/home/administrator/zenith-voip/.env`) tinha `DATABASE_URL` de `zenith-arq-transcript`
e `zenith-arq-cleanup` apontando para a porta **5433** — porta que só existe como mapeamento
externo host→container do `zenith-postgres-candidate` (`docker-compose.infra.yml`, `"5433:5432"`),
não como porta ouvida dentro da rede `ai-hub-net`. `zenith-api-1`/`zenith-arq-uploader` sempre
usaram a porta correta (5432) porque foram recriados num `docker compose up` com o shell exportando
`DATABASE_URL` correto — mascarando a divergência do `.env` até esta feature recriar
`arq-transcript`/`arq-cleanup` sem esse export.

Sinal de violação: `transcription_pending ... error=ConnectionRefusedError` nos logs de
`zenith-arq-transcript`, ou qualquer consumidor best-effort do banco falhando silenciosamente
(RN-04 engole o erro, chamada continua normal, só a transcrição/limpeza param).

Correção aplicada: `.env` corrigido para 5432 (backup salvo como `.env.bak-013-fix-*`), containers
recriados via `docker compose up -d --no-deps arq-transcript arq-cleanup`. **Watch**: qualquer
`docker compose up` futuro para esses dois serviços sem o shell exportando `DATABASE_URL`
explicitamente volta a usar o `.env` do disco — reconferir a porta viva
(`docker exec <container> env | grep DATABASE_URL`) depois de qualquer recriação.
