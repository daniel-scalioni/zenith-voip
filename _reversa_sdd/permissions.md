# Matriz de Permissões — zenith-voip

> Gerado pelo Detective — 2026-06-19
> Confiança: 🟢 CONFIRMADO

## Papéis

| Papel | Identificador | Descrição |
|-------|---------------|-----------|
| Agente | `agent` | Operador de call center, acessa o widget e participa de chamadas |
| Admin do Tenant | `tenant_admin` | Administrador do inquilino, gerencia PBXs e configurações |

**Nota:** O sistema não possui um papel de super-admin (cross-tenant). A gestão de tenants é feita externamente (via migrations ou admin direto no DB).

## Matriz de Permissões

| Funcionalidade | agent | tenant_admin | Origem |
|----------------|-------|-------------|--------|
| Criar PBX | ❌ | ✅ | `auth.py:35-40` |
| Listar PBXs | ❌ | ✅ | `auth.py:35-40` |
| Gerar token JWT | ✅ (role=agent) | ✅ (role=tenant_admin) | `auth.py:10-18` |
| Acessar WebSocket | ✅ | ✅ | `websockets.py:3` |
| Receber transcrições | ✅ | ✅ | `websockets.py:112-118` |
| Receber alertas | ✅ | ✅ | `websockets.py:99-110` |
| Linkage manual (*88) | ✅ | ✅ | `websockets.py:78-97` |
| Acessar /health e /ready | ✅ | ✅ | `main.py:26-33` |
| Acessar /metrics | ✅ | ✅ | `telemetry.py:58-60` |

## Mecanismo de Autenticação

1. Cliente obtém token JWT via endpoint externo (não implementado no código — token é gerado programaticamente por `create_access_token()`)
2. Token contém: `sub`, `tenant_id`, `role`, `exp`, `iat`
3. Endpoints protegidos usam `verify_token()` → decodifica JWT
4. `require_admin_role()` → verifica `role == "tenant_admin"`, senão 403

## Escopo de Dados

- Cada tenant vê **apenas seus próprios dados** (filtrando por `tenant_id` no payload JWT)
- Isolamento físico via schema PostgreSQL separado por tenant (multitenancy)
- O escopo cross-tenant não é suportado pela API atual
