# Regression Watch — AI Audio Hub (001)

> Feature: `001-ai-audio-hub`
> Data: `2026-05-17`
> Tipo: Greenfield

## Itens de Regressão

*n/a — Projeto greenfield. Não há regras de legado para monitorar. Todas as regras de negócio implementadas são novas (RN-01 a RN-10 do requirements.md).*

## Observações

As regras de negócio RN-01 a RN-10 foram implementadas como código novo e devem ser validadas por testes de aceitação (Gherkin no requirements.md, seção 7).

## Histórico de re-extrações

| Data | Re-extração | Veredito | Observações |
|------|-------------|----------|-------------|
| 2026-06-19 | Revisor (revisão completa) | 🟢 7/10 • 🟡 2/10 • 🔴 1/10 | W009 (DTMF) não documentado em specs; W001 (B2BUA) e W004 (consenso físico) parcialmente cobertos |

## Resultado: re-extração 2026-06-19

| ID | Veredito | Evidência |
|----|----------|-----------|
| W001 | 🟡 | Termo "B2BUA" não aparece nas specs, mas integração ESL está documentada em `telephony/requirements.md` |
| W002 | 🟢 | Events pub/sub documentado em `events/requirements.md` e `telephony/esl-integration/requirements.md` |
| W003 | 🟢 | STT→WebSocket documentado em `services/stt/requirements.md` e `api/websocket/requirements.md` |
| W004 | 🟡 | Consenso documentado em `ai/consensus-graph/`, mas sem menção explícita de exclusividade para "ações físicas" |
| W005 | 🟢 | Contexto de tenant documentado em `domain.md` e `database/multitenancy/requirements.md` |
| W006 | 🟢 | Whisper mode documentado em `telephony/whisper-mode/requirements.md` |
| W007 | 🟢 | Filler audio documentado em `telephony/filler-audio/requirements.md` |
| W008 | 🟢 | LLM self-hosted documentado em `domain.md` R23 e `extraction/llm_layer.py` |
| W009 | 🔴 | Senhas via DTMF não mencionadas em nenhuma spec — lacuna confirmada |
| W010 | 🟡 | Channel detection documentado como 🔴 stub em `audio/requirements.md` — speaker tagging não implementado |

## Arquivadas

*n/a*

| ID | Origem | Regra esperada | Tipo de verificação | Sinal de violação |
|----|--------|---------------|---------------------|-------------------|
| W001 | requirements.md RN-01 | Hub atua como B2BUA transparente sem corromper sinalização | presença | PBX rejeita tráfego SIP ou áudio não é interceptado |
| W002 | requirements.md RN-02 | Chamadas geram eventos de fim no Redis Streams | presença | Worker Arq não recebe eventos post-call |
| W003 | requirements.md RN-03 | Áudio transcrito alimenta motor de inferência RT via WebSocket | presença | WebSocket não entrega transcripts |
| W004 | requirements.md RN-04 | Consenso multi-agente exclusivo para ações físicas | redação | Consenso dispara para extração RT não-crítica |
| W005 | requirements.md RN-05 | Contexto do condomínio carregado antes da análise | presença | Modelo analisa sem contexto de tenant |
| W006 | requirements.md RN-06 | Whisper mode injeta áudio apenas no canal do atendente | presença | Morador ouve o whisper (vazamento de áudio) |
| W007 | requirements.md RN-07 | FreeSWITCH injeta áudio de "processando" durante latência | presença | Morador ouve silêncio durante validação |
| W008 | requirements.md RN-08 | Dados pessoais processados exclusivamente por LLM self-hosted | ausência | CPF/RG enviados para API externa |
| W009 | requirements.md RN-09 | Senhas via DTMF sem passar pelo pipeline de IA | ausência | Senha aparece em log de extração |
| W010 | requirements.md RN-10 | Transcrição identifica speaker (morador vs atendente) | presença | Transcrição sem tag de speaker |
