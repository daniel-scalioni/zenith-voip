---
spec:
  component: trunk-admin
  layer: api
  status: active
  version: 1.2.0
  language: python
  patterns: [repository, dependency-injection]
  inputs: [{name: admin_request, type: HTTP, from: tenant-admin}, {name: directory_lookup, type: HTTPForm, from: freeswitch}]
  outputs: [{name: trunk_view, type: JSON, to: tenant-admin}, {name: directory_xml, type: XML, to: freeswitch}]
  dependencies: [{component: trunk-registry, layer: database}, {component: auth, layer: api}, {component: trunk-registration, layer: telephony}]
  events_produced: []
  updated_at: 2026-08-17
---

# Administração e Diretório de Troncos — Tarefas

## Pré-requisitos

- [ ] Registry público e migration de troncos disponíveis. 🟢
- [ ] Chaves Fernet e credencial Basic fornecidas fora do repositório. 🟢
- [ ] Diretório legado privado montado somente leitura. 🟢

## Tarefas

- [ ] T-01, implementar DTOs e rotas tenant-scoped para condomínios/troncos.
  - Origem no legado: `src/api/routers/trunks.py`
  - Critério de pronto: JWT define tenant, outro tenant retorna 404 e resposta omite segredo.
  - Confiança: 🟢
- [ ] T-02, implementar importação CSV com limites, dry-run e erros sanitizados.
  - Origem no legado: `src/services/trunk_import.py::parse_trunk_csv`
  - Critério de pronto: 5 MiB/10.000 linhas são respeitados e senha não aparece no resultado.
  - Confiança: 🟢
- [ ] T-03, implementar importação JSON único/lote com pré-voo tudo-ou-nada.
  - Origem no legado: `src/services/trunk_import.py::import_trunk_json_batch`
  - Critério de pronto: PJSIP/7060 válido importa; uma linha inválida impede toda persistência.
  - Confiança: 🟢
- [ ] T-04, implementar provider legado seguro e cacheado por mtime.
  - Origem no legado: `src/services/legacy_directory.py`
  - Critério de pronto: fragmentos são aceitos, DTD/entidades e IDs duplicados falham fechados.
  - Confiança: 🟢
- [ ] T-05, implementar callback XML Curl com Basic, allowlist e resposta limitada.
  - Origem no legado: `src/api/freeswitch_directory.py`
  - Critério de pronto: DB/legado exclusivos resolvem; ambiguidade, entidade desabilitada ou erro de cifra retornam not-found.
  - Confiança: 🟢
- [ ] T-06, renderizar a configuração privada atomicamente.
  - Origem no legado: `scripts/render_freeswitch_secrets.py`
  - Critério de pronto: arquivo final tem modo 0600 e nenhuma credencial é impressa/versionada.
  - Confiança: 🟢
- [ ] T-07, expor PATCH tenant-scoped de condomínio e tronco. 🟢
- [ ] T-08, preencher `active_calls`/`in_use` via `TrunkStateService` em todas as views. 🟢

## Tarefas de Teste

- [ ] TT-01, provar RBAC, 404 horizontal e DTO sem segredo. 🟢
- [ ] TT-02, provar dry-run e rollback lógico de lote inválido. 🟢
- [ ] TT-03, provar XML escaping, limite, no-store e colisão DB/legado. 🟢
- [ ] TT-04, usar senha-canário e verificar responses, exceptions, repr e logs. 🟢
- [ ] TT-05, provar PATCH/404 horizontal e cardinalidades Redis não nulas em POST/PATCH/GET. 🟢

## Ordem Sugerida

1. Registry/cipher e provider legado antes dos adapters HTTP. 🟢
2. Rotas administrativas e importadores antes do callback de diretório. 🟢
3. Renderer/configuração somente após o contrato Basic estar estável. 🟢

## Lacunas Pendentes (🔴)

Nenhuma lacuna comportamental confirmada nesta unit. 🟢
