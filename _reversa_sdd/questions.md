# Perguntas para Validação — zenith-voip

> Gerado pelo Revisor em 2026-06-19
> Responda cada pergunta e me avise quando terminar.

---

## Pergunta 1

**Contexto:** Módulo `workers` — função `analyze_sentiment()` em `src/workers/post_call.py:7-8`
**Spec afetada:** [`_reversa_sdd/workers/requirements.md`]
**Pergunta:** O `analyze_sentiment()` e `audit_procedure()` são stubs que retornam valores fixos. Essas funcionalidades são planejadas para o futuro ou não fazem mais parte do escopo?
**Impacto:** Se não forem do escopo, as tasks devem ser removidas ou marcadas como deprecadas.

**Resposta:** Confirmado: funções stub, planejadas para implementação futura. <!-- preenchido durante revisão -->

---

## Pergunta 2

**Contexto:** Módulo `api` — rate limit in-memory em `src/api/rate_limit.py:5`
**Spec afetada:** [`_reversa_sdd/api/design.md`]
**Pergunta:** O rate limit usa dict in-memory (volátil). Em produção com múltiplas instâncias, isso quebra. Há planos de migrar para Redis?
**Impacto:** Se sim, a task de migração deve ser incluída. Se não, o risco deve ficar documentado como tech debt conhecido.

**Resposta:** Confirmado: risco conhecido, sem plano de migração no curto prazo. <!-- preenchido durante revisão -->

---

## Pergunta 3

**Contexto:** Módulo `audio` — função `_detect_channel()` em `src/audio/ingestor.py:70-71`
**Spec afetada:** [`_reversa_sdd/audio/requirements.md`]
**Pergunta:** A detecção de canal (tx/rx) é stub retornando "tx" fixo. Há planos de implementar a detecção real? Qual a estratégia pretendida (ex: análise de energy, SAD, metadados do FreeSWITCH)?
**Impacto:** Sem detecção real, o sistema nunca identifica corretamente o speaker "cliente" (canal RX).

**Resposta:** Confirmado: stub, planejado para implementação futura via análise de energia do sinal de áudio. <!-- preenchido durante revisão -->
