# Legacy Impact: Registro de troncos ATA

> Data: `2026-08-03` (tabela de arquivos afetados e diff conceitual), atualizado em `2026-08-10` (fechamento), `2026-08-12` (Fase 6) e `2026-08-18` (Fase 7)
> Feature: `012-trunk-registration`
> Execução: fechada — 70 de 70 ações concluídas (evidências e ressalvas em `progress.jsonl` e `regression-watch.md`)
> Âncora: `_reversa_sdd/architecture.md` + `_reversa_sdd/domain.md`

## Arquivos afetados

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|-----------------|------------|------|------------|---------------|
| `src/database/models.py`, `alembic/versions/002_ata_trunks.py` | database | delta-de-dados | HIGH | Adiciona condomínios e troncos ATA no schema público, com constraints tenant-safe. |
| `src/services/trunks.py`, `trunk_import.py`, `trunk_credentials.py`, `legacy_directory.py` | services | regra-nova | HIGH | Introduz registry, importação, cifra e compatibilidade somente leitura com usuários legados. |
| `src/api/routers/trunks.py`, `src/api/freeswitch_directory.py`, `src/main.py` | api | delta-de-contrato-externo | HIGH | Adiciona CRUD administrativo e callback XML Curl interno autenticado. |
| `src/telephony/trunk_state.py`, `src/telephony/esl_client.py` | telephony | regra-nova | HIGH | Normaliza register/unregister/expire, persiste estado e reconcilia registros/chamadas. |
| `freeswitch/conf/autoload_configs/modules.conf.xml`, `xml_curl.conf.xml.example` | telephony | regra-alterada | HIGH | Carrega `mod_xml_curl` antes do Sofia e define binding privado com `POST` literal. |
| `freeswitch/conf/sip_profiles/internal.xml`, `internal-7060.xml` | telephony | regra-alterada | HIGH | Habilita autenticação nos profiles 5060/7060, mantendo blind auth falso. |
| `freeswitch/conf/directory/default.xml`, `freeswitch/conf/dialplan/default.xml` | telephony | regra-alterada | HIGH | Diretório passa a ser dinâmico e dialplan usa metadados autenticados sem alterar dígitos/bridge. |
| `scripts/render_freeswitch_secrets.py`, `.env.example`, `.gitignore` | infra | componente-novo | HIGH | Renderiza segredo XML atomicamente em modo 0600 e impede versionamento do arquivo real. |
| `docker-compose.app.yml`, `freeswitch/Dockerfile`, `bunkerweb/server-http/deny-internal.conf` | infra | regra-alterada | HIGH | Exige o módulo no build/healthcheck e bloqueia `/internal/` no proxy público. |
| `src/utils/telemetry.py` | observability | regra-nova | MEDIUM | Acrescenta métricas agregadas sem labels sensíveis. |
| `src/**/test_*.py`, `tests/test_trunk_*.py` | tests | regra-nova | MEDIUM | Cobre persistência, serviços, API, eventos, segredos e configuração. |
| `_reversa_sdd/{api,database,telephony}/**`, `_reversa_forward/012-trunk-registration/**` | specs | regra-nova | LOW | Mantém contrato SDD e evidências sanitizadas antes do código e do rollout. |
| `freeswitch/conf/dialplan/default.xml` (Fase 6, 2026-08-12) | telephony | regra-corrigida | CRITICAL | A T037 (2026-08-05) removeu `zenith_tenant_id`/`zenith_pbx_id` do dialplan sem substituto para ramal legado — toda chamada de ramal comum parou de gerar `Call` em produção. Corrigido com guarda condicional (`break="never"`) que preserva a identidade injetada pelo diretório para tronco e restaura o fallback global só quando ausente. |
| `tests/test_trunk_dialplan.py`, `src/telephony/test_esl_client.py` (Fase 6) | tests | regra-nova | MEDIUM | Cobrem os dois cenários (fallback para ramal legado, preservação para tronco) que o Red original (T019) nunca provou. |
| `docker-compose.infra.yml`, `docker-compose.app.yml`, `.env*.example` (Fase 7) | infra | regra-corrigida | HIGH | Torna o PostgreSQL promovido declarativo, preserva volume/DNS e separa senha raw da URL privada codificada. |
| `src/services/trunks.py`, `src/api/routers/trunks.py` (Fase 7) | services/api | regra-corrigida | HIGH | Fecha PATCHs, isolamento cross-tenant/PBX, colisão legado, timestamps e leitura real/resiliente de uso. |
| `tests/test_postgres_cutover_compose.py`, testes de services/router (Fase 7) | tests | regra-nova | MEDIUM | Provam os quatro watches e bordas adicionadas após o primeiro NO-GO independente. |

## Diff conceitual por componente

### Database e services

O schema público passa a registrar condomínios e troncos ATA com escopo por tenant/PBX. Senhas SIP são cifradas com MultiFernet, e a importação nasce desabilitada e idempotente. O provider legado preserva `extensions.xml` sem migrar ou reescrever seus usuários.

### API

