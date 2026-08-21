# Regression Watch: Registro de troncos ATA

> Feature: `012-trunk-registration`
> Execução: fechada, 70 de 70 ações concluídas (Fase 7 — W002/W004/W006/W007 corrigidos em 2026-08-18)

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
| W008 | `freeswitch/conf/dialplan/default.xml`, extensão `zenith_audio_fork`; `src/api/freeswitch_directory.py` | O dialplan só pode setar `zenith_tenant_id`/`zenith_pbx_id` a partir do fallback global (`condition field="${zenith_tenant_id}" expression="^$" break="never"`) quando o canal ainda não tem essas variáveis. Identidade injetada pelo diretório dinâmico para um tronco (via `mod_xml_curl`) tem precedência e nunca pode ser sobrescrita. | presença + redação | (a) Qualquer edição do dialplan que volte a setar `zenith_tenant_id=$${tenant_id}` na primeira `condition` (incondicional) reintroduz a regressão original: todo tronco passaria a reportar `tenant_id=akom`, cruzando identidade entre tenants. (b) Remover o `break="never"` da condição de guarda reintroduz a regressão da T037: a chamada aborta antes de `answer`/`bridge` sempre que `zenith_tenant_id` já vier setado (todo tronco), silenciando também ramal legado se a ordem das `condition` mudar. Watch nasceu da correção RN-11/RF-13/D-15 (2026-08-12), depois que a T037 (2026-08-05) removeu a atribuição sem substituto para ramal legado — ver `requirements.md#9-esclarecimentos` e `roadmap.md#D-15`. |

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
- **Fase 6 (2026-08-12):** a T037 (`git show ca73f4e`) removeu `zenith_tenant_id=$${tenant_id}`/`zenith_pbx_id=$${pbx_id}` do dialplan sem substituto para ramal legado; confirmado por busca exaustiva (`grep -rl "zenith_tenant_id" freeswitch/conf/`) que nenhuma outra fonte cobria esse caminho entre 2026-08-05 e 2026-08-12. Corrigido com guarda condicional (T058); `tests/test_trunk_dialplan.py` (5 testes) e `src/telephony/test_esl_client.py` (3 testes novos: ausência não cria `Call`, ramal legado cria com `akom`, tronco cria com o tenant real e nunca `akom`) cobrem os dois cenários. Suite global re-executada: 308 passed (era 301), mesmos 10 failed/3 erros de coleta pré-existentes (ambiente sem `deepgram`/SMB, não relacionados). Validação com chamada real via ramal físico (equivalente ao T044 desta feature) ainda não foi feita — recomendada antes de considerar o item fechado em produção.

## Riscos consolidados no fechamento (T050)

Resumo curto por categoria — evidência completa e procedimentos em `legacy-impact.md#riscos-e-evidências-no-fechamento-t050` e `onboarding.md`, não duplicados aqui.

- **Auth:** só `internal-7060` tem `auth-calls=true`; binding `mod_xml_curl` é global por seção (não por profile), então quem isola 5060/5062 hoje é `auth-calls=false`, não o alcance do binding. Ver W003, W007.
- **Variáveis:** `TRUNK_CREDENTIAL_KEYS` (Fernet, falha rápido se ausente/inválida), `FREESWITCH_DIRECTORY_BASIC_USERNAME`/senha (Basic exclusivo do `mod_xml_curl`, distinto de JWT/ESL). Nenhuma nova variável reaproveita segredo existente.
- **5062:** intocado durante toda a feature, inclusive no ensaio de rollback e no T046; risco residual é apenas o binding global já registrado acima, não uma mudança desta feature.
- **Segredo:** cifra `MultiFernet` para senha SIP no banco; XML com Basic renderizado fora do Git em modo 0600. Canário do T047 não encontrou senha em claro em log/erro no loglevel atual (ressalva de retenção registrada em `security-verdict.md`).
- **Rollback:** ensaiado de verdade em 2026-08-06, encontrou e corrigiu um defeito no próprio procedimento (reverter só `auth-calls`, nunca o arquivo inteiro — W005). Tabelas aditivas nunca sofrem downgrade no rollback operacional.

## Histórico de re-extrações

### Re-extração 2026-08-17 15:25

| ID | Veredito | Observação |
|----|----------|------------|
| W001 | 🟢 verde | Healthcheck exige simultaneamente `mod_audio_stream` e `mod_xml_curl`. |
| W002 | 🔴 vermelho | Compose canônico ainda liga `zenith-postgres` à `ai-hub-net`, enquanto o compose candidato usa rede isolada e não declara o alias `postgres`; um `up` não preserva o cutover descrito pelo item. |
| W003 | 🟢 verde | `internal.xml` mantém `auth-calls=false`; 7060 é o único profile ATA autenticado neste ciclo. |
| W004 | 🔴 vermelho | Reimportação com senha chama `update`, redefine `registration_status=unknown` e não limpa/reconcilia timestamps anteriores. |
| W005 | 🟢 verde | `internal`, `internal-7060` e `internal-5062` usam `$${local_ip}` para SIP/RTP. |
| W006 | 🔴 vermelho | Router continua sem `PATCH /trunks/{id}` e `PATCH /condominiums/{id}`, apesar dos services implementados. |
| W007 | 🔴 vermelho | Views de create/list continuam usando `_trunk_view(item)` sem consultar `SCARD`; `active_calls=0` e `in_use=false` são defaults estáticos. |
| W008 | 🟢 verde | Guarda `${zenith_tenant_id} == vazio` com `break=never` preserva contexto ATA e fallback legado. |

### Revalidação corretiva 2026-08-18

| ID | Veredito | Observação |
|----|----------|------------|
| W002 | 🟢 verde | Compose canônico promove `zenith-postgres-candidate`, adota o volume externo existente e exige `DATABASE_URL` privada em todos os cinco consumidores. Parsing/teste estático passou; aplicação runtime aguarda o próximo deploy por ausência de Docker neste ambiente. |
| W004 | 🟢 verde | Reimportação com senha grava `unknown` e limpa ambos os timestamps na mesma chamada ao Repository; teste específico do caminho `upsert_imported` passou. |
| W006 | 🟢 verde | Ambos os PATCHs existem, derivam tenant do JWT, revalidam condomínio e identidade legada e rejeitam payload vazio/nulo inválido. |
| W007 | 🟢 verde | POST/PATCH/GET consultam `TrunkStateService`; lista concorrente preserva ordem e falha Redis degrada somente a view para zero, com log, sem converter mutação persistida em erro. |

Revisão independente pós-correção: **GO**, sem CRITICAL/HIGH/MEDIUM; 92 testes focados e probes
independentes aprovados. Gate canônico local: 401 passed, 29 skipped, cobertura 90,07%.

Nenhuma.

## Arquivadas

Nenhuma.
