# Interface HTTP: Administração de condomínios e troncos

> Prefixo: `/api/v1/admin`
> Autenticação: Bearer JWT com papel `tenant_admin`
> Escopo: `tenant_id` vem exclusivamente do token; nunca do body/query.

## Condomínios

### `POST /condominiums`

Request JSON:

```json
{"pbx_id":"uuid","name":"Condominio Exemplo","external_id":"vital-123","enabled":true}
```

Resposta `201`: `id`, `tenant_id`, `pbx_id`, `name`, `external_id`, `enabled`, timestamps.

### `GET /condominiums?pbx_id=<uuid>`

Resposta `200`: lista apenas itens do tenant autenticado; `pbx_id` é filtro opcional.

### `PATCH /condominiums/{id}`

Campos alteráveis: `name`, `external_id`, `enabled`. Mudança de tenant/PBX não é aceita.

## Troncos ATA

### `POST /trunks`

Request JSON:

```json
{
  "pbx_id":"uuid",
  "condominium_id":"uuid",
  "prefix":"1140",
  "auth_username":"ata-1140",
  "password":"segredo-somente-na-entrada",
  "sip_profile":"internal-7060",
  "transport":"udp",
  "enabled":false
}
```

Resposta `201` omite `password` e `encrypted_password`.

### `GET /trunks`

Filtros opcionais: `pbx_id`, `condominium_id`, `enabled`, `registration_status`, `sip_profile`.

Cada item contém:

```json
{
  "id":"uuid",
  "tenant_id":"uuid",
  "pbx_id":"uuid",
  "condominium_id":"uuid",
  "prefix":"1140",
  "auth_username_masked":"***1140",
  "sip_profile":"internal-7060",
  "transport":"udp",
  "enabled":true,
  "registration_status":"registered",
  "active_calls":1,
  "in_use":true,
  "last_registered_at":"2026-08-01T21:00:00Z",
  "last_unregistered_at":null,
  "last_error_code":null,
  "last_error_at":null
}
```

### `PATCH /trunks/{id}`

Campos alteráveis: `condominium_id`, `prefix`, `auth_username`, `password`, `sip_profile`, `enabled`. Senha ausente significa preservar; senha vazia é rejeitada. Mudanças de identidade invalidam caches e forçam `registration_status=unknown` até reconciliação.

### `POST /trunks/import?pbx_id=<uuid>&dry_run=true|false`

- Content-Type: `multipart/form-data`, campo `file`.
- Limite: 5 MiB e 10.000 linhas.
- `dry_run=true` não grava nem cifra valores.
- Importação real é idempotente por condomínio e `(tenant_id,prefix)`.

Resposta:

```json
{
  "dry_run":true,
  "rows":10,
  "created":8,
  "updated":1,
  "unchanged":0,
  "rejected":1,
  "errors":[{"line":7,"code":"duplicate_auth_identity","field":"auth_username"}]
}
```

O objeto de erro nunca inclui valor de senha ou linha CSV bruta.

## Erros comuns

| HTTP | Código | Condição |
|------|--------|----------|
| 400 | `invalid_payload` | campo, profile ou CSV inválido |
| 401 | `unauthorized` | token ausente/inválido |
| 403 | `forbidden` | papel insuficiente |
| 404 | `pbx_not_found` / `condominium_not_found` / `trunk_not_found` | ausente dentro do tenant; recurso de outro tenant também retorna 404 |
| 409 | `duplicate_prefix` / `duplicate_auth_identity` | constraint de unicidade |
| 413 | `csv_too_large` | limite excedido |
| 422 | `csv_schema_invalid` | cabeçalho obrigatório ausente |
| 503 | `credential_key_unavailable` | chave de cifra ausente/inválida |

## Idempotência, timeout e segurança

- POST unitário duplicado retorna 409; importação repetida atualiza/ignora conforme chave natural.
- Timeout alvo de operações administrativas: 10 s; importação acima disso deve ser cancelável sem commit parcial.
- Nenhuma resposta inclui senha, cifra, chave Fernet ou XML do diretório.
- Recursos de outro tenant não podem ser diferenciados de inexistentes.
