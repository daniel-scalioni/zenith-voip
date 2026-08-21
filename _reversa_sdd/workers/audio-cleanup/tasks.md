---
spec:
  component: audio-cleanup
  layer: workers
  status: active
  version: 2.0.0
  language: python
  updated_at: 2026-08-14
---

# Cleanup de Áudio, Tarefas

- [ ] Testar finais consumidos e fallback por TTL.
- [ ] Testar órfãos em duas rodadas, mudança, lease e marcador corrompido.
- [ ] Testar concorrência/idempotência e proteção de controles.
- [ ] Instrumentar candidatos, exclusões e falhas.
