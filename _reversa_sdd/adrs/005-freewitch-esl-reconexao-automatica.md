# ADR-005: ESL Client com Reconexão Automática e Event Loop Assíncrono

> **Data:** 2026-05-17 (inferido)
> **Status:** Aceito 🟢
> **Confiança:** 🟡 INFERIDO

## Contexto

A comunicação com FreeSWITCH via ESL é baseada em TCP. Quedas de conexão são esperadas em ambientes de produção (reinicialização do FreeSWITCH, problemas de rede).

## Decisão

Implementar ESL client assíncrono com:
- Reconexão automática com backoff de 2s
- Event loop contínuo com buffer de leitura
- Subscrição a 5 eventos: CHANNEL_CREATE, CHANNEL_ANSWER, CHANNEL_HANGUP, SOFIA_REGISTER, SOFIA_UNREGISTER

## Consequências

- **Positivas:** Resiliência a quedas de conexão, processamento assíncrono sem bloqueio
- **Negativas:** Necessidade de gerenciar UUID mapping em memória (volátil em restart)
