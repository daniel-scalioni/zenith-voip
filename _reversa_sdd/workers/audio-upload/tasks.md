---
spec:
  component: audio-uploader
  layer: workers
  status: active
  version: 2.0.0
  language: python
  updated_at: 2026-08-14
---

# Upload de Áudio, Tarefas

- [ ] Testar conversão WAV atômica, falha e preservação do raw.
- [ ] Testar descoberta por path, payload antigo e job duplicado.
- [ ] Implementar lease de conversão e enqueue determinístico.
