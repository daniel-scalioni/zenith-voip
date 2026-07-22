# Roadmap: Invocação de comandos de API do FreeSWITCH via ESL client

> Identificador: `009-api-invocation-via-esl-client`
> Data: `2026-07-14`
> Requirements: `_reversa_forward/009-api-invocation-via-esl-client/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

Remove do dialplan (`freeswitch/conf/dialplan/default.xml`, extension `zenith_audio_fork`) a ação
que tenta invocar `uuid_audio_stream` — comando de API do `mod_audio_stream` sem Application de
dialplan equivalente neste build do FreeSWITCH. A captura de áudio passa a ser disparada pelo
`ESLClient` (`src/telephony/esl_client.py`), dentro de `_handle_channel_answer`, via `send_bgapi`,
reaproveitando os dados que o evento `CHANNEL_ANSWER` já traz (`Caller-Unique-ID`,
`variable_zenith_tenant_id`, `variable_zenith_pbx_id`, `variable_zenith_agent_extension`). O host de
callback do WebSocket sai do hardcode em `vars.xml` e vira uma config Python
(`AUDIO_STREAM_CALLBACK_HOST`), única fonte de verdade. Erro ao disparar a captura é logado, mas não
derruba a chamada — a chamada permanece bridged. Este roadmap generaliza o padrão para qualquer
comando de API por-canal futuro, não só `uuid_audio_stream`.

## 2. Princípios aplicados

`.reversa/principles.md` não existe neste projeto ainda (nenhum princípio formal registrado via
`/reversa-principles`). Nenhum conflito a avaliar nesta seção.

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|----------------|--------------------------|-------------|
| D-01 | Disparar `uuid_audio_stream` a partir de `ESLClient._handle_channel_answer`, via `send_bgapi` | O ESLClient já é o único ponto do código que reage a eventos de canal (CHANNEL_CREATE/ANSWER/HANGUP — `_reversa_sdd/architecture.md#Fluxo Principal de uma Chamada`); reaproveita infraestrutura existente (`send_api`/`send_bgapi` já implementados) em vez de criar um novo componente | (a) manter no dialplan usando `application="api"` — inválido neste build, confirmado por observação direta; (b) instalar/compilar módulo adicional de scripting (mod_lua) só para viabilizar chamada de API no dialplan — infla a imagem Docker (`freeswitch/Dockerfile`) e o escopo desta correção para resolver um problema que o ESLClient já resolve sem dependência nova | 🟢 |
| D-02 | Usar `send_bgapi` (assíncrono) em vez de `send_api` (síncrono) para o disparo de `uuid_audio_stream` | `_handle_channel_answer` já é executado dentro do loop de eventos assíncrono do ESLClient (`_event_loop`/`_read_events`); uma chamada `send_api` bloqueante aumentaria a latência de processamento de TODOS os eventos subsequentes na mesma conexão ESL enquanto aguarda a resposta | `send_api` sequencial — descartado por acoplar a resposta do FreeSWITCH ao processamento do próximo evento | 🟡 |
| D-03 | Nova config `AUDIO_STREAM_CALLBACK_HOST` em `src/config.py`, default `"127.0.0.1:8001"` (mesmo valor hoje hardcoded em `vars.xml#zenith_api_host`) | Elimina duplicação entre `vars.xml` e o processo Python que agora monta a URL; resolve RF-03 do requirements | Manter o valor apenas em `vars.xml` e o ESLClient ler o channel-variable do evento — descartado porque o ESLClient não depende mais de nenhuma variável de dialplan para montar essa URL, e manter as duas fontes reintroduziria o mesmo tipo de drift que já causou o GAP-DIALPLAN-02 | 🟢 |
| D-04 | Falha ao disparar `uuid_audio_stream` é logada (WARNING, com `call_id` e corpo da resposta de erro) e NÃO propага exceção que interrompa `_handle_channel_answer` | Resolve a Esclarecimento #2 do `requirements.md`: gravação é best-effort, atendimento ao cliente não pode ser interrompido por erro de infraestrutura de captura | Deixar exceção subir e potencialmente derrubar o `_event_loop` inteiro do ESLClient (afetaria TODAS as chamadas em andamento, não só a que falhou) — descartado por criar um raio de impacto desproporcional ao problema | 🟢 |
| D-05 | Dialplan mantém `answer`, todos os `set` de variáveis `zenith_*` e o `bridge` — remove apenas a linha `uuid_audio_stream`/`api` | As variáveis `zenith_call_id`, `zenith_tenant_id`, `zenith_pbx_id`, `zenith_agent_extension` continuam necessárias: chegam ao ESLClient via `variable_zenith_*` no evento `CHANNEL_ANSWER` e são a única forma de o ESLClient saber qual tenant/pbx/agente pertence a cada `call_id` | Remover essas variáveis do dialplan e buscar tenant/pbx/agente por outra via (ex.: consulta ao banco por `call_id`) — descartado, adicionaria uma query síncrona no caminho crítico do evento sem necessidade, quando o dado já vem de graça no evento | 🟢 |
| D-06 | Trocar `sofia/external/${destination_number}@${pbx_host}` por `sofia/gateway/upstream-${sip_from_user}/${destination_number}` no `bridge` de `zenith_audio_fork` | Descoberto durante a validação end-to-end (T009): o profile `external` nunca existiu neste FreeSWITCH (`sofia status` só lista `internal`, `internal-7060`, `internal-5062`, `upstream`), causando `[ERR] Invalid Profile`/`INVALID_PROFILE` assim que o `bridge` era alcançado — mascarado até agora pelos GAP-DIALPLAN-01/02, que sempre derrubavam a chamada antes. Bridgar via `sofia/gateway/upstream-${sip_from_user}/...` usa o gateway já registrado individualmente para o ramal que originou a chamada (`sofia status gateway upstream-1001` → `REGED`/`UP`), consistente com o desenho de B2BUA por-ramal (`_reversa_sdd/architecture.md#Papel do FreeSWITCH`) | Criar um profile `external` novo só para satisfazer a string original — descartado, o projeto já registra cada ramal individualmente via gateway upstream, criar um profile paralelo duplicaria a autenticação/registro sem necessidade | 🟢 |

