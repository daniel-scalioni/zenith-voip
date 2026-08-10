# Legacy Impact: Registro de troncos ATA

> Data: `2026-08-03` (tabela de arquivos afetados e diff conceitual), atualizado em `2026-08-10` (fechamento)
> Feature: `012-trunk-registration`
> Execução: fechada — 56 de 56 ações concluídas (T004/T005/T042/T043/T044/T046 exigiam evidência de ambiente e todas foram cumpridas com evidência real, não por inferência, exceto a cláusula de chamadas simultâneas/eventos duplicados do T046, coberta pela suíte automatizada por decisão do usuário, não por E2E real — ver `regression-watch.md`; demais evidências em `progress.jsonl`)
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

## Diff conceitual por componente

### Database e services

O schema público passa a registrar condomínios e troncos ATA com escopo por tenant/PBX. Senhas SIP são cifradas com MultiFernet, e a importação nasce desabilitada e idempotente. O provider legado preserva `extensions.xml` sem migrar ou reescrever seus usuários.

### API

A API ganha contratos administrativos tenant-scoped e um callback interno de diretório. O spike T042 confirmou `sip_profile`, `sip_auth_username` e `key_value` como envelope real; aliases têm precedência explícita e o domínio nunca é usado como username.

### Telephony

`mod_xml_curl` torna-se autoridade exclusiva do diretório nos profiles-alvo. Evidência real exigiu `method=POST` em maiúsculas. Eventos CUSTOM de registro e expiração foram capturados; `sofia::expire` usa `user`/`username`. Profile 5062, dígitos e bridge upstream permanecem protegidos.

### Infra e segurança

O XML com HTTP Basic é gerado fora do Git, modo 0600, e o endpoint é bloqueado no proxy público. Todos os recursos usados no rehearsal têm prefixo `zenith-`; o `zenith-freeswitch` operacional não foi modificado.

## Preservadas

- R05: PBX continua pertencendo ao tenant.
- R07: portas/topologia 5060, 7060 e 5062 permanecem; 5062 não foi migrado.
- R24/R25/R26: TTL SIP legado, linkage `*88` e reconexão ESL permanecem.
- R46: chamada sem `tenant_id` continua sem persistência.
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

## Pendências desta execução

Nenhuma. T043–T049 concluídas com evidência real (checkpoint humano T044 cumprido com ATA físico real no 7060). Gaps conhecidos e deliberadamente não corrigidos nesta rodada — `PATCH /trunks|condominiums` ausente (W006) e `active_calls`/`in_use` não populados em `GET/POST /trunks` (W007) — ficam registrados em `regression-watch.md` para decisão em feature futura, não bloqueiam o fechamento desta.
