# Onboarding: Transcrição persistida (F1)

> Procedimento de primeira validação. Use somente recursos `zenith-*` e chamadas de teste até o checkpoint de produção.

## 1. Pré-requisitos

1. Estar no branch `feature/013-transcricao-persistida`.
2. Confirmar que a imagem da aplicação foi rebuildada com o binário `whisper-cpp` e o modelo
   (D-06) — `docker compose exec zenith-api-1 whisper-cpp --help` (ou caminho equivalente do
   binário) deve responder, não `command not found`.
3. Usar exclusivamente PostgreSQL, Redis e diretório de gravações de teste com prefixo `zenith-`;
   nunca tocar recursos externos ao projeto.

## 2. Gates antes do banco

1. Rodar a suíte Red documentada em `progress.jsonl` e comprovar as falhas esperadas (worker,
   correção do `WhisperCppSTT`, geração do `.md`).
2. Confirmar `alembic upgrade head` sem erro — nenhuma migração nova é esperada (`data-delta.md`),
   então este passo só confirma que nada quebrou.

## 3. Teste unitário do fix de detecção do binário (D-05)

1. Instanciar `WhisperCppSTT` com o binário de teste presente no `$PATH`.
2. Confirmar que `transcribe()` não retorna mais `{"error": "whisper-cpp not installed"}` quando
   o binário está instalado corretamente fora do diretório de trabalho atual.

## 4. Teste do chunking (D-04)

1. Gerar (ou usar fixture) um `tx.mp3`/`rx.mp3` de teste com duração conhecida.
2. Rodar a etapa de chunking isoladamente e confirmar que o número de janelas geradas bate com a
   duração/parâmetro configurado, sem perda de áudio nas bordas dos cortes.

## 5. Teste do worker `arq-transcript` com dados fictícios

1. Colocar um par `tx.mp3`/`rx.mp3` de teste em `RECORDINGS_PATH/{tenant-teste}/{call-id-teste}/`.
2. Disparar manualmente o job (ou aguardar o ciclo de cron) e confirmar:
   2.1. Linhas `Transcript` aparecem no schema do tenant de teste, com `speaker` correto
        (`tx`→atendente, `rx`→cliente) e `extra_metadata` sem erro de kwarg (D-07).
   2.2. Reexecutar o job para o mesmo `call_id` e confirmar que não duplica linhas (RF-05).
3. Confirmar que o `.md` foi gerado localmente com o formato de `interfaces/transcript-md.md`
   (timestamp + confidence + falante por linha).

## 6. Teste do upload SMB do `.md`

1. Confirmar que o `.md` foi publicado no SMB de teste, mesmo diretório e nome-base do
   `stereo.mp3` correspondente (reaproveitando a config `SMB_*` já documentada em
   `011-smb-audio-backup/interfaces/smb.md`).
2. Simular falha do SMB (indisponibilidade) e confirmar que a gravação e o backup do `.mp3`
   continuam completando normalmente (RN-04) — a falha do `.md` fica isolada, retentada no
   próximo ciclo.

## 7. Validação com chamada real (checkpoint de produção)

1. Originar uma chamada real de teste (mesmo procedimento já usado nas features anteriores do
   Épico 1, ex. `_reversa_forward/010-record-real-call-audio-e2e/onboarding.md`).
2. Aguardar o backup SMB (`011`) concluir para essa chamada.
3. Aguardar o ciclo do worker `arq-transcript` processá-la.
4. Confirmar no SMB de produção (ou staging, conforme política do usuário) que o `.md` existe ao
   lado do `.mp3`, com conteúdo legível e falantes corretamente rotulados.
5. Confirmar no banco que `Transcript` tem as linhas correspondentes.
