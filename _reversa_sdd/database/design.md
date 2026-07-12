# Database, Design Técnico

> Gerado pelo Writer — 2026-06-19

## Interface

### Modelos ORM (SQLAlchemy)

| Modelo | Schema | Tabela |
|--------|--------|--------|
| Tenant | public | tenants |
| PBX | public | pbxs |
| Call | tenant_{id} | calls |
| Transcript | tenant_{id} | transcripts |
| CallInsight | tenant_{id} | call_insights |
| STTMetric | tenant_{id} | stt_metrics |

### Funções

| Símbolo | Assinatura | Retorno |
|---------|-----------|---------|
| `get_tenant_session` | `(tenant_id: UUID)` | `AsyncSession` |
| `init_db` | `()` | `None` |
| `run_migrations` | `()` | `None` |

## Fluxo Principal

1. `init_db()` cria engine e verifica conexão — `src/database/database.py:10-20`
2. Tenant autenticado → schema `tenant_{id}` resolvido do JWT
3. `get_tenant_session()` retorna sessão com `search_path` = schema do tenant — `src/database/database.py:33-37`
4. Operações CRUD via GenericRepository — `src/services/base.py:40-60`
5. Migrations executadas por Alembic nas 3 revisões existentes (**apenas contra o schema `public`** — ver ressalva abaixo)
6. Provisionamento de um novo tenant: `scripts/provision_tenant.py` insere `Tenant`/`PBX` em `public` e cria o schema do tenant via `create_tenant_schema(schema_name)` (`database.py:33-37`, `TenantBase.metadata.create_all` direto)

## Decisões de Design

| Decisão | Evidência | Confiança |
|---------|-----------|-----------|
| Schema-per-tenant com search_path | `database.py:33-37` | 🟢 |
| Repositório genérico CRUD | `services/base.py:40-60` | 🟢 |
| Migrations Alembic com revisões | `alembic/versions/` | 🟢 |
| `run_migrations_for_schema(schema_name)` **não deve ser usado** para provisionar schema de tenant | Migrations 001 e 003 criam tabelas com os mesmos nomes (`calls`, `transcripts`, `call_insights`, `stt_metrics`) sem qualificar `schema=` — rodar `alembic upgrade head` com `SET search_path` para um schema de tenant executa 001 e 003 em sequência e colide ("relation already exists"). Confirmado empiricamente (2026-07-10, MVP Fase 1). Usar `create_tenant_schema()` (SQLAlchemy `metadata.create_all` direto) para isso, via `scripts/provision_tenant.py` | 🟢 |
| Colunas booleanas precisam de tipo explícito (`Column(Boolean, default=...)`) | `Column(default=...)` sem tipo compila para `NullType`, quebra `create_tenant_schema()` — ver GAP-19 em `gaps.md` | 🟢 |

## Riscos e Lacunas

- 🟡 Sem pool de conexões configurado além do default do SQLAlchemy
- 🟡 Criação de schema de tenant não está exposta via API (apenas migration manual)
