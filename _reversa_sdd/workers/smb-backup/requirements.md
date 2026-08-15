---
spec:
  component: smb-backup
  layer: workers
  status: active
  version: 2.0.0
  language: python
  patterns: [strategy, singleton-module]
  inputs: [{name: recordings, type: "tx.wav + rx.wav", from: audio-uploader}]
  outputs: [{name: stereo_audio, type: "PCM16 stereo WAV", to: smb-storage}]
  dependencies: [{component: recording-consumers, layer: workers}, {component: recording-lifecycle, layer: audio}]
  events_produced: []
  updated_at: 2026-08-14
---

# Backup SMB de Áudio

- Consumir par WAV mono 16 kHz e ignorar `.tmp.raw`/MP3 legado incompleto.
- Gerar `stereo.tmp.wav`, publicar `stereo.wav` e enviar remotamente como `<final>.wav.tmp` antes
  de rename/checksum.
- Marcar `.consumed-smb` somente após checksum final bem-sucedido.
- Remover temporário remoto órfão apenas após duas observações separadas por 900 s.
