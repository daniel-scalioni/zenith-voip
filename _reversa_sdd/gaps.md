# Lacunas Identificadas — zenith-voip

> Gerado pelo Revisor em 2026-06-19
> Categorizadas por severidade

---

## Críticas (bloqueiam reimplementação)

| ID | Módulo | Descrição | Spec afetada | Status |
|----|--------|-----------|-------------|--------|
| GAP-01 | `audio` | `_detect_channel()` é stub — canal RX nunca detectado | `audio/requirements.md` | Aberta |
| GAP-02 | `workers` | `analyze_sentiment()` e `audit_procedure()` são stubs | `workers/requirements.md` | Aberta |

## Moderadas (impactam qualidade)

| ID | Módulo | Descrição | Spec afetada | Status |
|----|--------|-----------|-------------|--------|
| GAP-03 | `api` | Rate limit in-memory volátil — sem efeito após restart | `api/design.md` | Aberta |
| GAP-04 | `api` | Webhook dispatcher fire-and-forget sem confirmação de entrega | `api/design.md` | Aberta |
| GAP-05 | `domain` | Personas de portaria remota não refletidas no modelo de domínio | `domain.md` | Aberta |
| GAP-06 | `telephony` | Auto-link SIP sem fallback se Redis vazio | `telephony/design.md` | Aberta |

## Cosméticas

| ID | Módulo | Descrição | Spec afetada | Status |
|----|--------|-----------|-------------|--------|
| GAP-07 | `ai` | Contagem de keywords corrigida (13→27) | `ai/requirements.md` | ✅ Resolvida |
| GAP-08 | `c4` | Typo `api_fastagi` → `api_fastapi` | `c4-context.md` | ✅ Resolvida |
| GAP-09 | `stt` | Timeout descrito como hardcoded (é configurável) | `services/stt/design.md` | ✅ Resolvida |
| GAP-10 | `telephony` | Eventos ESL incompletos (faltavam SOFIA events) | `telephony/requirements.md` | ✅ Resolvida |
