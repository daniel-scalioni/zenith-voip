# Multitenancy, Design

**Interface:** `get_tenant_session(tenant_id) → AsyncSession`
**Mecanismo:** search_path = tenant_{id} na sessão SQLAlchemy; tabelas globais no schema public
**Modelos:** Tenant, PBX (public); Call, Transcript, CallInsight, STTMetric (tenant_{id})
**Origem:** `src/database/database.py:33-37` 🟢

**Provisionamento de tenant:** `scripts/provision_tenant.py --name <nome> --schema tenant_<slug> --pbx-name <nome> --pbx-host <host> --pbx-port <porta>` — insere `Tenant`/`PBX` em `public` (idempotente, checa existência antes de inserir) e cria o schema do tenant via `create_tenant_schema(schema_name)`. **Não usa Alembic** (`run_migrations_for_schema` colide entre as migrations 001/003 — ver `database/design.md`). O slug do schema (após `tenant_`) precisa ser alfanumérico simples, sem hífen: `_tenant_schema()`/consultas ao schema montam a string via f-string sem aspas.

**Primeiro tenant real provisionado (2026-07-10, MVP Fase 1):** Akom (`schema_name=tenant_akom`), PBX "VitalPBX Akom" (`sip.maisalerta.tecnorise.com:7060`). `tenant_id=akom`/`pbx_id=<uuid>` fixados em `freeswitch/conf/vars.xml` para que ramais registrados nativamente no FreeSWITCH (não via `bypass_to_pbx`) populem esses valores no dialplan — resolve GAP-21 (`gaps.md`), sem isso nenhuma linha `Call` era criada.

**Reprovisionado em 2026-07-23 (GAP-25):** `public.tenants` estava vazio e o schema `tenant_akom` não existia mais em nenhum dos volumes Postgres do host (nem no volume antigo `postgres_data`, nem no atual `zenith_postgres_data`) — o provisionamento de 07-10 nunca persistiu de fato, ou foi perdido antes da renomeação de volumes registrada em `docker-compose.infra.yml`. Reprovisionado com os mesmos parâmetros; novo `pbx_id` (`c5bf3191-75b4-4a45-b5e1-c9b7942f8176`) atualizado em `freeswitch/conf/vars.xml` (o antigo `0cc6c169-...` não existe mais em `public.pbxs`).
