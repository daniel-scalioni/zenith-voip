# Impacto no legado — Feature 013

| Componente | Tipo | Impacto | Proteção de regressão |
|------------|------|---------|-----------------------|
| `src/services/stt_whisper.py` | regra-alterada | Adapter usa `whisper-cli`, JSON completo, offsets em ms e confidence normalizada | Testes de binário, sidecar, payload, timeout e cancelamento |
| `src/workers/transcript_batch.py` | componente-novo | Transcrição pós-chamada, persistência, Markdown e ownership SMB | Testes de WAV, chunk, silêncio, colisão, retry, lease e idempotência |
| `src/workers/audio_cleanup.py` | regra-alterada | Preserva backlog saudável e aplica TTL sob pressão de capacidade | Testes acima/abaixo da margem e métrica de shedding |
| `src/audio/recording_lifecycle.py` | regra-alterada | Novo estágio `transcription` na exclusão cross-stage | Suíte de lifecycle e probes concorrentes |
| `src/workers/smb_sync.py` | interface-ampliada | Listagem assíncrona e transfer log como ownership da saída WAV | Testes SMB existentes e regressões da 013 |
| `docker-compose.app.yml` | infraestrutura | Worker `zenith-arq-transcript`, fila e recursos exclusivos | Parse/gate Compose e smoke da imagem candidata |

Telefonia, captura e backup continuam independentes do STT. A transcrição é best-effort: falha
não interrompe chamadas; sob pressão, backlog vencido pode ser descartado com log e métrica para
preservar a admissão de novas gravações.
