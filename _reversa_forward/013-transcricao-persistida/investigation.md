# Investigation: Transcrição persistida (F1)

> Identificador: `013-transcricao-persistida`
> Data: `2026-08-12`

## Pesquisa de fundo

Comparação de engines de STT gratuitas para transcrição assíncrona em português (feita antes da
decisão registrada em `requirements.md`, sessão de 2026-08-12):

| Opção | WER pt-BR (aprox.) | Requer GPU | Já integrado no projeto | Decisão |
|-------|----------------------|--------------|----------------------------|---------|
| Whisper.cpp | ~7-10% | Não | Sim (`WhisperCppSTT`, nunca exercitado) | **Escolhido** — menor avanço possível, zero infra nova além do binário/modelo |
| Voxtral Mini Transcribe V2 (Mistral AI, fev/2026, Apache 2.0) | ~4-6% | Recomendado | Não | Descartado nesta feature — exigiria runtime `vLLM` novo, componente de infra inexistente hoje; ver `_reversa_sdd/ai/epico-2-qualidade-atendimento.md` para reavaliar em feature futura se a precisão do Whisper.cpp se mostrar insuficiente |
| Deepgram (já integrado) | — | — | Sim | Reservado para a análise em tempo real (F6), fora de escopo de F1 por decisão do usuário |

Fontes consultadas nesta sessão:
- [faster-whisper vs whisper.cpp vs OpenAI Whisper (2026)](https://codersera.com/blog/faster-whisper-vs-whisper-cpp-speech-to-text-2026/)
- [Voxtral vs Whisper 2026: WER Benchmarks](https://weesperneonflow.ai/en/blog/2026-03-31-voxtral-whisper-open-source-speech-models-comparison-2026/)
- [Voxtral Transcribe 2 Review](https://screenapp.io/blog/voxtral-transcribe-2-review-comparison)
- [Northflank — Best open source STT 2026](https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks)

## Padrões aplicáveis já em uso no projeto (reaproveitados nesta feature)

- **Cron polling sobre diretório de gravações**, com verificação de idempotência antes de
  processar — mesmo padrão de `run_smb_sync`/`_run_cycle` (`src/workers/smb_sync.py`, feature
  `011-smb-audio-backup`).
- **Fila ARQ exclusiva por worker** — `arq-uploader`/`arq-cleanup`/`arq-smb-sync`, cada um com
  fila própria (`RF-13` de `011`). Esta feature segue o mesmo princípio (`zenith:transcript`).
- **Chunking de áudio via `ffmpeg`** — já usado pela skill do projeto `audio-transcript-long`
  (`.agents/skills/audio-transcript-long/scripts/transcribe.py`) para transcrição de áudio longo;
  esta feature aplica o mesmo mecanismo de corte preciso, adaptado ao motor já decidido
  (`WhisperCppSTT`) e ao formato de saída (`.md`, não `.srt`).
- **Reaproveitamento de conexão/nomenclatura SMB** já implementada em `src/workers/smb_sync.py`
  (`build_remote_directory`, `build_remote_name`, `SMBConnection`) — evita duplicar client SMB.

## Alternativas avaliadas e descartadas

- **Hook síncrono no `CHANNEL_HANGUP`** para disparar a transcrição imediatamente: descartado em
  favor do polling já validado pela `011`, para não acoplar o domínio de qualidade ao caminho
  crítico de telefonia (RN-04).
- **Reaproveitar `TranscriptPersister` (buffer Redis + flush batch) só corrigindo o bug de
  kwarg**: descartado após consulta `/brainstorming-multiagent` — ver `requirements.md#9` e
  `roadmap.md#D-07` para o racional completo.
- **Container dedicado só para STT**: avaliado e adiado — a imagem da aplicação já tem `ffmpeg`
  instalado e o padrão de workers ARQ do projeto reaproveita a mesma imagem para todos os
  serviços de background; separar exigiria justificativa mais forte do que o observado nesta
  feature (ver `roadmap.md#9`, risco de tamanho de imagem).
