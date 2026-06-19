# Contrato: Agent Assist (Tempo Real)

**Tipo:** WebSocket
**Sentido:** Hub de IA (FastAPI) <-> Painel do Atendente (Frontend)
**Autenticação:** JWT (Bearer Token no handshake)

O painel deve conectar no WSS utilizando o UUID do Agente/Ramal como identificador.

## Evento Emitido (Server -> Client): Transcrição (Transcript)
Enviado continuamente (a cada trecho processado pelo STT).
```json
{
  "type": "transcript",
  "call_id": "uuid-1234",
  "speaker": "customer",
  "text": "meu cpf é",
  "is_final": false,
  "confidence": 0.95,
  "stt_provider": "deepgram"
}
```

## Evento Emitido (Server -> Client): Entidade Extraída
Enviado quando o Triage (Regex + LLM local) detecta uma entidade validada.
```json
{
  "type": "entity",
  "call_id": "uuid-1234",
  "entity_type": "cpf",
  "value": "123.456.789-00",
  "confidence": 0.98,
  "source": "triage_llm"
}
```

## Evento Emitido (Server -> Client): Insight / Agent Assist
Enviado quando o motor LLM detecta uma ação predefinida (checklist, dica).
```json
{
  "type": "insight",
  "call_id": "uuid-1234",
  "insight_type": "checklist_validation",
  "action": "checked",
  "item": "Solicitação de CPF confirmada"
}
```

## Evento Emitido (Server -> Client): Alerta de Anomalia
Enviado quando a IA detecta estresse/fúria no áudio.
```json
{
  "type": "alert",
  "call_id": "uuid-1234",
  "alert_type": "fury_detected",
  "severity": "high",
  "recommendation": "Ativar Copiloto Áudio",
  "speaker": "customer"
}
```

## Evento Emitido (Server -> Client): Status do STT
Enviado quando ocorre fallback ou recuperação do STT.
```json
{
  "type": "stt_status",
  "call_id": "uuid-1234",
  "provider": "whisper_cpp",
  "reason": "deepgram_timeout",
  "timestamp": "2026-05-17T02:30:00Z"
}
```

## Evento Recebido (Client -> Server): Controle
```json
{
  "type": "control",
  "action": "activate_whisper"
}
```

### Ações de controle disponíveis:
| action | Descrição |
|--------|-----------|
| `activate_whisper` | Ativa o Copiloto Áudio (Whisper Mode) para a chamada ativa. |
| `deactivate_whisper` | Desativa o Copiloto Áudio. |
| `pause_ai` | Pausa temporariamente a IA (ex: morador ditando dados sensíveis via DTMF). |
| `resume_ai` | Retoma a IA após pausa. |
| `request_consensus` | Solicita debate multi-agente para ação crítica. |
