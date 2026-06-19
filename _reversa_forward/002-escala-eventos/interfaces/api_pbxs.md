# Interface: PBX Management API

> Identificador: `002-escala-eventos`
> Data: `2026-05-21`
> Tipo: HTTP REST API

Contrato para o gerenciamento administrativo de múltiplos PBXs IP vinculados a um inquilino (`tenant_id`).

---

## 1. Cadastro de Novo PBX

Cria um registro associando as configurações de rede de um PABX original ao inquilino autenticado.

- **Endpoint**: `POST /api/v1/admin/pbxs`
- **Headers**:
  - `Content-Type: application/json`
  - `Authorization: Bearer <JWT_TOKEN>`
- **Autenticação e Permissão**: Exige role de `tenant_admin` no payload do JWT.

### Corpo da Requisição (Request Payload)

```json
{
  "name": "PABX-Matriz-SP",
  "host": "200.120.45.10",
  "port": 5060
}
```

### Corpo da Resposta (Response - 201 Created)

```json
{
  "id": "771e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "99f38400-e29b-41d4-a716-446655441111",
  "name": "PABX-Matriz-SP",
  "host": "200.120.45.10",
  "port": 5060,
  "created_at": "2026-05-21T18:00:00Z"
}
```

### Respostas de Erro (Errors)

- **401 Unauthorized**: Token expirado ou inválido.
- **403 Forbidden**: Atendente comum tentando gerenciar PABX de filiais.
- **422 Unprocessable Entity**: IP ou Host inválido.

```json
{
  "error": "Forbidden",
  "message": "Apenas administradores de inquilino podem cadastrar novos PBXs."
}
```

---

## 2. Listagem de PBXs do Tenant

Retorna todos os PABXs ativos cadastrados para a empresa do usuário autenticado.

- **Endpoint**: `GET /api/v1/admin/pbxs`
- **Headers**:
  - `Authorization: Bearer <JWT_TOKEN>`

### Corpo da Resposta (Response - 200 OK)

```json
[
  {
    "id": "771e8400-e29b-41d4-a716-446655440000",
    "name": "PABX-Matriz-SP",
    "host": "200.120.45.10",
    "port": 5060,
    "created_at": "2026-05-21T18:00:00Z"
  },
  {
    "id": "882e8400-e29b-41d4-a716-446655442222",
    "name": "PABX-Filial-RJ",
    "host": "189.44.120.15",
    "port": 5061,
    "created_at": "2026-05-21T18:02:15Z"
  }
]
```
