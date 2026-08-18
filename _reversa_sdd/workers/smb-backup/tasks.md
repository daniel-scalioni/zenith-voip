---
spec:
  component: smb-backup
  layer: workers
  status: active
  version: 2.2.0
  language: python
  updated_at: 2026-08-17
---

# Backup SMB de Áudio, Tarefas

- [ ] Testar par WAV, mixagem atômica e nome remoto parametrizado.
- [ ] Testar consumo somente após checksum e temporário remoto em duas rodadas.
- [ ] Validar arquivo real reproduzível com tx esquerdo e rx direito.
- [ ] Testar que chamada ativa, par incompleto e MP3 legado não são tocados pela descoberta.
- [ ] Testar lease com par estável e lease surgindo entre descoberta e aquisição SMB, ambos sem log.
