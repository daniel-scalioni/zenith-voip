# IA, Tarefas de Implementação

> Gerado pelo Writer — 2026-06-19

## Tarefas

- [ ] T-01, Implementar detecção de anomalias (fury score + stress patterns)
  - Origem: `src/ai/anomaly_detector.py:6-34`
  - Critério: score >= 3 dispara alerta; >= 5 severidade danger
  - Confiança: 🟢

- [ ] T-02, Implementar grafo de consenso LangGraph (3 ciclos)
  - Origem: `src/ai/consensus_graph.py:40-72`
  - Critério: approved/rejected após até 3 iterações; sentiment < -0.3 rejeita
  - Confiança: 🟢

- [ ] T-03, Implementar cache de POPs no Redis
  - Origem: `src/ai/pops_cache.py:5-30`
  - Critério: POPs cacheados por tenant com TTL 1h
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, Testar anomalia com texto contendo keywords de fúria
- [ ] TT-02, Testar consenso com sentimento positivo (approved)
- [ ] TT-03, Testar consenso com sentimento negativo (rejected)
- [ ] TT-04, Testar limite de 3 ciclos
