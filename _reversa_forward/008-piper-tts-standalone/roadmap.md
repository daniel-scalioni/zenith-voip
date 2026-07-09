# Roadmap: Piper TTS como Processo Local

> Identificador: `008-piper-tts-standalone`
> Data: `2026-07-09`
> Requirements: `_reversa_forward/008-piper-tts-standalone/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

`src/services/tts_service.py::PiperTTS` hoje é um cliente HTTP para um microserviço Docker (`piper-tts`) cuja imagem nunca existiu (GAP-18). A correção troca a integração por chamada direta à API Python do pacote `piper-tts==1.4.2` (PyPI, projeto `OHF-Voice/piper1-gpl`, ativo), eliminando tanto o serviço Docker quebrado quanto o pin antigo (`1.2.0`) que dependia do pacote nativo `piper-phonemize` (indisponível, causa raiz do GAP-18). O modelo de voz `pt_BR` é baixado uma vez via `python3 -m piper.download_voices` e persistido fora do git. A chamada síncrona da API Python roda via `asyncio.to_thread()` para não bloquear o event loop do FastAPI. O contrato público (`TTSWithFallback.synthesize()`) não muda — só a implementação interna de `PiperTTS`.

## 2. Princípios aplicados

`.reversa/principles.md` vazio — feature segue apenas as convenções do `CLAUDE.md`.

| Princípio | Como a feature se relaciona | Status |
|-----------|------------------------------|--------|
| n/a — `principles.md` vazio | — | n/a |

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|----------------|---------------------------|-------------|
| D-01 | Trocar `piper-tts==1.2.0` (quebrado) por `piper-tts==1.4.2` (PyPI, `OHF-Voice/piper1-gpl`) | Testado nesta sessão: instala limpo, sem `piper-phonemize`; projeto ativo e é o sucessor oficial do Piper original | Vendorizar binário bruto do GitHub Releases (mais complexo, sem necessidade já que existe wheel PyPI); `rhasspy/wyoming-piper` via Docker (exigiria reescrever cliente para protocolo Wyoming) | 🟢 |
| D-02 | Usar a API Python (`PiperVoice.load()` / `synthesize_wav()`) em vez de subprocess ou HTTP | API nativa do pacote, mais simples e sem overhead de processo externo ou rede | Subprocess CLI do piper (mais complexo sem benefício); manter microserviço HTTP (era o design quebrado original) | 🟢 |
| D-03 | Rodar a chamada síncrona via `asyncio.to_thread()` dentro do método `async synthesize()` | Evita bloquear o event loop do FastAPI durante a inferência ONNX (CPU-bound) | Rodar diretamente no event loop (bloquearia outras requisições durante a síntese) | 🟢 |
| D-04 | Remover o serviço `piper-tts` de `docker-compose.app.yml` inteiramente | Serviço nunca funcionou; a nova abordagem não precisa de container separado | Corrigir a imagem para `rhasspy/wyoming-piper` (descartado por D-01/D-02) | 🟢 |
| D-05 | Modelo de voz `pt_BR` baixado em `audio/voices/`, fora do git | Mesmo padrão já usado para `freeswitch/vendor/debs/` (binários grandes, gitignored) | Empacotar o modelo na imagem Docker (aumentaria o tamanho da imagem desnecessariamente) | 🟢 |

## 4. Premissas

Nenhuma — todas as dúvidas do `requirements.md` foram resolvidas antes deste plano.

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-------------------|--------|
| `PiperTTS` (`src/services/tts_service.py`) | `_reversa_sdd/services/tts/design.md` | contrato-alterado | Implementação interna muda de cliente HTTP para chamada de API Python; assinatura pública `synthesize()` preservada |
| Serviço Docker `piper-tts` (`docker-compose.app.yml`) | — | componente-extinto | Removido — nunca funcionou, substituído por dependência pip local |
| `PIPER_TTS_URL` (`src/config.py`) | — | regra-removida | Variável de configuração deixa de ser necessária |
| `requirements.txt` | — | regra-alterada | `piper-tts==1.2.0` → `piper-tts==1.4.2` |

## 6. Delta no modelo de dados

- Resumo: nenhuma mudança em banco de dados. O "dado" novo é o modelo de voz `.onnx`/`.onnx.json` baixado em `audio/voices/`, tratado como artefato de infraestrutura, não dado de aplicação.
- Detalhe completo em: `_reversa_forward/008-piper-tts-standalone/data-delta.md`

## 7. Delta de contratos externos

Nenhum contrato HTTP/fila/gRPC/GraphQL externo afetado — a mudança elimina um contrato HTTP interno (`piper-tts` microserviço), não cria nem altera nenhum contrato externo. Pasta `interfaces/` omitida.

## 8. Plano de migração

1. Atualizar `requirements.txt`: `piper-tts==1.2.0` → `piper-tts==1.4.2`.
2. Baixar o modelo de voz `pt_BR` via `python3 -m piper.download_voices` para `audio/voices/` (gitignored).
3. Reescrever `src/services/tts_service.py::PiperTTS` para usar `PiperVoice.load()`/`synthesize_wav()` via `asyncio.to_thread()`, mantendo a assinatura `synthesize(text, voice, speaker_id) → bytes`.
4. Remover o serviço `piper-tts` de `docker-compose.app.yml` e a variável `PIPER_TTS_URL` de `src/config.py`.
5. Testar `pip install --dry-run -r requirements.txt` sem travar.
6. Testar síntese real (RF-05): confirmar que `TTSWithFallback.synthesize()` retorna WAV válido.
7. Atualizar `_reversa_sdd/gaps.md#GAP-18` e `_reversa_sdd/services/tts/design.md`.

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|-----------------|-----------|
| Modelo de voz `pt_BR` grande demais para o volume/disco do host | baixo | baixo | Modelos Piper são tipicamente 20-60MB, bem menores que os `.deb` do FreeSWITCH já vendorizados nesta sessão |
| `asyncio.to_thread()` não ser suficiente sob alta concorrência (muitas chamadas simultâneas de síntese) | médio | baixo | Fora do MVP (usuário confirmou que TTS não é crítico agora); revisitar se filler audio/whisper mode virarem uso intenso |
| Qualidade da voz `pt_BR` disponível não ser satisfatória | baixo | médio | Piper tem múltiplas vozes pt_BR (ex: faber); trocar o modelo é reconfiguração simples, não mudança de código |

## 10. Critério de pronto

- [ ] Todas as ações do `actions.md` marcadas `[X]`
- [ ] `regression-watch.md` gerado
- [ ] `pip install -r requirements.txt` não trava mais no `piper-phonemize`/`piper-tts`
- [ ] `docker compose config` não lista mais o serviço `piper-tts` quebrado
- [ ] Teste real de síntese confirma WAV válido (RF-05)
- [ ] `GAP-18` atualizado em `_reversa_sdd/gaps.md`
- [ ] Re-extração reversa executada e sem regressão vermelha (recomendado, não obrigatório)

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-07-09 | Versão inicial gerada por `/reversa-plan` | reversa |
