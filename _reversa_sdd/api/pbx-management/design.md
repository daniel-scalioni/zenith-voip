# Gerenciamento de PBXs, Design

**Interface:** POST `/api/v1/admin/pbxs` (PBXCreate → PBXResponse, 201), GET `/api/v1/admin/pbxs` (List[PBXResponse], 200)
**DTOs:** PBXCreate(name, host, port), PBXResponse(id, tenant_id, name, host, port, created_at)
**Dependências:** auth (require_admin_role), database (get_db)
**Origem:** `src/api/routers/pbxs.py:15-72` 🟢
