---
spec:
  component: audio-ingestion
  layer: audio
  status: active
  version: 2.0.0
  language: python
  updated_at: 2026-08-14
---

# Ingestão de Áudio, Tarefas

- [ ] Testar escrita incremental e de-interleaving a 16 kHz.
- [ ] Testar admissão, lease, heartbeat, ENOSPC e chunks tardios.
- [ ] Implementar finalização idempotente nos dois gatilhos.
- [ ] Provar memória não proporcional à duração em chamada real.
