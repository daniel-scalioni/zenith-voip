# IA, Design Técnico

> Gerado pelo Writer — 2026-06-19
> Escala: 🟢 CONFIRMADO | 🟡 INFERIDO | 🔴 LACUNA

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `analyze` | `(call_id: str, text: str, speaker: str)` | `dict` | Score de anomalia + severidade |
| `run` | `(call_id: str, transcript: str, sentiment: str, sentiment_score: float)` | `dict` | Decisão do consenso |

### AgentState (LangGraph)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| call_id | str | ID da chamada |
| transcript | str | Transcrição completa |
| entities | dict | Entidades extraídas |
| sentiment | str | Sentimento (positive/neutral/negative) |
| sentiment_score | float | Score -1 a 1 |
| final_decision | str | approved / rejected / bypass |
| iteration | int | Ciclo atual (1-3) |

## Fluxo Principal

1. `analyze()` recebe texto e speaker — `src/ai/anomaly_detector.py:10-20`
2. Calcula fury_score (13 keywords) + stress_score (ALL CAPS, !! repetição) — `src/ai/anomaly_detector.py:22-29`
3. Se score >= 5: severity = "danger"; se >= 3: "warning" — `src/ai/anomaly_detector.py:33-34`
4. `run()` inicia grafo de consenso LangGraph — `src/ai/consensus_graph.py:40-55`
5. Nó extractor: extrai entidades do texto
6. Nó reviewer: revisa entidades contra regras
7. Nó decider: decide approved/rejected; se rejected e iteration < 3, volta ao extractor
8. Se sentiment_score < -0.3, decisão é rejeitada — `src/ai/consensus_graph.py:65`

## Fluxos Alternativos

- **Score insuficiente:** anomalia não é disparada (score < 3), severidade ausente
- **Consenso esgotado:** após 3 ciclos sem aprovação, decisão final é "rejected"

## Dependências

- `extraction` — entidades extraídas são validadas pelo consenso 🟢
- `database` — resultados de anomalia e consenso persistidos em CallInsight 🟢

## Decisões de Design

| Decisão | Evidência | Confiança |
|---------|-----------|-----------|
| Keywords hardcoded em português | `anomaly_detector.py:6-13` | 🟢 |
| LangGraph com estado serializável (AgentState) | `consensus_graph.py:15-25` | 🟢 |
| Limite de 3 ciclos para evitar loops infinitos | `consensus_graph.py:70-72` | 🟢 |

## Riscos e Lacunas

- 🟡 Keywords hardcoded — sem i18n ou configuração externa
- 🟡 Padrões de estresse são regex simples, podem gerar falsos positivos
