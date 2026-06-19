# Gerenciamento de PBXs (api/pbx-management)

**Responsabilidades:** CRUD de PBXs por tenant
**Regras:** Somente tenant_admin pode criar/listar 🟢
**RF:** POST /api/v1/admin/pbxs, GET /api/v1/admin/pbxs
**Origem:** `src/api/routers/pbxs.py`
