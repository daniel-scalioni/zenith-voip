# Extraction, Tarefas de Implementação

> Gerado pelo Writer — 2026-06-19

## Tarefas

- [ ] T-01, Implementar 6 padrões regex de extração
  - Origem: `src/extraction/regex_layer.py:10-30`
  - Critério: CPF, RG, telefone, placa, CEP, cartão extraídos corretamente
  - Confiança: 🟢

- [ ] T-02, Implementar detecção de suspeita e sensitive
  - Origem: `src/extraction/regex_layer.py:32-35`
  - Critério: CPF/RG/placa disparam suspeita; cartão marcado como sensitive
  - Confiança: 🟢

- [ ] T-03, Implementar sanitização via LLM local
  - Origem: `src/extraction/llm_layer.py:10-20`
  - Critério: dados sensíveis sanitizados via Ollama; sem dados enviados para nuvem
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, Testar extração de cada padrão regex
- [ ] TT-02, Testar sanitização de cartão de crédito
- [ ] TT-03, Testar LLM offline (comportamento de fallback)
