<!--
Template de corpo do actions.md
Carregado por /reversa-to-do e atualizado por /reversa-coding.

REGRAS DE PREENCHIMENTO:
- IDs estáveis: T001, T002, ..., zero-padded três dígitos. Nunca recicle.
- Marcador de paralelismo é [//] no início da linha de ID. Tarefas [//] não compartilham arquivo alvo.
- Coluna "Dependências" lista IDs separados por vírgula. Ações sem dependência usam "-".
- Status inicial é [ ]. /reversa-coding muda para [X] ao concluir.
- Toda ação precisa ser ATÔMICA: cabe num turno do agente, sem precisar de feedback humano no meio.
-->

# Actions: Alta Escala, Isolamento Multitenant e PBX Múltiplos

> Identificador: `002-escala-eventos`
> Data: `2026-05-21`
> Roadmap: `_reversa_forward/002-escala-eventos/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 15 |
| Paralelizáveis (`[//]`) | 7 |
| Maior cadeia de dependência | 8 |

## Fase 1, Preparação

<!-- Setup, scaffolding, migrações iniciais, configuração de infraestrutura local. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T001 | Configurar o setup do Alembic para varrer múltiplos schemas PostgreSQL de forma automática e dinâmica. | - | `[//]` | `alembic/env.py` | 🟢 | `[X]` |
| [//] T002 | Criar as tabelas administrativas compartilhadas no schema `public` (`public.tenants` e `public.pbxs`). | - | `[//]` | `src/database/models.py` | 🟢 | `[X]` |
| T003 | Implementar a engine de roteamento de banco de dados assíncrono (Database Router) no SQLAlchemy definindo `search_path` dinamicamente conforme o `tenant_id`. | T002 | - | `src/database/database.py` | 🟢 | `[X]` |
| T004 | Atualizar os modelos de negócio legados (`calls`, etc.) para serem isolados por schema dedicados e adicionar chaves estrangeiras lógicas com `public.pbxs`. | T002 | - | `src/database/models.py` | 🟢 | `[X]` |

## Fase 2, Testes

<!-- Testes que precisam existir antes ou logo após o núcleo. Omitir se a equipe não pratica TDD. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T005 | Criar testes de integração automatizados simulando a criação e migração de novos schemas PostgreSQL por inquilino. | T003 | `[//]` | `tests/test_multitenancy.py` | 🟢 | `[X]` |
| [//] T006 | Criar testes unitários para a lógica de WebSocket handshake matching por IP e fluxo de pareamento manual SIP. | T004 | `[//]` | `tests/test_telephony_matching.py` | 🟢 | `[X]` |

## Fase 3, Núcleo

<!-- Lógica central da feature. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T007 | Configurar no SwitchPBX (FreeSWITCH) o profile de Registration Forwarding (Proxy de Registro Transparente) para desviar sinalização e mídias. | T003 | - | `freeswitch/conf/dialplan/default.xml` | 🟢 | `[X]` |
| T008 | Implementar listener de eventos ESL capturando SIP `REGISTER` e salvando o mapeamento `ramal -> IP` e `ramal -> PBX` no Redis com TTL de 3600s. | T007 | - | `src/telephony/esl_client.py` | 🟢 | `[X]` |
| T009 | Implementar o handshake dinâmico no WebSocket da API FastAPI do Widget cruzando o IP da conexão com o mapeamento Redis e enviando `session_linked`. | T008 | - | `src/api/websockets.py` | 🟢 | `[X]` |
| T010 | Implementar o fluxo de fallback manual de pareamento de ramal recebendo chamada para `*88` no dialplan e casando com a sessão WS ativa no Redis. | T009 | - | `src/telephony/esl_client.py` | 🟢 | `[X]` |
| T011 | Implementar o áudio fork dinâmico (`mod_audio_fork`) no SwitchPBX para ingestão em tempo real de chamadas ativas no Redis Streams com metadados de tenant e PBX. | T008 | - | `src/telephony/esl_client.py` | 🟢 | `[X]` |

## Fase 4, Integração

<!-- Cola com outras partes do sistema, contratos externos, ganchos. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T012 | Criar endpoints HTTP REST (`GET` e `POST /api/v1/admin/pbxs`) sob autenticação JWT de tenant admin para gerenciar múltiplos PBXs. | T003 | `[//]` | `src/api/routers/pbxs.py` | 🟢 | `[X]` |
| T013 | Implementar worker assíncrono para upload em lote das gravações locais de áudio para Object Storage S3 compatível de forma isolada por inquilino. | T011 | - | `src/workers/audio_uploader.py` | 🟢 | `[X]` |

## Fase 5, Polimento

<!-- Logs, telemetria, mensagens de erro, documentação curta. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T014 | Configurar monitoramento e métricas Prometheus de pooling de conexão multi-schema e tráfego de eventos do Redis Streams por segundo. | T012 | `[//]` | `src/utils/telemetry.py` | 🟢 | `[X]` |
| [//] T015 | Finalizar guia de simulação e onboarding ensinando os comandos de inicialização, mock SIP e queries para validação rápida local. | T013 | `[//]` | `_reversa_forward/002-escala-eventos/onboarding.md` | 🟢 | `[X]` |

## Notas de execução

<!--
Reservado para /reversa-coding registrar avisos ou observações que surgiram durante a execução.
Não use isso para corrigir ações, edits manuais ficam fora desse arquivo, vão direto no código.
-->

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-05-21 | Versão inicial gerada por `/reversa-to-do` | reversa |
| 2026-05-21 | Execução completa via `/reversa-coding`. 15/15 tarefas concluídas. | reversa |
