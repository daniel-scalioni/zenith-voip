# Interface: Widget WebSocket Event Stream

> Identificador: `002-escala-eventos`
> Data: `2026-05-21`
> Tipo: WebSocket Protocol

Fluxo bidirecional em tempo real entre o Zenith Widget (Tauri Desktop App) e o backend FastAPI para sinalizar eventos de ligação de ramal dinâmico associado e sincronização de checklist POP.

---

## 1. Conexão e Handshake

- **Endpoint**: `WS /api/v1/widget/ws`
- **Query Params**:
  - `token`: JWT de autenticação do atendente.
- **Protocolo**: `json`

No momento do aperto de mão (handshake):
1. O backend lê a origem do IP da conexão TCP do WebSocket.
2. Efetua a busca por IP em Redis Cache.
3. Se encontrado, envia a resposta de boas-vindas com o ramal e o PBX automaticamente vinculados.

---

## 2. Eventos de Servidor para Cliente (Downstream Events)

### Evento: `session_linked` (Vínculo Concluído)
Enviado assim que a associação de ramal dinâmico e PBX é confirmada por IP matching ou manual dial.

```json
{
  "event": "session_linked",
  "data": {
    "agent_uuid": "atend-123",
    "ramal_sip": "4001",
    "pbx_id": "771e8400-e29b-41d4-a716-446655440000",
    "pbx_name": "PABX-Matriz-SP",
    "strategy": "automatic_ip_matching"
  }
}
```

### Evento: `session_waiting_linkage` (Aguardando Fallback Manual)
Enviado quando o IP do WebSocket não possui ramal SIP mapeado no Redis (NAT complexo), instruindo o widget a exibir a tela de vinculação manual.

```json
{
  "event": "session_waiting_linkage",
  "data": {
    "agent_uuid": "atend-123",
    "message": "Associação de ramal pendente. Digite *88 no seu softphone corporativo para vincular este widget ao seu ramal."
  }
}
```

### Evento: `live_call_event` (Atualização de Áudio / Insights)
Despachado assim que um novo chunk de áudio da chamada do ramal é processado assincronamente pelo barramento de eventos (Redis Streams).

```json
{
  "event": "live_call_event",
  "data": {
    "call_id": "call-sp-99021",
    "status": "in_progress",
    "duration_seconds": 45.2,
    "last_transcript_chunk": {
      "speaker": "customer",
      "text": "Sim, eu confirmo o meu CPF final 32."
    },
    "checklist_pop_update": {
      "item_01_confirmar_documento": "checked",
      "item_02_identificar_anomalia": "unchecked"
    }
  }
}
```

---

## 3. Eventos de Cliente para Servidor (Upstream Events)

### Evento: `manual_linkage_request`
Enviado pelo widget quando o operador solicita a vinculação manual, colocando a sessão dele no Redis temporariamente sob escuta.

```json
{
  "event": "manual_linkage_request",
  "data": {
    "agent_uuid": "atend-123"
  }
}
```
