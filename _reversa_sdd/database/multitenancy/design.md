# Multitenancy, Design

**Interface:** `get_tenant_session(tenant_id) → AsyncSession`
**Mecanismo:** search_path = tenant_{id} na sessão SQLAlchemy; tabelas globais no schema public
**Modelos:** Tenant, PBX (public); Call, Transcript, CallInsight, STTMetric (tenant_{id})
**Origem:** `src/database/database.py:33-37` 🟢
