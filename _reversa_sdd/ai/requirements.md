# IA — Inteligência Artificial

> Gerado pelo Writer — 2026-06-19
> Escala: 🟢 CONFIRMADO | 🟡 INFERIDO | 🔴 LACUNA

## Visão Geral

Módulo de inteligência artificial: detecção de anomalias de tom em chamadas e grafo de consenso LangGraph para validação de entidades extraídas.

## Responsabilidades

- Detecção de anomalias de tom (fury score + stress patterns)
- Execução do grafo de consenso em até 3 ciclos (extract → review → decide)
- Cache de POPs (Procedimentos Operacionais Padrão) no Redis

## Regras de Negócio

- Anomalia detectada se fury_score + stress_score >= 3 🟢
- Severidade: warning (>= 3), danger (>= 5) 🟢
- Consenso rejeitado se sentiment_score < -0.3 🟢
- Máximo de 3 iterações no grafo de consenso 🟢
- 27 keywords de fúria em português 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Detectar anomalia baseada em keywords de fúria | Must | Score >= 3 dispara alerta |
| RF-02 | Detectar padrões de estresse (ALL CAPS, !! múltiplos, repetição) | Must | Cada padrão incrementa stress_score |
| RF-03 | Executar grafo de consenso em até 3 ciclos | Must | extract → review → decide; se rejeitado e < 3 ciclos, reinicia |
| RF-04 | Validar entidades extraídas no consenso | Must | Entidades passam por revisão antes da decisão final |
| RF-05 | Cachear POPs no Redis com TTL 1h | Should | POPs carregados por tenant e cacheados |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `src/ai/anomaly_detector.py` | `analyze()` | 🟢 |
| `src/ai/consensus_graph.py` | `run()` | 🟢 |
| `src/ai/pops_cache.py` | `get_pops()`, `set_pops()` | 🟢 |
