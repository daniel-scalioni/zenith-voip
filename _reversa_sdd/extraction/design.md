# Extraction, Design Técnico

> Gerado pelo Writer — 2026-06-19

## Interface

| Símbolo | Assinatura | Retorno |
|---------|-----------|---------|
| `extract` | `(text: str)` | `dict[str, list[dict]]` |
| `has_suspicion` | `(text: str)` | `bool` |
| `sanitize` | `(raw_value: str, entity_type: str, context: str)` | `dict` |

### Padrões Regex

| Padrão | Entidade | Sensitive |
|--------|----------|-----------|
| `\d{3}\.\d{3}\.\d{3}-\d{2}` | CPF | Suspeita |
| `\d{2}\.\d{3}\.\d{3}-\d{1}` | RG | Suspeita |
| `\(?\d{2}\)?\s?\d{4,5}-?\d{4}` | Telefone | Não |
| `[A-Z]{3}\d[A-Z0-9]{2}\d{2}` | Placa | Suspeita |
| `\d{5}-?\d{3}` | CEP | Não |
| `\d{4}\s?\d{4}\s?\d{4}\s?\d{4}` | Cartão | 🟢 Sensitive |

## Fluxo Principal

1. `extract(text)` aplica 6 regex patterns — `src/extraction/regex_layer.py:10-30`
2. Se cartão de crédito é detectado, marcado como sensitive — `src/extraction/regex_layer.py:15`
3. `has_suspicion(text)` retorna true se CPF, RG, placa ou cartão encontrados — `src/extraction/regex_layer.py:32-35`
4. `sanitize()` envia valor + contexto para Ollama local — `src/extraction/llm_layer.py:10-20`
5. LLM retorna valor corrigido ou mascarado

## Riscos e Lacunas

- 🟡 LLM local pode estar indisponível (Ollama fora do ar) — sem fallback definido
- 🟡 Regex para placa não cobre formato Mercosul (ABC1D23)
