---
name: audio-transcript-long
description: Transcribe long audio files (>= 1h30) efficiently using Whisper/faster-whisper. Use this skill whenever the user asks to "transcribe an audio", "generate subtitles", "create an SRT", or "process long audio" into text. Triggers on phrases like "transcrever áudio", "gerar legenda", "transcrição longa".
skills: [clean-code]
---

# Audio Transcript Long

A skill designed to handle transcription of very long audio/video files (1h30m or more) sem estourar a memória (RAM ou VRAM), suportando fallback automático e gravação incremental de legendas.

## Como Usar (Instruções para o Agente)

1. Verifique se o arquivo de áudio ou vídeo de entrada existe.
2. Execute o script de transcrição:
   ```bash
   python .agent/skills/audio-transcript-long/scripts/transcribe.py --input <path/to/audio> --output <path/to/output.srt>
   ```
3. O script irá gerenciar dependências de forma transparente (instalando `faster-whisper` se houver GPU, ou `openai-whisper` na ausência) e dividirá o áudio em blocos (chunks de 10 minutos).
4. **Tratamento de OOM (Out Of Memory):** Se o script falhar e na saída houver a palavra-chave `SUGESTAO_CPU`, isso indica que a GPU não suportou mesmo fatiando o áudio. **Pare e pergunte ao usuário:** "A GPU ficou sem memória. Deseja que eu execute a transcrição utilizando apenas a CPU? (Isso será mais lento)".
5. Se o usuário confirmar o uso da CPU, re-execute o comando adicionando a flag `--force-cpu`.

## Mecanismo de Funcionamento

- **Chunking Preciso:** Utiliza `ffmpeg` para quebrar o áudio original em segmentos exatos de WAV, mantendo a precisão temporal.
- **SRT Incremental:** Cada segmento processado já é imediatamente anexado ao arquivo `.srt` final, evitando perdas em caso de interrupção.
- **Fallback Dinâmico:** Se um chunk estourar a memória (OOM), o script corta o chunk pela metade e tenta novamente de forma recursiva antes de desistir.
- **Idioma Padrão:** O idioma está forçado para Português (`pt`) visando maior assertividade.