## 4. Premissas

Nenhuma. Os dois pontos originalmente `[DÚVIDA]` no `requirements.md` foram resolvidos na seção 9
daquele documento antes deste plano ser escrito (ver decisões D-03 e D-04 acima, que implementam
essas resoluções).

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-----------------|--------|
| Dialplan `zenith_audio_fork` | `_reversa_sdd/telephony/design.md#5. Dialplan` | contrato-alterado | Remove a action `uuid_audio_stream`/`api` (nunca funcional); mantém `answer`/`set`/`bridge` |
| `ESLClient._handle_channel_answer` | `_reversa_sdd/architecture.md#Fluxo Principal de uma Chamada` | regra-alterada | Passa a dsiparar `uuid_audio_stream start` via `send_bgapi`, além do que já fazia (`register_stream_metadata`, `create_call_record`) |
| `src/config.py` (Settings) | `_reversa_sdd/architecture.md#Stack Tecnológica` | componente-novo (campo) | Nova chave `AUDIO_STREAM_CALLBACK_HOST` |
| `vars.xml` | `_reversa_sdd/telephony/design.md#5. Dialplan` | regra-alterada | Remove `zenith_api_host`/`audio_fork_dest`, que só existiam para a action removida |

## 6. Delta no modelo de dados

- Nenhuma mudança de esquema de banco de dados. A mudança é inteiramente de fluxo de execução
  (dialplan → ESLClient) e configuração.
- Detalhe completo em: `_reversa_forward/009-api-invocation-via-esl-client/data-delta.md`

## 7. Delta de contratos externos

Nenhum contrato externo muda. O endpoint WebSocket `ws://.../audio-stream/{call_id}`
(`src/main.py:53`) continua com a mesma URL, protocolo e payload — apenas quem inicia a conexão do
lado do FreeSWITCH muda (ESLClient em vez de dialplan). Pasta `interfaces/` omitida por não haver
contrato afetado.

## 8. Plano de migração

1. Adicionar `AUDIO_STREAM_CALLBACK_HOST` em `src/config.py` (Settings), default `"127.0.0.1:8001"`.
2. Editar `_handle_channel_answer` em `src/telephony/esl_client.py`: após `register_stream_metadata`
   e `create_call_record`, montar o comando `uuid_audio_stream {call_id} start ws://{host}/audio-stream/{call_id} stereo 8k {"call_id":"{call_id}"}` e disparar via `send_bgapi`, com log de WARNING em
   caso de resposta de erro.
3. Editar `freeswitch/conf/dialplan/default.xml`: remover a action `uuid_audio_stream`/`api` da
   extension `zenith_audio_fork`.
4. Editar `freeswitch/conf/vars.xml`: remover `zenith_api_host` (não referenciado por mais nenhum
   lugar após o passo 3).
5. Atualizar `_reversa_sdd/telephony/design.md`: novo GAP (ou fechamento formal do GAP-DIALPLAN-02)
   documentando a mudança de responsabilidade dialplan → ESLClient, e o novo padrão geral (RN-01 do
   requirements) para comandos de API por-canal sem Application disponível.
6. Deploy: `scp` do dialplan e `vars.xml` corrigidos para o servidor + `reloadxml`; restart do
   serviço `fastapi-1` (ou `docker compose up -d --build fastapi-1` se o Dockerfile não mudar, um
   `restart` simples já recarrega o código Python montado por bind mount, se aplicável — confirmar
   no momento do deploy).
7. Teste real: originar chamada do ramal 1001 para a fila 30001, confirmar via `fs_cli` que a
   chamada completa sem "Invalid Application" e que a API recebe o stream de áudio.

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| `send_bgapi` não bloqueia, então um erro de sintaxe no comando só aparece no log, não trava o fluxo — pode passar despercebido em produção | médio | baixo | D-04 garante log estruturado de WARNING; validar manualmente no primeiro deploy antes de considerar a feature pronta |
| `CHANNEL_ANSWER` pode chegar antes de `create_call_record` persistir o registro da chamada, criando uma janela onde `uuid_audio_stream` dispara mas o `call_id` ainda não existe no banco | baixo | baixo | Ordem já preservada no código atual (`register_stream_metadata`/`create_call_record` primeiro, `uuid_audio_stream` depois, no mesmo handler síncrono até o ponto do `await`); não introduz uma race nova |
| Remover `zenith_api_host` de `vars.xml` sem confirmar que nenhum outro dialplan/config o referencia | baixo | baixo | Grep em `freeswitch/conf/` antes de remover (passo 4 do plano de migração) |

## 10. Critério de pronto

- [ ] Todas as ações do `actions.md` marcadas `[X]`
- [ ] `cross-check.md` (se executado) sem CRITICAL nem HIGH
- [ ] `regression-watch.md` gerado
- [ ] Re-extração reversa executada e sem regressão vermelha (recomendado, não obrigatório)
- [ ] Chamada real de teste (ramal 1001 → fila 30001) completa sem erro e com áudio capturado

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-07-14 | Versão inicial gerada por `/reversa-plan` | reversa |
