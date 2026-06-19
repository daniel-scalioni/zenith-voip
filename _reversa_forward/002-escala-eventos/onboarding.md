# Onboarding: Alta Escala e Teste de Isolamento Multitenant

> Identificador: `002-escala-eventos`
> Data: `2026-05-21`

Este guia fornece os passos práticos executáveis no container de desenvolvimento para que desenvolvedores e analistas possam testar e validar o isolamento físico multi-tenant e o rastreamento dinâmico de ramais localmente.

---

## 1. Configurando o Ambiente Local

No container de desenvolvimento Ubuntu, certifique-se de que a infraestrutura local está ativa:

```bash
# 1. Certifique-se de que os containers básicos estão de pé
docker compose ps

# 2. Executar a migração Alembic inicial no schema padrão 'public'
docker compose run --rm fastapi-1 alembic upgrade head

# 3. Executar migração nos schemas tenant (após criar tenants)
SCHEMA_NAME=tenant_akom docker compose run --rm fastapi-1 alembic upgrade head
```

---

## 2. Simulando Criação de Inquilino (Multi-Schema)

Para criar um novo inquilino e provisionar seu respectivo schema isolado dinamicamente:

```bash
# Provisionar schema e tabelas via função utilitária
docker compose exec fastapi-1 python -c "
import asyncio
from src.database.database import create_tenant_schema

asyncio.run(create_tenant_schema('tenant_akom'))
print('Schema tenant_akom criado com todas as tabelas de negócio!')
"

# Opção 2: Usando o endpoint REST admin (requer JWT de tenant_admin)
curl -X POST "http://localhost:8000/api/v1/admin/tenants" \
  -H "Authorization: Bearer <ADMIN_JWT>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Akom", "schema_name": "tenant_akom"}'
```

---

## 3. Gerenciando PBXs do Inquilino

```bash
# Listar PBXs do tenant autenticado
curl -X GET "http://localhost:8000/api/v1/admin/pbxs" \
  -H "Authorization: Bearer <ADMIN_JWT>"

# Cadastrar novo PBX
curl -X POST "http://localhost:8000/api/v1/admin/pbxs" \
  -H "Authorization: Bearer <ADMIN_JWT>" \
  -H "Content-Type: application/json" \
  -d '{"name": "PABX-Matriz-SP", "host": "200.120.45.10", "port": 5060}'

# Resposta esperada (201):
# {
#   "id": "771e8400-...",
#   "tenant_id": "99f38400-...",
#   "name": "PABX-Matriz-SP",
#   "host": "200.120.45.10",
#   "port": 5060,
#   "created_at": "2026-05-21T18:00:00Z"
# }
```

---

## 4. Testando o Mapeamento SIP + IP no Redis Cache

Para validar o algoritmo de IP Matching que associa o atendente ao seu ramal SIP de forma automática:

```bash
# 1. Simular a interceptação SIP de um pacote REGISTER gravando dados no Redis
docker compose exec redis redis-cli SETEX zenith:sip:ip_to_extension:172.20.0.1 3600 "4001"
docker compose exec redis redis-cli SETEX zenith:sip:extension_to_ip:4001 3600 "172.20.0.1"

# 2. Validar que as chaves estão gravadas corretamente
docker compose exec redis redis-cli GET zenith:sip:ip_to_extension:172.20.0.1
docker compose exec redis redis-clI GET zenith:sip:extension_to_ip:4001
```

---

## 5. Testando Isolamento de Dados entre Schemas

```bash
# Inserir dados no schema tenant_akom
docker compose exec fastapi-1 python -c "
import asyncio
from sqlalchemy import text
from src.database.database import engine

async def test():
    async with engine.connect() as conn:
        await conn.execute(text('SET search_path TO tenant_akom'))
        await conn.execute(text(
            \"INSERT INTO calls (id, call_id, direction, status) VALUES (gen_random_uuid(), 'call-akom-001', 'inbound', 'in_progress')\"
        ))
        await conn.commit()

        await conn.execute(text('SET search_path TO tenant_outro'))
        result = await conn.execute(text('SELECT COUNT(*) FROM calls'))
        count = result.scalar()
        print(f'Chamadas no tenant_outro: {count} (deve ser 0)')

        await conn.execute(text('SET search_path TO tenant_akom'))
        result = await conn.execute(text('SELECT COUNT(*) FROM calls'))
        count = result.scalar()
        print(f'Chamadas no tenant_akom: {count} (deve ser 1)')

asyncio.run(test())
"
```

---

## 6. Simulando a Conexão WebSocket do Widget

Para testar o cruzamento de sessão via WebSocket conectando-se a partir do mesmo IP (`172.20.0.1`):

```bash
# 1. Simular mapeamento SIP no Redis (se não tiver o FreeSWITCH rodando)
docker compose exec redis redis-cli SETEX zenith:sip:ip_to_extension:172.20.0.1 3600 "4001"

# 2. Conectar via WebSocket (usando wscat ou similar)
wscat -c "ws://localhost:8000/api/v1/widget/ws?token=<JWT>" \
  -H "X-Forwarded-For: 172.20.0.1"

# Resposta esperada (session_linked):
# {"event": "session_linked", "data": {"agent_uuid": "...", "ramal_sip": "4001", "strategy": "automatic_ip_matching"}}

# 3. Testar manual linkage request (enviar do client WS):
# {"event": "manual_linkage_request", "data": {"agent_uuid": "atend-123"}}
```

---

## 7. Testando Fallback Manual com Código SIP `*88`

Se o casamento de IP falhar devido a NAT compartilhado de internet de saída:

```bash
# 1. Simular o recebimento de chamada *88 no ESL
docker compose exec redis redis-cli PUBLISH zenith:events \
  '{"Event-Name": "CHANNEL_CREATE", "Caller-Destination-Number": "*88", "Caller-Caller-ID-Number": "4001", "Caller-Network-Addr": "172.20.0.1"}'

# 2. Verificar que o evento de manual_linkage foi disparado
docker compose exec redis redis-cli KEYS "zenith:ws:agent_session:*"
```

---

## 8. Validando Métricas Prometheus

```bash
# Verificar métricas customizadas
curl http://localhost:8000/metrics | grep -E "tenant_schemas|redis_stream|sip_mappings|websocket_connections|db_pool"
```

---

## 9. Resetando o Ambiente de Teste

```bash
# Limpar dados de teste do Redis
docker compose exec redis redis-cli FLUSHDB

# Dropar schemas de teste
docker compose exec postgres psql -U zenith -c "DROP SCHEMA IF EXISTS tenant_akom CASCADE"
docker compose exec postgres psql -U zenith -c "DROP SCHEMA IF EXISTS tenant_outro CASCADE"
```
