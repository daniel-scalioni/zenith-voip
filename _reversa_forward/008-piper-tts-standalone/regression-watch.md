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

### Re-extração 2026-07-27 (incremental, base 48da5b1 → 0658157)

| ID | Veredito | Observação |
|----|----------|------------|
| W001 | 🟢 verde | `synthesize(text, voice="pt_BR", speaker_id=0) -> bytes` preservado. ⚠️ Nota: `voice` e `speaker_id` são aceitos mas **ignorados** (GAP-RE-10) — a assinatura sobreviveu, a semântica não |
| W002 | 🟢 verde | `grep` em `requirements.txt` não encontra `piper-phonemize`, `greenswitch`, `redis-streams` nem `langgraph-checkpoint-redis` |
| W003 | 🟢 verde | Nenhum serviço `piper-tts` no compose — só um comentário registrando a remoção |
| W004 | 🟡 amarelo | `audio/voices/` está no `.gitignore` e o diretório não existe neste checkout — o modelo é vendorizado fora do git. Não verificável por análise estática; requer checagem no ambiente de deploy |


_Vazio — será preenchido na próxima execução de `/reversa` (extração reversa)._

## Arquivadas

_Vazio._
