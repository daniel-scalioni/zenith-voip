---
spec:
  component: transcript-batch
  layer: workers
  status: active
  version: 1.1.0
  language: python
  patterns: [strategy, repository, observer]
  inputs:
    - {name: recording_pair, type: "WAV PCM16 mono 16 kHz", from: audio-uploader}
    - {name: call_metadata, type: Call, from: postgres}
  outputs:
    - {name: transcript_segments, type: "list[Transcript]", to: postgres}
    - {name: transcript_markdown, type: Markdown, to: smb-backup}
  dependencies:
    - {component: recording-lifecycle, layer: audio}
    - {component: smb-backup, layer: workers}
    - {component: whisper-cpp-stt, layer: services}
    - {component: smb-transfer-log, layer: workers}
  events_produced: []
  updated_at: 2026-08-18
---

# Transcrição pós-chamada em lote

## Contrato

O worker descobre diretórios `RECORDINGS_PATH/{tenant_id}/{call_id}` que contenham os dois
arquivos finais `tx.wav` e `rx.wav`. Cada arquivo deve ter cabeçalho WAV legível, PCM sem
compressão, 16 bits, mono, 16 kHz e pelo menos um frame. Arquivos `.tmp`, formato divergente,
canal ausente ou somente um canal mantêm o diretório pendente e invisível a logs de falha.

Cada WAV é dividido, sem reamostragem, em janelas de duração configurada. `tx` representa
`atendente`, `rx` representa `cliente`; ambos partem do tempo relativo zero e os timestamps de
segmento recebem a soma das durações reais dos chunks anteriores, medida pelos frames WAV, sem
assumir que o muxer cortou exatamente no segundo configurado. Silêncio não gera segmento.

## Idempotência e concorrência

- A descoberta só ignora uma chamada falada quando existem segmentos no Postgres **e** o `.md`
  exato está presente no diretório SMB indicado pelo transfer log. Se esses dois sinais existem
  mas `.consumed-transcription` não, o ciclo repara o marcador sob o lock do lifecycle e não
  repete STT. Para silêncio, `.consumed-transcription` + `.md` explícito são o resultado terminal
  válido, pois zero segmentos no banco é parte do contrato.
- A escrita usa `pg_advisory_xact_lock(hashtext(call_id))`, delete e insert na mesma transação.
- O estágio `transcription` participa do lifecycle cross-stage. O lease é renovado durante STT e
  impede cleanup, conversão ou SMB concorrentes por outro owner.
- `.consumed-transcription` só é criado após persistência e publicação do `.md` concluírem.
- O `remote_name` e o diretório do WAV vêm do registro `done` da própria chamada em
  `smb_transfer_log.json`; presença de um nome candidato no SMB não prova ownership em colisões.
- Áudio sem fala é conclusão válida: persiste zero segmentos, publica um Markdown explícito e
  marca consumo, sem retry infinito.

## Falhas

Falhas de STT, banco, timeout ou SMB são registradas com `tenant_id` e `call_id`, liberam o lease,
não afetam captura/backup e deixam a chamada elegível ao próximo polling. O worker processa uma
chamada por vez e usa fila ARQ exclusiva `zenith:transcript`. O timeout do ciclo é maior e
independente do timeout por chamada para que uma chamada lenta não cancele o backlog seguinte.

## Saída Markdown

O nome troca somente a extensão do `remote_name` WAV pertencente à chamada no item `done` do
transfer log. A listagem SMB apenas confirma que esse WAV exato existe; nunca seleciona entre
base nominal e sufixo de colisão por presença, nem infere ownership pelo namespace de Markdown.
As falas são ordenadas por `start_time` e mostram intervalo, falante e confidence em `[0,1]`.
