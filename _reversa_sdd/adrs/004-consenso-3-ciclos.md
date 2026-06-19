# ADR-004: Consenso em 3 Ciclos com LangGraph

> **Data:** 2026-05-17 (inferido)
> **Status:** Aceito 🟢
> **Confiança:** 🟡 INFERIDO

## Contexto

Dados extraídos por regex podem conter falsos positivos. A correção via LLM é custosa e pode não ser necessária para todos os dados.

## Decisão

Implementar um grafo de consenso com 3 ciclos usando LangGraph:
1. **Extractor**: extrai entidades via regex
2. **Reviewer**: sanitiza apenas dados sensíveis via LLM
3. **Decider**: aprova/rejeita baseado em sentiment_score e presença de entidades

Se rejeitado e iteration < 3, volta ao reviewer.

## Consequências

- **Positivas:** Precisão maior, processamento apenas do necessário
- **Negativas:** Complexidade adicional, latência em chamadas longas
