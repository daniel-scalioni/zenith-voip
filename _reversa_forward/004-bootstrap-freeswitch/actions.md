# Actions: Bootstrap FreeSWITCH (container saudável)

> Identificador: `004-bootstrap-freeswitch`
> Data: `2026-06-23`
> Roadmap: `_reversa_forward/004-bootstrap-freeswitch/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 14 |
| Paralelizáveis (`[//]`) | 7 |
| Maior cadeia de dependência | T001 → T005 → T008 → T009 → T010 |

## Fase 1, Preparação

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T001 | Criar `vars.xml` com `domain` (valor lógico fixo), `local_ip=auto`, `external_rtp_ip`/`external_sip_ip` apontando para `$${local_ip}`, `global_codec_prefs` | - | `[//]` | `freeswitch/conf/vars.xml` | 🟡 | `[X]` |
| [//] T002 | Criar `acl.conf.xml` com a lista `rfc1918` já referenciada em `internal.xml` via `apply-nat-acl` | - | `[//]` | `freeswitch/conf/autoload_configs/acl.conf.xml` | 🟢 | `[X]` |
| [//] T003 | Criar `event_socket.conf.xml` (porta 8021, password = `FREESWITCH_ESL_PASSWORD`) | - | `[//]` | `freeswitch/conf/autoload_configs/event_socket.conf.xml` | 🟡 | `[X]` |
| [//] T004 | Criar `directory/default.xml` como esqueleto/placeholder (sem usuários reais) | - | `[//]` | `freeswitch/conf/directory/default.xml` | 🟢 | `[X]` |
| [//] T012 | Criar `autoload_configs/sofia.conf.xml` (descoberto durante a execução, ausente do levantamento original — ver roadmap D-05) com `<profiles><X-PRE-PROCESS cmd="include" data="../sip_profiles/*.xml"/></profiles>`, para que `mod_sofia` efetivamente carregue `sip_profiles/internal.xml` | - | `[//]` | `freeswitch/conf/autoload_configs/sofia.conf.xml` | 🟢 | `[X]` |

## Fase 2, Testes

n/a — escopo é configuração XML de infraestrutura (boot do FreeSWITCH), sem suíte automatizada aplicável; a validação real é manual via SSH no servidor (Fase 4, T008/T009), conforme `onboarding.md`. A suíte `pytest tests/` do projeto (TDD para código Python) não é afetada por esta feature e continua valendo como gate para mudanças de código de aplicação.

## Fase 3, Núcleo

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T005 | Criar `freeswitch.xml` raiz com includes de `vars.xml`, `sip_profiles/*.xml`, `dialplan/*.xml`, `autoload_configs/*.xml`, `directory/*.xml` | T001, T002, T003, T004 | - | `freeswitch/conf/freeswitch.xml` | 🟡 | `[X]` |
| T006 | Ajustar `sip_profiles/internal.xml`: trocar `$${domain}` (hoje indefinido) pelo domínio real definido em `vars.xml` | T001 | - | `freeswitch/conf/sip_profiles/internal.xml` | 🟢 | `[X]` |

## Fase 4, Integração

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T007 | Corrigir `modules.conf.xml`: `mod_esl` não é um módulo real do FreeSWITCH (ESL é biblioteca cliente, não módulo carregável) — trocar por `mod_event_socket`, o módulo correto que abre o listener ESL | T003 | - | `freeswitch/conf/autoload_configs/modules.conf.xml` | 🟢 | `[X]` |
| T008 | Subir isoladamente o container `freeswitch` no servidor real (`10.10.10.11`, via SSH): `docker compose -f docker-compose.app.yml up -d freeswitch` | T005, T006, T007, T012, T013, T014 | - | `docker-compose.app.yml` (ambiente) | 🟡 | `[X]` |
| T009 | Observar logs e `docker compose ps freeswitch` por pelo menos 60s, confirmando ausência de erro fatal de boot e de `Restarting` | T008 | - | ambiente (servidor `10.10.10.11`) | 🟡 | `[X]` |

## Fase 4b, Correção emergente (build customizado bloqueado)

<!-- Descoberto durante T008: build de mod_audio_fork falha com 401 contra o repositório SignalWire (token inválido/expirado). Ver roadmap D-06. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T013 | Trocar `freeswitch` service de `build:` customizado para `image: safarov/freeswitch:1.10.12` (vanilla) só para este ciclo, já que `mod_audio_fork` está fora de escopo e o build real falhou por token | - | - | `docker-compose.app.yml` | 🟢 | `[X]` |
| T014 | Remover `<load module="mod_audio_fork"/>` de `modules.conf.xml` (módulo não estará presente na imagem vanilla) | T013 | - | `freeswitch/conf/autoload_configs/modules.conf.xml` | 🟢 | `[X]` |

## Fase 5, Polimento

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T010 | Atualizar `_reversa_sdd/gaps.md`: registrar o resultado real da validação de boot (resolvido, ou ajuste necessário descoberto) | T009 | `[//]` | `_reversa_sdd/gaps.md` | 🟢 | `[X]` |
| [//] T011 | Atualizar `_reversa_sdd/infra/deployment/design.md`: documentar a config de boot do FreeSWITCH agora completa, mantendo o registro do risco residual de `mod_audio_fork` (GAP-11) como item separado, ainda não validado | T009 | `[//]` | `_reversa_sdd/infra/deployment/design.md` | 🟢 | `[X]` |

## Notas de execução

<!-- Reservado para /reversa-coding registrar avisos ou observações que surgiram durante a execução. -->

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-06-23 | Versão inicial gerada por `/reversa-to-do` | reversa |
| 2026-06-24 | Execução completa via `/reversa-coding`. 14/14 tarefas concluídas (T012-T014 adicionadas durante a execução, ver roadmap D-05/D-06). Validado com boot real em `10.10.10.11`. | reversa |
