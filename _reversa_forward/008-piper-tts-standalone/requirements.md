# Requirements: Piper TTS como Processo Local (sem microserviço quebrado)

> Identificador: `008-piper-tts-standalone`
> Data: `2026-07-09`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

O serviço de TTS do Zenith (`src/services/tts_service.py::PiperTTS`) é um cliente HTTP que depende de um microserviço `piper-tts` cuja imagem Docker (`rhasspy/piper-tts:2023.11.14`, declarada em `docker-compose.app.yml`) **não existe** — descoberto ao tentar deployar `zenith-api-1` durante a feature `007-audio-stream-migration` (GAP-18). O pacote pip `piper-tts==1.2.0` em `requirements.txt` também é dead weight (nada importa esse pacote — a integração é via HTTP, não via biblioteca Python). Esta feature substitui a arquitetura de microserviço quebrado por Piper rodando como **binário local** (baixado do GitHub Releases oficial do projeto Piper, com modelo de voz `pt_BR`), invocado via `subprocess` diretamente no processo que hoje faria a chamada HTTP — eliminando o hop de rede e a dependência de uma imagem Docker de terceiros que nunca funcionou.

## 2. Contexto a partir do legado

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `_reversa_sdd/services/tts/design.md` | `TTSStrategy: synthesize(text, voice, speaker_id) → bytes`, implementações `PiperTTS` (primário) e `WavFallback` (local) | 🟢 |
| `src/services/tts_service.py::PiperTTS` | Cliente HTTP (`httpx.AsyncClient`) chamando `POST {PIPER_TTS_URL}/synthesize`; `PIPER_TTS_URL` default `http://piper-tts:5000` (`src/config.py:19`) | 🟢 |
| `src/services/tts_fallback.py::TTSWithFallback` | Encapsula `PiperTTS`, cai para WAV local (`audio/<key>.wav`) em qualquer exceção | 🟢 |
| `docker-compose.app.yml` (serviço `piper-tts`) | `image: rhasspy/piper-tts:2023.11.14` — tag/repositório inexistente, `docker compose up` falha com "pull access denied" (validado nesta sessão, 2026-07-09) | 🟢 |
| `requirements.txt` | `piper-tts==1.2.0` listado mas não importado em nenhum lugar de `src/` (verificado nesta sessão) | 🟢 |
| `_reversa_sdd/gaps.md#GAP-18` | Registra que `zenith-api-1` nunca foi buildado com sucesso neste host antes de 2026-07-09, e que o bloqueio do `piper-tts` ficou pendente | 🟢 |
| Pesquisa nesta sessão (GitHub/Docker Hub) | `rhasspy/wyoming-piper` existe e é mantido, mas fala protocolo Wyoming (TCP+JSON), não REST — exigiria reescrever o cliente para outro protocolo | 🟢 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| Zenith AI Audio Hub (sistema) | Sintetizar voz em pt-BR para o modo whisper/filler audio durante uma chamada | `whisper_mode.py`/`filler_audio.py` chamam `TTSWithFallback.synthesize()` e recebem áudio sem depender de um serviço externo indisponível |
| Operador de infraestrutura (Daniel) | Não ter mais um serviço fantasma no `docker-compose.app.yml` que nunca sobe | `docker compose up` não tenta mais puxar uma imagem inexistente |

## 4. Regras de negócio novas ou alteradas

1. **RN-01:** A síntese de voz primária (Piper) DEVE rodar como processo local (binário + modelo `.onnx`), sem depender de um serviço HTTP externo. 🟢
   - Origem no legado: `_reversa_sdd/services/tts/design.md` (regra alterada — mecanismo de execução muda, contrato `synthesize(text, voice, speaker_id) → bytes` permanece)
   - Tipo: alterada
2. **RN-02:** O fallback para WAV local (`TTSWithFallback`) DEVE continuar funcionando sem alteração de comportamento. 🟢
   - Origem no legado: `src/services/tts_fallback.py`
   - Tipo: nova (restrição de compatibilidade)
3. **RN-03:** O binário e o modelo de voz Piper DEVEM ser obtidos de fontes oficiais (GitHub Releases do projeto Piper), sem depender de uma imagem Docker de terceiros não mantida. 🟢
   - Origem: requisito explícito do usuário, motivado pela descoberta do GAP-18
   - Tipo: nova
