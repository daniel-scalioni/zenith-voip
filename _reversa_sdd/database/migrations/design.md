---
spec:
  component: database-migrations
  layer: database
  status: active
  version: 2.0.0
  language: python
  patterns: [repository]
  inputs:
    - {name: database_url, type: PostgreSQL DSN, from: environment}
  outputs:
    - {name: public_schema, type: PostgreSQL schema, to: database}
    - {name: tenant_schema, type: PostgreSQL schema, to: database}
  dependencies:
    - {component: database-models, layer: database}
  events_produced: []
  updated_at: 2026-07-31
---

# Migrations, Design

## Decisão aceita

Como nenhum ambiente conhecido possui `alembic_version` e o usuário escolheu recriar o banco,
substituir a cadeia inválida por uma baseline única de `public`. Essa baseline cria apenas
`tenants`, `pbxs`, índices/constraints e a versão Alembic. As tabelas de negócio continuam no
schema físico de cada tenant, criadas por um provisionador explícito baseado em `TenantBase`.

A decisão está registrada no ADR-011. Se surgir qualquer ambiente com revisão Alembic aplicada,
a decisão é automaticamente suspensa antes de alterar migrations.

## Topologia alvo

```text
public
├── alembic_version
├── tenants
└── pbxs

tenant_<slug>
├── calls
├── transcripts
├── call_insights
└── stt_metrics
```

## Estratégia de corte

1. Gerar dump lógico completo e validá-lo por restore em PostgreSQL 16 temporário.
2. Criar três recursos separados, todos sem porta publicada no host:
   `zenith-postgres-test`, `zenith-postgres-rehearsal` e `zenith-postgres-candidate`, cada qual
   com volume e rede próprios prefixados por `zenith-`.
3. Rodar a baseline no banco vazio e provisionar o tenant com UUIDs explícitos preservados.
4. Restaurar as 9 chamadas e demais tabelas, mesmo quando vazias, validando tipos e constraints.
5. Rodar testes contra banco de teste separado, nunca contra o novo banco candidato.
6. Trocar os serviços para o novo volume somente após todos os gates verdes.
7. Regerar os ramais a partir do CSV privado, comparar manifesto sanitizado e recarregar apenas o
   profile FreeSWITCH necessário.

O `zenith-postgres` atual publica 5433 em todas as interfaces. Embora volume, rede e conexões
observadas sejam exclusivas do projeto, consumidores externos inativos não podem ser descartados.
Por decisão do usuário, o container, sua porta e seu volume não serão recriados, reconfigurados,
parados ou removidos durante esta recuperação.

## Artefato de backup privado

O dump não pode ser gravado no repositório, em diretório compartilhado ou em `/tmp`. No host de
deploy, criar um diretório privado por execução sob
`/home/administrator/.zenith-backups/feature-011/<UTC>-<random>/`, com modo `0700`; dump e
manifesto recebem modo `0600`. O nome é resolvido e validado antes de qualquer limpeza.

Fluxo obrigatório:

1. `pg_dump --format=custom` do banco operacional, sem incluir segredo na linha de comando ou log.
2. Calcular SHA-256 do dump fechado e gravar manifesto com versão do PostgreSQL, tamanho, contagens
   e hash; nunca gravar DSN, UUID em claro ou conteúdo de negócio.
3. Validar o dump exclusivamente por `pg_restore` no rehearsal isolado.
4. Recalcular contagens e hashes após restore; qualquer divergência é `NO-GO`.
5. Ensaiar rollback dos serviços para o DSN anterior antes de autorizar cutover.
6. Manter dump e volumes anterior/candidato durante o aceite. O descarte exige autorização humana,
   alvo absoluto validado e confirmação de que os manifests pós-cutover são idênticos.

## Recursos isolados

| Papel | Container | Volume | Rede | Porta no host | Lifecycle |
|------|-----------|--------|------|---------------|-----------|
| Testes | `zenith-postgres-test` | `zenith-postgres-test-data` | `zenith-quality-test-net` | nenhuma | por execução de quality gate |
| Rehearsal | `zenith-postgres-rehearsal` | `zenith-postgres-rehearsal-data` | `zenith-quality-rehearsal-net` | nenhuma | descartável após ensaio aceito |
| Candidato | `zenith-postgres-candidate` | `zenith-postgres-candidate-data` | `zenith-quality-candidate-net` | nenhuma | preservado durante cutover/aceite |

Cada rede e volume usa `name:` explícito com prefixo `zenith-`. Teste, rehearsal e candidato não
compartilham rede nem volume entre si. Nenhum volume usa `external: true`; em especial, o candidato
não possui referência a `zenith-voip_zenith_postgres_data`.

O banco de teste aceita somente DSN com hostname `zenith-postgres-test` e nome de banco de teste.
Rehearsal e candidato não são destinos válidos para pytest. Nomes de database/schema de testes
incluem identificador aleatório por execução e o teardown só pode remover esse alvo exato.

## Go/No-Go

`GO` exige simultaneamente:

- checksum do dump conferido antes do restore;
- restore rehearsal íntegro e manifesto idêntico;
- rollback ensaiado sem tocar o volume operacional;
- baseline idempotente e topologia pública/tenant correta;
- suíte global e cobertura bloqueante verdes no banco de teste;
- candidato com manifesto idêntico e ramais regenerados;
- aprovação humana explícita no checkpoint de cutover.

Qualquer item ausente, divergência de hash/contagem, DSN inesperado, porta publicada ou referência ao
volume atual é `NO-GO`.

## Rollback

Reapontar os containers Zenith ao volume PostgreSQL anterior e recriá-los de forma rolling. Não
usar `docker compose down -v`, `docker volume rm`, `DROP DATABASE` ou `DROP SCHEMA` durante a
primeira entrega. O volume novo também permanece disponível para diagnóstico.

## Gates

- Restore ensaiado com UUIDs e contagens idênticos.
- `alembic upgrade head` em banco vazio e repetido.
- Nenhuma tabela de chamada em `public`.
- Provisionamento de tenant cria somente tabelas de tenant.
- Suíte global sem falhas e cobertura global ≥ 80%.
- 939 ramais regenerados; conjunto de gateways ativos preservado.
- Chamada smoke cria nova linha no tenant e não quebra a feature 011.
