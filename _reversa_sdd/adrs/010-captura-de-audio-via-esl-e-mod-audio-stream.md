# ADR-010: Captura de áudio por `mod_audio_stream` disparada via ESL, não pelo dialplan

**Data:** 2026-07-15 (retroativo — registrado na re-extração de 2026-07-27)
**Status:** Aceito
**Contexto:** zenith-voip — módulos `telephony`, `audio`, `infra`
**Commits de origem:** `3585470`, `a9f0a0a`, `766ad24`, `4016923`

---

## Contexto

Duas forças independentes convergiram para a mesma mudança.

**1. O módulo de captura morreu.** O `mod_audio_fork` vinha do repositório
`drachtio-freeswitch-modules`, que foi **descontinuado**. Sem upstream, não havia como
manter o build do FreeSWITCH nem corrigir bugs do módulo.

**2. O disparo pelo dialplan não funcionava.** A captura era uma ação da extensão
`zenith_audio_fork`:

```xml
<action application="mod_audio_fork" data="ws://zenith-api-1:8000/audio-stream start ${uuid} both"/>
```

Isso trazia três problemas encadeados:

- As variáveis `zenith_tenant_id` e `zenith_pbx_id` eram lidas como `${tenant_id}` (variável
  **de canal**, inexistente naquele instante) em vez de `$${tenant_id}` (variável **global**).
  Chegavam vazias ao `CHANNEL_ANSWER`, e o guard `if tenant_id:` do ESLClient descartava a
  chamada em silêncio — nenhuma linha `Call`, nenhuma gravação.
- A ordem das ações estava errada: o `mod_audio_fork` era invocado antes do `answer`, quando
  ainda não há mídia estabelecida para capturar.
- O dialplan não tem como saber se a API está de pé. Falha de captura era invisível — sem
  retorno, sem log do lado da aplicação.

## Decisão

1. Substituir `mod_audio_fork` por **`mod_audio_stream`**, compilado em **build próprio** do
   FreeSWITCH (`freeswitch/Dockerfile`, `.deb` vendorizados, secret `signalwire_token`).
2. **Tirar a captura do dialplan.** O `ESLClient` passa a disparar, no handler de
   `CHANNEL_ANSWER`:
   ```
   bgapi uuid_audio_stream <call_id> start ws://<AUDIO_STREAM_CALLBACK_HOST>/audio-stream/<call_id> stereo 8k <metadata>
   ```
3. Corrigir o dialplan: `$${tenant_id}`/`$${pbx_id}` (globais, definidos em `vars.xml`),
   `answer` antes de `start_dtmf`, e bridge direto para `sofia/gateway/upstream-<ext>/<dest>`.
4. Adicionar **healthcheck de módulo** ao container:
   `fs_cli -x 'module_exists mod_audio_stream' | grep -q true`.

## Justificativa

Mover o disparo para a aplicação inverte quem tem a informação. O ESLClient sabe se o tenant
foi resolvido, sabe se a linha `Call` foi criada, recebe a resposta do comando e pode logar
`-ERR`. O dialplan não sabe nada disso — ele só sabe casar um padrão de discagem.

O healthcheck de módulo entrou porque a imagem chegou a rodar **24 horas "healthy" em
produção sem `mod_audio_stream` carregado**, sem nenhum sinal (GAP-24). Um healthcheck que
não verifica a única coisa que o container precisa fazer não é um healthcheck.

## Consequências

**Positivas**
- Captura só começa quando há mídia estabelecida e tenant resolvido — a ordem passou a ser
  garantida pelo código, não pela ordem das linhas de um XML.
- Falha de `uuid_audio_stream` é observável (`logger.warning` com a resposta do FreeSWITCH).
- O `call_id` na URL do WebSocket é o que permite o guard de autorização do `AudioIngestor`
  (fecha 4401 para `call_id` não registrado).
- Build próprio elimina a dependência de uma imagem pública com módulo descontinuado.

**Negativas**
- 🔴 A captura passou a depender do **socket de comandos ESL estar saudável**. Foi
  necessário separar a conexão de comandos da de eventos: as duas no mesmo socket causavam
  corrida entre o event loop e a resposta de um `bgapi` disparado de dentro de um handler.
- 🔴 Se `fastapi-1` (a única instância que consome ESL) estiver fora, **nenhuma chamada é
  gravada** — mesmo com o FreeSWITCH e a `fastapi-2` perfeitamente saudáveis.
- O build do FreeSWITCH ficou mais lento e exige o `signalwire_token` disponível.
- `start_period: 90s` no healthcheck: o profile `upstream` carrega ~939 gateways no boot.

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Continuar com `mod_audio_fork` | Repositório descontinuado, sem correções |
| Manter o disparo no dialplan, só corrigindo as variáveis | Resolveria o sintoma; a falha de captura continuaria invisível para a aplicação |
| `mod_audio_stream` invocado por dialplan | Mesmo problema de observabilidade e ordenação |

## Relacionados

- [ADR-005](005-freewitch-esl-reconexao-automatica.md) — a robustez do ESL virou pré-requisito da captura
- [ADR-007](007-validacao-e2e-chamada-real.md) — validação E2E que expôs os bugs de dialplan
- [ADR-009](009-gravacao-local-tmpfs-substitui-s3.md) — destino do áudio capturado
- `_reversa_sdd/telephony/legacy-mapping.md`, `_reversa_sdd/flowcharts/telephony-flow.md`
