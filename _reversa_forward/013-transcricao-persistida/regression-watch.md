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
