# ADR-002: STT com Fallback Automático (Deepgram → Whisper)

> **Data:** 2026-05-17 (inferido)
> **Status:** Aceito 🟢
> **Confiança:** 🟡 INFERIDO

## Contexto

Transcrição de áudio em tempo real é crítica para a operação. Deepgram oferece qualidade superior mas depende de nuvem e tem custo. Whisper.cpp roda localmente (sem custo, sem latência de rede) mas com qualidade inferior.

## Decisão

Implementar **fallback automático**: Deepgram como provider primário, Whisper.cpp como fallback. Gatilho: timeout de 500ms ou confidence ≤ 0.3.

## Alternativas Consideradas

| Alternativa | Motivo da Rejeição |
|-------------|-------------------|
| Apenas Deepgram | Dependência total de nuvem, sem resiliência |
| Apenas Whisper | Qualidade inferior em português |
| Fallback manual | Complexidade operacional para o agente |

## Consequências

- **Positivas:** Resiliência operacional, qualidade mantida na maioria dos casos
- **Negativas:** Duas implementações de STT para manter, complexidade adicional no pipeline
