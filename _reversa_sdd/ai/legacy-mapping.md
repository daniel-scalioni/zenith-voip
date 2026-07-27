# Módulo: ai

> Gerado pelo Archaeologist — 2026-06-19
> Confiança: 🟢 CONFIRMADO

## Arquivos

| Arquivo | Propósito | Linhas |
|---------|-----------|--------|
| `src/ai/anomaly_detector.py` | Detecção de anomalias de tom (fúria/estresse) | 60 |
| `src/ai/consensus_graph.py` | Grafo de consenso LangGraph (3 ciclos) | 102 |
| `src/ai/pops_cache.py` | Cache Redis de POPs (Procedimentos Operacionais) | 29 |

## Fluxo de Controle

### anomaly_detector.py
- `analyze(call_id, text, speaker)` → calcula fury_score + stress_score
- Se total_score >= 3: dispara alerta WebSocket
- Se total_score >= 5: severidade "danger", senão "warning"
- `_score_fury()` → busca 13 keywords em lowercase
- `_score_stress()` → busca ALL CAPS, !! múltiplos, palavras repetidas

### consensus_graph.py
- `ConsensusGraph` constrói StateGraph LangGraph com 3 nós: extractor → reviewer → decider
- `run(call_id, transcript, sentiment, sentiment_score)` → executa o grafo
- Até 3 iterações (se decider rejeitar e iteration < 3)
- Publica decisão final em Redis Stream
- 🔄 **Usa `MemorySaver` como checkpointer** (era `RedisSaver.from_conn_info(host="redis")`).
  A troca foi forçada por conflito de dependências: `arq` exige `redis<6` e
  `langgraph-checkpoint-redis` exige `redis>=6.2.0` — sem interseção possível no mesmo
  `requirements.txt`. O pacote `langgraph-checkpoint-redis` foi removido.
  **Consequência:** o estado do consenso deixa de ser durável e deixa de ser compartilhado
  entre `fastapi-1`/`fastapi-2`. Aceitável porque o consenso é resolvido dentro de uma única
  chamada síncrona a `graph.ainvoke()` (até 3 iterações, ADR-004), mas um restart de processo
  no meio da execução perde o estado. Ver ADR-008.

### pops_cache.py
- `POPsCache` armazena/recupera POPs por tenant_id no Redis
- TTL: 3600s
- Métodos: get_pops, set_pops, invalidate

## Algoritmos

**Score de anomalia**: soma de fury_score (0-13, 1 por keyword) + stress_score (contagem de matches de padrões regex). Threshold = 3 para alerta, 5 para danger.

**Consensus Graph**: LangGraph com:
1. Extractor: extrai entidades do transcript via RegexExtractor
2. Reviewer: sanitiza entidades sensíveis via LocalLLMExtractor (Ollama)
3. Decider: aprova/rejeita baseado em presença de entidades + sentiment_score >= -0.3
4. Loop: se rejected e iteration < 3, volta ao reviewer

## Estruturas de Dados

### AgentState (TypedDict)
| Campo | Tipo | Descrição |
|-------|------|-----------|
| call_id | str | ID da chamada |
| transcript | str | Texto transcrito |
| entities | dict | Entidades extraídas |
| sentiment | str | Sentimento (neutral, positive, negative) |
| sentiment_score | float | Score (-1 a 1) |
| proposed_action | str | Ação proposta |
| justification | str | Justificativa |
| revision_notes | str | Notas de revisão |
| final_decision | str | approved / rejected / bypass |
| human_bypass | bool | Bypass manual |
| iteration | int | Contador de iterações |

## Regras de Negócio

| Regra | Local | Confiança |
|-------|-------|-----------|
| Alerta de anomalia se score >= 3 | `anomaly_detector.py:29` | 🟢 |
| Keywords de fúria em português (13 termos) | `anomaly_detector.py:6-13` | 🟢 |
| Consenso rejeitado se sentiment < -0.3 | `consensus_graph.py:65` | 🟢 |
| Máximo 3 iterações no grafo de consenso | `consensus_graph.py:71` | 🟢 |
| Dados sensíveis passam por sanitização via LLM | `consensus_graph.py:58-59` | 🟢 |
| POPs em cache por 1 hora | `pops_cache.py:9` | 🟢 |
| 🆕 Estado do consenso é in-process e volátil (`MemorySaver`) | `consensus_graph.py:28-34` | 🟢 |
