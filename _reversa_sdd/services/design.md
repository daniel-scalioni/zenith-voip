# Services, Design Técnico

> Gerado pelo Writer — 2026-06-19

## Interface

| Símbolo | Assinatura | Retorno |
|---------|-----------|---------|
| `transcribe` | `(audio_chunk: bytes)` | `dict` |
| `synthesize` | `(text: str, voice: str, speaker_id: str)` | `bytes` |

### Strategy Pattern

| Interface | Implementações |
|-----------|---------------|
| STTStrategy | DeepgramSTT, WhisperSTT |
| TTSStrategy | PiperTTS, WavFallback |
| LLMStrategy | OllamaLLM |

## Fluxo Principal (STT)

1. `stt_autofallback.transcribe()` recebe áudio — `src/services/stt_autofallback.py:10`
2. Tenta Deepgram com timeout de 500ms — `src/services/stt_autofallback.py:14-15`
3. Se timeout ou confidence <= 0.3, fallback para Whisper — `src/services/stt_autofallback.py:20`

## Fluxo Principal (TTS)

1. `tts_service.synthesize()` recebe o texto — `src/services/tts_service.py:19-20`
   ⚠️ Os parâmetros `voice` e `speaker_id` continuam na assinatura mas **são ignorados**: a voz
   é definida por `PIPER_VOICE_PATH` (GAP-RE-10)
2. Delega a `asyncio.to_thread(_synthesize_sync)` para não bloquear o event loop
3. `_load_voice()` (`@lru_cache(maxsize=1)`) carrega o modelo ONNX uma vez por processo
4. `PiperVoice.synthesize_wav()` escreve num `io.BytesIO` — **in-process**, sem HTTP
5. Se falhar, `tts_fallback.synthesize()` retorna WAV local — `src/services/tts_fallback.py:13-17`

> 🔄 **Mudança 2026-07-09** (feature `008-piper-tts-standalone`): o `PiperTTS` era um cliente
> HTTP (`POST http://piper-tts:5000/synthesize`) de um microserviço que nunca subiu de forma
> estável. Passou a rodar dentro do processo FastAPI; o container `piper-tts` foi removido do
> compose e o método `close()` deixou de existir.

## Dependências

- `extraction` — entidades extraídas usadas em contexto de LLM
- `events` — resultados de STT publicados em stream

## Riscos e Lacunas

- 🟡 DEEPGRAM_API_KEY vazia por padrão — sistema opera sempre em fallback
- 🟡 Sem cache de resultados de STT para chunks idênticos


---

## Ciclo de vida da chamada (`services/calls.py`) 🆕

> Componente novo na re-extração de 2026-07-27 (delta D-05).

| Função | Assinatura | Retorno |
|---|---|---|
| `_tenant_schema` | `(tenant_id: str)` | `str` — `tenant_<id>` |
| `create_call_record` | `(tenant_id, call_id, pbx_id, agent_extension)` | `None` |
| `finalize_call_record` | `(tenant_id, call_id)` | `None` |

**Fluxo**

1. `get_tenant_db(schema)` abre a sessão com `search_path` no schema do tenant
2. `Repository(session, Call)` — nenhum SQL solto, conforme o padrão do projeto
3. `create_call_record`: cria com `direction=inbound`, `status=in_progress`
4. `finalize_call_record`: `find_by(call_id)`; se não achar, retorna em silêncio; se achar,
   atualiza `status=completed`, `ended_at=now(utc)` e
   `duration_seconds = ended_at - started_at`

**Restrições**

- 🔴 `create_call_record` **não é idempotente**. É essa característica que obriga apenas
  `INSTANCE_ID == 1` a consumir o ESL (GAP-RE-01)
- 🔴 `duration_seconds` é derivado, não medido — se `started_at` for nulo, fica nulo
- 🔴 Nenhum caminho atribui `failed` ou `ringing` (GAP-RE-02)
