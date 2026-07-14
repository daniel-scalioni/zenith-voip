# Investigation: Invocação de comandos de API do FreeSWITCH via ESL client

> Identificador: `009-api-invocation-via-esl-client`
> Data: `2026-07-14`

## 1. Pesquisa de fundo

O FreeSWITCH separa dois tipos de comando registrados por módulo:

- **Application**: invocável de dentro de um dialplan via `<action application="nome" data="...">`.
  Executa no contexto do canal da chamada.
- **API**: invocável via `fs_cli`, `mod_event_socket` (comandos `api`/`bgapi` na conexão ESL), ou
  `switch_api_execute()` internamente. Não depende de haver um canal de chamada ativo.

Um módulo pode registrar as duas formas para a mesma funcionalidade (ex.: `uuid_transfer` costuma
ter as duas), ou só uma delas. Observado nesta sessão via `fs_cli -x 'show application'` e
`fs_cli -x 'show modules'` em produção (10.10.10.11, 2026-07-13/14): `mod_audio_stream` registra
`uuid_audio_stream` **apenas como API** (`api,uuid_audio_stream,mod_audio_stream,...`), não como
Application.

Historicamente, a forma padrão de FreeSWITCH para invocar um comando de API a partir de um dialplan
é a Application genérica `api` (ex.: `<action application="api" data="uuid_transfer ...">`),
normalmente registrada por `mod_dptools`. Essa Application, porém, **não está presente** no build em
produção — confirmado por `show application` não listá-la em nenhum módulo carregado. O conjunto de
módulos carregados neste ambiente (`freeswitch/conf/autoload_configs/modules.conf.xml`) é
deliberadamente mínimo: `mod_commands`, `mod_conference`, `mod_dptools`, `mod_event_socket`,
`mod_sofia`, `mod_spandsp`, mais `mod_audio_stream` (compilado sob medida no `freeswitch/Dockerfile`
para substituir o descontinuado `mod_audio_fork`, feature `007-audio-stream-migration`). Não há
`mod_lua`, `mod_python`, `mod_xml_curl` nem qualquer outro módulo de scripting/API-bridge.

## 2. Alternativas avaliadas

| Alternativa | Por que foi descartada |
|-------------|-------------------------|
| Adicionar `mod_lua` (ou outro scripting engine) ao build e invocar `uuid_audio_stream` via script Lua no dialplan | Infla a imagem Docker do FreeSWITCH (novo módulo + runtime), introduz uma segunda linguagem no projeto (CLAUDE.md define Python como a linguagem do projeto), e resolve só o caso pontual — não estabelece um padrão reutilizável para o próximo módulo API-only |
| Investigar por que `mod_dptools` não registra a Application `api` neste build e tentar "consertar" isso na imagem (patch/rebuild) | Aumenta a superfície de manutenção da imagem customizada do FreeSWITCH (já documentada como fonte de fragilidade em GAP-11, `_reversa_sdd/gaps.md`) para resolver um problema que o projeto já tem infraestrutura pronta para resolver de outro jeito |
| Manter a invocação no dialplan usando `bgapi` em vez de `api` como nome da Application | Mesma causa raiz — nenhuma das duas está registrada como Application neste build, ambas só existem como comando de API |
| Disparar via ESLClient (escolhida) | Reaproveita `send_api`/`send_bgapi`, já implementados e testados em uso (`_handle_manual_linkage`, mapeamento SIP); o ESLClient já é o consumidor natural do evento `CHANNEL_ANSWER` que carrega o `call_id` e as variáveis de tenant/pbx/agente necessárias |

## 3. Padrão geral extraído (aplica-se além deste caso)

Regra adotada (RN-01 do `requirements.md`): **qualquer comando de API do FreeSWITCH que dependa de
contexto por-chamada, quando não houver Application de dialplan disponível no build em uso, é
disparado pelo `ESLClient` a partir do handler de evento de canal correspondente — nunca via
`<action>` no dialplan.** Antes de adicionar uma nova integração com módulo FreeSWITCH, confirmar
com `fs_cli -x 'show application'` se a funcionalidade desejada está disponível como Application; se
não estiver, este é o padrão a seguir por padrão, não a exceção.

## 4. Fontes

- `fs_cli -x 'show application'` e `fs_cli -x 'show modules'` executados em produção
  (10.10.10.11), 2026-07-13 e 2026-07-14, durante teste real de chamada ponta a ponta.
- `_reversa_sdd/telephony/design.md#5. Dialplan` (GAP-DIALPLAN-01, GAP-DIALPLAN-02).
- `_reversa_sdd/gaps.md` (GAP-11, fragilidade da imagem customizada do FreeSWITCH).
- Código-fonte já existente: `src/telephony/esl_client.py` (`send_api`, `send_bgapi`,
  `_handle_channel_answer`, `_handle_manual_linkage`).
