---
spec:
  component: recording-lifecycle
  layer: audio
  status: active
  version: 1.2.0
  language: python
  updated_at: 2026-08-17
---

# Lifecycle de Gravação, Tarefas

- [ ] Testar allowlist, atomicidade, expiração/corrupção e owner.
- [ ] Implementar aquisição, renovação, heartbeat e release.
- [ ] Integrar captura, conversão, SMB e cleanup.
- [ ] Testar serialização entre mutação de lease e cleanup concorrente no mesmo diretório.
- [ ] Testar exclusão entre estágios para owners distintos e encadeamento para o mesmo owner.
