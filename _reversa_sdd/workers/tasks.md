# Workers, Tarefas de Implementação

> Gerado pelo Writer — 2026-06-19

## Tarefas

- [ ] T-01, Implementar worker de cleanup S3 (cron 03:00)
  - Origem: `src/workers/audio_cleanup.py:32-101`
  - Critério: áudio com > 90 dias deletado em lotes de 1000
  - Confiança: 🟢

- [ ] T-02, Implementar worker de upload S3
  - Origem: `src/workers/audio_uploader.py`
  - Critério: áudio enviado para bucket {prefix}-{tenant_id}
  - Confiança: 🟢

- [ ] T-03, Implementar worker de persistência de transcrições (batch)
  - Origem: `src/workers/transcript_persist.py`
  - Critério: transcripts bufferizados no Redis e persistidos em lote a cada 5s
  - Confiança: 🟢

- [ ] T-04, Implementar worker pós-chamada
  - Origem: `src/workers/post_call.py:7-12`
  - Critério: sentimento e auditoria executados (resolver 🔴 stubs)
  - Confiança: 🔴

## Tarefas de Teste

- [ ] TT-01, Testar cleanup S3 (lotes de 1000)
- [ ] TT-02, Testar upload S3
- [ ] TT-03, Testar batch persist de transcrições
- [ ] TT-04, Testar worker pós-chamada
