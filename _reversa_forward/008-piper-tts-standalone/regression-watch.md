# Regression Watch: Piper TTS como Processo Local

> Identificador: `008-piper-tts-standalone`

## Itens de observação

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|--------------------------|-------------------------------|------------------------|---------------------|
| W001 | `_reversa_sdd/services/tts/design.md` | `TTSStrategy.synthesize(text, voice, speaker_id) → bytes` continua com a mesma assinatura pública, independente da implementação interna | presença | Chamadores de `TTSWithFallback.synthesize()` (`whisper_mode.py`, `filler_audio.py`) quebram por mudança de assinatura |
| W002 | `requirements.txt` | `pip install -r requirements.txt` resolve sem erro, sem pins mortos ou conflitantes | presença | Nova adição a `requirements.txt` reintroduz `piper-phonemize`, `greenswitch`, `redis-streams` ou pin de `redis` incompatível com `arq`/`langgraph-checkpoint-redis` |
| W003 | `docker-compose.app.yml` | Nenhum serviço `piper-tts` (ou imagem inexistente equivalente) presente | ausência | Serviço `piper-tts` reaparece no compose apontando para uma imagem não verificada |
| W004 | `audio/voices/pt_BR-faber-medium.onnx` | Modelo de voz vendorizado presente e carregável por `PiperVoice.load()` | presença | `PiperTTS.health()` retorna `false` porque o arquivo do modelo foi removido ou corrompido |

## Observações (confidência 🟡/🔴, sem peso de regressão)

- 🟡 Teste de síntese real (T008) rodou num container Python isolado com o pacote instalado ad-hoc, não dentro do container `zenith-api-1` de fato buildado (que segue bloqueado por outros motivos não relacionados ao TTS — build completo da imagem da aplicação ainda não validado ponta a ponta).
- 🟡 Qualidade da voz `pt_BR-faber-medium` não avaliada subjetivamente — só validado que gera áudio, não a qualidade percebida.

## Histórico de re-extrações

_Vazio — será preenchido na próxima execução de `/reversa` (extração reversa)._

## Arquivadas

_Vazio._
