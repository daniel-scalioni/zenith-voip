# Regression Watch: Registro de troncos ATA

> Feature: `012-trunk-registration`
> Execução: fechada, 51 de 51 ações reais concluídas

## Watch principal

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|-------------------------|-----------------------------|--------------------|-------------------|
| W001 | `_reversa_sdd/domain.md#SIP e Telefonia`, R54 | FreeSWITCH só fica healthy quando `mod_audio_stream` e `mod_xml_curl` estão carregados. | redação | Healthcheck aceita container sem um dos dois módulos. |
| W002 | `docker-compose.infra.yml`, serviço `postgres` | O banco que a API usa é quem detém o alias de rede `postgres` em `zenith-voip_ai-hub-net`. Hoje é o `zenith-postgres-candidate`; o compose ainda declara `zenith-postgres`, que está fora de qualquer rede. | presença | Um `docker compose up` sem `--no-deps` reconecta o `zenith-postgres`, a API passa a apontar para um banco sem `condominiums`/`ata_trunks` e o registro de troncos falha fechado sem erro aparente. |
| W003 | `freeswitch/conf/sip_profiles/internal.xml` | **RESOLVIDO em 2026-08-07.** O profile `internal` (5060) tinha `auth-calls=true` em disco (repo e servidor) sem ativação deliberada; descoberto que 5060 hospeda troncos PSTN externos reais (ver requirements.md §9). Revertido para `false` nos dois lugares, sem restart. Mantido no histórico como lembrete de nunca reintroduzir sem antes resolver a coexistência com identidades PSTN no mesmo profile. | presença | Qualquer edição futura de `internal.xml` que reintroduza `auth-calls=true` sem essa resolução prévia. |
| W004 | `src/services/trunks.py::upsert_imported` | Reimportar um tronco existente não deve deixar o estado operacional inconsistente. | redação | `registration_status` volta para `unknown` enquanto `last_registered_at`/`last_unregistered_at` seguem preenchidos — observado no tronco 1780 em 2026-08-06. Um tronco registrado que for reimportado passa a reportar estado desconhecido sem que nada tenha mudado na telefonia. |
| W005 | `freeswitch/conf/sip_profiles/*.xml`, `ext-sip-ip`/`ext-rtp-ip` | Os profiles internos devem usar `$${local_ip}`, nunca `$${external_sip_ip}`/`$${external_rtp_ip}`. | presença | O `zenith-ip-watcher` sobrescreve as variáveis `external_*` com o IP público; um profile interno que as use sobe em `200.170.149.139` e quebra peers locais (GAP-NET-01). Reintroduzido acidentalmente no ensaio de rollback de 2026-08-06 ao restaurar os arquivos a partir de `main`. |
| W006 | `src/api/routers/trunks.py` | `PATCH /trunks/{id}` e `PATCH /condominiums/{id}`, documentados em `interfaces/trunks-api.md`, devem existir e delegar para `TrunkService.update`/`CondominiumService.update` (já implementados e testados na camada de serviço). | presença | O router só expõe `POST`/`GET` para os dois recursos; a rota HTTP de atualização não existe (404), embora a lógica de serviço já esteja pronta e testada (`test_update_trunk_without_password_preserves_existing_cipher`). Hoje só é possível editar um tronco/condomínio direto no banco. Registrado como gap conhecido por decisão do usuário em 2026-08-07, não implementado nesta rodada. |
| W007 | `src/api/routers/trunks.py::_trunk_view`, `interfaces/trunks-api.md`, `_reversa_sdd/database/trunk-registry/design.md` | `active_calls` (via `TrunkStateService.active_calls`, que lê `SCARD`) e `in_use` (derivado) devem refletir o estado real de chamadas do tronco em `GET/POST /trunks`. | presença | `create_trunk` e `list_trunks` chamam `_trunk_view(item)` sem passar `active_calls`, então o parâmetro fica sempre no default `0`/`in_use=False`, mesmo com chamadas ativas reais. Descoberto em 2026-08-10 durante revisão anti-viés do advisor sobre os testes de T049 (`test_list_trunks_returns_serialized_items` documenta o comportamento atual, não a especificação). Não corrigido nesta rodada — fora do escopo de T049. |

