# Módulo: extraction

> Gerado pelo Archaeologist — 2026-06-19
> Confiança: 🟢 CONFIRMADO

## Arquivos

| Arquivo | Propósito | Linhas |
|---------|-----------|--------|
| `src/extraction/regex_layer.py` | Extração por regex (CPF, RG, placa, etc.) | 36 |
| `src/extraction/llm_layer.py` | Correção contextual via Ollama | 31 |

## Fluxo de Controle

### regex_layer.py
- `RegexExtractor` com 6 padrões de regex pré-definidos
- `extract(text)` → busca todos os padrões, retorna dict por tipo com value, start, end, sensitive
- `has_suspicion(text)` → retorna True se encontrar CPF, RG ou placa
- Padrão de credit_card marcado como `sensitive: true`

### llm_layer.py
- `LocalLLMExtractor` (Ollama + Mistral 7B)
- `sanitize(raw_value, entity_type, context)` → envia prompt para LLM corrigir/validar dado extraído
- Prompt pede resposta JSON com value, corrected, confidence

## Padrões Regex

| Label | Padrão | Sensitivo |
|-------|--------|-----------|
| cpf | `\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b` | Não |
| rg | `\b\d{1,2}\.?\d{3}\.?\d{3}-?[0-9xX]\b` | Não |
| phone | `\b\(?\d{2}\)?\s?\d{4,5}-?\d{4}\b` | Não |
| plate | `\b[A-Za-z]{3}[-\s]?\d[A-Za-z0-9]\d{2}\b` | Não |
| cep | `\b\d{5}-?\d{3}\b` | Não |
| credit_card | `\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b` | Sim |

## Regras de Negócio

| Regra | Local | Confiança |
|-------|-------|-----------|
| CPF, RG, placa disparam suspeita | `regex_layer.py:32-35` | 🟢 |
| Dados sensíveis (cartão) passam por sanitização LLM | `consensus_graph.py:58-59` | 🟢 |
| LLM nunca recebe dados externos (Ollama local) | `llm_layer.py:6` | 🟢 |
