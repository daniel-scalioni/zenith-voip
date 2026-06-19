# Extraction — Extração de Dados

> Gerado pelo Writer — 2026-06-19

## Visão Geral

Extrai dados estruturados de transcrições usando regex (6 padrões) com correção contextual via LLM local (Ollama Mistral 7B) para dados sensíveis.

## Responsabilidades

- Extrair entidades de texto via regex (CPF, RG, telefone, placa, CEP, cartão de crédito)
- Marcar cartão de crédito como sensitive
- Corrigir extrações suspeitas via LLM local

## Regras de Negócio

- CPF, RG e placa disparam suspeita 🟢
- Cartão de crédito é sensitive — sanitização obrigatória via LLM 🟢
- LLM roda localmente (Ollama) — nenhum dado enviado para nuvem 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade |
|----|-----------|-----------|
| RF-01 | Extrair CPF de texto via regex | Must |
| RF-02 | Extrair RG de texto via regex | Must |
| RF-03 | Extrair telefone de texto via regex | Must |
| RF-04 | Extrair placa de veículo via regex | Must |
| RF-05 | Extrair CEP de texto via regex | Must |
| RF-06 | Extrair cartão de crédito e marcar como sensitive | Must |
| RF-07 | Sanitizar dados sensíveis via LLM local | Must |

## Rastreabilidade

| Arquivo | Função | Cobertura |
|---------|--------|-----------|
| `src/extraction/regex_layer.py` | `extract()`, `has_suspicion()` | 🟢 |
| `src/extraction/llm_layer.py` | `sanitize()` | 🟢 |
