# Autenticação, Design

**Interface:** `create_access_token(subject, tenant_id, role, expires_delta) → str`, `verify_token(credentials) → dict`, `require_admin_role(payload) → dict`
**Fluxo:** JWT HS256 com claims sub, tenant_id, role, exp, iat → verify decodifica → admin role verifica role == "tenant_admin"
**Origem:** `src/api/auth.py:10-40` 🟢
