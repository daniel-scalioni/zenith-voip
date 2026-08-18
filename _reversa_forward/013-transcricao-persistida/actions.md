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
| T001 | Criar a spec SDD ativa do componente `transcript-batch` (Front Matter YAML, contrato de descoberta/idempotência/lease D-01/D-03/D-09/D-10, dependências) antes de qualquer código | - | - | `_reversa_sdd/workers/transcript-batch/` | 🟢 | [X] |
| T002 | Criar `Dockerfile.transcript` dedicado (D-06), com etapa de build/instalação do binário `whisper-cpp` | T001 | `[//]` | `Dockerfile.transcript` | 🟢 | `[X]` |
| T003 | Adicionar ao `Dockerfile.transcript` o download/instalação do modelo GGML (`ggml-base.bin` ou variante), path parametrizável | T002 | - | `Dockerfile.transcript` | 🟢 | `[X]` |
| T004 | Coletar specs reais do host de produção (`nproc`, `free -h`, `docker info`) em `10.10.10.11` e registrar (plano de migração, passo 0) | T001 | `[//]` | `_reversa_forward/013-transcricao-persistida/investigation.md` | 🟢 | [X] |
| T005 | Rodar benchmark baseline de `whisper-cpp` (imagem de T003) no host real: tempo/janela, CPU%, RAM peak | T003, T004 | - | `_reversa_forward/013-transcricao-persistida/investigation.md` | 🟡 | `[X]` |
| T006 | Definir, a partir de T005, os valores de `deploy.resources.limits` (D-06) e a duração de janela de chunk (D-04); registrar no roadmap | T005 | - | `_reversa_forward/013-transcricao-persistida/roadmap.md` | 🟡 | `[X]` |
| T007 | Criar o esqueleto do serviço `arq-transcript` no compose (imagem `Dockerfile.transcript`, fila `zenith:transcript`, `deploy.resources.limits` de T006, sem lógica ainda) | T003, T006 | - | `docker-compose.app.yml` | 🟢 | `[X]` |

## Fase 2, Testes

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T008 | Criar testes Red do `WhisperCppSTT`: binário via `$PATH`, ausente, JSON sidecar completo `-ojf`, payload inválido, timeout/cancelamento/exit não zero e confidence por tokens com fallback normalizada em `[0,1]` (D-05) | T001 | `[//]` | `src/services/test_stt_whisper.py` | 🟢 | [X] |
| T009 | Criar testes Red do chunking de WAV 16 kHz sem reamostragem: janelas fixas, arquivo menor, bordas e offset temporal (D-04) | T001 | - | `src/workers/test_transcript_batch.py` | 🟢 | [X] |
| T010 | Acrescentar testes Red da descoberta: exige `tx.wav`+`rx.wav` não vazios e ignora `.tmp`, par incompleto e canal ausente (D-01, D-09, D-12) | T009 | - | `src/workers/test_transcript_batch.py` | 🟢 | [X] |
| T011 | Acrescentar testes Red de ownership e conclusão: item `done` da chamada no transfer log, WAV exato presente, `Transcript` + `.md`, colisão e reparo de marcador sem download remoto (D-03) | T010 | - | `src/workers/test_transcript_batch.py` | 🟢 | [X] |
| T012 | Acrescentar testes Red do estágio `transcription`, heartbeat, exclusão cross-stage, integração com `RECORDING_REQUIRED_CONSUMERS` e `mark_consumed` apenas após banco+SMB (D-10) | T011 | - | `src/workers/test_transcript_batch.py`, `src/audio/test_recording_lifecycle.py`, `src/test_config.py` | 🟢 | [X] |
| T013 | Acrescentar testes Red da persistência transacional: `pg_advisory_xact_lock` por `call_id`, delete+insert idempotente, `extra_metadata` correto (não `metadata`) (D-07) | T012 | - | `src/workers/test_transcript_batch.py` | 🟢 | `[X]` |
| T014 | Acrescentar testes Red do mapeamento de falante nos segmentos persistidos (`tx`→"atendente", `rx`→"cliente") (RN-01) | T013 | - | `src/workers/test_transcript_batch.py` | 🟢 | `[X]` |
| T015 | Acrescentar testes Red do `.md`: ordenação/intercalação por offset, timestamp+confidence, ausência de silêncio e alinhamento tx/rx em zero (RF-03) | T014 | - | `src/workers/test_transcript_batch.py` | 🟢 | [X] |
| T016 | Acrescentar testes Red da nomeação/upload do `.md` com `extension="md"`, mesma base do `.wav` (D-08, RN-03) | T015 | - | `src/workers/test_transcript_batch.py` | 🟢 | [X] |
| T017 | Acrescentar testes Red de timeout/retry e isolamento: Whisper não afeta backup; SMB falha após Postgres e não marca consumo (RN-04, D-12) | T016 | - | `src/workers/test_transcript_batch.py` | 🟢 | [X] |
| T018 | Acrescentar testes Red de concorrência: duas execuções simultâneas do mesmo `call_id` não duplicam nem corrompem (advisory lock cobre) | T013, T017 | - | `src/workers/test_transcript_batch.py` | 🟢 | `[X]` |

