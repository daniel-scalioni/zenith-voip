# Actions: Captura de áudio em WAV 16 kHz na origem

> Identificador: `014-captura-wav-16k`
> Data: `2026-08-13`
> Roadmap: `_reversa_forward/014-captura-wav-16k/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 40 |
| Paralelizáveis (`[//]`) | 19 |
| Maior cadeia de dependência | 14 (T004→T014→T027→T028→T029→T030→T031→T032→T033→T034→T037→T038→T039→T040) |

## Fase 1, Preparação

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T001 | Atualizar a spec SDD de ingestão para cobrir escrita incremental em `<channel>.tmp.raw`, finalização idempotente, rename para `.raw` e descarte de chunks tardios (D-03/D-04/D-14/D-15) | - | `[//]` | `_reversa_sdd/audio/audio-ingestion/design.md` | 🟡 | `[ ]` |
| T002 | Atualizar a spec SDD da integração ESL para o token `stereo 16000` e para os dois gatilhos de finalização, hangup e desconexão WebSocket (D-01/D-04) | - | `[//]` | `_reversa_sdd/telephony/esl-integration/design.md` | 🟡 | `[ ]` |
| T003 | Atualizar a spec SDD do uploader para conversão PCM16 mono 16 kHz, preservação do `.raw` e payload ARQ baseado em caminhos no disco (D-02/D-05) | - | `[//]` | `_reversa_sdd/workers/audio-upload/design.md` | 🟢 | `[ ]` |
| T004 | Atualizar a spec SDD do backup SMB para par mono WAV, estéreo WAV, extensão remota parametrizada e confirmação de consumo após publicação íntegra (D-06/D-07/D-08/D-11) | - | `[//]` | `_reversa_sdd/workers/smb-backup/design.md` | 🟢 | `[ ]` |
| T005 | Atualizar a spec SDD do cleanup para exclusão antecipada por confirmação completa e fallback por TTL (D-12) | - | `[//]` | `_reversa_sdd/workers/audio-cleanup/design.md` | 🟢 | `[ ]` |
| T006 | Criar a spec SDD do componente `recording-consumers`, incluindo marcador atômico `.consumed-<consumer>` e verificação da lista exigida (D-09/D-13) | - | `[//]` | `_reversa_sdd/workers/recording-consumers/design.md` | 🟡 | `[ ]` |
| T007 | Registrar na spec SDD de workers a configuração `RECORDING_REQUIRED_CONSUMERS`, default `['smb']`, e a adesão futura de consumidores sem redesenho (D-10) | - | `[//]` | `_reversa_sdd/workers/requirements.md` | 🟢 | `[ ]` |

## Fase 2, Testes

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T008 | Criar testes Red da ingestão incremental: de-interleaving preservado, append imediato em `tx.tmp.raw`/`rx.tmp.raw` e ausência de buffer proporcional à duração | T001 | `[//]` | `src/audio/test_ingestor.py` | 🟢 | `[ ]` |
| T009 | Acrescentar testes Red da finalização: fechamento conjunto dos canais, rename `.tmp.raw`→`.raw`, enfileiramento único e idempotência nas duas ordens de gatilho | T008 | - | `src/audio/test_ingestor.py` | 🟡 | `[ ]` |
| T010 | Acrescentar testes Red para desconexão WebSocket e chunk tardio: finaliza no `finally`, não reabre arquivo, não escreve em handle fechado e registra uma vez por chamada | T009 | - | `src/audio/test_ingestor.py` | 🟢 | `[ ]` |
| T011 | Atualizar testes Red do ESL para exigir `uuid_audio_stream ... stereo 16000` e delegação do hangup à finalização idempotente | T002 | `[//]` | `src/telephony/test_esl_client.py` | 🟡 | `[ ]` |
| T012 | Atualizar testes Red do uploader para `_convert_to_wav`: PCM16 mono 16 kHz, publicação atômica e preservação do `.raw` com log por `call_id` na falha | T003 | `[//]` | `src/workers/test_audio_uploader.py` | 🟢 | `[ ]` |
| T013 | Acrescentar testes Red do uploader para descobrir os `.raw` finalizados no diretório da chamada e enfileirar somente `tenant_id`/`call_id`, sem bytes no Redis | T012 | - | `src/workers/test_audio_uploader.py` | 🟢 | `[ ]` |
| T014 | Atualizar testes Red do SMB para resolver `tx.wav`/`rx.wav`, converter `.raw` finalizado e ignorar sem erro `.tmp.raw` ativo ou diretório apenas com `.mp3` legado | T004 | `[//]` | `src/workers/test_smb_sync.py` | 🟢 | `[ ]` |
| T015 | Acrescentar testes Red do SMB para gerar `stereo.wav` PCM16 estéreo 16 kHz, parametrizar a extensão remota e registrar caminhos `.wav` no transfer log | T014 | - | `src/workers/test_smb_sync.py` | 🟢 | `[ ]` |
| T016 | Acrescentar testes Red garantindo que `.consumed-smb` só seja marcado após publicação e checksum bem-sucedidos, nunca nos caminhos de falha | T015 | - | `src/workers/test_smb_sync.py` | 🟢 | `[ ]` |
| T017 | Criar testes Red de `mark_consumed` e `is_fully_consumed`, cobrindo escrita atômica, consumidor ausente, múltiplos consumidores e lista vazia | T006 | `[//]` | `src/workers/test_recording_consumers.py` | 🟡 | `[ ]` |
| T018 | Atualizar testes Red do cleanup: remover WAV confirmado antes do TTL, preservar WAV não confirmado antes do cutoff e remover órfão após o TTL | T005, T006 | `[//]` | `src/workers/test_audio_cleanup.py` | 🟢 | `[ ]` |
| T019 | Criar testes Red da configuração para o default `['smb']` e override por variável de ambiente de `RECORDING_REQUIRED_CONSUMERS` | T007 | `[//]` | `tests/test_recording_consumers_config.py` | 🟢 | `[ ]` |

## Fase 3, Núcleo

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T020 | Substituir `AudioIngestor.buffers` por handles por chamada/canal e gravar cada frame de-intercalado imediatamente em `<channel>.tmp.raw` | T008 | `[//]` | `src/audio/ingestor.py` | 🟢 | `[ ]` |
| T021 | Implementar em `AudioIngestor` a finalização idempotente, rename para `.raw`, gatilho no `finally` e guarda/log de chunk tardio (D-04/D-14/D-15) | T009, T010, T020 | - | `src/audio/ingestor.py` | 🟡 | `[ ]` |
| T022 | Alterar a captura ESL para `stereo 16000` e fazer o hangup chamar a finalização idempotente sem montar payload de áudio em memória | T011, T021 | - | `src/telephony/esl_client.py` | 🟡 | `[ ]` |
| T023 | Renomear `_convert_to_mp3` para `_convert_to_wav` e materializar WAV PCM16 mono 16 kHz atomicamente, preservando `.raw` e logando a falha original | T012 | `[//]` | `src/workers/audio_uploader.py` | 🟢 | `[ ]` |
| T024 | Alterar `upload_recording_batch` e `enqueue_recording_upload` para operar pelo diretório da chamada e retirar bytes de áudio do payload ARQ | T013, T021, T023 | - | `src/workers/audio_uploader.py` | 🟢 | `[ ]` |
| T025 | Adicionar `RECORDING_REQUIRED_CONSUMERS: list[str] = ['smb']` às settings, mantendo override via ambiente | T019 | `[//]` | `src/config.py` | 🟢 | `[ ]` |
| T026 | Implementar marcadores atômicos e verificação de todos os consumidores exigidos no novo módulo `recording_consumers.py` | T017, T025 | - | `src/workers/recording_consumers.py` | 🟡 | `[ ]` |
| T027 | Adaptar `ensure_mono_pair` para WAV e `_convert_to_wav`, mantendo `.tmp.raw` e MP3 legado invisíveis como pares incompletos | T014, T023 | - | `src/workers/smb_sync.py` | 🟢 | `[ ]` |
| T028 | Adaptar `generate_stereo`, `build_remote_name` e o transfer log para produzir, nomear e registrar somente os artefatos WAV previstos | T015, T027 | - | `src/workers/smb_sync.py` | 🟢 | `[ ]` |
| T029 | Marcar o consumo `smb` apenas depois do retorno bem-sucedido da publicação com checksum, antes de remover o estéreo transitório | T016, T026, T028 | - | `src/workers/smb_sync.py` | 🟢 | `[ ]` |
| T030 | Alterar `cleanup_tenant_bucket` para excluir `tx.wav`/`rx.wav` plenamente consumidos antes do TTL e conservar o cutoff como rede de segurança | T018, T026, T029 | - | `src/workers/audio_cleanup.py` | 🟢 | `[ ]` |
| T031 | Instrumentar ocupação do diretório de gravações e confirmações pendentes usando log estruturado/métrica, sem alterar a política de retenção | T018, T030 | - | `src/utils/telemetry.py`, `src/workers/audio_cleanup.py` | 🟢 | `[ ]` |

## Fase 4, Integração

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T032 | Executar os testes focados de ingestão, ESL, uploader, consumidores, SMB e cleanup; corrigir apenas regressões dentro do escopo desta feature | T022, T024, T025, T030, T031 | - | `_reversa_forward/014-captura-wav-16k/progress.jsonl` | 🟢 | `[ ]` |
| T033 | Executar o gate principal `pytest -v tests src` e registrar o resultado completo | T032 | - | `_reversa_forward/014-captura-wav-16k/progress.jsonl` | 🟢 | `[ ]` |
| T034 | Executar `alembic upgrade head` para confirmar que o delta exclusivamente em filesystem não exige migração nova | T033 | `[//]` | `_reversa_forward/014-captura-wav-16k/data-delta.md` | 🟢 | `[ ]` |
| T035 | Executar cobertura com `pytest -v tests src --cov=src --cov-fail-under=80` e registrar o gate de 80% | T033 | - | `_reversa_forward/014-captura-wav-16k/progress.jsonl` | 🟢 | `[ ]` |

## Fase 5, Polimento

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T036 | Chamar `advisor()` com código e testes da feature para avaliar bordas, caminhos infelizes, concorrência e viés de implementação; registrar o veredito | T035 | `[//]` | `_reversa_forward/014-captura-wav-16k/test-bias-verdict.md` | 🟢 | `[ ]` |
| T037 | Antes do deploy, confirmar novamente que `/data/recordings` não contém pares legados e preparar drenagem da fila `zenith:audio-upload` com restart coordenado apenas dos containers `zenith-*` envolvidos | T034, T035 | - | `_reversa_forward/014-captura-wav-16k/onboarding.md` | 🟢 | `[ ]` |
| T038 | Validar numa chamada real a vazão efetiva de 16 kHz, crescimento incremental de `.tmp.raw`, memória estável, rename final, `ffprobe` PCM16 mono e semântica correta de `tx`/`rx` | T036, T037 | - | `_reversa_forward/014-captura-wav-16k/onboarding.md` | 🟢 | `[ ]` |
| T039 | Validar o ciclo real SMB e cleanup: `stereo.wav` reproduzível com checksum, caminhos do log válidos, confirmação `smb` e remoção dos monos antes do TTL | T038 | - | `_reversa_forward/014-captura-wav-16k/onboarding.md` | 🟢 | `[ ]` |
| T040 | Medir numa chamada de duração representativa o pico do `zenith_recordings_tmpfs`, a fila SMB e ausência de jitter; registrar decisão explícita caso a capacidade de 512 MB seja insuficiente | T039 | - | `_reversa_forward/014-captura-wav-16k/onboarding.md` | 🟡 | `[ ]` |

## Notas de execução

O deploy precisa coordenar produtores e consumidor da fila `zenith:audio-upload`, porque D-05 altera
a assinatura do job ARQ. Nenhuma ação desta lista autoriza tocar em containers sem prefixo
`zenith-` ou aumentar o tmpfs sem decisão explícita.

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-08-13 | Versão inicial gerada por `/reversa-to-do` | reversa |
