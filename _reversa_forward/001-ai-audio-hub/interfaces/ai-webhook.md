# Contrato: AI Webhook (Pós-chamada)

**Tipo:** HTTP POST
**Sentido:** Hub de IA -> Sistema Terceiro (CRM, ERP, Integrações)
**Idempotência:** Baseada no `call_id` e UUID do Webhook Event.

## Payload de Requisição

```json
{
  "event_id": "evt-abc123xyz",
  "event_type": "call.analyzed",
  "call_id": "uuid-1234",
  "timestamp": "2026-05-16T15:00:00Z",
  "metadata": {
    "caller_id": "1001",
    "callee_id": "5511999999999",
    "duration_seconds": 120,
    "status": "completed"
  },
  "insights": {
    "sentiment": "positive",
    "audit_score": 85,
    "audit_failures": ["Não ofereceu o plano superior"],
    "checklist_result": [
      {"item": "Pediu nome completo", "passed": true},
      {"item": "Verificou autorização", "passed": true},
      {"item": "Ofereceu plano superior", "passed": false}
    ],
    "extracted_entities": {
      "cpf": "123.456.789-00",
      "protocolo": "20260516"
    },
    "consensus_log": {
      "extractor": "autorizar",
      "reviewer": "negar",
      "decider": "escalar para humano",
      "reason": "Estresse vocal detectado acima do limiar"
    }
  },
  "summary": "Cliente ligou para confirmar o cancelamento, mas o atendente aplicou retenção..."
}
```

## Resposta Esperada
- `200 OK` (Opcionalmente `202 Accepted` ou `201 Created` dependendo do recebedor).
- Se houver falha (timeout, status 4xx/5xx), o Worker Arq utilizará um padrão de "Exponential Backoff" retentando até 5 vezes num período de 24 horas.