## Fase 3, Núcleo

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T019 | Corrigir `WhisperCppSTT`: `$PATH`, JSON sidecar completo, validação/cleanup e confidence por tokens com fallback `exp(avg_logprob)` em `[0,1]` (D-05) | T008 | `[//]` | `src/services/stt_whisper.py` | 🟢 | [X] |
| T020 | Criar o esqueleto do módulo `transcript_batch.py` (`WorkerSettings`, cron job, fila) | T001, T007 | - | `src/workers/transcript_batch.py` | 🟢 | `[X]` |
| T021 | Implementar chunking dos WAV 16 kHz sem reamostragem e offsets com duração definida em T006 (D-04) | T009, T006, T020 | - | `src/workers/transcript_batch.py` | 🟡 | [X] |
| T022 | Implementar descoberta exigindo par WAV final, não vazio, sem `.tmp` (D-01, D-09, D-12) | T010, T020 | - | `src/workers/transcript_batch.py` | 🟢 | [X] |
| T023 | Implementar a checagem dos dois sinais de "já processado" (D-03) | T011, T022 | - | `src/workers/transcript_batch.py` | 🟢 | `[X]` |
| T024 | Implementar estágio/heartbeat `transcription`, consumidor obrigatório e `mark_consumed` pós banco+SMB (D-10) | T012, T022 | - | `src/audio/recording_lifecycle.py`, `src/config.py`, `src/workers/transcript_batch.py` | 🟢 | [X] |
| T025 | Implementar a orquestração por chamada: ler `tx`/`rx`, chunkar (T021), chamar `WhisperCppSTT` (T019) por janela/canal, mapear falante (RN-01) | T019, T021, T014, T022 | - | `src/workers/transcript_batch.py` | 🟢 | `[X]` |
| T026 | Implementar a persistência transacional com advisory lock + delete/insert e `extra_metadata` correto (D-07) | T013, T025 | - | `src/workers/transcript_batch.py` | 🟢 | `[X]` |
| T027 | Implementar a geração do `.md` consolidado (formato de `interfaces/transcript-md.md`) | T015, T026 | - | `src/workers/transcript_batch.py` | 🟢 | `[X]` |
| T028 | Implementar a nomeação/upload do `.md` reaproveitando `smb_sync.py` (D-08) | T016, T027 | - | `src/workers/transcript_batch.py` | 🟢 | `[X]` |
| T029 | Implementar o isolamento best-effort (falha de STT/SMB não bloqueia gravação/backup) + log estruturado por `call_id` (RN-04, RNF Observabilidade) | T017, T028 | - | `src/workers/transcript_batch.py` | 🟢 | `[X]` |
| T030 | Implementar a proteção de concorrência ponta a ponta, ligando lease (T024) e advisory lock (T026) na mesma execução | T018, T023, T024, T026 | - | `src/workers/transcript_batch.py` | 🟢 | `[X]` |

## Fase 4, Integração

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T031 | Completar `arq-transcript`: comando, tmpfs, dependências, timeout, concorrência 1 e cleanup exigindo `smb`+`transcription` | T007, T030 | - | `docker-compose.app.yml` | 🟢 | [X] |
| T032 | Confirmar fila exclusiva `zenith:transcript` sem herdar a fila default (D-02) | T031 | - | `docker-compose.app.yml` | 🟢 | `[X]` |
| T033 | Rodar `alembic upgrade head` e confirmar que nenhuma migração nova é necessária (`data-delta.md`) | T026 | `[//]` | `_reversa_forward/013-transcricao-persistida/data-delta.md` | 🟢 | `[X]` |

## Fase 5, Polimento

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T034 | Instrumentar métricas/logs adicionais (chamadas transcritas, falhas, tamanho da fila `zenith:transcript`, mesmo padrão de `set_smb_queue_size`) | T029 | `[//]` | `src/utils/telemetry.py`, `src/workers/transcript_batch.py` | 🟢 | `[X]` |
| T035 | Atualizar o épico marcando F1 implementada e contexto herdado para F2+ | T036 | - | `_reversa_sdd/ai/epico-2-qualidade-atendimento.md` | 🟢 | [ ] |
| T036 | Após gates e advisor, validar chamada real: `.md` ao lado do `.wav`, `Transcript` no banco | T031, T032, T033, T037, T038 | - | `_reversa_forward/013-transcricao-persistida/onboarding.md` | 🟢 | [ ] |
| T037 | Rodar `pytest -v tests src` e cobertura canônica ≥80% antes de rollout | T031, T032, T033, T034 | - | `progress.jsonl` | 🟢 | [X] |
| T038 | Obter parecer independente sobre bordas/viés antes de rollout; registrar e corrigir bloqueantes | T037 | - | `_reversa_forward/013-transcricao-persistida/test-bias-verdict.md` | 🟢 | [X] |

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
