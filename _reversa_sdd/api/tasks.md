# API, Tarefas de Implementação

> Gerado pelo Writer — 2026-06-19
> Escala: 🟢 CONFIRMADO | 🟡 INFERIDO | 🔴 LACUNA

## Pré-requisitos

- [ ] Dependências da unit listadas em `design.md` estão disponíveis (database, events, extraction, telephony)
- [ ] Redis disponível para cache de sessões e mapeamento SIP
- [ ] JWT_SECRET configurado em ambiente
- [ ] OpenTelemetry SDK configurado para tracing

## Tarefas

- [ ] T-01, Implementar módulo de autenticação JWT
  - Origem no legado: `src/api/auth.py:10-40`
  - Critério de pronto: `create_access_token()` gera token HS256 válido; `verify_token()` decodifica corretamente; `require_admin_role()` retorna 403 para role != tenant_admin
  - Confiança: 🟢

- [ ] T-02, Implementar rate limiter in-memory
  - Origem no legado: `src/api/rate_limit.py:5-12`
  - Critério de pronto: 101ª requisição do mesmo IP em 60s retorna 429; contador reseta após 60s
  - Confiança: 🟢

- [ ] T-03, Implementar CRUD de PBXs
  - Origem no legado: `src/api/routers/pbxs.py:15-72`
  - Critério de pronto: POST /api/v1/admin/pbxs cria PBX com tenant_id do JWT; GET lista PBXs do tenant; validação de unicidade de nome por tenant
  - Confiança: 🟢

- [ ] T-04, Implementar WebSocket Agent Assist
  - Origem no legado: `src/api/websockets.py:33-118`
  - Critério de pronto: conexão em `/ws/{call_id}` aceita; auto-link por IP via Redis; broadcast de transcript/alert/insight para todas as conexões do call_id
  - Confiança: 🟢

- [ ] T-05, Implementar auto-link SIP
  - Origem no legado: `src/api/websockets.py:40-56`
  - Critério de pronto: ao conectar WS, busca `zenith:sip:ip_to_extension:{ip}` no Redis; se encontrado, vincula sessão; se não, enfileira linkage manual
  - Confiança: 🟢

- [ ] T-06, Implementar linkage manual via *88
  - Origem no legado: `src/api/websockets.py:78-97`
  - Critério de pronto: recebe mensagem *88, cria sessão "awaiting_linkage" no Redis com TTL 120s
  - Confiança: 🟢

- [ ] T-07, Implementar webhook dispatcher
  - Origem no legado: `src/api/webhooks.py:15-36`
  - Critério de pronto: `dispatch_post_call()` monta payload e envia HTTP POST para URL configurada
  - Confiança: 🟢

- [ ] T-08, Implementar health check endpoints
  - Origem no legado: `src/main.py:26-33`
  - Critério de pronto: `/health` retorna 200; `/ready` retorna 200 quando dependências estão disponíveis
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, Testar happy path: admin autenticado cria e lista PBXs
- [ ] TT-02, Testar fluxo de erro: agent tenta criar PBX (esperado 403)
- [ ] TT-03, Testar rate limit: 101 requisições em 60s (esperado 429)
- [ ] TT-04, Testar JWT inválido/expirado (esperado 401)
- [ ] TT-05, Testar WebSocket connect + auto-link SIP
- [ ] TT-06, Testar linkage manual via *88
- [ ] TT-07, Testar broadcast de transcript para múltiplas conexões

## Ordem Sugerida

1. T-01 (auth) primeiro — todas as outras dependem de autenticação
2. T-08 (health) em paralelo com T-01
3. T-02 (rate limit) — middleware independente
4. T-03 (PBX CRUD) — depende de T-01
5. T-04 (WebSocket) — core do agent assist
6. T-05 e T-06 (auto-link e manual) — dependem de T-04
7. T-07 (webhooks) — menor prioridade

## Lacunas Pendentes (🔴)

- Rate limit in-memory é volátil: reinicialização zera contadores. Considere migrar para Redis se necessário
- Webhook dispatcher sem confirmação de entrega — fire-and-forget
