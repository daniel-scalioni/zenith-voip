---
spec:
  component: trunk-registry
  layer: database
  status: active
  version: 1.3.0
  language: python
  patterns: [repository]
  inputs: [{name: trunk_configuration, type: validated_command, from: trunk-admin}]
  outputs: [{name: persisted_trunk, type: ATATrunk, to: trunk-registration}]
  dependencies: [{component: tenants-pbxs, layer: database}]
  events_produced: []
  updated_at: 2026-08-18
---

# Registro Persistente de Troncos

## Visão Geral

Esta unit mantém condomínios e troncos ATA no schema público, preserva a hierarquia tenant/PBX e
protege credenciais SIP. O registry é a fonte de verdade depois da importação operacional. 🟢

## Responsabilidades

- Persistir `Condominium` e `ATATrunk` com constraints equivalentes às regras de serviço. 🟢
- Cifrar, decifrar e rotacionar senha via MultiFernet sem expor plaintext. 🟢
- Traduzir violações do banco após rollback para erros estáveis de domínio. 🟢

## Regras de Negócio

- Condomínio e tronco devem pertencer ao mesmo tenant/PBX. 🟢
- `(sip_profile, auth_username)` é globalmente único; prefixo não nulo é único por tenant. 🟢
- Profile aceito é `internal` ou `internal-7060`; transporte é UDP. 🟢
- Mudança de identidade/senha reinicia o estado operacional em `unknown` e limpa, atomicamente,
  `last_registered_at` e `last_unregistered_at`. 🟢
- Tenant/PBX/condomínio desabilitado impede o lookup operacional. 🟢
- Atualização de `condominium_id` revalida o mesmo tenant e PBX antes da escrita. 🟢
- Atualização de profile/username rejeita colisão no registry e no diretório legado. 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|---|---|---|---|
| RF-01 | Persistir condomínios com unicidade por tenant/PBX/nome e external_id opcional | Must | duplicidade é rejeitada deterministicamente 🟢 |
| RF-02 | Persistir troncos com FKs e coerência transitiva | Must | referências cross-tenant/cross-PBX falham 🟢 |
| RF-03 | Aceitar prefixo nulo ou 1–32 dígitos | Must | múltiplos nulos são válidos; duplicado não nulo no tenant falha 🟢 |
| RF-04 | Proteger senha por MultiFernet e permitir rotação | Must | token antigo é lido e rotacionado para a chave primária 🟢 |
| RF-05 | Traduzir corrida de constraint sem deixar sessão inválida | Must | commit falha, rollback ocorre e erro de domínio é emitido 🟢 |
| RF-06 | Aplicar migration pública aditiva após baseline | Must | upgrade vazio e com baseline existente concluem sem schema tenant novo 🟢 |
| RF-07 | Invalidar evidência temporal junto com mudança de identidade ou senha | Must | estado `unknown` nunca conserva timestamps de registro/desregistro anteriores 🟢 |
| RF-08 | Preservar isolamento ao mover um tronco entre condomínios | Must | condomínio de outro tenant/PBX é rejeitado antes do Repository update 🟢 |
| RF-09 | Preservar exclusividade de identidade em alterações | Must | identidade já existente no banco ou XML legado é rejeitada antes da escrita 🟢 |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|---|---|---|---|
| Segurança | plaintext existe apenas na fronteira de entrada/diretório | `src/services/trunk_credentials.py` | 🟢 |
| Integridade | checks/FKs/índices parciais reforçam invariantes | `src/database/models.py`; `alembic/versions/002_ata_trunks.py` | 🟢 |
| Isolamento | schema público guarda registry; chamadas continuam schema-per-tenant | `src/database/database.py` | 🟢 |
| Recuperação | Repository executa rollback em toda falha de commit | `src/services/base.py` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado dois tenants diferentes
Quando ambos cadastram o mesmo prefixo válido
Então ambos os troncos são aceitos

Dado dois troncos no mesmo profile com o mesmo auth_username
Quando o segundo é persistido
Então a operação faz rollback e retorna duplicate_auth_identity

Dado uma cifra produzida por uma chave anterior configurada
Quando ela é rotacionada
Então a senha permanece igual e o token passa a usar a chave primária

Dado um banco somente com 001_public_baseline
Quando 002_ata_trunks é aplicado
Então condominiums e ata_trunks são criadas sem alterar schemas de tenant
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|---|---|---|
| FKs, unicidade e cifra | Must | Autenticação e isolamento dependem dessas invariantes 🟢 |
| Rotação de chave | Should | Há leitura por chave antiga, mas rotação reduz dívida operacional 🟢 |
| Prefixo | Could | Metadado opcional, não participa da autenticação/roteamento 🟢 |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---|---|---|
| `src/database/models.py` | `Condominium`, `ATATrunk` | 🟢 |
| `alembic/versions/002_ata_trunks.py` | `upgrade`, `downgrade` | 🟢 |
| `src/services/trunks.py` | `CondominiumService`, `TrunkService` | 🟢 |
| `src/services/trunk_credentials.py` | `TrunkCredentialCipher` | 🟢 |
| `src/services/base.py` | `Repository` | 🟢 |
