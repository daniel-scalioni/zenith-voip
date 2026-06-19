# ADR-003: Dados Sensíveis Processados Apenas por LLM Local

> **Data:** 2026-05-17 (inferido)
> **Status:** Aceito 🟢
> **Confiança:** 🟡 INFERIDO

## Contexto

O sistema extrai dados potencialmente sensíveis (CPF, RG, cartão de crédito) das transcrições. Enviar esses dados para serviços cloud (como OpenAI) violaria políticas de compliance e LGPD.

## Decisão

Usar **Ollama + Mistral 7B rodando localmente** para sanitização e correção contextual de dados sensíveis. A comunicação nunca sai da rede interna.

## Alternativas Consideradas

| Alternativa | Motivo da Rejeição |
|-------------|-------------------|
| OpenAI API | Dados sairiam do ambiente controlado — risco LGPD |
| Regex puro | Sem capacidade de correção contextual |
| Modelo local menor | Mistral 7B oferece bom equilíbrio entre qualidade e recursos |

## Consequências

- **Positivas:** Compliance LGPD, zero vazamento de dados sensíveis
- **Negativas:** Requer GPU para performance aceitável, consumo de recursos locais
