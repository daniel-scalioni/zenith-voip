---
spec:
  component: audio-uploader
  layer: workers
  status: active
  version: 2.0.0
  language: python
  patterns: [singleton-module]
  inputs: [{name: finalized_raw, type: path, from: audio-ingestion}]
  outputs: [{name: mono_wav, type: path, to: smb-backup}]
  dependencies: [{component: recording-lifecycle, layer: audio}]
  events_produced: []
  updated_at: 2026-08-14
---

# Upload de Áudio, Design

`upload_recording_batch(ctx, tenant_id, call_id)` adquire lease de conversão e processa os raws
existentes. `_convert_to_wav` invoca ffmpeg com `-f s16le -ar 16000 -ac 1` e saída
`pcm_s16le -ar 16000 -ac 1`. O temporário determinístico pode ser descartado/substituído sob o
lease; o nome final só aparece depois de sucesso.

O worker usa exclusivamente `zenith:audio-upload`. O produtor publica job idempotente
`recording-upload:<tenant_id>:<call_id>`.

> ✅ **GAP-RE-04 fechado (feature `014-captura-wav-16k`):** o gap original descrevia
> `upload_audio_chunk` retornando `failed` por chamada quando o tmpfs de 512 MB enchia, sem
> alarme agregado nem política de descarte. Essa arquitetura foi substituída pelo lease-based
> acima; a proteção de capacidade agora é `src/audio/capacity.py::RecordingCapacityGuard`
> (admissão com histerese 20/30%, projeta reservas + processamento pendente + headroom) com
> `record_recording_refused()`/`recording_degraded_mode` no Prometheus. Ver `workers/design.md`.