4. **RN-04:** O serviço `piper-tts` (imagem quebrada) e o pacote pip não utilizado `piper-tts==1.2.0` DEVEM ser removidos de `docker-compose.app.yml` e `requirements.txt`. 🟢
   - Tipo: removida

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| RF-01 | Atualizar `requirements.txt` para `piper-tts==1.4.2` (pacote pip real, `OHF-Voice/piper1-gpl`) e baixar um modelo de voz `pt_BR` (`.onnx` + `.onnx.json`) via `python3 -m piper.download_voices`, persistido em `audio/voices/` (gitignored) | Must | `pip install` limpo; modelo presente em `audio/voices/` | 🟢 |
| RF-02 | Reescrever `src/services/tts_service.py::PiperTTS` para invocar o binário local via `subprocess` em vez de HTTP, mantendo a assinatura `synthesize(text, voice, speaker_id) → bytes` | Must | `TTSWithFallback.synthesize()` continua funcionando sem mudança de assinatura para os chamadores | 🟢 |
| RF-03 | Remover o serviço `piper-tts` de `docker-compose.app.yml` e a variável `PIPER_TTS_URL` de `src/config.py` (ou marcá-la deprecated) | Must | `docker compose config` não lista mais o serviço `piper-tts`; `docker compose up` não tenta puxar a imagem quebrada | 🟢 |
| RF-04 | Remover `piper-tts==1.2.0` de `requirements.txt` | Must | `pip install --dry-run -r requirements.txt` não trava mais no `piper-phonemize` | 🟢 |
| RF-05 | Teste real: sintetizar um texto em pt-BR e confirmar que o áudio resultante é um WAV válido, não vazio | Must | Chamada de teste retorna bytes de áudio reproduzíveis | 🔴 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| Segurança/Privacidade | Síntese de voz continua 100% local, sem chamada a serviço de terceiros na nuvem | Consistente com ADR-003 (dados sensíveis nunca saem do ambiente local) — mesmo que o texto sintetizado não seja necessariamente sensível, mantém a mesma postura arquitetural do projeto (Ollama local para LLM) | 🟢 |
| Desempenho | Latência de síntese via subprocess local deve ser igual ou menor que via HTTP para um serviço na mesma rede (elimina round-trip de rede) | Inferência lógica, não medida | 🟡 |
| Portabilidade | O binário vendorizado deve ser compatível com a arquitetura do host de produção (linux/amd64, mesmo padrão já usado no build do FreeSWITCH) | `_reversa_forward/007-audio-stream-migration` já estabeleceu esse padrão | 🟢 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Síntese de voz bem-sucedida
  Dado que o binário piper e o modelo pt_BR estão vendorizados no projeto
  Quando TTSWithFallback.synthesize("Aguarde um momento") é chamado
  Então retorna bytes de áudio WAV válidos e não vazios

Cenário: Fallback continua funcionando
  Dado que o binário piper está ausente ou falha
  Quando TTSWithFallback.synthesize() é chamado com fallback_key válido
  Então retorna o WAV de fallback local, sem lançar exceção

Cenário: docker compose sobe sem tentar puxar imagem quebrada
  Dado docker-compose.app.yml atualizado
  Quando "docker compose config" é executado
  Então nenhum serviço "piper-tts" aparece na lista de serviços

Cenário: Build da API não trava mais no piper-phonemize
  Dado requirements.txt sem piper-tts==1.2.0
  Quando pip install -r requirements.txt roda
  Então a instalação não falha por causa do piper-phonemize
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|----------------|
| RF-04 — remover pip piper-tts | Must | Bloqueia o build de `zenith-api-1` (GAP-18), prioridade máxima |
| RF-03 — remover serviço Docker quebrado | Must | Elimina confusão operacional (serviço que nunca sobe) |
| RF-01/RF-02 — Piper local via subprocess | Must | Sem isso, TTS fica sem implementação funcional nenhuma |
| RF-05 — teste real de síntese | Should | Importante para confiança, mas MVP já não depende de TTS conforme o usuário |

## 9. Esclarecimentos

### Sessão 2026-07-09 (resolução autônoma, autorizada explicitamente pelo usuário)

- **Q:** Qual repositório usar para o Piper?
  **R:** Nem é preciso vendorizar binário bruto. `OHF-Voice/piper1-gpl` (fork ativo, mantido pela Open Home Foundation, sucessor do `rhasspy/piper` original) publica **wheels prontos no PyPI** como pacote `piper-tts`, versão atual `1.4.2` — instala limpo via `pip install piper-tts==1.4.2` (testado nesta sessão, sem depender de `piper-phonemize`, que era a causa do bloqueio original). O pin antigo (`1.2.0`) era uma versão pré-migração, dependente do pacote quebrado.

- **Q:** Onde vendorizar binário + modelo de voz?
  **R:** Não precisa vendorizar binário — é um pacote pip normal. Só o **modelo de voz** (`.onnx` + `.onnx.json`, pt_BR) precisa ser baixado (via `python3 -m piper.download_voices`) e persistido em `audio/voices/` (mesmo padrão de diretório já usado para os WAVs de fallback em `src/services/tts_fallback.py`), fora do git por ser binário grande.

- **Q:** subprocess bloqueante ou API Python direta?
  **R:** API Python direta (`PiperVoice.load()` + `voice.synthesize_wav()`), sem subprocess — o pacote `piper-tts` 1.4.2 expõe uma API Python nativa (`from piper import PiperVoice`), mais simples e sem overhead de processo externo. Para não bloquear o event loop do FastAPI, a chamada síncrona deve rodar via `asyncio.to_thread()`.

## 10. Lacunas

- 🟢 Fonte do Piper: pacote pip `piper-tts==1.4.2` (PyPI, projeto `OHF-Voice/piper1-gpl`), não binário vendorizado.
- 🟢 Modelo de voz: baixado via `python3 -m piper.download_voices pt_BR-<voz>-medium`, persistido em `audio/voices/` (gitignored).
- 🟢 Integração: API Python (`PiperVoice`), executada via `asyncio.to_thread()` dentro do método `async synthesize()`.

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-07-09 | Versão inicial gerada por `/reversa-requirements` | reversa |
