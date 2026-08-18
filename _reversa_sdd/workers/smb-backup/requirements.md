---
spec:
  component: smb-backup
  layer: workers
  status: active
  version: 2.2.0
  language: python
  patterns: [strategy, singleton-module]
  inputs: [{name: recordings, type: "tx.wav + rx.wav", from: audio-uploader}]
  outputs: [{name: stereo_audio, type: "PCM16 stereo WAV", to: smb-storage}]
  dependencies: [{component: recording-consumers, layer: workers}, {component: recording-lifecycle, layer: audio}]
  events_produced: []
  updated_at: 2026-08-17
---

# Backup SMB de Áudio

- Consumir par WAV mono 16 kHz e ignorar `.tmp.raw`/MP3 legado incompleto.
- Na descoberta do ciclo, selecionar somente diretórios sem lease válido e com os dois canais
  estáveis em `.raw` ou `.wav`; chamada ativa, par incompleto e MP3 legado não criam lease nem
  entrada nova no transfer log.
- Após resolver metadados, reivindicar o diretório com lease SMB que exclui owners de qualquer
  estágio. Se outra operação vencer a corrida ou o par deixar de estar completo, não registrar
  tentativa no transfer log.
- Gerar `stereo.tmp.wav`, publicar `stereo.wav` e enviar remotamente como `<final>.wav.tmp` antes
  de rename/checksum.
- Marcar `.consumed-smb` somente após checksum final bem-sucedido.
- Remover temporário remoto órfão apenas após duas observações separadas por 900 s.
