# Data Delta: Transcrição persistida (F1)

> Identificador: `013-transcricao-persistida`
> Data: `2026-08-12`

## Resumo

Nenhuma tabela nova, nenhuma coluna nova, nenhuma migração Alembic necessária. O schema de
`Transcript` (`src/database/models.py:161-177`) já contém todos os campos exigidos pelos
requisitos desta feature. O delta é **comportamental**, não estrutural: pela primeira vez desde
que o schema existe, linhas são de fato inseridas nessa tabela.

## Tabela afetada (sem alteração de schema)

### `transcripts` (já existe)

| Coluna | Tipo | Uso nesta feature |
|--------|------|----------------------|
| `call_id` | UUID (FK → `calls.id`) | Chave de agrupamento e de idempotência (D-03: `EXISTS` por `call_id` decide se a chamada já foi transcrita) |
| `channel` | String(16) | `"tx"` ou `"rx"`, conforme o de-interleaving já feito na captura (GAP-01) |
| `speaker` | String(64) | Mapeado a partir de `channel` conforme RN-01: `tx`→`"atendente"`, `rx`→`"cliente"` |
| `text` | Text | Texto transcrito do segmento/janela |
| `confidence` | Float | Confidence retornado por `WhisperCppSTT` |
| `start_time` / `end_time` | Float | Timestamps do segmento dentro da chamada, usados também no `.md` (RF-03) |
| `is_final` | Boolean | Sempre `True` nesta feature — não há transcrição parcial/streaming em F1 |
| `extra_metadata` | JSONB | Reservado para dados auxiliares futuros (ex.: índice da janela/chunk); não obrigatório para o corte inicial |

## Migração necessária

Nenhuma. `alembic upgrade head` não precisa de revisão nova para esta feature — o schema já
suporta o novo comportamento.

## Idempotência (D-03, D-07)

Reprocessamento do mesmo `call_id` substitui as linhas existentes de forma transacional
(delete+insert ou upsert, a decidir em `/reversa-to-do`), sem depender de coluna nova nem de
tabela de controle separada — a própria existência de linhas `Transcript` para o `call_id` é o
sinal de "já processado" usado pelo worker de descoberta (D-01/D-03).
