# ADR-008: Checkpointer do grafo de consenso em memória (MemorySaver)

**Data:** 2026-07-09 (retroativo — registrado na re-extração de 2026-07-27)
**Status:** Aceito
**Contexto:** zenith-voip — módulo `ai`, `src/ai/consensus_graph.py`
**Commit de origem:** `d25d2f4` — *fix: resolve conflito redis entre arq e langgraph-checkpoint-redis*

---

## Contexto

O `ConsensusGraph` (LangGraph) usava `RedisSaver.from_conn_info(host="redis", port=6379)`
como checkpointer, o que dava ao grafo persistência durável e estado compartilhado entre as
duas instâncias FastAPI.

Ao consolidar o `requirements.txt` descobriu-se um conflito **sem solução possível**:

| Pacote | Restrição sobre `redis` |
|---|---|
| `arq` (workers e cron do projeto) | `redis < 6` |
| `langgraph-checkpoint-redis` | `redis >= 6.2.0` |

Não existe versão de `redis` que satisfaça os dois. Como `arq` é a espinha dorsal dos workers
(upload de gravação, cleanup, persistência de transcript), abandoná-lo custaria muito mais do
que abandonar a durabilidade do checkpoint do consenso.

## Decisão

Trocar o checkpointer por **`MemorySaver`** (in-process, volátil) e **remover
`langgraph-checkpoint-redis`** do `requirements.txt`.

```python
from langgraph.checkpoint.memory import MemorySaver
self.checkpointer = MemorySaver()
```

## Justificativa

O consenso é resolvido **dentro de uma única chamada síncrona** a `graph.ainvoke()` — até 3
iterações (ADR-004), sem espera por evento externo e sem interação humana no meio. O estado
não precisa sobreviver a restart de processo nem ser lido por outra instância: ele nasce e
morre no mesmo `await`.

## Consequências

**Positivas**
- Conflito de dependência eliminado; `arq` mantido.
- Uma dependência a menos e um ponto de rede a menos no caminho crítico do consenso.
- Latência menor: sem round-trip ao Redis a cada transição de nó do grafo.

**Negativas**
- 🔴 Se o processo reiniciar no meio de um `ainvoke()`, o estado do consenso é perdido —
  não há retomada; a análise daquela chamada precisa ser refeita do zero.
- 🔴 `fastapi-1` e `fastapi-2` não compartilham checkpoint. Hoje isso é inócuo, mas
  **bloqueia** qualquer evolução para consenso assíncrono, multi-turno ou com aprovação
  humana no meio do fluxo.
- O `human_bypass` presente em `AgentState` sugere exatamente esse cenário futuro. Se ele
  virar um fluxo real (esperar decisão de um humano entre iterações), este ADR precisa ser
  revisto — e aí o conflito `arq` × `redis` volta à mesa.

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Manter `RedisSaver` e trocar `arq` por outro worker | Custo muito alto: cron, filas e três workers em produção seriam reescritos |
| Checkpointer em PostgreSQL (`langgraph-checkpoint-postgres`) | Não avaliado na época; é a saída natural se a durabilidade voltar a ser requisito |
| Fixar `redis` numa versão e ignorar o conflito | `pip` não resolve; instalação quebra |

## Relacionados

- [ADR-004](004-consenso-3-ciclos.md) — o limite de 3 ciclos é o que torna a volatilidade aceitável
- `_reversa_sdd/ai/legacy-mapping.md`
