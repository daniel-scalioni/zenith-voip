# Actions: Piper TTS como Processo Local

> Identificador: `008-piper-tts-standalone`
> Data: `2026-07-09`
> Roadmap: `_reversa_forward/008-piper-tts-standalone/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 9 |
| Paralelizáveis (`[//]`) | 3 |
| Maior cadeia de dependência | 5 (T001 → T003 → T005 → T007 → T008) |

## Fase 1, Preparação

<!-- Atualização de dependências e vendorização do modelo de voz. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T001 | Atualizar `requirements.txt`: `piper-tts==1.2.0` → `piper-tts==1.4.2` | - | `[//]` | `requirements.txt` | 🟢 | `[X]` |
| T002 | Baixar o modelo de voz `pt_BR-faber-medium` via `python3 -m piper.download_voices` para `audio/voices/`, e adicionar `audio/voices/` ao `.gitignore` | - | `[//]` | `audio/voices/`, `.gitignore` | 🟢 | `[X]` |

## Fase 3, Núcleo

<!-- Reescrita da integração TTS. Sem fase de testes automatizados dedicada: projeto não tem suíte de TDD para serviços de áudio. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T003 | Reescrever `src/services/tts_service.py::PiperTTS`: substituir cliente HTTP por `PiperVoice.load()`/`synthesize_wav()` via `asyncio.to_thread()`, mantendo a assinatura `synthesize(text, voice, speaker_id) → bytes` | T001, T002 | - | `src/services/tts_service.py` | 🟢 | `[X]` |
| T004 | Ajustar `method health()` de `PiperTTS` para refletir a nova implementação local (ex: checar se o modelo carregou), já que não há mais endpoint HTTP `/health` remoto | T003 | - | `src/services/tts_service.py` | 🟢 | `[X]` |
| T005 | Remover o serviço `piper-tts` de `docker-compose.app.yml` e a variável `PIPER_TTS_URL` de `src/config.py` | - | `[//]` | `docker-compose.app.yml`, `src/config.py` | 🟢 | `[X]` |

## Fase 4, Integração

<!-- Validação real do build e da síntese. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T006 | Rodar `pip install --dry-run -r requirements.txt` e confirmar que resolve sem travar no `piper-phonemize`/`piper-tts` | T001 | - | `-` | 🟢 | `[X]` |
| T007 | Rodar `docker compose config --services` e confirmar que `piper-tts` não aparece mais na lista | T005 | - | `-` | 🟢 | `[X]` |
| T008 | Testar síntese real: `TTSWithFallback.synthesize("...")` retorna WAV válido e não vazio (RF-05) | T004, T006 | - | `-` | 🟡 | `[X]` |

## Fase 5, Polimento

<!-- Fechamento de gap e watch de regressão. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T009 | Atualizar `_reversa_sdd/gaps.md#GAP-18` e `_reversa_sdd/services/tts/design.md` para refletir a nova implementação, e gerar `regression-watch.md` | T007, T008 | - | `_reversa_sdd/gaps.md`, `_reversa_sdd/services/tts/design.md`, `_reversa_forward/008-piper-tts-standalone/regression-watch.md` | 🟢 | `[X]` |

## Notas de execução

<!-- Reservado para /reversa-coding registrar avisos ou observações que surgiram durante a execução. -->

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-07-09 | Versão inicial gerada por `/reversa-to-do` | reversa |
