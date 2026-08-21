# ADR-012: Promover `zenith-postgres-candidate` a `zenith-postgres`

**Data:** 2026-08-20
**Status:** Aceito
**Contexto:** zenith-voip — módulo `infra/deployment`
**Reverte parcialmente:** a regra "🟢 O Compose não pode reintroduzir `zenith-postgres` nesse
alias" registrada em `_reversa_sdd/infra/deployment/requirements.md` (feature `012`, W002,
2026-08-18)

---

## Contexto

Na feature `012-trunk-registration`, o cutover de banco (W002) promoveu o container de
rehearsal `zenith-postgres-candidate` a produção, mantendo o serviço Compose com o alias de
rede `postgres` (para não quebrar DNS dos consumidores) mas com `container_name` e volume
ainda nomeados `-candidate`. A decisão explícita foi **não** renomear para `zenith-postgres`:
o serviço antigo `zenith-postgres` continuava declarado em `docker-compose.infra.yml`, e um
`docker compose up` sem `--no-deps` o reconectaria à rede, fazendo a API apontar de volta para
um banco sem `condominiums`/`ata_trunks` — falha fechada e silenciosa (W002, regression-watch
da feature 012).

Essa proteção deixou de fazer sentido: o serviço `zenith-postgres` **já não existe em nenhum
compose file do projeto** — só havia, até hoje, um volume Docker órfão remanescente
(`zenith-voip_postgres_data`), sem container algum anexado. Investigação nesta sessão (via
instância `postgres:16-alpine` temporária, `--network none`, montando o volume só para leitura)
confirmou que esse volume não continha nenhuma chamada nem transcrição — apenas as tabelas
`public.tenants`/`public.pbxs` de antes do provisionamento schema-per-tenant, 45,8 MB no total.
As 12 chamadas que `_reversa_sdd/gaps.md` (GAP-28) atribuía a esse volume já estavam, na
verdade, na produção atual (`zenith-postgres-candidate`) — confirmado por `call_id`/
`started_at` idênticos nas duas fontes antes da remoção. O volume foi removido
(`docker volume rm zenith-voip_postgres_data`) nesta mesma sessão, sem perda de dado.

Com o serviço antigo ausente do Compose e o volume órfão removido, não existe mais nenhum
caminho — acidental ou não — para um `docker compose up` reintroduzir um `zenith-postgres`
divergente. O nome `-candidate` em produção é hoje puramente vestigial (terminologia do
processo de promoção blue-green), não uma proteção ativa.

## Decisão

Renomear o serviço canônico em `docker-compose.infra.yml`:

- `container_name`: `zenith-postgres-candidate` → `zenith-postgres`
- Volume Compose (chave `zenith_postgres_candidate_data`, nome externo
  `zenith-postgres-candidate-data`) → chave `zenith_postgres_data`, nome externo
  `zenith-postgres-data`, apontando para o **mesmo volume físico já existente**
  (renomeação de referência, não migração de dados — Docker não suporta rename nativo de
  volume, então o volume físico é recriado com o novo nome e os dados copiados por um
  container efêmero antes do corte).
- `POSTGRES_USER`/`POSTGRES_DB`/variável de senha continuam `zenith_candidate`/
  `ZENITH_CANDIDATE_POSTGRES_PASSWORD` — renomear essas credenciais exigiria reemitir
  `DATABASE_URL` em todos os consumidores simultaneamente; fora do escopo deste ADR, que trata
  apenas do nome do container/volume. Pode ser revisitado depois, sem urgência (não há
  colisão nem risco associado ao nome da credencial).
- O alias de rede `postgres` em `ai-hub-net`, já usado por todos os consumidores, **não muda**.

`docker-compose.candidate.yml` (rehearsal do gate de qualidade) já usa nome próprio
(`zenith-postgres-quality-candidate`, corrigido no GAP-27) e não é afetado.

## Consequências

**Positivas**
- Elimina o débito cosmético registrado em GAP-27: o nome de produção deixa de carregar
  terminologia de um processo de promoção já concluído há mais de um mês.
- `docker ps --filter name=zenith-` volta a listar o Postgres de produção com o nome que
  qualquer operador esperaria.

**Negativas**
- Requer recriar o container em produção (`docker compose up -d --no-deps postgres` após a
  cópia do volume) — interrupção breve de conexão para todo consumidor de `DATABASE_URL**
  durante a janela de corte (segundos, não minutos; mesmo padrão de risco já aceito no cutover
  original W002).
- `test_postgres_cutover_compose.py` precisa ser atualizado para os novos nomes antes do
  Compose mudar (TDD: teste vermelho primeiro).

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Manter `-candidate` indefinidamente | Nome deixou de refletir qualquer risco real; dívida cosmética permanente sem motivo |
| Renomear também usuário/banco/credencial | Amplia a janela de corte e o raio de mudança sem necessidade — nenhuma colisão depende disso |

## Relacionados

- `_reversa_forward/012-trunk-registration/regression-watch.md` (W002) — decisão original que
  este ADR reverte parcialmente
- `_reversa_sdd/gaps.md` — GAP-27 (nome vestigial, agora fechado por este ADR) e GAP-28
  (volume órfão, removido nesta sessão)
