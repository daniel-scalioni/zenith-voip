---
spec:
  component: audio-uploader
  layer: workers
  status: active
  version: 2.0.0
  language: python
  patterns: [singleton-module]
  inputs: [{name: finalized_raw, type: "tx.raw + rx.raw", from: audio-ingestion}]
  outputs: [{name: mono_wav, type: "PCM16 mono 16000 Hz", to: smb-backup}]
  dependencies: [{component: recording-lifecycle, layer: audio}]
  events_produced: []
  updated_at: 2026-08-14
---

# Upload de Áudio

- O job recebe somente `tenant_id` e `call_id`; bytes nunca trafegam pelo Redis.
- Descobre `tx.raw`/`rx.raw` finalizados e ignora `.tmp.raw`.
- Converte PCM16 mono 16 kHz em `<channel>.tmp.wav`, publica `<channel>.wav` por `os.replace` e
  preserva `.raw`, inclusive após sucesso, até confirmação dos consumidores.
- Usa `_job_id` determinístico e `.conversion-processing` para serializar retries/duplicatas.
- Raw ausente e payload antigo são no-op compatível, sem criar final vazio.
