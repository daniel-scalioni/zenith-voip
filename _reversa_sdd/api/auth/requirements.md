# Autenticação (api/auth)

**Responsabilidades:** JWT auth + RBAC (agent/tenant_admin)
**Regras:** Apenas tenant_admin gerencia PBXs 🟢
**RF:** generate_token, verify_token, require_admin_role
**Origem:** `src/api/auth.py`
