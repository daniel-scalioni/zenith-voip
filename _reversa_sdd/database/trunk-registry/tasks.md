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
  updated_at: 2026-08-17
---

# Registro Persistente de Troncos — Tarefas

## Pré-requisitos

- [ ] Baseline pública com tenants e PBXs aplicada. 🟢
- [ ] Chaves MultiFernet disponibilizadas por configuração privada. 🟢

## Tarefas

- [ ] T-01, modelar `Condominium` com FKs, unicidades e habilitação.
  - Origem no legado: `src/database/models.py::Condominium`
  - Critério de pronto: nome/external_id duplicados no mesmo escopo são rejeitados.
  - Confiança: 🟢
- [ ] T-02, modelar `ATATrunk` com constraints de prefixo/profile/transporte/status.
  - Origem no legado: `src/database/models.py::ATATrunk`
  - Critério de pronto: somente valores contratuais persistem e múltiplos prefixos nulos são válidos.
  - Confiança: 🟢
- [ ] T-03, criar migration pública aditiva e reversão ordenada.
  - Origem no legado: `alembic/versions/002_ata_trunks.py`
  - Critério de pronto: upgrade cria condomínio antes de tronco e downgrade remove na ordem inversa.
  - Confiança: 🟢
- [ ] T-04, implementar cipher MultiFernet com códigos sanitizados.
  - Origem no legado: `src/services/trunk_credentials.py`
  - Critério de pronto: encrypt/decrypt/rotate funcionam e token/chave nunca aparecem em erro.
  - Confiança: 🟢
- [ ] T-05, implementar services tenant-scoped e validação de identidade legada.
  - Origem no legado: `src/services/trunks.py`
  - Critério de pronto: coerência transitiva, prefixo e colisões são validados antes da escrita.
  - Confiança: 🟢
- [ ] T-06, tornar Repository seguro após falha de commit.
  - Origem no legado: `src/services/base.py::Repository`
  - Critério de pronto: IntegrityError gera rollback e `IntegrityConstraintError`; outras falhas também fazem rollback.
  - Confiança: 🟢
- [ ] T-07, limpar timestamps operacionais ao invalidar identidade ou senha. 🟢
- [ ] T-08, revalidar escopo de condomínio e colisão DB/legado em PATCH de identidade. 🟢

## Tarefas de Teste

- [ ] TT-01, testar constraints ORM e migration em baseline vazia/preenchida. 🟢
- [ ] TT-02, testar prefixo igual entre tenants e identidade global duplicada. 🟢
- [ ] TT-03, testar cifra, rotação, chave ausente e token corrompido. 🟢
- [ ] TT-04, testar corrida check-then-act traduzida após IntegrityError. 🟢
- [ ] TT-05, testar que `unknown` e timestamps nulos são enviados na mesma atualização. 🟢
- [ ] TT-06, testar condomínio cross-tenant/cross-PBX e identidade já existente no XML legado. 🟢

## Tarefas de Migração de Dados

- [ ] TM-01, aplicar `002_ata_trunks` somente sobre `001_public_baseline`; não criar tabelas tenant-scoped. 🟢

## Ordem Sugerida

1. Modelos e migration. 🟢
2. Cipher e Repository transacional. 🟢
3. Serviços de domínio e testes de integração. 🟢

## Lacunas Pendentes (🔴)

Nenhuma lacuna estrutural confirmada; rollout exige backup e ensaio operacional já descritos no onboarding da feature 012. 🟢
