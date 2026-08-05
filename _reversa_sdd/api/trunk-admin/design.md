---
spec:
  component: trunk-admin
  layer: api
  status: active
  version: 1.1.0
  language: python
  patterns: [repository, dependency-injection]
  inputs: [{name: admin_request, type: HTTP, from: tenant-admin}, {name: directory_lookup, type: HTTPForm, from: freeswitch}]
  outputs: [{name: trunk_view, type: JSON, to: tenant-admin}, {name: directory_xml, type: XML, to: freeswitch}]
  dependencies: [{component: trunk-registry, layer: database}, {component: auth, layer: api}, {component: trunk-registration, layer: telephony}]
  events_produced: []
  updated_at: 2026-08-04
---

# Trunk Admin — Design

## Responsabilidade

Expor operações administrativas tenant-scoped para condomínios/troncos, cadastro individual, importação CSV opcional e um callback interno de diretório para o FreeSWITCH. Routers permanecem finos e delegam regras a serviços.

## API administrativa

Prefixo `/api/v1/admin`, Bearer JWT e papel obrigatório `tenant_admin`.

- `POST /condominiums`
- `GET /condominiums`
- `PATCH /condominiums/{id}`
- `POST /trunks`
- `GET /trunks`
- `PATCH /trunks/{id}`
- `POST /trunks/import?pbx_id=<uuid>&dry_run=<bool>`

`tenant_id` vem somente do token. Recurso de outro tenant retorna 404 indistinguível de ausente. A primeira versão não oferece DELETE físico.

## Importação CSV

- Multipart, máximo 5 MiB e 10.000 linhas.
- Formato canônico definido em `interfaces/trunk-csv.md`.
- Tenant vem do JWT e PBX do parâmetro autenticado, nunca do arquivo.
- `dry_run` valida sem cifrar/persistir.
- Cadastro/importação é idempotente por `(sip_profile, auth_username)` quando o prefixo estiver ausente; prefixo não nulo continua único no tenant.
- Erro estrutural aborta tudo; erros de linha são reportados sem linha bruta ou senha.
- Default `enabled=false`.

## Configuração individual VitalPBX

- Quando não houver exportação em lote, o adaptador privado segue `interfaces/trunk-json.md`.
- Condomínio é informado explicitamente; descrição, login e número discado não são inferidos como prefixo.
- PJSIP/7060 mapeia para `internal-7060`; identidades e segredos locais/remotos divergentes falham fechado.
- Dry-run não cifra nem persiste; primeiro cadastro real sempre usa `enabled=false`.

## Respostas

- Nunca incluem `password`, `encrypted_password`, chave Fernet ou XML bruto.
- Username é mascarado nas listagens operacionais.
- Status inclui `enabled`, `registration_status`, `active_calls`, `in_use`, timestamps e código de erro sanitizado.
- `active_calls` vem de `SCARD`; `in_use` é derivado.

## Callback interno

Endpoint `POST /internal/freeswitch/directory`:

- aceita somente HTTP Basic dedicado usando comparação em tempo constante;
- rota é bloqueada pelo proxy público;
- aceita apenas `section=directory` e uma allowlist de campos;
- aceita o profile real enviado pelo FreeSWITCH 1.10.12 em `sip_profile`, preservando os aliases `sip_profile_name` e `variable_sofia_profile_name`; o campo canônico tem precedência;
- usa `sip_auth_username` como identidade canônica, com `user` apenas como alias; `key_value` representa o domínio e nunca é interpretado como username;
- resolve `(sip_profile, auth_username)` no banco e, se ausente, no provider legado;
- colisão entre fontes falha fechado;
- tronco/PBX/condomínio/tenant desabilitado retorna not-found;
- resposta XML usa escaping seguro, `application/xml` e `Cache-Control: no-store`;
- nunca loga request body ou response XML.

## Compatibilidade legada

`LegacyDirectoryProvider` lê o `extensions.xml` privado somente para preservar usuários existentes quando o binding exclusivo estiver ativo. Rejeita DTD/entidades, mantém cache por `mtime`, não altera o arquivo e não inventa IDs de tronco.

## Configuração privada XML Curl

- Repositório contém apenas `xml_curl.conf.xml.example` sem segredo.
- `scripts/render_freeswitch_secrets.py` lê `.env`, valida campos e grava o XML real atomicamente com modo 0600.
- `xml_curl.conf.xml` real é gitignored.
- Nenhum valor real aparece em diff, specs ou logs.

## Erros

- 400 payload inválido.
- 401 autenticação ausente/inválida.
- 403 papel insuficiente.
- 404 recurso ausente ou fora do tenant.
- 409 prefixo/identidade duplicada.
- 413 CSV grande.
- 422 schema CSV inválido.
- 503 chaves/serviço interno indisponíveis.

## Testes bloqueantes

- RBAC e isolamento horizontal.
- 404 opaco e 409 determinístico.
- dry-run/idempotência/rollback/limites CSV.
- senha-canário ausente de todas as saídas.
- Basic inválido, XML escaping, not-found, ambiguidade e no-store.
- provider legado equivalente e resistente a XML malicioso.
- renderer sem segredo versionado, atomicidade e modo 0600.

## Rastreabilidade

- `_reversa_forward/012-trunk-registration/interfaces/trunks-api.md`.
- `_reversa_forward/012-trunk-registration/interfaces/freeswitch-directory.md`.
- `_reversa_forward/012-trunk-registration/interfaces/trunk-csv.md`.
- Requirements RF-01, RF-02, RF-03, RF-04, RF-09, RF-12.
