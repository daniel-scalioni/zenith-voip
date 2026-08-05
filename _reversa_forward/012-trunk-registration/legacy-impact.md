# Legacy Impact: Registro de troncos ATA

> Data: `2026-08-03`
> Feature: `012-trunk-registration`
> Execução: parcial, 45 de 55 ações concluídas após T042
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

## Pendências desta execução parcial

T043 foi concluída com configuração individual privada; exportação CSV de troncos deixou de ser pré-requisito. T055 ainda exige a comparação legada e T044-T046 exigem checkpoint humano e ATAs reais. T047-T051 permanecem bloqueadas por essas evidências e pelos gates globais.
