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
- **Reaproveitar a imagem da API para STT**: descartado. O worker usa imagem dedicada para manter
  binário/modelo e limites de CPU/memória fora do caminho crítico de telefonia/API (D-06).

## Host de produção — baseline 2026-08-18 (T004)

- Kernel Linux 6.8 x86_64; Docker com `overlayfs`.
- 6 vCPUs (`nproc` e `docker info`).
- 16.769.347.584 bytes de RAM; 12.387.897.344 bytes disponíveis no momento da leitura.
- A coleta foi somente leitura e filtrou containers pelo prefixo `zenith-`.

## Benchmark whisper.cpp — 2026-08-18 (T005/T006)

Imagem `zenith-transcript:013-candidate`, whisper.cpp v1.8.6, modelo `base` multilíngue e WAV
PCM16 mono 16 kHz sintético de 30 s, no host real:

| Configuração | Wall | CPU | Pico de memória |
|-------------|------|-----|-----------------|
| 1 thread, cap 1,5 CPU/768 MiB | 107,887 s | 107,310 s | 294.146.048 bytes |
| default 4 threads, mesmo cap | 126,708 s | 189,870 s | 296.878.080 bytes |

Decisão: janela 30 s, um thread, cap 1,5 CPU/768 MiB, concorrência 1 e timeout por chamada de
3.600 s. O teste de um thread foi mais eficiente sob cgroup; o pico observado cabe com margem de
mais de 2,5×. O benchmark mede custo computacional; precisão pt-BR será validada na chamada real.
