# Audio, Design Técnico

> Gerado pelo Writer — 2026-06-19

## Interface

| Símbolo | Assinatura | Retorno |
|---------|-----------|---------|
| `handle_forked_stream` | `(call_id: str, websocket: WebSocket)` | `None` |

### AudioChunk

| Campo | Tipo | Descrição |
|-------|------|-----------|
| call_id | str | ID da chamada |
| channel | str | "tx" (agente) ou "rx" (cliente) |
| data | bytes | Áudio PCM16 de um canal, já de-interleado |
| timestamp | float | Timestamp do chunk |

## Protocolo `mod_audio_fork` (atualizado em 2026-06-19, investigação pós-MVP)

> Fonte: [README mod_audio_fork (drachtio-freeswitch-modules)](https://github.com/mdslaney/drachtio-freeswitch-modules/blob/main/modules/mod_audio_fork/README.md). Sem acesso a FreeSWITCH real neste ambiente de investigação — pendência de validação marcada abaixo.

- `mix-type` documentados: `mono` (só caller), `mixed` (caller+callee somados em 1 canal), `stereo` (caller e callee em canais separados, **intercalados por amostra dentro do mesmo frame binário PCM16**). O valor `both`, usado anteriormente no dialplan, **não existe** na especificação — corrigido para `stereo` em `freeswitch/conf/dialplan/default.xml`, junto com o nome de aplicação correto (`uuid_audio_fork`, sintaxe `<uuid> start <wss-url> <mix-type> <sampling-rate> <metadata>`).
- Cada frame binário recebido em `handle_forked_stream` contém **os dois canais intercalados** (amostra par = canal A, amostra ímpar = canal B) — não é "um frame = um canal". A separação tx/rx é feita por *de-interleaving* de cada frame, não por inspeção de metadado por frame.
- 🟡 **Pendência de validação:** qual canal (A ou B) corresponde ao agente (`tx`) vs cliente (`rx`) não está documentado pelo módulo. Convenção adotada (canal A = `tx`/agente, canal B = `rx`/cliente), consistente com o uso de "tx" no whisper mode, mas **precisa ser confirmada contra FreeSWITCH real** antes de produção.

## Fluxo Principal

1. FreeSWITCH fork do áudio e envia via WebSocket — evento CHANNEL_ANSWER
2. `handle_forked_stream()` é chamada com call_id e WebSocket — `src/audio/ingestor.py:30-40`
3. Metadados do stream são registrados — `src/audio/ingestor.py:63-68`
4. Frames estéreo PCM16 são recebidos em loop
5. Cada frame é de-interleado em dois `AudioChunk` (`tx` e `rx`) — `src/audio/ingestor.py`
6. Chunks publicados no Redis Stream `call:events` — `src/audio/ingestor.py:45-55`

## Riscos e Lacunas

- 🟡 Convenção de canal A=tx/B=rx assumida, não validada contra FreeSWITCH real (ver seção de protocolo acima)
- 🟡 Sem bufferização robusta — chunks pequenos podem causar sobrecarga de mensagens no Redis
