# Actions: SMB Audio Backup para Auditoria

> Identificador: `011-smb-audio-backup`
> Data: `2026-07-27`
> Roadmap: `_reversa_forward/011-smb-audio-backup/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 26 |
| Paralelizáveis (`[//]`) | 10 |
| Maior cadeia de dependência | 10 (T003 → T010 → T013 → T016 → T017 → T020 → T022 → T023 → T024 → T025) |

## Fase 1, Preparação

<!-- Setup, scaffolding, configuração. Spec SDD primeiro, conforme CLAUDE.md#SDD. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T001 | Criar spec SDD do componente com Front Matter YAML (`component: smb-backup`, `layer: workers`, `patterns: [strategy]`, `inputs`/`outputs`/`dependencies`), descrevendo o contrato antes do código (CLAUDE.md#SDD exige spec antes de código) | - | `[//]` | `specs/workers/smb-backup/design.md` | 🟢 | `[ ]` |
| [//] T002 | Adicionar `pysmb==1.2.10` a `requirements.txt` na seção Utils (`tenacity==9.0.0` já existe, não adicionar de novo) | - | `[//]` | `requirements.txt` | 🟢 | `[ ]` |
| [//] T003 | Adicionar em `Settings` as chaves `SMB_ENABLED: bool = False`, `SMB_HOST`, `SMB_SHARE`, `SMB_PATH`, `SMB_USERNAME`, `SMB_PASSWORD`, `SMB_BANDWIDTH_LIMIT_MBS: float = 5`, `SMB_TRANSFER_LOG_PATH: str = "/data/smb_logs/smb_transfer_log.json"`, `SMB_SYNC_INTERVAL_MINUTES: int = 5` (default desligado para não quebrar ambiente sem SMB) | - | `[//]` | `src/config.py` | 🟢 | `[ ]` |
| [//] T004 | Documentar as chaves `SMB_*` em `.env.example` com valores de exemplo e `SMB_PASSWORD=` vazio (nunca senha real — CLAUDE.md#Anti-Padrões) | - | `[//]` | `.env.example` | 🟢 | `[ ]` |
| [//] T005 | Ampliar a janela de retry aumentando o default de retenção de áudio de `0.0417` (~1h) para `0.0833` (~2h) no service `arq-cleanup` | - | `[//]` | `docker-compose.app.yml` | 🟡 | `[ ]` |
| [//] T006 | Declarar as 4 métricas Prometheus (`smb_backup_success_total`, `smb_backup_failed_total`, `smb_backup_latency_seconds`, `smb_backup_queue_size`) mais os helpers de registro, seguindo o padrão das métricas de cleanup já existentes no mesmo arquivo | - | `[//]` | `src/utils/telemetry.py` | 🟢 | `[ ]` |

## Fase 2, Testes

<!-- Projeto tem suíte pytest com teste de worker precedente (tests/test_audio_uploader.py). -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T007 | Criar `tests/test_smb_sync.py` cobrindo o builder de nome/caminho: formato exato `{YYYY-MM-DD}-{HH}-{MM}-{SS}-{call_id}-{origem}-{destino}-{tx\|rx}.mp3` e destino `{tenant}/{YYYY-MM-DD}/`, incluindo caso de `origem`/`destino` ausentes | T001, T003 | - | `tests/test_smb_sync.py` | 🟢 | `[ ]` |
| T008 | Acrescentar testes do log de transferência: pular entrada `status=done`, retentar `status=pending`, remover entrada cujo arquivo local não existe mais, e podar entradas `done` com mais de 7 dias | T007 | - | `tests/test_smb_sync.py` | 🟢 | `[ ]` |
| T009 | Acrescentar teste do cálculo de throttle: dado limite de 1 MB/s e chunk de 512 KB, a espera calculada aproxima 0,5 s; com limite alto a espera é zero | T008 | - | `tests/test_smb_sync.py` | 🟢 | `[ ]` |

## Fase 3, Núcleo

<!-- Todas as ações desta fase editam o mesmo módulo, por isso são sequenciais. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T010 | Criar o módulo com esqueleto do worker: `WorkerSettings` com `redis_settings` de `settings.REDIS_URL` e `cron_jobs=[cron(run_smb_sync, minute=...)]` a cada `SMB_SYNC_INTERVAL_MINUTES`, mais `run_smb_sync(ctx)` que retorna `{"status": "disabled"}` quando `SMB_ENABLED` é falso | T002, T003 | - | `src/workers/smb_sync.py` | 🟢 | `[ ]` |
| T011 | Implementar `build_remote_name()` e `build_remote_dir()` como funções puras (sem I/O), derivando data/hora de `started_at` da chamada e recebendo `call_id`, `origem`, `destino`, `channel` | T010 | - | `src/workers/smb_sync.py` | 🟢 | `[ ]` |
| T012 | Implementar o log de transferência: `load_log()`, `mark_pending()`, `mark_done()`, `drop_entry()` e `prune_log(days=7)`, com escrita atômica (tempfile + `os.replace`) em `SMB_TRANSFER_LOG_PATH` | T010 | - | `src/workers/smb_sync.py` | 🟢 | `[ ]` |
| T013 | Implementar `SMBBackupStrategy` (padrão Strategy de `src/services/base.py`) com conexão `pysmb` a partir das settings, criação recursiva do diretório remoto e escrita em `.tmp` seguida de rename no destino | T010 | - | `src/workers/smb_sync.py` | 🟢 | `[ ]` |
| T014 | Implementar throttle GLOBAL de banda dentro do laço de escrita: chunks de 512 KB, acumulador de bytes/tempo compartilhado por todas as cópias do processo, `sleep` do delta quando o ritmo excede `SMB_BANDWIDTH_LIMIT_MBS` | T013 | - | `src/workers/smb_sync.py` | 🟢 | `[ ]` |
| T015 | Implementar validação de integridade: SHA256 do arquivo local e do arquivo remoto após o rename, apagando o remoto e sinalizando falha quando houver divergência | T013 | - | `src/workers/smb_sync.py` | 🟢 | `[ ]` |
| T016 | Envolver a cópia em `tenacity` com `stop_after_attempt(3)` e `wait_exponential(1,2,4)`, mais circuit breaker de módulo que suspende novas tentativas por 5 min após 5 falhas consecutivas | T013 | - | `src/workers/smb_sync.py` | 🟢 | `[ ]` |
| T017 | Implementar `run_smb_sync`: varrer `settings.RECORDINGS_PATH` por `*.mp3`, montar fila ordenada por mtime, despachar cada cópia com `asyncio.to_thread(...)` sob `asyncio.wait_for(timeout=60)`, e tratar arquivo já removido pelo cleanup registrando log e chamando `drop_entry()` | T011, T012, T014, T015, T016 | - | `src/workers/smb_sync.py` | 🟢 | `[ ]` |

## Fase 4, Integração

<!-- Cola com banco, ESL, compose e telemetria. T018/T019 fecham um gap pré-existente: as colunas caller_number/callee_number existem no modelo mas nunca foram populadas. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T018 | Estender `create_call_record` para aceitar e persistir `caller_number` e `callee_number` (colunas já existem em `Call`, hoje sempre `NULL`), mantendo os parâmetros opcionais para não quebrar chamadores atuais | - | `[//]` | `src/services/calls.py` | 🟢 | `[ ]` |
| T019 | Passar `Caller-Caller-ID-Number` e `Caller-Destination-Number` do evento `CHANNEL_ANSWER` para `create_call_record`, checando explicitamente que os campos vieram populados antes de usar (CLAUDE.md#Anti-Padrões: variável de canal lida sem checar) | T018 | - | `src/telephony/esl_client.py` | 🟢 | `[ ]` |
| T020 | Resolver metadados da chamada no worker: consultar `started_at`, `caller_number` e `callee_number` por `call_id` no schema do tenant, com fallback para mtime do arquivo e literal `desconhecido` quando o registro ou a coluna estiver ausente | T017, T018 | - | `src/workers/smb_sync.py` | 🟡 | `[ ]` |
| [//] T021 | Adicionar o service `smb-sync` (container `zenith-smb-sync`, `command: ["arq", "src.workers.smb_sync.WorkerSettings"]`, `env_file: .env`, `depends_on` redis+postgres) e o volume nomeado `zenith_smb_logs` montado em `/data/smb_logs`, reusando `zenith_recordings_tmpfs` em modo leitura | T005, T017 | `[//]` | `docker-compose.app.yml` | 🟢 | `[ ]` |
| T022 | Instrumentar o worker com as métricas de T006 nos pontos de sucesso, falha, latência de cópia e tamanho da fila pendente | T006, T020 | - | `src/workers/smb_sync.py` | 🟢 | `[ ]` |

## Fase 5, Polimento

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T023 | Revisar o logging do módulo: `logger` de módulo com mensagens estruturadas (`call_id`, `tenant_id`, `status`, `bytes`, `latency_ms`, `attempts`), garantindo que `SMB_PASSWORD` e a URL com credencial nunca apareçam em log ou exceção | T022 | - | `src/workers/smb_sync.py` | 🟢 | `[ ]` |
| T024 | Executar a validação manual do `onboarding.md` no servidor real (chamada 1001 → destino, arquivo no SMB em < 30 s, checksum conferido, retry com SMB bloqueado, throttle sob carga) e registrar o resultado real de cada passo | T021, T022, T023 | - | `_reversa_forward/011-smb-audio-backup/onboarding.md` | 🟡 | `[ ]` |
| [//] T025 | Gerar `regression-watch.md` com os pontos de vigilância: worker offline sem alerta, fila crescendo além de 100, throughput acima do limite configurado, cleanup apagando antes da cópia, e credencial vazando em log | T024 | `[//]` | `_reversa_forward/011-smb-audio-backup/regression-watch.md` | 🟢 | `[ ]` |
| [//] T026 | Atualizar `specs/workers/smb-backup/design.md` e `specs/gaps.md` com o resultado real da validação, incluindo o gap fechado de `caller_number`/`callee_number` nunca populados | T024 | `[//]` | `specs/gaps.md` | 🟢 | `[ ]` |

## Notas de execução

<!-- Reservado para /reversa-coding. -->

- **Divergências entre `roadmap.md` e o código real, corrigidas nesta decomposição:** métricas ficam em `src/utils/telemetry.py` (é de lá que `audio_cleanup.py` importa), não em `src/observability/metrics.py`; o compose de aplicação é `docker-compose.app.yml`, não `docker-compose.yml`; a retenção real hoje é ~1 h (`AUDIO_RETENTION_DAYS=0.0417`), não 2 h — daí T005.
- **Gap pré-existente descoberto ao decompor:** `create_call_record` (`src/services/calls.py`) nunca popula `caller_number` nem `callee_number`, embora as colunas existam em `Call`. Sem T018/T019 a nomeação exigida pela RN-03 não tem fonte de dado. Mesmo padrão histórico de `pbx_host`/`tenant_id` nunca populados.

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-07-27 | Versão inicial gerada por `/reversa-to-do` | reversa |
