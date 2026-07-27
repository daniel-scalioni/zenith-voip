# Módulo: services

> Gerado pelo Archaeologist — 2026-06-19
> **Re-extração incremental — 2026-07-27** (base `48da5b1` → `0658157`, deltas D-05/D-09)
> Confiança: 🟢 CONFIRMADO

## Arquivos

| Arquivo | Propósito | Linhas |
|---------|-----------|--------|
| `src/services/base.py` | Interfaces: Strategy, Repository, Factory | 80 |
| `src/services/calls.py` 🆕 | Ciclo de vida da entidade `Call` por tenant | 39 |
| `src/services/stt_autofallback.py` | AutoFallback STT (Deepgram → Whisper) | 28 |
| `src/services/stt_deepgram.py` | Deepgram STT (cloud) | 44 |
| `src/services/stt_whisper.py` | Whisper.cpp STT (local) | 40 |
| `src/services/tts_service.py` | Piper TTS **in-process** (era HTTP) | 33 |
| `src/services/tts_fallback.py` | TTS com fallback WAV local | 27 |

## Fluxo de Controle

### base.py — Padrões
- `Strategy` (ABC): interface execute()
- `STTStrategy` (ABC): transcribe()
- `TTSStrategy` (ABC): synthesize()
- `LLMStrategy` (ABC): analyze()
- `Repository[ModelType]`: CRUD genérico com SQLAlchemy AsyncSession
- `Factory` (ABC): create_pipeline(tenant_id)

### stt_autofallback.py — Algoritmo de Fallback
1. Tenta DeepgramSTT com timeout (500ms configurável)
2. Se timeout ou erro ou confidence <= 0.3 → fallback para WhisperCppSTT
3. Marca fallback_activated no resultado

### stt_deepgram.py
- Usa Deepgram SDK com model nova-2, language pt, diarize, punctuate
- Retorna: text, confidence, words (com word, start, end, speaker)

### stt_whisper.py
- Executa whisper-cpp via subprocess com arquivo temporário
- Retorna: text, confidence (avg_logprob), segments

### calls.py 🆕
Serviço de ciclo de vida da chamada, consumido pelos handlers ESL (`telephony`):

- `_tenant_schema(tenant_id)` → `f"tenant_{tenant_id}"` — convenção de schema-per-tenant
  (ver ADR-001) materializada aqui em código, não mais só na camada de banco.
- `create_call_record(tenant_id, call_id, pbx_id, agent_extension)` → abre sessão via
  `get_tenant_db(schema)`, usa `Repository(session, Call)` e cria a linha com
  `direction=inbound` e `status=in_progress`. **Não é idempotente** — é por isso que apenas
  a instância `INSTANCE_ID==1` conecta ao ESL (ver `main.py`).
- `finalize_call_record(tenant_id, call_id)` → busca por `call_id`, e se existir atualiza
  para `status=completed`, `ended_at=now(utc)` e `duration_seconds = ended_at - started_at`.
  Se não achar, retorna em silêncio (chamada sem registro prévio não gera erro).

### tts_service.py (🔄 reescrito)
- Deixou de ser cliente HTTP de um microserviço Piper e passa a carregar o modelo
  **no próprio processo**: `PiperVoice.load(settings.PIPER_VOICE_PATH)`.
- `_load_voice()` é `@lru_cache(maxsize=1)` — o modelo ONNX é carregado uma vez e reusado.
- `synthesize()` delega a `asyncio.to_thread(self._synthesize_sync, text)` para não bloquear
  o event loop; o WAV é montado em memória (`io.BytesIO` + `wave`).
- `health()` agora só confirma que o modelo carrega; o método `close()` deixou de existir.
- Os parâmetros `voice` e `speaker_id` continuam na assinatura, mas **são ignorados** —
  a voz é definida por `PIPER_VOICE_PATH` (`pt_BR-faber-medium.onnx`). 🔴 LACUNA
- Consequência arquitetural: o container `piper-tts` foi removido do compose (ver `infra`).

### tts_fallback.py
- `TTSWithFallback`: tenta `PiperTTS`, se falhar → carrega WAV local do disco.

## Regras de Negócio

| Regra | Local | Confiança |
|-------|-------|-----------|
| Fallback STT se timeout > 500ms | `stt_autofallback.py:14-15` | 🟢 |
| Fallback STT se confidence <= 0.3 | `stt_autofallback.py:20` | 🟢 |
| Deepgram model: nova-2, pt-BR | `stt_deepgram.py:15-19` | 🟢 |
| Whisper local via subprocess | `stt_whisper.py:22-36` | 🟢 |
| TTS fallback para WAV local se Piper falhar | `tts_fallback.py:13-17` | 🟢 |
| 🆕 Schema do tenant é `tenant_<tenant_id>` | `calls.py:7-8` | 🟢 |
| 🆕 Chamada nasce `inbound` / `in_progress` | `calls.py:16-17` | 🟢 |
| 🆕 `duration_seconds` é calculado no hangup, não medido durante a chamada | `calls.py:32` | 🟢 |
| 🆕 Hangup de chamada sem registro prévio é ignorado silenciosamente | `calls.py:26-28` | 🟢 |
| 🆕 Modelo Piper carregado uma única vez por processo (`lru_cache`) | `tts_service.py:9-11` | 🟢 |
| 🆕 `voice`/`speaker_id` de `synthesize()` são ignorados | `tts_service.py:19-20` | 🔴 LACUNA |