A API ganha contratos administrativos tenant-scoped e um callback interno de diretório. O spike T042 confirmou `sip_profile`, `sip_auth_username` e `key_value` como envelope real; aliases têm precedência explícita e o domínio nunca é usado como username.

Na Fase 7, os PATCHs documentados tornaram-se alcançáveis com revalidação tenant/PBX e de
identidade legado. As views consultam uso real no Redis; falha dessa leitura não desfaz nem mascara
como erro uma mutação já persistida.

### Telephony

`mod_xml_curl` torna-se autoridade exclusiva do diretório nos profiles-alvo. Evidência real exigiu `method=POST` em maiúsculas. Eventos CUSTOM de registro e expiração foram capturados; `sofia::expire` usa `user`/`username`. Profile 5062, dígitos e bridge upstream permanecem protegidos.

### Infra e segurança

O XML com HTTP Basic é gerado fora do Git, modo 0600, e o endpoint é bloqueado no proxy público. Todos os recursos usados no rehearsal têm prefixo `zenith-`; o `zenith-freeswitch` operacional não foi modificado.

O serviço canônico `postgres` agora aponta declarativamente ao container/volume promovidos. A
senha do container e a `DATABASE_URL` URL-encoded são segredos separados, sem default versionado.

## Preservadas

- R05: PBX continua pertencendo ao tenant.
- R07: portas/topologia 5060, 7060 e 5062 permanecem; 5062 não foi migrado.
- R24/R25/R26: TTL SIP legado, linkage `*88` e reconexão ESL permanecem.
- R46: chamada sem `tenant_id` continua sem persistência. **Nota (Fase 6, 2026-08-12):** a regra em si nunca mudou, mas entre 2026-08-05 (T037) e 2026-08-12 o *caminho de entrada* dela ficou errado — praticamente toda chamada de ramal legado passou a cair no ramo "sem `tenant_id`" por falta de fonte, não por ausência real de tenant. R46 continuou "preservada" no sentido estrito (regra íntegra), mas produzindo o efeito prático oposto ao pretendido para o caso de uso central do produto. Corrigido nesta mesma feature (RN-11/RF-13/D-15).
- R52/R53: somente `INSTANCE_ID == 1` consome eventos e comandos usam socket separado.
- R55/R56: recursos permanecem prefixados `zenith-` e API publicada apenas em loopback.

## Modificadas

- R54: o healthcheck continua exigindo `mod_audio_stream` e agora exige também `mod_xml_curl` antes de considerar o FreeSWITCH saudável.

## Riscos e evidências no fechamento (T050)

### Autenticação

- `internal-7060` é o único profile com `auth-calls=true` ativado nesta feature; `internal` (5060) foi revertido para `false` após descobrir-se que hospeda troncos PSTN externos reais (W003, resolvido). Ativação real do 5060 fica para feature futura dedicada (`requirements.md §9`).
- O binding `mod_xml_curl` é declarado por seção (`bindings="directory"`), não por profile: uma vez carregado, atende lookups de 5060, 7060 **e** 5062 ao mesmo tempo. O que isola cada profile é `auth-calls`, não o alcance do binding — ver W007 (observação) e onboarding.md §7.
- `TrunkService` falha fechado (403, não erro explícito) quando `tenant.status != "active"` — comportamento correto de segurança, mas documentado como pitfall operacional em `regression-watch.md` para quem for provisionar tenants de teste.
- Auditoria de vazamento de credencial (T047, canário real) não encontrou ocorrência em logs de app/FreeSWITCH/proxy/métricas no nível de log atual; ressalva registrada em `security-verdict.md`: `docker logs zenith-freeswitch` retém pouquíssimo, então "zero ocorrências" reflete retenção quase nula, não prova de robustez sob log verboso — se o loglevel do Sofia for elevado no futuro, reauditar.

### Variáveis de ambiente novas

| Variável | Arquivo | Função | Nota |
|---|---|---|---|
| `TRUNK_CREDENTIAL_KEYS` | `src/config.py`, `.env.example` | Uma ou mais chaves Fernet (CSV) para `TrunkCredentialCipher`/`MultiFernet` | Falha rápido na construção (`CredentialConfigurationError`) se vazia ou inválida — nunca falha silenciosamente no primeiro `encrypt`/`decrypt` |
| `FREESWITCH_DIRECTORY_BASIC_USERNAME` / senha correspondente | `.env.example` | HTTP Basic exclusivo do binding `mod_xml_curl` | Distinto de `JWT_SECRET` e da senha ESL; nunca reaproveitar |
| `FREESWITCH_ESL_PASSWORD` | `src/config.py` | Pré-existente (default `ClueCon`, já registrado em ADR-005 como to-do) | Não alterado por esta feature |

### Porta 5062

- `internal-5062.xml` permanece com `auth-calls=false` e não foi tocado por nenhuma ação desta feature — confirmado intacto ao longo de todo o ensaio de rollback (onboarding.md §"Ensaio de rollback") e do T046 (troncos duplicados).
- Risco residual conhecido (não corrigido, é comportamento herdado do binding global): se `auth-calls` for setado `true` em 5062 por engano em qualquer mudança futura, o mesmo diretório dinâmico já responderá lookups nesse profile imediatamente, sem código adicional. Vale monitorar em qualquer PR futuro que toque `sip_profiles/`.

