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
2. Casamento do regex de CPF passa por validação de **dígito verificador** (fix GAP-RE-09,
   2026-08-21) antes de entrar no resultado — `src/extraction/regex_layer.py::_is_valid_cpf`.
   Sequência de 11 dígitos que casa o formato mas falha o cálculo do módulo 11 (ex: dígitos
   repetidos `111.111.111-11`, ou dígito verificador incorreto) é descartada, não retornada como
   CPF. Reintroduz a garantia que `python-brasilcpf` dava antes de ser removido (GAP-18) sem
   reintroduzir a dependência.
3. Se cartão de crédito é detectado, marcado como sensitive — `src/extraction/regex_layer.py:15`
4. `has_suspicion(text)` retorna true se CPF (validado), RG, placa ou cartão encontrados —
   `src/extraction/regex_layer.py:32-35`
5. `sanitize()` envia valor + contexto para Ollama local — `src/extraction/llm_layer.py:10-20`
6. LLM retorna valor corrigido ou mascarado

## Riscos e Lacunas

- 🟡 LLM local pode estar indisponível (Ollama fora do ar) — sem fallback definido
- 🟡 Regex para placa não cobre formato Mercosul (ABC1D23)
- ✅ ~~CPF sem validação de dígito verificador~~ — fechado (GAP-RE-09, 2026-08-21)
