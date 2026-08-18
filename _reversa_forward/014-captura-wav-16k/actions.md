# Actions: Captura de áudio em WAV 16 kHz na origem

> Identificador: `014-captura-wav-16k`
> Data: `2026-08-13`
> Roadmap: `_reversa_forward/014-captura-wav-16k/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 60 |
| Paralelizáveis (`[//]`) | 28 |
| Maior cadeia de dependência | 17 (T003→T012→T023→T027→T028→T029→T030→T031→T057→T032→T033→T035→T036→T038→T039→T040→T060) |

## Fase 1, Preparação

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T001 | Atualizar o conjunto SDD de ingestão (`requirements`, `design`, `tasks` e front matter) para cobrir escrita incremental em `<channel>.tmp.raw`, finalização idempotente, rename para `.raw` e descarte de chunks tardios (D-03/D-04/D-14/D-15) | - | `[//]` | `_reversa_sdd/audio/audio-ingestion/` | 🟡 | `[X]` |
| T002 | Atualizar o conjunto SDD da integração ESL (`requirements`, `design`, `tasks` e front matter) para o token `stereo 16000` e para os dois gatilhos de finalização, hangup e desconexão WebSocket (D-01/D-04) | - | `[//]` | `_reversa_sdd/telephony/esl-integration/` | 🟡 | `[X]` |
| T003 | Atualizar o conjunto SDD do uploader (`requirements`, `design`, `tasks` e front matter) para entrada PCM16 16 kHz, saída `<channel>.tmp.wav`→`.wav`, preservação do `.raw`, payload por paths e idempotência por job/lease (D-02/D-05) | - | `[//]` | `_reversa_sdd/workers/audio-upload/` | 🟢 | `[X]` |
| T004 | Completar o conjunto SDD do backup SMB (`requirements`, `design`, `tasks` e front matter) para par mono WAV, estéreo WAV, extensão remota parametrizada e confirmação de consumo após publicação íntegra (D-06/D-07/D-08/D-11) | - | `[//]` | `_reversa_sdd/workers/smb-backup/` | 🟢 | `[X]` |
| T005 | Atualizar o conjunto SDD do cleanup (`requirements`, `design`, `tasks` e front matter) para separar finais consumidos/TTL de temporários órfãos em duas rodadas, proteger controles e tratar concorrência (D-12/D-18/D-19/D-23) | - | `[//]` | `_reversa_sdd/workers/audio-cleanup/` | 🟢 | `[X]` |
| T006 | Criar o conjunto SDD do componente `recording-consumers` (`requirements`, `design`, `tasks` e front matter), incluindo marcador atômico `.consumed-<consumer>` e verificação da lista exigida (D-09/D-13) | - | `[//]` | `_reversa_sdd/workers/recording-consumers/` | 🟡 | `[X]` |
| T007 | Atualizar o conjunto SDD raiz de workers (`requirements`, `design`, `tasks` e front matter) com consumidores exigidos, configurações de lease/cleanup/capacidade, tmpfs de 2 GiB e adesão futura sem redesenho (D-10/D-17/D-20/D-21) | - | `[//]` | `_reversa_sdd/workers/` | 🟢 | `[X]` |

### Adendo de preparação pós-auditoria (IDs novos preservam T001–T040)

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T041 | Criar o conjunto SDD do ciclo de vida de gravação (`requirements`, `design`, `tasks` e front matter) com leases nomeados, JSON versionado, owner UUID, expiração e API neutra consumida por audio/workers (D-16/D-17) | - | `[//]` | `_reversa_sdd/audio/recording-lifecycle/` | 🟢 | `[X]` |
| T042 | Atualizar o conjunto SDD do SMB e o contrato de arquivo com temporários WAV explícitos e coleta de `<final>.wav.tmp` remoto em duas observações (D-07/D-19) | T004 | - | `_reversa_sdd/workers/smb-backup/` | 🟢 | `[X]` |
| T043 | Criar o conjunto SDD de admissão de gravações (`requirements`, `design`, `tasks` e front matter) com reserva de 5 min, headroom, histerese 80/70 e degradação apenas da gravação (D-20/D-22) | - | `[//]` | `_reversa_sdd/audio/recording-capacity/` | 🟢 | `[X]` |

## Fase 2, Testes

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T008 | Criar testes Red da ingestão incremental: de-interleaving preservado, append imediato em `tx.tmp.raw`/`rx.tmp.raw` e ausência de buffer proporcional à duração | T001 | `[//]` | `src/audio/test_ingestor.py` | 🟢 | `[X]` |
| T009 | Acrescentar testes Red da finalização: fechamento conjunto, metadata preservada, rename `.tmp.raw`→`.raw`, enfileiramento único e idempotência nas duas ordens de gatilho | T008 | - | `src/audio/test_ingestor.py` | 🟢 | `[X]` |
| T010 | Acrescentar testes Red para desconexão WebSocket e chunk tardio: finaliza no `finally`, não reabre arquivo, não escreve em handle fechado e registra uma vez por chamada | T009 | - | `src/audio/test_ingestor.py` | 🟢 | `[X]` |
| T011 | Atualizar testes Red do ESL para exigir `uuid_audio_stream ... stereo 16000` e delegação do hangup à finalização idempotente | T002 | `[//]` | `src/telephony/test_esl_client.py` | 🟡 | `[X]` |
| T012 | Atualizar testes Red do uploader para `_convert_to_wav`: taxa de entrada e saída 16000, `<channel>.tmp.wav`, publicação atômica e preservação do `.raw` com log por `call_id` | T003 | `[//]` | `src/workers/test_audio_uploader.py` | 🟢 | `[X]` |
| T013 | Acrescentar testes Red do uploader para descobrir os `.raw` finalizados no diretório da chamada e enfileirar somente `tenant_id`/`call_id`, sem bytes no Redis | T012 | - | `src/workers/test_audio_uploader.py` | 🟢 | `[X]` |
| T014 | Atualizar testes Red do SMB para resolver `tx.wav`/`rx.wav`, converter `.raw` finalizado e ignorar sem erro `.tmp.raw` ativo ou diretório apenas com `.mp3` legado | T004 | `[//]` | `src/workers/test_smb_sync.py` | 🟢 | `[X]` |
| T015 | Acrescentar testes Red do SMB para gerar `stereo.wav` PCM16 estéreo 16 kHz, parametrizar a extensão remota e registrar caminhos `.wav` no transfer log | T014 | - | `src/workers/test_smb_sync.py` | 🟢 | `[X]` |
| T016 | Acrescentar testes Red garantindo que `.consumed-smb` só seja marcado após publicação e checksum bem-sucedidos, nunca nos caminhos de falha | T015 | - | `src/workers/test_smb_sync.py` | 🟢 | `[X]` |
| T017 | Criar testes Red de `mark_consumed` e `is_fully_consumed`, cobrindo escrita atômica, consumidor ausente, múltiplos consumidores e lista vazia | T006 | `[//]` | `src/workers/test_recording_consumers.py` | 🟡 | `[X]` |
| T018 | Atualizar testes Red do cleanup: remover WAV confirmado antes do TTL, preservar WAV não confirmado antes do cutoff e remover órfão após o TTL | T005, T006 | `[//]` | `src/workers/test_audio_cleanup.py` | 🟢 | `[X]` |
| T019 | Criar testes Red das configurações de consumidores, lease 30/120 s, cleanup 900 s, chamada 300 s, margens 20/30 e headroom | T007 | `[//]` | `tests/test_recording_consumers_config.py` | 🟢 | `[X]` |

### Adendo de testes Red pós-auditoria

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T044 | Criar testes Red do lifecycle: allowlist `.*-processing`, escrita atômica, lease íntegro/expirado/corrompido, owner UUID, renovação e release idempotente | T041 | `[//]` | `src/audio/test_recording_lifecycle.py` | 🟢 | `[X]` |
| T045 | Criar testes Red de captura com lease: criado antes de `.tmp.raw`, heartbeat, falha de renovação, metadata após WS-before-hangup e zero `await` entre claim/write | T001, T009, T041 | - | `src/audio/test_ingestor.py` | 🟢 | `[X]` |
| T046 | Criar testes Red do capacity guard: reserva restante, 30×5 min, headroom, recusa abaixo de 20%, saída a 30%, preservação de ativas e release idempotente | T043 | `[//]` | `src/audio/test_capacity.py` | 🟢 | `[X]` |
| T047 | Acrescentar testes Red de uploader duplicado/payload antigo, `_job_id`, lease de conversão, `.tmp.wav` órfão substituído com segurança e raw ausente como no-op | T012, T013, T041 | - | `src/workers/test_audio_uploader.py` | 🟢 | `[X]` |
| T048 | Acrescentar testes Red do cleanup em duas rodadas: fingerprint, lease reaparecido, arquivo alterado, candidato corrompido, controles protegidos e dois cleanups concorrentes | T018, T041 | - | `src/workers/test_audio_cleanup.py` | 🟢 | `[X]` |
| T049 | Acrescentar testes Red do SMB para temporário remoto órfão em duas observações, upload ativo protegido e mixagem determinística `stereo.tmp.wav` | T014, T042 | - | `src/workers/test_smb_sync.py` | 🟢 | `[X]` |
| T050 | Criar testes Red de telemetria para ocupação/reserva, transições do modo degradado, recusas, candidatos/exclusões e falhas de lease sem spam por chunk | T043 | `[//]` | `src/utils/test_telemetry.py` | 🟢 | `[X]` |

## Fase 3, Núcleo

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T020 | Substituir `AudioIngestor.buffers` por handles por chamada/canal e gravar cada frame de-intercalado imediatamente em `<channel>.tmp.raw` | T008 | `[//]` | `src/audio/ingestor.py` | 🟢 | `[X]` |
| T021 | Implementar em `AudioIngestor` a finalização idempotente, rename para `.raw`, gatilho no `finally` e guarda/log de chunk tardio (D-04/D-14/D-15) | T009, T010, T020 | - | `src/audio/ingestor.py` | 🟡 | `[X]` |
| T022 | Alterar a captura ESL para `stereo 16000` e fazer o hangup chamar a finalização idempotente sem montar payload de áudio em memória | T011, T021 | - | `src/telephony/esl_client.py` | 🟡 | `[X]` |
| T023 | Renomear `_convert_to_mp3` para `_convert_to_wav`, interpretar entrada 16000, escrever `.tmp.wav` e publicar WAV PCM16 mono 16 kHz preservando `.raw` | T012 | `[//]` | `src/workers/audio_uploader.py` | 🟢 | `[X]` |
| T024 | Alterar upload/enqueue para paths, `_job_id` determinístico e no-op compatível para payload/estado antigo, sem bytes no Redis | T013, T021, T023 | - | `src/workers/audio_uploader.py` | 🟢 | `[X]` |
| T025 | Adicionar todas as settings de consumidores, lease, cleanup e capacidade com overrides via ambiente | T019 | `[//]` | `src/config.py` | 🟢 | `[X]` |
| T026 | Implementar marcadores atômicos e verificação de todos os consumidores exigidos no novo módulo `recording_consumers.py` | T017, T025 | - | `src/workers/recording_consumers.py` | 🟡 | `[X]` |
| T027 | Adaptar `ensure_mono_pair` para WAV e `_convert_to_wav`, mantendo `.tmp.raw` e MP3 legado invisíveis como pares incompletos | T014, T023 | - | `src/workers/smb_sync.py` | 🟢 | `[X]` |
| T028 | Adaptar `generate_stereo`, `build_remote_name` e o transfer log para produzir, nomear e registrar somente os artefatos WAV previstos | T015, T027 | - | `src/workers/smb_sync.py` | 🟢 | `[X]` |
| T029 | Marcar o consumo `smb` apenas depois do retorno bem-sucedido da publicação com checksum, antes de remover o estéreo transitório | T016, T026, T028 | - | `src/workers/smb_sync.py` | 🟢 | `[X]` |
| T030 | Alterar `cleanup_tenant_bucket` para excluir `tx.wav`/`rx.wav` plenamente consumidos antes do TTL e conservar o cutoff como rede de segurança | T018, T026, T029 | - | `src/workers/audio_cleanup.py` | 🟢 | `[X]` |
| T031 | Instrumentar ocupação e confirmações pendentes conforme os testes Red de telemetria, sem log por chunk | T018, T030, T050 | - | `src/utils/telemetry.py`, `src/workers/audio_cleanup.py` | 🟢 | `[X]` |

### Adendo de núcleo pós-auditoria

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T051 | Implementar `recording_lifecycle.py` com leases nomeados/validados, heartbeat-safe, escrita atômica e helpers de descoberta/release | T044, T025 | `[//]` | `src/audio/recording_lifecycle.py` | 🟢 | `[X]` |
| T052 | Implementar `RecordingCapacityGuard` com uso real, crescimento restante, reserva de 19.200.000 B, headroom e histerese 80/70 | T046, T025 | `[//]` | `src/audio/capacity.py` | 🟢 | `[X]` |
| T053 | Integrar lease de captura, capacity guard, metadata no estado reivindicado e tratamento de falha/ENOSPC ao `AudioIngestor` | T020, T021, T045, T051, T052 | - | `src/audio/ingestor.py` | 🟢 | `[X]` |
| T054 | Integrar `.conversion-processing`, idempotência e serialização de job duplicado ao uploader | T024, T047, T051 | - | `src/workers/audio_uploader.py` | 🟢 | `[X]` |
| T055 | Implementar `.cleanup-candidates.json`, duas rodadas, proteção de controles, cron unique e exclusão idempotente por arquivo | T026, T030, T048, T051 | - | `src/workers/audio_cleanup.py` | 🟢 | `[X]` |
| T056 | Implementar coleta SMB de `<final>.wav.tmp` remoto em duas observações sem conflitar com upload ativo | T028, T029, T049, T051 | - | `src/workers/smb_sync.py` | 🟢 | `[X]` |
| T057 | Implementar métricas e logs de capacidade, recusas, lifecycle e cleanup exigidos por T050 | T031, T050, T052, T055 | - | `src/utils/telemetry.py` | 🟢 | `[X]` |
| T058 | Configurar `zenith_recordings_tmpfs` em 2 GiB e propagar settings de capacidade/lease/cleanup somente aos serviços `zenith-*` relevantes | T025, T043 | `[//]` | `docker-compose.app.yml` | 🟢 | `[X]` |

## Fase 4, Integração

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T032 | Executar testes focados de ingestão, lifecycle, capacidade, ESL, uploader, consumidores, SMB, cleanup e telemetria | T022, T053, T054, T055, T056, T057, T058 | - | `_reversa_forward/014-captura-wav-16k/progress.jsonl` | 🟢 | `[X]` |
| T033 | Executar o gate principal `pytest -v tests src` e registrar o resultado completo | T032 | - | `_reversa_forward/014-captura-wav-16k/progress.jsonl` | 🟢 | `[X]` |
| T034 | Executar `alembic upgrade head` para confirmar que o delta exclusivamente em filesystem não exige migração nova | T033 | `[//]` | `_reversa_forward/014-captura-wav-16k/data-delta.md` | 🟢 | `[X]` |
| T035 | Executar cobertura com `pytest -v tests src --cov=src --cov-fail-under=80` e registrar o gate de 80% | T033 | - | `_reversa_forward/014-captura-wav-16k/progress.jsonl` | 🟢 | `[X]` |

## Fase 5, Polimento

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T036 | Chamar `advisor()` com código e testes da feature para avaliar bordas, caminhos infelizes, concorrência e viés de implementação; registrar o veredito | T035 | `[//]` | `_reversa_forward/014-captura-wav-16k/test-bias-verdict.md` | 🟢 | `[X]` |
| T037 | Registrar rollback, inspecionar/drenar gravações e fila antiga e executar rollout coordenado somente dos containers `zenith-*` afetados | T034, T035, T058 | - | `_reversa_forward/014-captura-wav-16k/onboarding.md` | 🟢 | `[X]` |
| T038 | Validar em chamada real de até 5 min vazão 16 kHz, `.tmp.raw`, lease, memória estável, rename, ffprobe e semântica tx/rx | T036, T037 | - | `_reversa_forward/014-captura-wav-16k/onboarding.md` | 🟢 | `[X]` |
| T039 | Validar SMB/cleanup reais: WAV/checksum/log, consumo, final antecipado, temporário órfão em duas rodadas, lease reaparecido e remoto `.tmp` | T038 | - | `_reversa_forward/014-captura-wav-16k/onboarding.md` | 🟢 | `[X]` |
| T040 | Executar gate com 30 chamadas simultâneas de até 5 min em tmpfs 2 GiB, provar ≥20% livre, fila sem crescimento sustentado e modo degradado 20/30 sem afetar SIP | T039 | - | `_reversa_forward/014-captura-wav-16k/onboarding.md` | 🟢 | `[X]` |

### Adendo de integração pós-auditoria

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T059 | Criar/rodar teste de integração local que simula 30 reservas, conversões concorrentes padrão e backlog, verificando a projeção de 20% sem alocar 2 GiB reais | T032, T052, T058 | `[//]` | `tests/test_recording_capacity_integration.py` | 🟢 | `[X]` |
| T060 | Atualizar checklist de rollout com evidências, revisão/imagem de rollback, containers tocados, métricas e resultados reais antes do sync (D-24) | T037, T038, T039, T040 | - | `_reversa_forward/014-captura-wav-16k/onboarding.md` | 🟢 | `[X]` |

## Notas de execução

O deploy precisa coordenar produtores e consumidor da fila `zenith:audio-upload`, porque D-05 altera
a assinatura do job ARQ. Nenhuma ação desta lista autoriza tocar em containers sem prefixo
`zenith-` ou aumentar o tmpfs sem decisão explícita.

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-08-13 | Versão inicial gerada por `/reversa-to-do` | reversa |
| 2026-08-14 | T001–T040 preservadas e revisadas; T041–T060 adicionadas após revisão Claude/Gemini/DeepSeek para leases, duas rodadas, capacidade, races, temporário remoto, telemetria e rollout | reversa |