### Segredo

- Senhas SIP são cifradas com `MultiFernet` (`TrunkCredentialCipher`); chave nunca versionada, carregada só de `TRUNK_CREDENTIAL_KEYS`.
- O XML com HTTP Basic do `mod_xml_curl` é renderizado fora do Git (`scripts/render_freeswitch_secrets.py`), modo `0600`, escrita atômica; `.gitignore` bloqueia o arquivo real, mantendo só `.example`.
- Nenhuma senha SIP em claro observada em disco, log ou resposta de erro durante o canário do T047 (`security-verdict.md`).

### Rollback

Procedimento real, ensaiado e com um defeito próprio corrigido em 2026-08-06 (ver `onboarding.md §8` para o passo a passo completo — não duplicado aqui):

1. Descarregar `mod_xml_curl` devolve o diretório estático a todos os profiles de uma vez (o binding não é por profile).
2. Reverter **apenas o parâmetro `auth-calls`**, nunca `git checkout main -- freeswitch/conf/sip_profiles/` inteiro — a versão de `main` reintroduz GAP-NET-01 (W005) via `$${external_sip_ip}`/`$${external_rtp_ip}` sobrescritas pelo `zenith-ip-watcher`.
3. Tabelas aditivas (`condominiums`, `ata_trunks`) permanecem no banco; não há downgrade de migration no rollback operacional.
4. Comportamento operacional observado: após `403`, o ATA entra em backoff e não retenta sozinho — um rollback real exige forçar o registro no equipamento, não só desfazer a config.

## Correção pós-fechamento (Fase 6, 2026-08-12)

### Causa raiz

A T037 (`git show ca73f4e`, 2026-08-05) removeu de `zenith_audio_fork` as duas linhas `zenith_tenant_id=$${tenant_id}`/`zenith_pbx_id=$${pbx_id}`, única fonte dessas variáveis para chamadas de ramal legado. O Red correspondente (T019) só provou a ausência do mecanismo antigo, nunca a presença de um substituto para esse caminho — a injeção nova (`src/api/freeswitch_directory.py`) só cobre identidades resolvidas como tronco. Confirmado por busca exaustiva (`grep -rl "zenith_tenant_id" freeswitch/conf/`): nenhuma outra fonte preenchia a variável para ramal legado entre 2026-08-05 e 2026-08-12.

### Efeito em produção

Toda chamada por ramal comum deixou de gerar linha `Call` (guard `if tenant_id:` em `esl_client.py`, comportamento de R46 já documentado como risco em `_reversa_sdd/telephony/design.md#6`, GAP-RE-03) — sem erro visível. Por consequência, `Transcript`, `CallInsight`, upload de gravação e backup SMB (feature 011) também pararam de ser gerados para esse caminho. Só chamadas por tronco ATA continuaram funcionando.

### Correção

Dialplan (`freeswitch/conf/dialplan/default.xml`) dividido em três `<condition>`: (1) `zenith_call_id`/`zenith_agent_extension`, incondicional, como antes; (2) guarda `field="${zenith_tenant_id}" expression="^$" break="never"` — só aplica o fallback global quando o canal ainda não tem a variável, e o `break="never"` garante que a chamada sempre chega em `answer`/`bridge` mesmo quando a guarda não casa (tronco); (3) `answer`/`start_dtmf`/`bridge`, idênticos ao original. Testes: `tests/test_trunk_dialplan.py` (5 casos, estrutura do XML) e `src/telephony/test_esl_client.py` (3 casos novos, comportamento do `ESLClient` dado o evento). Suite global: 308 passed (era 301), mesma baseline de 10 failed/3 erros de coleta pré-existentes.

### Pendência real desta correção

Diferente do restante da feature 012 (T044 exigiu ATA físico real), esta correção **não foi validada com uma chamada real via ramal físico** através do dialplan corrigido — só com testes estruturais (XML) e de serviço (mocks). O histórico de `_reversa_sdd/telephony/design.md#5-6` (GAP-DIALPLAN-01 a 04) mostra que mudanças de dialplan já esconderam bugs reais que só apareceram em chamada real. Recomendado registrar chamada real de ramal comum e conferir a linha `Call` no banco antes de considerar o item "fechado" em produção — decisão do usuário quanto ao momento.

## Pendências desta execução

Nenhuma pendência bloqueante das 60 ações. T043–T049 concluídas com evidência real (checkpoint humano T044 cumprido com ATA físico real no 7060). Gaps conhecidos e deliberadamente não corrigidos — `PATCH /trunks|condominiums` ausente (W006) e `active_calls`/`in_use` não populados em `GET/POST /trunks` (W007) — ficam registrados em `regression-watch.md` para decisão em feature futura. A Fase 6 (T057-T060, 2026-08-12) corrigiu a regressão da T037; a única pendência real é a validação com chamada física de ramal comum, descrita acima — não bloqueante, mas recomendada.
