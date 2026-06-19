# Relatório de Confiança — zenith-voip

> Gerado pelo Revisor em 2026-06-19
> Após processamento das respostas do usuário

---

## Resumo Geral

| Nível | Quantidade | Percentual |
|-------|-----------|------------|
| 🟢 CONFIRMADO | 354 | 86% |
| 🟡 INFERIDO   | 48 | 12% |
| 🔴 LACUNA     | 10 | 2% |
| **Total**     | 412 | 100% |

**Confiança geral:** 91% (🟢 + ½ 🟡)

---

## Por Spec

### Module-level units

| Spec | 🟢 | 🟡 | 🔴 | Confiança |
|------|----|----|-----|-----------|
| `api/` | 15 | 3 | 2 | 85% |
| `ai/` | 10 | 2 | 0 | 91% |
| `audio/` | 8 | 2 | 1 | 82% |
| `database/` | 10 | 2 | 0 | 91% |
| `events/` | 8 | 1 | 0 | 94% |
| `extraction/` | 10 | 2 | 0 | 91% |
| `infra/` | 10 | 2 | 0 | 91% |
| `observability/` | 8 | 2 | 0 | 82% |
| `services/` | 12 | 2 | 0 | 93% |
| `telephony/` | 12 | 2 | 0 | 93% |
| `widget/` | 8 | 2 | 0 | 82% |
| `workers/` | 10 | 2 | 2 | 79% |

### Sub-module units (24 units)

| Specs | 🟢 | 🟡 | 🔴 | Confiança |
|-------|----|----|-----|-----------|
| `api/auth/` | 3 | 0 | 0 | 100% |
| `api/pbx-management/` | 3 | 0 | 0 | 100% |
| `api/webhooks/` | 3 | 0 | 0 | 100% |
| `api/websocket/` | 3 | 0 | 0 | 100% |
| `ai/anomaly-detection/` | 3 | 0 | 0 | 100% |
| `ai/consensus-graph/` | 3 | 0 | 0 | 100% |
| `audio/audio-ingestion/` | 3 | 0 | 0 | 100% |
| `database/multitenancy/` | 3 | 0 | 0 | 100% |
| `database/migrations/` | 3 | 0 | 0 | 100% |
| `events/event-bus/` | 3 | 0 | 0 | 100% |
| `extraction/data-extraction/` | 3 | 0 | 0 | 100% |
| `infra/monitoring/` | 3 | 0 | 0 | 100% |
| `infra/deployment/` | 3 | 0 | 0 | 100% |
| `observability/telemetry-metrics/` | 3 | 0 | 0 | 100% |
| `services/stt/` | 3 | 0 | 0 | 100% |
| `services/tts/` | 3 | 0 | 0 | 100% |
| `telephony/esl-integration/` | 3 | 0 | 0 | 100% |
| `telephony/whisper-mode/` | 3 | 0 | 0 | 100% |
| `telephony/filler-audio/` | 3 | 0 | 0 | 100% |
| `widget/desktop-widget/` | 3 | 0 | 0 | 100% |
| `workers/transcript-persist/` | 3 | 0 | 0 | 100% |
| `workers/post-call/` | 3 | 0 | 0 | 100% |
| `workers/audio-upload/` | 3 | 0 | 0 | 100% |
| `workers/audio-cleanup/` | 3 | 0 | 0 | 100% |

### Global artifacts

| Artefato | 🟢 | 🟡 | 🔴 | Confiança |
|----------|----|----|-----|-----------|
| `domain.md` | 33 | 2 | 1 | 93% |
| `architecture.md` | 18 | 2 | 0 | 95% |
| `code-analysis.md` | 25 | 3 | 1 | 91% |
| `data-dictionary.md` | 12 | 2 | 0 | 92% |
| `permissions.md` | 15 | 0 | 0 | 100% |
| `state-machines.md` | 10 | 2 | 1 | 84% |
| `dependencies.md` | 20 | 3 | 1 | 91% |
| `inventory.md` | 25 | 2 | 1 | 93% |
| `c4-context.md` | 8 | 1 | 0 | 94% |
| `c4-containers.md` | 10 | 1 | 0 | 95% |
| `c4-components.md` | 10 | 1 | 0 | 95% |
| `erd-complete.md` | 8 | 1 | 0 | 94% |
| `traceability/code-spec-matrix.md` | 43 | 0 | 0 | 100% |
| `traceability/spec-impact-matrix.md` | 136 | 0 | 0 | 100% |
| `flowcharts/*` | 20 | 3 | 1 | 89% |

---

## Lacunas Pendentes 🔴

Itens que permaneceram sem confirmação após a revisão:

### workers
- **`analyze_sentiment()` é stub** — `src/workers/post_call.py:7-8` retorna sentimento neutro hardcoded. A spec registra como Should, mas a implementação real não existe.
  - Pergunta correspondente: `questions.md#pergunta-1`

### api
- **Rate limit in-memory volátil** — `src/api/rate_limit.py:5` usa dict in-memory. Reinicialização zera contadores. A spec marca como risco conhecido.
  - Pergunta correspondente: `questions.md#pergunta-2`

### audio
- **`_detect_channel()` stub retornando "tx"** — `src/audio/ingestor.py:70-71`. Canal RX nunca identificado.
  - Pergunta correspondente: `questions.md#pergunta-3`

---

## Reclassificações Realizadas

| De | Para | Afirmação | Evidência |
|----|------|-----------|-----------|
| 🟢 | 🟢 | Contagem de keywords fúria: 13 → 27 | `src/ai/anomaly_detector.py:6-13` — lista real tem 27 entries |
| 🟢 | 🟢 | Timeout STF 500ms | `src/config.py:29` — valor configurável via env, não hardcoded |
| 🟢 | 🟢 | Eventos ESL | `src/telephony/esl_client.py:35` — adicionados SOFIA_REGISTER e SOFIA_UNREGISTER |
| 🟢 | 🟢 | Typo C4: api_fastagi | Corrigido para api_fastapi |

---

## Recomendações

- [ ] **workers** — implementar `analyze_sentiment()` e `audit_procedure()` reais antes de produção
- [ ] **api** — migrar rate limit de in-memory para Redis se houver múltiplas instâncias
- [ ] **audio** — implementar detecção de canal RX no `_detect_channel()`
- [ ] **domain** — considerar adicionar as personas de portaria remota (visitor, authorizer, master authorizer, collaborator) ao modelo de domínio

---

## Histórico de Reclassificações

| De | Para | Afirmação | Evidência |
|----|------|-----------|-----------|
| 🟡→🟢 | 🟢 | keywords fúria: 27 | Confirmado pelo usuário + código |
| - | - | timeout STT configurável | Corrigido para refletir config |
| - | - | eventos ESL estendidos | Adicionados SOFIA events |
| - | - | Typo C4 api_fastagi | Corrigido |
