# Extração de Dados, Design

**Interface:** `extract(text) → dict`, `has_suspicion(text) → bool`, `sanitize(raw_value, entity_type, context) → dict`
**Algoritmo:** 6 regex → marcar sensitive → LLM local (Ollama) para correção contextual
**Origem:** `src/extraction/regex_layer.py:10-35`, `src/extraction/llm_layer.py:10-20` 🟢