## Observações

- O binding exige `method=POST` em maiúsculas na imagem FreeSWITCH 1.10.12; `post` causa HTTP 501.
- O envelope XML Curl observado usa `sip_profile`, `sip_auth_username` e `key_value` como domínio.
- `sofia::expire` foi observado com `profile-name` e identidade em `user`/`username`.
- Usuários de `extensions.xml`, profile 5062 e gateways upstream continuam protegidos; equivalência real aguarda T055.
- O tronco 1020 é identidade SIP, não prefixo: o Zenith deve preservar o destino `100` sem adicionar ou remover dígitos.
- A configuração individual de Parque Portugal foi importada com `prefix=null` e `enabled=false`; a ativação real continua bloqueada por T044.
- A equivalência do diretório legado foi comprovada para 939 usuários, sem ausências ou divergências; um registro legado real em 7060 e sua remoção retornaram SIP 200.
- O binding XML Curl é declarado por seção (`bindings="directory"`), nunca por profile: uma vez ativo, vale para 5060, 7060 e 5062 simultaneamente. O que isola o 5062 hoje é `auth-calls=false`, não o alcance do binding.
- Com o binding global ativo, um usuário legado registrou no profile `internal` (5060) com 200/200, confirmando que o provider somente-leitura atende a população existente.
- **T046 (2026-08-07):** prefixo idêntico (`9199`) provisionado em dois tenants distintos (Akom real + tenant sintético de teste, ambos `status=active`) e registrado simultaneamente via SIP real em `internal-7060` — `sofia status profile internal-7060 reg` mostrou as duas entradas ao mesmo tempo, banco confirmou `registration_status=registered` nos dois com `tenant_id` diferentes. Sem cruzamento de estado. Cláusula de chamadas simultâneas/eventos duplicados/contador não-negativo do critério de aceite **não foi exercitada em E2E real** (FreeSWITCH vanilla sem `mod_loopback`/`mod_dummy`, sem segundo ATA físico disponível); coberta pela suíte automatizada (T016/T030, já verde), por decisão do usuário.
- Pitfall descoberto durante T046: `TrunkService` exige `tenant.status == "active"` para resolver lookups de diretório; um tenant com outro status (ex.: `test`) falha fechado como se o tronco não existisse, sem sinalizar o motivo real. Não é um bug de isolamento entre tenants, mas vale documentar para quem for criar tenants de teste no futuro.

## Riscos consolidados no fechamento (T050)

Resumo curto por categoria — evidência completa e procedimentos em `legacy-impact.md#riscos-e-evidências-no-fechamento-t050` e `onboarding.md`, não duplicados aqui.

- **Auth:** só `internal-7060` tem `auth-calls=true`; binding `mod_xml_curl` é global por seção (não por profile), então quem isola 5060/5062 hoje é `auth-calls=false`, não o alcance do binding. Ver W003, W007.
- **Variáveis:** `TRUNK_CREDENTIAL_KEYS` (Fernet, falha rápido se ausente/inválida), `FREESWITCH_DIRECTORY_BASIC_USERNAME`/senha (Basic exclusivo do `mod_xml_curl`, distinto de JWT/ESL). Nenhuma nova variável reaproveita segredo existente.
- **5062:** intocado durante toda a feature, inclusive no ensaio de rollback e no T046; risco residual é apenas o binding global já registrado acima, não uma mudança desta feature.
- **Segredo:** cifra `MultiFernet` para senha SIP no banco; XML com Basic renderizado fora do Git em modo 0600. Canário do T047 não encontrou senha em claro em log/erro no loglevel atual (ressalva de retenção registrada em `security-verdict.md`).
- **Rollback:** ensaiado de verdade em 2026-08-06, encontrou e corrigiu um defeito no próprio procedimento (reverter só `auth-calls`, nunca o arquivo inteiro — W005). Tabelas aditivas nunca sofrem downgrade no rollback operacional.

## Histórico de re-extrações

Nenhuma.

## Arquivadas

Nenhuma.
