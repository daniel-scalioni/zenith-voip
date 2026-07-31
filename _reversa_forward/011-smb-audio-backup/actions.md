# Actions: SMB Audio Backup para Auditoria

> Identificador: `011-smb-audio-backup`
> Data: `2026-07-27`
> Roadmap: `_reversa_forward/011-smb-audio-backup/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 115 |
| Paralelizáveis (`[//]`) | 35 |
| Maior cadeia de dependência | 30 |

## Fase 1, Preparação

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T001 | Criar a spec SDD ativa do componente `smb-backup`, com Front Matter YAML, contrato estéreo, publicação atômica, retry de conversão, processo único, interfaces SMB e critérios de aceite antes de qualquer código | - | - | `_reversa_sdd/workers/smb-backup/design.md` | 🟢 | `[X]` |
| [//] T002 | Adicionar `pysmb==1.2.14` à seção de utilitários, preservando `tenacity==9.0.0` | T001 | `[//]` | `requirements.txt` | 🟢 | `[X]` |
| [//] T004 | Documentar em `.env.example` todas as chaves `SMB_*`, incluindo `SMB_SIGN_OPTIONS=2`, senha vazia, Direct TCP/445, NTLMv2 e nomes NetBIOS sem valor sensível | T001 | `[//]` | `.env.example` | 🟢 | `[X]` |
| T005 | Aumentar a retenção do serviço `zenith-arq-cleanup` de `0.0417` para `0.0833` dia, mantendo o prefixo e sem alterar recursos de terceiros | T001 | - | `docker-compose.app.yml` | 🟢 | `[X]` |
| T042 | Executar mini-spike real com `pysmb==1.2.14` para Direct TCP, assinatura, `storeFileFromOffset`, rename, leitura e SHA256, sem registrar segredo | T002, T004 | - | `_reversa_forward/011-smb-audio-backup/storage-write-spike.md` | 🟢 | `[X]` |
| T052 | Atualizar specs SDD e artefatos forward com o isolamento das filas ARQ aprovado após a primeira ligação E2E | T042 | - | `_reversa_sdd/workers/`, `_reversa_forward/011-smb-audio-backup/` | 🟢 | `[X]` |
| [//] T056 | Registrar labels, volume, rede, porta publicada e clientes observados do `zenith-postgres`, formalizando que o recurso atual não pode ser parado, recriado, reconfigurado ou removido | T055 | `[//]` | `_reversa_forward/011-smb-audio-backup/onboarding.md` | 🟢 | `[X]` |
| T057 | Inventariar todos os ambientes conhecidos quanto a `alembic_version`; se algum tiver histórico aplicado, suspender T058/T083/T084 e registrar caminho compatível em vez de squash | T056 | - | `_reversa_forward/011-smb-audio-backup/investigation.md` | 🟡 | `[X]` |
| T058 | Registrar ADR da baseline pública e provisionamento explícito por tenant somente após T057 confirmar que o squash é seguro | T057 | - | `_reversa_sdd/adrs/011-baseline-publica-e-provisionamento-tenant.md` | 🟡 | `[X]` |
| T059 | Capturar manifesto sanitizado de UUIDs/contagens do banco e de quantidade/conjunto ativo dos ramais, sem valores pessoais ou credenciais | T056 | - | `_reversa_forward/011-smb-audio-backup/onboarding.md` | 🟢 | `[X]` |
| T060 | Especificar dump lógico, checksum, restore, descarte seguro, rollback e critérios go/no-go sem usar diretório versionado ou `/tmp` compartilhado | T056 | - | `_reversa_sdd/database/migrations/design.md` | 🟢 | `[X]` |
| T061 | Especificar `zenith-postgres-test` com volume/rede próprios e sem porta publicada no host | T060 | - | `_reversa_sdd/database/migrations/design.md` | 🟢 | `[X]` |
| T062 | Especificar `zenith-postgres-rehearsal` descartável, separado do candidato, com volume/rede próprios e sem porta publicada | T061 | - | `_reversa_sdd/database/migrations/design.md` | 🟢 | `[X]` |
| T063 | Especificar `zenith-postgres-candidate` com volume/rede próprios, sem porta publicada e sem referência `external` ao volume atual | T062 | - | `_reversa_sdd/database/migrations/design.md` | 🟢 | `[X]` |
| T064 | Promover requirements/design/tasks de migrations de `draft` para `active` após ADR e topologia dos três recursos estarem fechados | T058, T061, T062, T063 | - | `_reversa_sdd/database/migrations/requirements.md` | 🟢 | `[X]` |
| T065 | Adicionar configuração Compose somente do banco de teste e quality runner, usando recursos `zenith-*` isolados e sem host port | T061 | - | `docker-compose.quality.yml` | 🟢 | `[X]` |

## Fase 2, Testes

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T007 | Criar testes Red para o diretório e nome remoto, fallback/sanitização, checksum divergente, sufixo `call_id[6:10]` e segunda colisão sem overwrite | T001 | - | `src/workers/test_smb_sync.py` | 🟢 | `[X]` |
| T008 | Acrescentar testes Red do log em `/data/smb_logs/`: estados pending/done/failed, escrita atômica, idempotência, expiração, poda e recuperação de JSON inválido | T007 | - | `src/workers/test_smb_sync.py` | 🟢 | `[X]` |
| T009 | Acrescentar testes Red do throttle por `storeFileFromOffset`: primeiro chunk offset 0/truncate, offsets crescentes, relógio/sleep injetáveis e limites inválidos | T008 | - | `src/workers/test_smb_sync.py` | 🟢 | `[X]` |
| [//] T027 | Criar testes Red para conversão mono com saída temporária, `os.replace` somente após ffmpeg bem-sucedido e preservação de `.raw` em falha | T001 | `[//]` | `src/workers/test_audio_uploader.py` | 🟢 | `[X]` |
| T028 | Acrescentar testes Red para gerar `stereo.mp3` atomicamente, com `tx` à esquerda, `rx` à direita, par incompleto e destino já existente | T009 | - | `src/workers/test_smb_sync.py` | 🟢 | `[X]` |
| T029 | Acrescentar testes Red para retentar `.raw`, manter pending enquanto faltar um canal e registrar falha de conversão sem copiar parcial | T028 | - | `src/workers/test_smb_sync.py` | 🟢 | `[X]` |
| [//] T030 | Criar testes Red dos defaults e validações `SMB_*`: disabled, porta, Direct TCP, nomes NetBIOS, NTLMv2, assinatura default 2, limite, log e intervalo | T001 | `[//]` | `src/test_config.py` | 🟢 | `[X]` |
| [//] T031 | Criar testes Red dos helpers Prometheus para sucesso, falha, latência, fila e conversão pendente, sem label de alta cardinalidade | T001 | `[//]` | `src/utils/test_telemetry.py` | 🟢 | `[X]` |
| [//] T038 | Criar teste de regressão para `create_call_record` persistir `caller_number` e `callee_number` opcionais sem quebrar chamadores existentes | T001 | `[//]` | `src/services/test_calls.py` | 🟢 | `[X]` |
| [//] T039 | Criar teste de regressão para `CHANNEL_ANSWER` encaminhar Caller-ID e destino somente quando presentes no evento | T001 | `[//]` | `src/telephony/test_esl_client.py` | 🟢 | `[X]` |
| T040 | Acrescentar testes Red da resolução de metadados por tenant/call_id, com fallback para mtime e `desconhecido` | T029 | - | `src/workers/test_smb_sync.py` | 🟢 | `[X]` |
| T043 | Acrescentar testes Red para impedir ciclos simultâneos e retornar `already_running` sem processar a fila duas vezes | T040 | - | `src/workers/test_smb_sync.py` | 🟢 | `[X]` |
| T045 | Acrescentar testes Red do lease UTC: validade 120 s, renovação a cada 30 s, remoção e conteúdo expirado/inválido/corrompido com alerta | T043 | - | `src/workers/test_smb_sync.py` | 🟢 | `[X]` |
| [//] T047 | Criar testes Red para o cleanup ignorar lease válido e remover chamada somente após lease expirado e retenção atingida | T001 | `[//]` | `src/workers/test_audio_cleanup.py` | 🟢 | `[X]` |
| T049 | Acrescentar testes Red para remover `stereo.mp3` após checksum e preservá-lo em transferência/checksum falhos | T045 | - | `src/workers/test_smb_sync.py` | 🟢 | `[X]` |
| T051 | Acrescentar testes Red do orçamento global de 30 s cobrindo geração estéreo + cópia, cancelamento observável e permanência em pending | T049 | - | `src/workers/test_smb_sync.py` | 🟢 | `[X]` |
| T053 | Criar testes Red para filas exclusivas dos três `WorkerSettings` e publicação explícita de `upload_recording_batch` em `zenith:audio-upload` | T052 | - | `src/workers/test_audio_uploader.py`, `src/workers/test_audio_cleanup.py`, `src/workers/test_smb_sync.py` | 🟢 | `[X]` |
| T066 | Delegar a LLM externa testes Red de upgrade Alembic em banco vazio, segunda execução e ausência de tabelas de chamada em `public` | T064, T065 | - | `src/database/test_migrations.py` | 🟢 | `[ ]` |
| T067 | Delegar a LLM externa testes Red de provisionamento por tenant e restore com UUIDs explícitos, preservando o fluxo normal sem UUID informado | T064, T065 | - | `src/database/test_provision_tenant.py` | 🟢 | `[ ]` |
| T068 | Delegar a LLM externa testes Red do guard de DSN operacional, nomes únicos por execução e teardown do banco de teste | T065 | - | `tests/test_database_isolation.py` | 🟢 | `[ ]` |
| [//] T069 | Delegar teste Red do ingestor usando `receive()` atual, frames de controle/binário, desconexão e ausência de estado global residual | T056 | `[//]` | `tests/test_audio_ingestor.py` | 🟢 | `[X]` |
| [//] T070 | Delegar testes Red do contrato BunkerWeb com endpoint configurável, erro explícito e separação entre integração e unitário | T056 | `[//]` | `tests/test_bunker_sticky.py` | 🟢 | `[X]` |
| [//] T071 | Delegar testes Red do protocolo ESL real, framing/auth, timeout e indisponibilidade explicitamente marcada | T056 | `[//]` | `tests/test_freeswitch_esl.py` | 🟢 | `[ ]` |
| [//] T072 | Delegar testes Red WebSocket de conexão/desconexão usando `Address`, estado por teste e Redis mockado somente na porta de cliente externo | T056 | `[//]` | `tests/test_telephony_matching.py` | 🟢 | `[ ]` |
| T073 | Acrescentar testes Red WebSocket de broadcast, sessão pendente, erro Redis e envio para conexão encerrada | T072 | - | `tests/test_telephony_matching.py` | 🟢 | `[ ]` |
| T074 | Delegar testes Red de multitenancy com DSN exclusivo, SQL parametrizado, schemas únicos e teardown mesmo em falha | T068 | - | `tests/test_multitenancy.py` | 🟢 | `[ ]` |
| [//] T075 | Delegar testes comportamentais Red de Repository, Strategy e Factory, cobrindo rollback e erro de dependência externa | T056 | `[//]` | `src/services/test_base.py` | 🟢 | `[ ]` |
| [//] T076 | Delegar testes comportamentais Red de Redis Streams, cobrindo publish, consume vazio/parcial, ack e falha de rede | T056 | `[//]` | `src/events/test_redis_streams.py` | 🟢 | `[X]` |
| [//] T077 | Delegar testes comportamentais Red de extraction regex/LLM, cobrindo entrada vazia, inválida, sensível e resposta LLM malformada | T056 | `[//]` | `src/extraction/test_layers.py` | 🟢 | `[ ]` |
| [//] T078 | Delegar testes comportamentais Red de auth/RBAC, cobrindo token inválido/expirado, papéis e acesso negado | T056 | `[//]` | `src/api/test_auth.py` | 🟢 | `[ ]` |
| [//] T079 | Delegar testes comportamentais Red de anomalia e consenso, cobrindo limites, estado vazio e término máximo | T056 | `[//]` | `src/ai/test_behavior.py` | 🟢 | `[ ]` |
| [//] T080 | Delegar testes de regressão para origem local ausente antes da cópia e sanitização de exceções SMB sem segredo | T056 | `[//]` | `src/workers/test_smb_sync.py` | 🟢 | `[ ]` |
| T081 | Revisar independentemente os diffs de banco T066–T068 quanto a bordas, isolamento e viés, devolvendo achados bloqueantes ao autor externo | T066, T067, T068 | - | `_reversa_forward/011-smb-audio-backup/test-bias-verdict.md` | 🟢 | `[ ]` |
| T113 | Revisar independentemente os diffs de fronteiras T069–T074 quanto a bordas, isolamento e viés, devolvendo achados bloqueantes ao autor externo | T069, T070, T071, T072, T073, T074 | - | `_reversa_forward/011-smb-audio-backup/test-bias-verdict.md` | 🟢 | `[ ]` |
| T114 | Revisar independentemente os diffs de domínio T075–T080 quanto a bordas, isolamento e cobertura inflada, devolvendo achados bloqueantes ao autor externo | T075, T076, T077, T078, T079, T080 | - | `_reversa_forward/011-smb-audio-backup/test-bias-verdict.md` | 🟢 | `[ ]` |
| T115 | Consolidar os três vereditos pré-Green, garantindo autoria externa serializada por arquivo e correções bloqueantes aplicadas pelos autores | T081, T113, T114 | - | `_reversa_forward/011-smb-audio-backup/test-bias-verdict.md` | 🟢 | `[ ]` |

## Fase 3, Núcleo

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T003 | Adicionar settings `SMB_ENABLED`, host/share/path/credenciais, porta, Direct TCP, client/server name, domínio, NTLMv2, assinatura, limite, log e intervalo com defaults seguros | T030 | `[//]` | `src/config.py` | 🟢 | `[X]` |
| [//] T006 | Declarar métricas e helpers SMB conforme os testes, seguindo o padrão de cleanup e evitando `call_id` como label | T031 | `[//]` | `src/utils/telemetry.py` | 🟢 | `[X]` |
| [//] T032 | Refatorar `_convert_to_mp3` para saída `*.tmp.mp3`, publicação com `os.replace` e preservação do `.raw` até sucesso | T027 | `[//]` | `src/workers/audio_uploader.py` | 🟢 | `[X]` |
| T010 | Criar esqueleto do worker ARQ, validação de configuração e retorno `disabled` quando `SMB_ENABLED=false` | T002, T003 | - | `src/workers/smb_sync.py` | 🟢 | `[X]` |
| T011 | Implementar builders puros e política de colisão: seis caracteres, sufixo `call_id[6:10]` uma vez e nunca overwrite divergente | T007, T010 | - | `src/workers/smb_sync.py` | 🟢 | `[X]` |
| T012 | Implementar log JSON canônico em `/data/smb_logs/`, estados pending/done/failed, retenção e recuperação que preserva corrupção para diagnóstico | T008, T010 | - | `src/workers/smb_sync.py` | 🟢 | `[X]` |
| T013 | Implementar `SMBBackupStrategy` com `SMBConnection`, validação de nomes/porta, criação recursiva e operação remota sequencial | T002, T010 | - | `src/workers/smb_sync.py` | 🟢 | `[X]` |
| T014 | Implementar limiter com chunks de 512 KiB via `storeFileFromOffset`, truncando só o primeiro e usando offsets crescentes | T009, T013 | - | `src/workers/smb_sync.py` | 🟢 | `[X]` |
| T033 | Implementar geração atômica de `stereo.mp3` via ffmpeg/amerge, fixando left=`tx` e right=`rx` | T028, T032, T010 | - | `src/workers/smb_sync.py` | 🟢 | `[X]` |
| T034 | Implementar retry de conversão de `.raw` reutilizando a função atômica do uploader e mantendo a chamada pending em falha | T029, T032, T010 | - | `src/workers/smb_sync.py` | 🟢 | `[X]` |
| T015 | Implementar escrita remota `.tmp`→rename, SHA256 local/remoto e tratamento idempotente de destino existente | T013, T033 | - | `src/workers/smb_sync.py` | 🟢 | `[X]` |
| T016 | Aplicar retry 1s/2s/4s e circuit breaker de módulo após cinco falhas, distinguindo erro transitório de configuração/autenticação | T013 | - | `src/workers/smb_sync.py` | 🟢 | `[X]` |
| T044 | Implementar exclusão de ciclo com identidade estável e retorno `already_running` | T010, T043 | - | `src/workers/smb_sync.py` | 🟢 | `[X]` |
| T046 | Implementar lease UTC de 120 s, renovação a cada 30 s e alerta/expiração segura para conteúdo inválido ou corrompido | T010, T045 | - | `src/workers/smb_sync.py` | 🟢 | `[X]` |
| T048 | Alterar cleanup para respeitar lease válido e recuperar lease expirado, mantendo a retenção configurada | T046, T047 | - | `src/workers/audio_cleanup.py` | 🟢 | `[X]` |
| T050 | Remover somente o `stereo.mp3` local após checksum remoto confirmado e preservá-lo em falha | T015, T049 | - | `src/workers/smb_sync.py` | 🟢 | `[X]` |
| T017 | Implementar `run_smb_sync`: varrer pares, recuperar raw, gerar/copy/checksum sob timeout global de 30 s, ordenar fila, aplicar lock/lease e atualizar log | T011, T012, T014, T015, T016, T034, T040, T044, T046, T050, T051 | - | `src/workers/smb_sync.py` | 🟢 | `[X]` |
| T054 | Configurar filas `zenith:audio-upload`, `zenith:audio-cleanup` e `zenith:smb-sync`, roteando o produtor para a fila do uploader e removendo o uso da fila default nesses workers | T053 | - | `src/workers/audio_uploader.py`, `src/workers/audio_cleanup.py`, `src/workers/smb_sync.py` | 🟢 | `[X]` |
| T082 | Implementar baseline Alembic pública mínima para tornar T066 verde, sem tabelas de chamada em `public` | T057, T064, T066, T081 | - | `alembic/versions/001_public_baseline.py` | 🟡 | `[ ]` |
| T083 | Restringir `alembic/env.py` e metadata alvo ao schema `public`, mantendo segunda execução como no-op | T066, T082 | - | `alembic/env.py` | 🟢 | `[ ]` |
| T084 | Adaptar provisionamento/restauração para UUIDs explícitos, preservando o caminho normal e tornando T067 verde | T067, T081, T083 | - | `scripts/provision_tenant.py` | 🟢 | `[ ]` |
| T085 | Implementar guard de DSN, criação única e teardown do banco de teste para tornar T068 verde | T068, T081, T065 | - | `tests/conftest.py` | 🟢 | `[ ]` |
| [//] T086 | Corrigir ingestor somente se T069 provar defeito; se o contrato atual estiver correto, fechar N/A com evidência e manter só o teste atualizado | T069, T113 | `[//]` | `src/audio/ingestor.py` | 🟢 | `[ ]` |
| [//] T087 | Ajustar harness BunkerWeb para tornar T070 verde sem alterar proxy de produção; fechar N/A se a falha for somente ambiente | T070, T113 | `[//]` | `tests/test_bunker_sticky.py` | 🟢 | `[ ]` |
| [//] T088 | Corrigir cliente/harness ESL somente se T071 provar defeito; caso contrário fechar N/A com evidência de ambiente | T071, T113 | `[//]` | `src/telephony/esl_client.py` | 🟢 | `[ ]` |
| T089 | Corrigir conexão/desconexão WebSocket somente conforme T072, fechando N/A se o defeito for apenas mock obsoleto | T072, T113 | - | `src/api/websockets.py` | 🟢 | `[ ]` |
| T090 | Corrigir broadcast e caminhos de erro WebSocket somente conforme T073, sem mudar o contrato público | T073, T089 | - | `src/api/websockets.py` | 🟢 | `[ ]` |
| T091 | Tornar multitenancy verde exclusivamente no banco de teste, provando teardown e ausência de schema residual no operacional | T074, T085 | - | `tests/test_multitenancy.py` | 🟢 | `[ ]` |
| [//] T092 | Implementar apenas ajustes de testabilidade necessários em Repository/Strategy/Factory; fechar N/A se T075 já passar | T075, T114 | `[//]` | `src/services/base.py` | 🟢 | `[ ]` |
| [//] T093 | Implementar apenas ajustes de testabilidade necessários em Redis Streams; fechar N/A se T076 já passar | T076, T114 | `[//]` | `src/events/redis_streams.py` | 🟢 | `[ ]` |
| [//] T094 | Implementar apenas ajustes de testabilidade necessários em extraction; fechar N/A se T077 já passar | T077, T114 | `[//]` | `src/extraction/` | 🟢 | `[ ]` |
| [//] T111 | Implementar apenas ajustes de testabilidade necessários em auth/RBAC; fechar N/A se T078 já passar | T078, T114 | `[//]` | `src/api/auth.py` | 🟢 | `[ ]` |
| [//] T112 | Implementar apenas ajustes de testabilidade necessários em anomalia/consenso; fechar N/A se T079 já passar | T079, T114 | `[//]` | `src/ai/` | 🟢 | `[ ]` |

## Fase 4, Integração

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T018 | Estender `create_call_record` para persistir `caller_number` e `callee_number` opcionais via Repository | T038 | `[//]` | `src/services/calls.py` | 🟢 | `[X]` |
| T019 | Encaminhar Caller-ID e Destination-Number validados do `CHANNEL_ANSWER` para `create_call_record` | T018, T039 | - | `src/telephony/esl_client.py` | 🟢 | `[X]` |
| T020 | Resolver `started_at`, `caller_number` e `callee_number` por tenant/call_id no worker, com fallback seguro | T040, T010 | - | `src/workers/smb_sync.py` | 🟢 | `[X]` |
| T021 | Adicionar `zenith-smb-sync`, volume `zenith_smb_logs` e montagem de `zenith_recordings_tmpfs`, sem reutilizar recursos externos | T003, T005, T017, T048 | - | `docker-compose.app.yml` | 🟢 | `[X]` |
| T022 | Instrumentar sucesso, falha, latência, fila e conversão pendente nos pontos definidos pelo contrato | T006, T017 | - | `src/workers/smb_sync.py` | 🟢 | `[X]` |
| T041 | Verificar sem exibir valores que o `.env` privado contém endpoint e conta técnica WRITE, registrar as operações confirmadas no spike e manter credenciais de auditoria fora do Zenith | T003, T004, T042 | - | `_reversa_forward/011-smb-audio-backup/storage-write-spike.md` | 🟢 | `[X]` |
| T035 | Executar e registrar a configuração manual de ACL: conta worker com WRITE e conta auditor com READ-ONLY, incluindo delete/rename negados | T021 | - | `_reversa_forward/011-smb-audio-backup/onboarding.md` | 🟡 | `[ ]` |
| T055 | Redeployar os três workers afetados e executar rolling restart das duas APIs que hospedam o produtor, comprovar filas distintas no Redis e executar nova ligação sem recuperar o job falho da primeira ligação | T054 | - | `_reversa_forward/011-smb-audio-backup/onboarding.md` | 🟢 | `[X]` |
| [//] T095 | Adicionar recursos Compose do rehearsal sem porta publicada, sem reutilizar volumes/redes e sem tocar `zenith-postgres` | T062 | `[//]` | `docker-compose.quality.yml` | 🟢 | `[ ]` |
| [//] T096 | Adicionar recursos Compose do candidato sem porta publicada, sem reutilizar volumes/redes e sem tocar `zenith-postgres` | T063 | `[//]` | `docker-compose.candidate.yml` | 🟢 | `[ ]` |
| T097 | Gerar dump lógico em diretório privado gitignored, registrar checksum e inventário, sem parar ou alterar `zenith-postgres` | T059, T060 | - | `_reversa_forward/011-smb-audio-backup/onboarding.md` | 🟢 | `[ ]` |
| T098 | Restaurar o dump no rehearsal e comparar schemas, UUIDs, contagens, tipos e constraints | T095, T097 | - | `_reversa_forward/011-smb-audio-backup/onboarding.md` | 🟢 | `[ ]` |
| T099 | Rodar baseline duas vezes no candidato vazio, provisionar tenant e restaurar dados com UUIDs preservados | T084, T096, T097 | - | `_reversa_forward/011-smb-audio-backup/onboarding.md` | 🟢 | `[ ]` |
| [//] T100 | Regenerar ramais em diretório privado temporário, comparar 939 entradas e conjunto ativo, e remover os temporários após o manifesto | T059 | `[//]` | `scripts/import_extensions.py` | 🟢 | `[ ]` |
| T101 | Executar toda a suíte no banco de teste com coleta explícita `tests/` e testes `src/**/test_*.py`, `--cov=src --cov-fail-under=80`, sem falhas ou schemas residuais | T082, T083, T084, T085, T086, T087, T088, T090, T091, T092, T093, T094, T111, T112, T115 | - | `tests/`, `src/` | 🟢 | `[ ]` |
| T102 | Obter veredito independente de que a cobertura de T101 é comportamental, não inflada, e devolver correções bloqueantes aos autores externos | T101 | - | `_reversa_forward/011-smb-audio-backup/test-bias-verdict.md` | 🟢 | `[ ]` |
| T103 | Ensaiar rollback antes do corte, alternando somente rehearsal/candidato e comprovando retorno de UUIDs, contagens e health sem tocar o banco atual | T098, T099 | - | `_reversa_forward/011-smb-audio-backup/onboarding.md` | 🟢 | `[ ]` |
| T104 | Repetir inspeção de ownership e apresentar checkpoint humano go/no-go; manter `[ ]` até aprovação explícita, sem mutação nesta tarefa | T100, T101, T102, T103 | - | `_reversa_forward/011-smb-audio-backup/onboarding.md` | 🟢 | `[ ]` |
| T105 | Após T104 aprovado, apontar por rolling restart `zenith-api-1`, `zenith-api-2`, `zenith-arq-uploader`, `zenith-arq-cleanup` e `zenith-smb-sync` ao candidato, validando health entre cada recriação e preservando o PostgreSQL atual | T104 | - | `docker-compose.app.yml` | 🟡 | `[ ]` |
| T106 | Reimportar os ramais validados, confirmar contagem e conjunto ativo e recarregar apenas o profile upstream, com fallback para os arquivos privados anteriores | T100, T105 | - | `_reversa_forward/011-smb-audio-backup/onboarding.md` | 🟢 | `[ ]` |
| T107 | Executar smoke pós-cutover de tenant/PBX e uma ligação curta, provando nova linha `Call` com caller/callee; não duplicar o E2E SMB de T024 | T105, T106 | - | `_reversa_forward/011-smb-audio-backup/onboarding.md` | 🟢 | `[ ]` |

## Fase 5, Polimento

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T023 | Revisar logging estruturado e sanitização inclusive das exceções `pysmb`, impedindo exposição de username, password ou conexão | T016, T017, T022 | - | `src/workers/smb_sync.py` | 🟢 | `[X]` |
| T036 | Obter veredito independente sobre casos de borda e viés dos testes, registrando lacunas e correções aplicadas | T019, T020, T023 | - | `_reversa_forward/011-smb-audio-backup/test-bias-verdict.md` | 🟢 | `[X]` |
| T037 | Executar Compose, `alembic upgrade head` duas vezes e suíte global coletando `tests/` + `src/**/test_*.py` com `--cov=src --cov-fail-under=80`, registrando resultados reais | T021, T036, T101, T102, T107 | - | `tests/`, `src/` | 🟢 | `[ ]` |
| T024 | Executar E2E real: SLA/timeout 30 s, checksum, canais, offline, circuit breaker, throttle, lease 120/30 s, colisão, cleanup e segredos | T035, T037, T041, T048, T050, T051, T107 | - | `_reversa_forward/011-smb-audio-backup/onboarding.md` | 🟡 | `[ ]` |
| [//] T025 | Gerar regression watch para worker offline, fila, canal invertido/misturado, parcial, cleanup precoce, throughput e segredo | T024 | `[//]` | `_reversa_forward/011-smb-audio-backup/regression-watch.md` | 🟢 | `[ ]` |
| T026 | Atualizar spec SDD e gaps com resultados reais, incluindo caller/callee, estéreo, ACL e compatibilidade do servidor | T024 | - | `_reversa_sdd/workers/smb-backup/design.md` | 🟢 | `[ ]` |
| T108 | Registrar hashes, contagens, versões, resultados de rollback/cutover e ausência de segredos nos artefatos da feature | T024, T026, T103, T107 | - | `_reversa_forward/011-smb-audio-backup/onboarding.md` | 🟢 | `[ ]` |
| T109 | Obter veredito multi-LLM final sobre migrations, risco de dados, isolamento dos testes e rollback a partir dos diffs/evidências reais | T108 | - | `_reversa_forward/011-smb-audio-backup/audit/cross-check.md` | 🟢 | `[ ]` |
| T110 | Preparar `/reversa-sync` somente após T025, T026 e T109, mantendo o PostgreSQL anterior disponível até aceite pós-entrega | T025, T026, T109 | - | `_reversa_forward/011-smb-audio-backup/regression-watch.md` | 🟢 | `[ ]` |

## Notas de execução

- IDs T001–T050 foram preservados; T051 cobre em TDD o timeout global esclarecido.
- T052–T055 incorporam o achado da primeira ligação E2E: colisão entre workers na fila ARQ
  default, corrigida por filas exclusivas conforme decisões 1A/2B/3A.
- O escopo aprovado para a primeira rodada de coding continua sendo somente **Preparação**, agora sequenciado: T001 primeiro; T002/T004/T005 depois; T042 após a dependência e configuração documentada.
- T024/T035 dependem de acesso ao servidor SMB e evidência humana; não marcar sem execução real.
- O MP3 remoto é único e estéreo. `tx.mp3`/`rx.mp3` locais permanecem como intermediários atômicos.
- T056–T110 recuperam os gates globais sem tocar o `zenith-postgres` atual; porta 5433 publicada
  impede provar exclusividade externa absoluta, portanto teste, rehearsal e candidato são recursos novos.
- T066–T080 têm autoria externa serializada por arquivo; T081/T113/T114/T115 e T102 são revisões
  independentes distintas, respectivamente antes do Green e após a medição de cobertura.
- T104 é checkpoint humano bloqueante. T105 não pode iniciar por inferência ou timeout.

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-07-30 | T056–T110 adicionadas após decomposição e cross-check Claude/DeepSeek/Mimo para migrations, suíte global, bancos isolados e cutover reversível | reversa |
| 2026-07-29 | T052–T055 adicionadas após E2E confirmar `function not found` por fila ARQ compartilhada | reversa |
| 2026-07-28 | T041 adicionada para configuração privada e evidência do spike SMB | reversa |
| 2026-07-28 | Revisão multi-LLM/cross-check incorporada com ordem spec-first e T042–T050 | reversa |
| 2026-07-28 | Clarify pós-auditoria propagado em T008/T012/T017/T045/T046 e novo teste T051; paralelismo de T020/T041 removido | reversa |
| 2026-07-27 | Regenerado após clarify/plan, preservando IDs e adicionando T027–T040 | reversa |
