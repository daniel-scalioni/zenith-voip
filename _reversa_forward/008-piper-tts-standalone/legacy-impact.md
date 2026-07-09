# Legacy Impact: Piper TTS como Processo Local

> Identificador: `008-piper-tts-standalone`
> Data: `2026-07-09`
> Execução: completa — 9/9 ações concluídas e validadas

## Tabela de impacto

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|------------------|------------|------|------------|----------------|
| `requirements.txt` | Dependências da aplicação | regra-alterada | HIGH | `piper-tts` 1.2.0 → 1.4.2, resolve bloqueio de build (GAP-18) |
| `src/services/tts_service.py::PiperTTS` | Serviço TTS (`_reversa_sdd/services/tts/design.md`) | contrato-alterado | HIGH | Implementação interna muda de cliente HTTP para API Python local; assinatura pública preservada |
| `docker-compose.app.yml` (serviço `piper-tts`) | Deploy da aplicação | componente-extinto | MEDIUM | Serviço que nunca funcionou removido; volume `piper_models` também removido (não usado) |
| `src/config.py` | Configuração | regra-alterada | LOW | `PIPER_TTS_URL` → `PIPER_VOICE_PATH`; `FREESWITCH_ESL_HOST` default corrigido para `172.21.0.1` (consistência com a subnet corrigida nesta sessão) |
| `audio/voices/` (novo, gitignored) | Artefato de infraestrutura | componente-novo | LOW | Modelo de voz `pt_BR-faber-medium` (~63MB), vendorizado |
| `_reversa_sdd/gaps.md#GAP-18` | Documentação | regra-alterada | MEDIUM | De "parcialmente resolvida" para "✅ Resolvida" |
| `_reversa_sdd/services/tts/design.md` | Documentação | regra-alterada | LOW | Descreve a nova execução local |

## Diff conceitual por componente

**Serviço de TTS:** antes desta feature, `PiperTTS` era um cliente HTTP para um microserviço Docker cuja imagem nunca existiu — TTS estava, na prática, sempre indisponível (caía direto no fallback WAV local). Agora, `PiperTTS` carrega o modelo de voz localmente via API Python (`piper-tts==1.4.2`) e sintetiza em processo, sem rede nem serviço externo. O contrato observável para os chamadores (`whisper_mode.py`, `filler_audio.py` via `TTSWithFallback`) não muda.

**Cadeia de descoberta:** esta feature nasceu de uma investigação em cascata a partir da feature `007-audio-stream-migration` — ao tentar validar T009 (chamada real), descobriu-se que `zenith-api-1` nunca tinha sido buildado com sucesso no host, o que revelou GAP-18 (múltiplas dependências mortas/conflitantes em `requirements.txt`), do qual o bloqueio do `piper-tts` era a última peça.

## Preservadas

- 🟢 Interface `TTSStrategy: synthesize(text, voice, speaker_id) → bytes` — inalterada.
- 🟢 Comportamento de fallback (`TTSWithFallback`) — inalterado, continua caindo para WAV local em qualquer exceção.
- 🟢 Todas as correções da feature `007-audio-stream-migration` (mod_audio_stream, profiles SIP) — não afetadas por esta feature.

## Modificadas

- 🟡 GAP-18 — de "parcialmente resolvida" para "✅ Resolvida". Confidência 🟡 (não 🟢 plena) porque o build completo de `zenith-api-1` dentro do próprio `docker-compose` ainda não foi executado ponta a ponta nesta sessão (o teste de síntese rodou num container Python isolado, não no container final da aplicação).
