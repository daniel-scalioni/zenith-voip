# Data Delta: Registro de troncos ATA

> Feature: `012-trunk-registration`
> Base: `_reversa_sdd/database/legacy-mapping.md#Modelos de Dados`

## Tabelas novas no schema `public`

### `condominiums`

| Campo | Tipo | Nulo | Regra |
|-------|------|------|-------|
| `id` | UUID | não | PK |
| `tenant_id` | UUID | não | FK `public.tenants(id)` CASCADE |
| `pbx_id` | UUID | não | FK `public.pbxs(id)` CASCADE; serviço valida que o PBX pertence ao mesmo tenant |
| `name` | varchar(128) | não | nome operacional |
| `external_id` | varchar(128) | sim | chave estável da origem VitalPBX |
| `enabled` | boolean | não | default true |
| `created_at` | timestamptz | não | default now |
| `updated_at` | timestamptz | não | default now/on update |

Constraints/índices:

- índice `(tenant_id, pbx_id)`;
- unique parcial/lógico `(tenant_id, pbx_id, external_id)` quando `external_id` estiver preenchido;
- unique `(tenant_id, pbx_id, name)` para idempotência do contrato canônico.

### `ata_trunks`

| Campo | Tipo | Nulo | Regra |
|-------|------|------|-------|
| `id` | UUID | não | PK |
| `tenant_id` | UUID | não | FK `public.tenants(id)` CASCADE |
| `pbx_id` | UUID | não | FK `public.pbxs(id)` CASCADE |
| `condominium_id` | UUID | não | FK `public.condominiums(id)` CASCADE |
| `prefix` | varchar(32) | sim | metadado opcional; unique por tenant quando preenchido |
| `auth_username` | varchar(128) | não | identidade digest; nunca mascarada de forma reversível em logs |
| `encrypted_password` | text | não | token MultiFernet; nunca exposto pela API |
| `sip_profile` | varchar(32) | não | `internal` ou `internal-7060` |
| `transport` | varchar(8) | não | default/único valor v1: `udp` |
| `enabled` | boolean | não | default false na importação, habilitação explícita |
| `registration_status` | varchar(16) | não | `unknown`, `registered`, `unregistered`; default `unknown` |
| `last_registered_at` | timestamptz | sim | evento Sofia confirmado |
| `last_unregistered_at` | timestamptz | sim | unregister/expire confirmado |
| `last_error_code` | varchar(64) | sim | código sanitizado, sem mensagem arbitrária do peer |
| `last_error_at` | timestamptz | sim | momento do erro |
| `created_at` | timestamptz | não | default now |
| `updated_at` | timestamptz | não | default now/on update |

Constraints/índices:

- unique parcial `(tenant_id, prefix)` onde `prefix IS NOT NULL`;
- unique incondicional `(sip_profile, auth_username)` para resolução não ambígua no domínio SIP atual;
- índice `(tenant_id, pbx_id, condominium_id)`;
- checks de `sip_profile`, `transport` e `registration_status`;
- serviço valida coerência transitiva tenant → PBX → condomínio antes de persistir.
- serviço consulta o provider legado e rejeita identidade que colida com usuário atual do mesmo profile; essa verificação externa complementa a constraint do banco.

## Estado efêmero no Redis

| Chave | Tipo | Conteúdo | TTL |
|-------|------|----------|-----|
| `zenith:trunk:active_calls:{trunk_id}` | set | UUIDs de canais ativos | renovado; expira após 24 h sem evento |
| `zenith:trunk:registration:{profile}:{username}` | string JSON | `trunk_id`, status e timestamp | duração do registro + margem |
| `zenith:trunk:lookup:{profile}:{username}` | string UUID | cache da resolução DB | 5 min; invalidado em alteração/importação |

`active_calls` é `SCARD` do conjunto e `in_use` é `active_calls > 0`; nenhum dos dois é coluna persistida.

## Migration

- Nova revisão `002_ata_trunks`, descendente de `001_public_baseline`.
- Upgrade apenas aditivo: duas tabelas, constraints e índices.
- Downgrade permitido somente em ambiente isolado e deve remover primeiro `ata_trunks`, depois `condominiums`.
- A migration não altera tabelas tenant-scoped nem o conteúdo de `calls`.
- Validação obrigatória: banco vazio, banco em head, segunda execução no-op e baseline com tenants/PBXs existentes.

## Proteção e rotação de segredo

- `TRUNK_CREDENTIAL_KEYS` contém uma ou mais chaves Fernet separadas por vírgula em configuração privada.
- Novas cifras usam a primeira chave; leitura tenta todas.
- Rotação regrava `encrypted_password` em lote sem mudar a senha SIP.
- Ausência/chave inválida impede criar/importar/servir credenciais, mas não derruba health geral da API nem chamadas existentes.
- Nenhuma fixture, migration, log ou documento contém credencial real.

## Dados removidos

Nenhum. O `extensions.xml` privado atual não será apagado automaticamente; deixa de ser autoridade apenas após o rollout aprovado do binding dinâmico.
