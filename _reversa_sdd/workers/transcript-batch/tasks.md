---
spec:
  component: transcript-batch-tasks
  layer: workers
  status: active
  version: 1.0.0
  language: python
  patterns: [strategy, repository]
  inputs: [{name: requirements, type: Markdown, from: transcript-batch}]
  outputs: [{name: implementation, type: Python, to: src-workers}]
  dependencies: [{component: transcript-batch, layer: workers}]
  events_produced: []
  updated_at: 2026-08-18
---

# Tarefas

- [ ] Testar e corrigir o adapter whisper.cpp (PATH, sidecar, confidence e erros).
- [ ] Testar prontidão, chunking WAV, timestamps, Markdown e mapeamento de falante.
- [ ] Testar e implementar lease, idempotência transacional e consumidor concluído.
- [ ] Testar e implementar publicação SMB, retry, timeout e isolamento.
- [ ] Criar imagem/worker dedicados, medir no host e definir limites.
- [ ] Passar gates locais, revisão independente e chamada real.
