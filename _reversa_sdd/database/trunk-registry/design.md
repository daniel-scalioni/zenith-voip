---
spec:
  component: trunk-registry
  layer: database
  status: active
  version: 1.1.0
  language: python
  patterns: [repository]
  inputs: [{name: trunk_configuration, type: validated_command, from: trunk-admin}]
  outputs: [{name: persisted_trunk, type: ATATrunk, to: trunk-registration}]
  dependencies: [{component: tenants-pbxs, layer: database}]
  events_produced: []
  updated_at: 2026-08-04
---

# Trunk Registry — Design

## Responsabilidade

Persistir condomínios e troncos ATA no schema `public`, mantendo a hierarquia `Tenant → PBX → Condominium → ATATrunk`, o isolamento por tenant e a proteção das credenciais SIP.

## Modelo

### `Condominium`

- UUID como chave primária.
- `tenant_id` obrigatório, FK para `public.tenants` com CASCADE.
- `pbx_id` obrigatório, FK para `public.pbxs` com CASCADE.
- `name` obrigatório, até 128 caracteres.
- `external_id` opcional, até 128 caracteres.
- `enabled` booleano, default verdadeiro.
- timestamps UTC de criação e atualização.
- unicidade `(tenant_id, pbx_id, name)`.
- unicidade de `external_id` dentro de tenant/PBX quando preenchido.

### `ATATrunk`

- UUID como chave primária.
- `tenant_id`, `pbx_id` e `condominium_id` obrigatórios com FKs públicas.
- `prefix` opcional; quando preenchido, contém 1 a 32 dígitos e é único por tenant. Não participa de autenticação nem roteamento.
- `auth_username` de 1 a 128 caracteres.
- `encrypted_password` obrigatório; nunca retornado por repository/API.
- `sip_profile`: `internal` ou `internal-7060`.
- `transport`: somente `udp` nesta versão.
- `enabled` booleano; importações iniciam desabilitadas por padrão.
- `registration_status`: `unknown`, `registered` ou `unregistered`.
- timestamps opcionais de registro, desregistro e erro.
- `last_error_code` sanitizado, até 64 caracteres.
- unicidade incondicional `(sip_profile, auth_username)`.

## Invariantes de serviço

1. PBX precisa pertencer ao tenant informado.
2. Condomínio precisa pertencer ao mesmo tenant e PBX do tronco.
3. Prefixo não nulo igual pode existir em tenants diferentes, nunca no mesmo tenant; múltiplos troncos sem prefixo são válidos.
4. Identidade SIP não pode colidir com outro tronco nem com usuário do diretório legado no mesmo profile.
5. Desabilitar um tronco não libera sua identidade automaticamente.
6. Mudança de username, senha ou profile força `registration_status=unknown` e invalida caches.
7. Senha vazia é inválida; senha ausente em update preserva a cifra atual.

## Credenciais

- `TrunkCredentialCipher` usa `MultiFernet`.
- `TRUNK_CREDENTIAL_KEYS` é uma lista privada: a primeira chave cifra, todas podem decifrar.
- Erro de chave/token retorna apenas código sanitizado.
- A senha em claro existe somente durante importação/alteração e serialização do diretório.
- Rotação regrava a cifra sem mudar a senha SIP.

## Migration

- Revision: `002_ata_trunks`.
- Down revision: `001_public_baseline`.
- Upgrade aditivo no schema `public`.
- Ordem de criação: `condominiums`, depois `ata_trunks`.
- Downgrade apenas em ambiente isolado: `ata_trunks`, depois `condominiums`.
- Não alterar tabelas ou schemas tenant-scoped.

## Contrato Repository

- Routers e handlers não emitem SQL.
- Serviços reutilizam `Repository` para operações simples e queries SQLAlchemy encapsuladas para filtros/locks compostos.
- Toda falha de commit executa rollback e preserva o erro original no log sanitizado.

## Testes bloqueantes

- FKs e coerência transitiva.
- Unicidade por tenant/profile.
- tenants diferentes com mesmo prefixo.
- cifra, rotação, chave ausente e token corrompido.
- migration em banco vazio, com dados existentes e segunda aplicação.
- nenhum segredo em `repr`, response, log ou mensagem de constraint.

## Rastreabilidade

- `_reversa_forward/012-trunk-registration/requirements.md`: RN-01, RN-02, RN-03, RN-07, RN-09.
- `_reversa_forward/012-trunk-registration/data-delta.md`.
- `_reversa_forward/012-trunk-registration/roadmap.md`: D-01, D-05, D-06, D-07.
