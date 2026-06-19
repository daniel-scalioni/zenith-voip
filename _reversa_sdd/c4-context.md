# Diagrama C4 — Contexto (Nível 1)

> Gerado pelo Architect — 2026-06-19
> Escala: 🟢 CONFIRMADO | 🟡 INFERIDO | 🔴 LACUNA

## Propósito

Mostrar o sistema Zenith AI Audio Hub no centro, com seus usuários e sistemas externos.

## Diagrama

```mermaid
C4Context
  title Diagrama de Contexto — Zenith AI Audio Hub

  Person(agent, "Operador", "Agente de call center que usa o widget desktop")
  Person(customer, "Cliente", "Cliente que liga para a central via SIP")
  Person(visitor, "Visitante", "Cliente que liga para a central mas não é Autorizador")
  Person(authorizer, "Autorizador", "Cliente que o Operador liga solicitando autorização de procedimento")
  Person(master_authorizer, "Autorizador Master", "Responsável pelo local monitorado, autoriza serviços para áreas comuns (síndico)")
  Person(collaborator, "Colaborador", "Responsável operacional pelo local, acompanha Visitante em serviços e áreas comuns")

  System_Boundary(zenith, "Zenith AI Audio Hub") {
    System(api_fastapi, "FastAPI Application", "2 instâncias ativas, REST + WebSocket")
    System(workers_arq, "ARQ Workers", "Background jobs: STT, TTS, extração, cleanup")
    System(widget_tauri, "Widget Desktop", "Tauri app (sempre-on-top, system tray)")
    System(redis_streams, "Redis Streams", "Event bus + cache + filas")
    System(postgres, "PostgreSQL", "Banco principal, schema-per-tenant")
  }

  System_Ext(freeswitch, "FreeSWITCH", "PBX SIP, eventos ESL, forked audio")
  System_Ext(deepgram, "Deepgram API", "STT cloud (primário)")
  System_Ext(ollama, "Ollama (Mistral 7B)", "LLM local — extração + correção contextual")
  System_Ext(piper, "Piper TTS", "TTS local — síntese de voz")
  System_Ext(s3, "S3-compatible Storage", "Armazenamento de áudio (bucket por tenant)")
  System_Ext(prometheus, "Prometheus + Grafana + Loki", "Métricas, dashboards e logs")
  System_Ext(bunkerweb, "BunkerWeb", "Proxy reverso com sticky session (X-Call-ID)")

  Rel(customer, freeswitch, "Liga", "SIP/RTP")
  Rel(visitor, freeswitch, "Liga", "SIP/RTP")
  Rel(authorizer, freeswitch, "Recebe ligação do Operador", "SIP/RTP")
  Rel(master_authorizer, freeswitch, "Recebe ligação do Operador", "SIP/RTP")
  Rel(collaborator, freeswitch, "Acompanha Visitante", "SIP/RTP")
  Rel(freeswitch, api_fastapi, "Eventos ESL + áudio", "ESL + WebSocket")
  Rel(agent, widget_tauri, "Usa", "WebSocket (wss://)")
  Rel(widget_tauri, api_fastapi, "Conecta", "WebSocket")
  Rel(api_fastapi, redis_streams, "Publica/consome", "Redis protocol")
  Rel(workers_arq, redis_streams, "Consome/publica", "Redis protocol")
  Rel(workers_arq, postgres, "Persiste", "asyncpg")
  Rel(workers_arq, deepgram, "Transcreve áudio", "HTTPS/gRPC")
  Rel(workers_arq, ollama, "Corrige extrações", "HTTP")
  Rel(workers_arq, piper, "Sintetiza voz", "HTTP")
  Rel(workers_arq, s3, "Upload/download", "HTTPS/S3 API")
  Rel(api_fastapi, prometheus, "Exporta métricas", "OTLP + /metrics")
  Rel(bunkerweb, api_fastapi, "Proxy", "HTTP reverso")
```

## Atores

| Ator | Descrição | Tipo |
|------|-----------|------|
| **Operador** | Agente de call center que usa o widget desktop para acompanhamento de chamadas | Person |
| **Cliente** | Pessoa que liga para a central via SIP | Person |
| **Visitante** | Cliente que liga para a central mas não é Autorizador | Person |
| **Autorizador** | Cliente que o Operador liga solicitando autorização de procedimento | Person |
| **Autorizador Master** | Responsável pelo local monitorado, autoriza serviços para áreas comuns (síndico) | Person |
| **Colaborador** | Responsável operacional pelo local, acompanha Visitante em serviços e áreas comuns | Person |

## Sistemas Externos

| Sistema | Descrição | Protocolo | Confiança |
|---------|-----------|-----------|-----------|
| **FreeSWITCH** | Central telefônica, gera eventos ESL e envia áudio | ESL + WebSocket | 🟢 |
| **Deepgram API** | STT cloud com modelo nova-2 em português | HTTPS/gRPC | 🟢 |
| **Ollama (Mistral 7B)** | LLM local para correção contextual de dados extraídos | HTTP | 🟢 |
| **Piper TTS** | Síntese de voz local | HTTP | 🟢 |
| **S3-compatible** | Storage para arquivos de áudio | HTTPS/S3 API | 🟢 |
| **Prometheus + Grafana + Loki** | Stack de observabilidade | OTLP/HTTP | 🟢 |
| **BunkerWeb** | Proxy reverso com stickiness por X-Call-ID | HTTP | 🟢 |
