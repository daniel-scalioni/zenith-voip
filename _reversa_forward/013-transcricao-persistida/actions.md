# Actions: Transcrição persistida (F1 — Épico 2: Qualidade do Atendimento)

> Identificador: `013-transcricao-persistida`
> Data: `2026-08-12`
> Roadmap: `_reversa_forward/013-transcricao-persistida/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 38 |
| Paralelizáveis (`[//]`) | 7 |
| Maior cadeia de dependência | 17 (T001→T009→T010→T011→T012→T013→T014→T015→T016→T017→T018→T030→T031→T032→T036→T037→T038) |

## Fase 1, Preparação

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T001 | Criar a spec SDD ativa do componente `transcript-batch` (Front Matter YAML, contrato de descoberta/idempotência/lease D-01/D-03/D-09/D-10, dependências) antes de qualquer código | - | - | `_reversa_sdd/workers/transcript-batch/design.md` | 🟢 | `[ ]` |
| T002 | Criar `Dockerfile.transcript` dedicado (D-06), com etapa de build/instalação do binário `whisper-cpp` | T001 | `[//]` | `Dockerfile.transcript` | 🟢 | `[ ]` |
| T003 | Adicionar ao `Dockerfile.transcript` o download/instalação do modelo GGML (`ggml-base.bin` ou variante), path parametrizável | T002 | - | `Dockerfile.transcript` | 🟢 | `[ ]` |
| T004 | Coletar specs reais do host de produção (`nproc`, `free -h`, `docker info`) em `10.10.10.11` e registrar (plano de migração, passo 0) | T001 | `[//]` | `_reversa_forward/013-transcricao-persistida/investigation.md` | 🟡 | `[ ]` |
| T005 | Rodar benchmark baseline de `whisper-cpp` (imagem de T003) no host real: tempo/janela, CPU%, RAM peak | T003, T004 | - | `_reversa_forward/013-transcricao-persistida/investigation.md` | 🟡 | `[ ]` |
| T006 | Definir, a partir de T005, os valores de `deploy.resources.limits` (D-06) e a duração de janela de chunk (D-04); registrar no roadmap | T005 | - | `_reversa_forward/013-transcricao-persistida/roadmap.md` | 🟡 | `[ ]` |
| T007 | Criar o esqueleto do serviço `arq-transcript` no compose (imagem `Dockerfile.transcript`, fila `zenith:transcript`, `deploy.resources.limits` de T006, sem lógica ainda) | T003, T006 | - | `docker-compose.app.yml` | 🟢 | `[ ]` |

## Fase 2, Testes

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T008 | Criar testes Red para `WhisperCppSTT` detectar o binário via `$PATH` (`shutil.which`), cobrindo ausente, presente fora do `cwd`, presente no `cwd` (D-05) | T001 | `[//]` | `src/services/test_stt_whisper.py` | 🟢 | `[ ]` |
| T009 | Criar testes Red do chunking via `ffmpeg`: janelas de tamanho fixo, arquivo menor que uma janela, corte sem perda nas bordas (D-04) | T001 | - | `src/workers/test_transcript_batch.py` | 🟢 | `[ ]` |
| T010 | Acrescentar testes Red da descoberta por polling respeitando prontidão por rename atômico (ignora par com `.tmp`/incompleto) (D-01, D-09) | T009 | - | `src/workers/test_transcript_batch.py` | 🟢 | `[ ]` |
| T011 | Acrescentar testes Red dos dois sinais de "já processado": `Transcript` existe E `.md` confirmado no SMB — não reprocessa só com um dos dois (D-03) | T010 | - | `src/workers/test_transcript_batch.py` | 🟢 | `[ ]` |
| T012 | Acrescentar testes Red do lease compartilhado com o cleanup: adquire, renova, expira, protege o diretório da chamada (D-10) | T011 | - | `src/workers/test_transcript_batch.py` | 🟢 | `[ ]` |
| T013 | Acrescentar testes Red da persistência transacional: `pg_advisory_xact_lock` por `call_id`, delete+insert idempotente, `extra_metadata` correto (não `metadata`) (D-07) | T012 | - | `src/workers/test_transcript_batch.py` | 🟢 | `[ ]` |
| T014 | Acrescentar testes Red do mapeamento de falante nos segmentos persistidos (`tx`→"atendente", `rx`→"cliente") (RN-01) | T013 | - | `src/workers/test_transcript_batch.py` | 🟢 | `[ ]` |
| T015 | Acrescentar testes Red da geração do `.md`: ordenação por tempo intercalando `tx`/`rx`, timestamp+confidence por linha, sem linha para silêncio (RF-03) | T014 | - | `src/workers/test_transcript_batch.py` | 🟢 | `[ ]` |
| T016 | Acrescentar testes Red da nomeação/upload do `.md` reaproveitando `smb_sync.build_remote_directory`/`build_remote_name` (mesmo nome-base do `.mp3`) (D-08, RN-03) | T015 | - | `src/workers/test_transcript_batch.py` | 🟢 | `[ ]` |
| T017 | Acrescentar testes Red do isolamento best-effort: falha simulada do Whisper não impede gravação/backup; falha simulada do SMB não impede persistência no Postgres (RN-04) | T016 | - | `src/workers/test_transcript_batch.py` | 🟢 | `[ ]` |
| T018 | Acrescentar testes Red de concorrência: duas execuções simultâneas do mesmo `call_id` não duplicam nem corrompem (advisory lock cobre) | T013, T017 | - | `src/workers/test_transcript_batch.py` | 🟢 | `[ ]` |

## Fase 3, Núcleo

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T019 | Corrigir `WhisperCppSTT.__init__`/`transcribe()`: trocar `os.path.exists(self.whisper_binary)` por `shutil.which(self.whisper_binary)` (D-05) | T008 | `[//]` | `src/services/stt_whisper.py` | 🟢 | `[ ]` |
| T020 | Criar o esqueleto do módulo `transcript_batch.py` (`WorkerSettings`, cron job, fila) | T001, T007 | - | `src/workers/transcript_batch.py` | 🟢 | `[ ]` |
| T021 | Implementar a função de chunking via `ffmpeg` com a duração definida em T006 (D-04) | T009, T006, T020 | - | `src/workers/transcript_batch.py` | 🟡 | `[ ]` |
| T022 | Implementar a descoberta por polling reaproveitando a garantia de prontidão de `011` (ignora `.tmp`) (D-01, D-09) | T010, T020 | - | `src/workers/transcript_batch.py` | 🟢 | `[ ]` |
| T023 | Implementar a checagem dos dois sinais de "já processado" (D-03) | T011, T022 | - | `src/workers/transcript_batch.py` | 🟢 | `[ ]` |
| T024 | Implementar o lease compartilhado com o cleanup (D-10) | T012, T022 | - | `src/workers/transcript_batch.py` | 🟢 | `[ ]` |
| T025 | Implementar a orquestração por chamada: ler `tx`/`rx`, chunkar (T021), chamar `WhisperCppSTT` (T019) por janela/canal, mapear falante (RN-01) | T019, T021, T014, T022 | - | `src/workers/transcript_batch.py` | 🟢 | `[ ]` |
| T026 | Implementar a persistência transacional com advisory lock + delete/insert e `extra_metadata` correto (D-07) | T013, T025 | - | `src/workers/transcript_batch.py` | 🟢 | `[ ]` |
| T027 | Implementar a geração do `.md` consolidado (formato de `interfaces/transcript-md.md`) | T015, T026 | - | `src/workers/transcript_batch.py` | 🟢 | `[ ]` |
| T028 | Implementar a nomeação/upload do `.md` reaproveitando `smb_sync.py` (D-08) | T016, T027 | - | `src/workers/transcript_batch.py` | 🟢 | `[ ]` |
| T029 | Implementar o isolamento best-effort (falha de STT/SMB não bloqueia gravação/backup) + log estruturado por `call_id` (RN-04, RNF Observabilidade) | T017, T028 | - | `src/workers/transcript_batch.py` | 🟢 | `[ ]` |
| T030 | Implementar a proteção de concorrência ponta a ponta, ligando lease (T024) e advisory lock (T026) na mesma execução | T018, T023, T024, T026 | - | `src/workers/transcript_batch.py` | 🟢 | `[ ]` |

## Fase 4, Integração

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T031 | Completar o serviço `arq-transcript` no compose: comando real, volume `zenith_recordings_tmpfs`, `depends_on` postgres/redis | T007, T030 | - | `docker-compose.app.yml` | 🟢 | `[ ]` |
| T032 | Confirmar fila exclusiva `zenith:transcript` sem herdar a fila default (D-02) | T031 | - | `docker-compose.app.yml` | 🟢 | `[ ]` |
| T033 | Rodar `alembic upgrade head` e confirmar que nenhuma migração nova é necessária (`data-delta.md`) | T026 | `[//]` | `_reversa_forward/013-transcricao-persistida/data-delta.md` | 🟢 | `[ ]` |

## Fase 5, Polimento

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T034 | Instrumentar métricas/logs adicionais (chamadas transcritas, falhas, tamanho da fila `zenith:transcript`, mesmo padrão de `set_smb_queue_size`) | T029 | `[//]` | `src/utils/telemetry.py`, `src/workers/transcript_batch.py` | 🟢 | `[ ]` |
| T035 | Atualizar `_reversa_sdd/ai/epico-2-qualidade-atendimento.md` marcando F1 como implementada, registrando D-06/D-09/D-10/D-11 como contexto herdado para F2+ | - | `[//]` | `_reversa_sdd/ai/epico-2-qualidade-atendimento.md` | 🟢 | `[ ]` |
| T036 | Validar com chamada real em produção (`onboarding.md`, seção 7): `.md` no SMB ao lado do `.mp3`, `Transcript` no banco | T031, T032 | - | `_reversa_forward/013-transcricao-persistida/onboarding.md` | 🟢 | `[ ]` |
| T037 | Rodar a suíte completa `pytest -v tests src --cov=src --cov-fail-under=80` e registrar o resultado | T036 | - | `progress.jsonl` | 🟢 | `[ ]` |
| T038 | Chamar `advisor()` sobre os testes (T008-T018) e o código implementado (T019-T030), perguntando por casos de borda não cobertos e viés de implementação; registrar veredito | T037 | - | `_reversa_forward/013-transcricao-persistida/test-bias-verdict.md` | 🟢 | `[ ]` |

## Notas de execução

### 2026-08-12 — rodada de `/reversa-coding` encerrada sem execução (bloqueio de sequenciamento)

Nenhuma ação foi executada nesta rodada. Durante a orientação do `/reversa-coding` apareceram
quatro achados que não estavam nos artefatos de planejamento, e um deles levou a uma decisão do
usuário de reordenar features:

1. **Formato do áudio de origem (bloqueante, decisão do usuário).** A captura hoje é PCM16 mono
   **8 kHz** por canal (`mod_audio_stream ... stereo 8k` no dialplan → `.raw` →
   `audio_uploader._convert_to_mp3` com `-ar 8000`), enquanto o `whisper.cpp` exige WAV 16 kHz
   mono. O plano original resolveria isso com transcode dentro do chunking (T021). O usuário
   decidiu o contrário: mudar a **produção** do áudio para WAV 16 kHz na origem, em feature e
   branch próprios (`feature/014-captura-wav-16k`), e só depois retomar a 013 assumindo `.wav`
   puro. MP3 foi um formato arbitrário, não um requisito.
2. **O lease de D-10 não protege nada como especificado.** `audio_cleanup.py` chama
   `has_valid_lease(root)`, que tem `.smb-processing` hardcoded (`smb_sync.py:197`), e
   `smb_sync.process_call` apaga esse arquivo incondicionalmente no `finally` (`smb_sync.py:600`).
   Lease com nome novo fica invisível ao cleanup; lease com o mesmo nome é apagado por um ciclo
   concorrente do smb_sync. Correção autorizada pelo usuário: generalizar `write_lease`/
   `has_valid_lease` para lease nomeado (default `.smb-processing`) e fazer o cleanup honrar
   qualquer `.*-processing`.
3. **`WhisperCppSTT` tem mais defeitos que o de D-05.** Além do `os.path.exists` → `shutil.which`,
   `confidence` é lido de `avg_logprob` (log-prob negativo, incompatível com o `0.94` de
   `interfaces/transcript-md.md`) e `-oj` grava JSON sidecar em vez de stdout, o que torna
   `json.loads(result.stdout)` suspeito. T019 precisa cobrir os três.
4. **`build_remote_name` fixa `.mp3`** (`smb_sync.py:117`), contrariando D-08 ("reaproveitado sem
   alteração"). Correção autorizada: kwarg `extension=".mp3"`, default preservando os testes
   existentes.
5. **D-03 deve usar `_list_names`, não `_remote_sha`** para checar o `.md` remoto — `_remote_sha`
   baixa o arquivo inteiro a cada ciclo de polling.

Também autorizado: benchmark de `whisper-cpp` no host de produção `10.10.10.11` (T005), a ser
executado **sobre WAV 16 kHz** quando a 014 entregar esse formato — medir sobre MP3 8 kHz agora
mediria um pipeline que deixará de existir.

Ao retomar esta feature, o `actions.md` precisa ser revisado: T021 perde a etapa de reamostragem,
T019 ganha escopo, e T009/T022 passam a falar de `tx.wav`/`rx.wav`.

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-08-12 | Versão inicial gerada por `/reversa-to-do` | reversa |
| 2026-08-12 | Nota de execução: rodada de `/reversa-coding` encerrada sem execução; 013 pausada em favor da 014 (captura WAV 16 kHz) por decisão do usuário; 4 achados de código registrados | reversa |
