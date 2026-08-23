# Multitenancy, Design

**Interface:** `get_tenant_session(tenant_id) → AsyncSession`
**Mecanismo:** search_path = tenant_{id} na sessão SQLAlchemy; tabelas globais no schema public
**Modelos:** Tenant, PBX (public); Call, Transcript, CallInsight, STTMetric (tenant_{id})
**Origem:** `src/database/database.py:33-37` 🟢

**Provisionamento de tenant:** `scripts/provision_tenant.py --name <nome> --schema tenant_<slug> --pbx-name <nome> --pbx-host <host> --pbx-port <porta>` — insere `Tenant`/`PBX` em `public` (idempotente, checa existência antes de inserir) e cria o schema do tenant via `create_tenant_schema(schema_name)`. **Não usa Alembic** (`run_migrations_for_schema` colide entre as migrations 001/003 — ver `database/design.md`). O slug do schema (após `tenant_`) precisa ser alfanumérico simples, sem hífen: `_tenant_schema()`/consultas ao schema montam a string via f-string sem aspas.

**Primeiro tenant real provisionado (2026-07-10, MVP Fase 1):** Akom (`schema_name=tenant_akom`), PBX "VitalPBX Akom" (`sip.maisalerta.tecnorise.com:7060`). `tenant_id=akom`/`pbx_id=<uuid>` fixados em `freeswitch/conf/vars.xml` para que ramais registrados nativamente no FreeSWITCH (não via `bypass_to_pbx`) populem esses valores no dialplan — resolve GAP-21 (`gaps.md`), sem isso nenhuma linha `Call` era criada.

**Reprovisionado em 2026-07-23 (GAP-25):** `public.tenants` estava vazio e o schema `tenant_akom` não existia mais em nenhum dos volumes Postgres do host (nem no volume antigo `postgres_data`, nem no atual `zenith_postgres_data`) — o provisionamento de 07-10 nunca persistiu de fato, ou foi perdido antes da renomeação de volumes registrada em `docker-compose.infra.yml`. Reprovisionado com os mesmos parâmetros; novo `pbx_id` (`c5bf3191-75b4-4a45-b5e1-c9b7942f8176`) atualizado em `freeswitch/conf/vars.xml` (o antigo `0cc6c169-...` não existe mais em `public.pbxs`).

**Sincronização vars.xml ← Postgres (GAP-RE-07, decisão do usuário 2026-08-21):** o
`tenant_id=akom`/`pbx_id=<uuid>` de `vars.xml` (linha 18-19) era editado à mão a cada
reprovisionamento — foi assim que GAP-25 (schema perdido, `pbx_id` desatualizado sem erro
visível) aconteceu. Postgres passa a ser a **fonte de verdade**; `vars.xml` é gerado a partir
dele, não editado direto.

- `scripts/sync_vars_xml.py --schema tenant_<slug> [--vars-xml PATH] [--check]` — lê o `Tenant`
  (por `schema_name`) e seu `PBX` no Postgres, substitui só as duas linhas
  `X-PRE-PROCESS cmd="set" data="tenant_id=..."`/`data="pbx_id=..."` de `vars.xml`, preservando
  o resto do arquivo byte a byte (comentários, `local_ip`, `external_*_ip`, `domain`,
  `pbx_host`, codecs). Escrita atômica (`tempfile` + `os.replace`), padrão de
  `render_freeswitch_secrets.py` — mas **preservando o modo original do arquivo** (`vars.xml`
  não é segredo, tem que continuar legível pelo processo do FreeSWITCH depois da troca;
  `render_freeswitch_secrets.py` fixa em 0600 de propósito porque o dele é segredo, aqui seria
  regressão de permissão). `--check` não escreve, só retorna código de saída ≠0 se `vars.xml`
  divergir do Postgres (uso em smoke test / futuro alerta).
  **Escrever o arquivo não recarrega o FreeSWITCH** — `X-PRE-PROCESS` é avaliado no parse do
  XML; sem `reloadxml` (ou restart do container) depois de rodar o script, o processo em memória
  continua com o `pbx_id` antigo mesmo com o arquivo já correto no disco. `--check` reflete o
  arquivo, não o processo rodando.
- **Limitação intencional, não é bug:** exige exatamente 1 `Tenant` com o `schema_name` pedido
  e exatamente 1 `PBX` associado — se houver mais de um PBX para o tenant, falha alto e explícito
  em vez de escolher um. `vars.xml` só tem uma variável global por chave; não há como representar
  N tenants nele hoje (seria só resolvido por `GAP-PROV-01`, provisionamento dinâmico via
  `mod_xml_curl` — enquanto isso não existe, o fallback de ramal local continua sendo
  necessariamente de **um** tenant só, o mesmo limite que já existia manualmente).
- `scripts/provision_tenant.py` ganhou a flag opcional `--sync-vars-xml PATH` — chama a mesma
  lógica para o tenant recém-provisionado. **Opt-in, não automático por padrão**: rodar sem a
  flag continua imprimindo as instruções manuais de sempre, porque escrever
  `vars.xml` sem essa flag poderia sobrescrever silenciosamente o tenant que hoje está lá se
  alguém provisionar um segundo tenant sem perceber a implicação (ver limitação acima).
- **Não inclui** reescrever `vars.xml` no servidor de produção (10.10.10.11) — isso é uma ação
  de deploy, fora do escopo desta mudança de código; exige confirmação separada quando for
  executada de fato.
- Teste de drift (`tests/test_vars_xml_drift.py`, `ZENITH_RUN_INFRA_TESTS=1`) roda `--check`
  contra o Postgres e o `vars.xml` reais do ambiente de integração, mesmo padrão de
  `test_infra.py`/`test_chaos_restart.py` (pulado por padrão, exige stack real).
