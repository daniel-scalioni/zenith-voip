# Data Delta: Modelagem Multitenant Física e Gerenciamento de PBXs

> Identificador: `002-escala-eventos`
> Data: `2026-05-21`

Este documento apresenta a modelagem de dados conceitual nova e as alterações estruturais necessárias no PostgreSQL para suportar isolamento físico por inquilino (Database-per-Tenant) e associação dinâmica de ramais e múltiplos PBXs.

---

## 1. Mapeamento de Schemas no PostgreSQL

Adotaremos a infraestrutura de **Múltiplos Schemas** sob a mesma instância PostgreSQL.
- O schema `public` conterá apenas as tabelas compartilhadas e administrativas (dados agregados de faturamento, cadastro básico de inquilinos e logs de segurança global).
- Cada inquilino possuirá um schema dedicado nomeado `tenant_<tenant_uuid>`, contendo todas as tabelas de negócio e inteligência (`calls`, `transcripts`, `call_insights` e `stt_metrics`).

---

## 2. Estrutura de Tabelas Novas (Shared Schema: `public`)

Estas tabelas residem apenas no namespace `public` global e gerenciam os metadados dos clientes.

### `tenants`
Armazena a relação global de clientes corporativos Zenith.

```sql
CREATE TABLE public.tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(128) NOT NULL,
    schema_name VARCHAR(64) UNIQUE NOT NULL, -- Ex: 'tenant_akom_99f3'
    status VARCHAR(32) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### `pbxs`
Armazena as configurações de múltiplos PBXs IP pertencentes a cada Inquilino.

```sql
CREATE TABLE public.pbxs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    name VARCHAR(128) NOT NULL,
    host VARCHAR(128) NOT NULL,
    port INTEGER DEFAULT 5060,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_pbxs_tenant ON public.pbxs(tenant_id);
```

---

## 3. Alteração nas Tabelas de Negócio (Tenant Schemas: `tenant_*`)

Tabelas legadas mapeadas em `src/database/models.py` que serão isoladas nos schemas dedicados de cada cliente.

### Tabela `calls`
Sofre alteração estrutural para vincular cada chamada ao PBX de origem, além de manter seus campos de telefonia originais.

```diff
CREATE TABLE tenant_<tenant_uuid>.calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id VARCHAR(128) UNIQUE NOT NULL,
    agent_uuid VARCHAR(128),
    customer_uuid VARCHAR(128),
+   pbx_id UUID, -- Relacionamento lógico com public.pbxs(id)
+   agent_sip_extension VARCHAR(64), -- Ramal ativo do atendente detectado dinamicamente
    direction VARCHAR(32) NOT NULL,
    status VARCHAR(32) DEFAULT 'in_progress',
-   tenant_id VARCHAR(64), -- Removido da tabela interna (redundante pois vive no schema dedicado)
    caller_number VARCHAR(32),
    callee_number VARCHAR(32),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    duration_seconds FLOAT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
+ CREATE INDEX idx_calls_pbx ON tenant_<tenant_uuid>.calls(pbx_id);
```

As tabelas de suporte `transcripts`, `call_insights` e `stt_metrics` mantêm sua modelagem original idêntica à de `src/database/models.py`, mas passam a ser criadas dinamicamente dentro do schema de cada inquilino recém-cadastrado.

---

## 4. Estrutura em Redis para Cache de Ramais SIP

Para mapear de forma dinâmica e rápida os ramais detectados pelo proxy `SwitchPBX` (FreeSWITCH) via ESL e cruzar com conexões WebSocket do Widget:

| Chave Redis | Tipo | Valor | Exemplo | TTL | Justificativa |
|---|---|---|---|---|---|
| `zenith:sip:ip_to_extension:<ip>` | String | `ramal_sip` | `4001` | 3600s | Mapeia o IP de origem do softphone ao ramal ativo detectado via SIP `REGISTER` / `INVITE`. |
| `zenith:sip:extension_to_pbx:<ramal>` | String | `pbx_uuid` | `550e8400-e29b-...` | 3600s | Correlaciona o ramal ao PBX respectivo de onde a ligação foi interceptada. |
| `zenith:ws:agent_session:<agent_uuid>` | Hash | `{ramal, pbx, ip}` | `{ramal: 4001, pbx: ..., ip: ...}` | 30s (ping) | Rastreia a sessão WebSocket ativa do widget do agente para despachar alertas. |
