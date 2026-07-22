# Requirements: Invocação de comandos de API do FreeSWITCH via ESL client

> Identificador: `009-api-invocation-via-esl-client`
> Data: `2026-07-14`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

Estabelece o padrão que o projeto deve seguir sempre que um módulo do FreeSWITCH expõe uma
funcionalidade apenas como comando de **API** (invocável via ESL/`fs_cli`), sem registrar uma
**Application** de dialplan correspondente: a invocação passa a ser responsabilidade do `ESLClient`
(`src/telephony/esl_client.py`), disparada a partir dos handlers de evento de canal já existentes
(`_handle_channel_create`, `_handle_channel_answer`, `_handle_channel_hangup`), em vez de uma
`<action>` no XML do dialplan. Resolve, como primeiro caso de aplicação, o início da captura de
áudio via `mod_audio_stream` (`uuid_audio_stream`), que hoje impede toda chamada real de completar.

## 2. Contexto a partir do legado

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `_reversa_sdd/architecture.md#Fluxo Principal de uma Chamada` | ESLClient já escuta CHANNEL_CREATE → CHANNEL_ANSWER → CHANNEL_HANGUP como ponto central de orquestração pós-evento | 🟢 |
| `_reversa_sdd/architecture.md#Papel do FreeSWITCH: B2BUA com Registration Forwarding` | FreeSWITCH captura áudio via `mod_audio_stream` (sucessor de `mod_audio_fork`, feature `007-audio-stream-migration`) | 🟢 |
| `_reversa_sdd/domain.md#SIP e Telefonia` (R24-R27) | Padrões já confirmados de responsabilidade do ESLClient: mapeamento SIP→IP, linkage manual via `*88`, reconexão automática | 🟢 |
| `_reversa_sdd/telephony/design.md#5. Dialplan` | GAP-DIALPLAN-01 e GAP-DIALPLAN-02 documentam achados desta mesma investigação: extensions mortas interceptando chamadas e a tentativa (inválida) de chamar `uuid_audio_stream` direto e via `application="api"` no dialplan | 🟢 |
| Observação direta em produção (`fs_cli -x 'show application'`, 2026-07-13/14) | Este build do FreeSWITCH (`mod_commands`, `mod_conference`, `mod_dptools`, `mod_event_socket`, `mod_sofia`, `mod_spandsp` + `mod_audio_stream`) não registra `api`/`bgapi` como Application de dialplan — só como comando de API via ESL | 🟢 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| Desenvolvedor do Zenith | Adicionar/manter integração com um módulo FreeSWITCH que só expõe API (não Application) | Precisa saber, sem redescobrir por tentativa e erro, onde no código essa invocação deve morar |
| Operador do call center | Ter a chamada capturada e transcrita sem falha perceptível | Disca para uma fila/ramal externo e a chamada completa normalmente, com áudio sendo capturado |

## 4. Regras de negócio novas ou alteradas

1. **RN-01:** Comandos de API do FreeSWITCH que dependem de contexto por-chamada (UUID do canal, variáveis do canal) e que não têm Application de dialplan equivalente disponível no build em uso devem ser invocados pelo `ESLClient`, via `send_api`/`send_bgapi`, a partir do handler do evento de canal apropriado — nunca via `<action application="...">` no XML do dialplan. 🟢
   - Origem no legado: não há regra confirmada anterior no `_reversa_sdd/domain.md`; é uma regra nova, generalizando o achado do GAP-DIALPLAN-02 (`_reversa_sdd/telephony/design.md`).
   - Tipo: nova
2. **RN-02:** O dialplan (`freeswitch/conf/dialplan/*.xml`) permanece responsável apenas por: roteamento de destino, `answer`, `bridge`, e `set` de variáveis de canal que o ESLClient consome depois via evento (`variable_zenith_*`). Nenhuma ação de dialplan deve depender de uma Application que não exista comprovadamente no build em produção. 🟢
   - Tipo: nova
3. **RN-03:** A captura de áudio da chamada (`uuid_audio_stream ... start`) é disparada pelo `ESLClient._handle_channel_answer`, usando os dados já presentes no evento `CHANNEL_ANSWER` (`Caller-Unique-ID`, `variable_zenith_tenant_id`, `variable_zenith_pbx_id`, `variable_zenith_agent_extension`), reaproveitando o mesmo evento que já dispara `register_stream_metadata`/`create_call_record`. 🟢
   - Origem no legado: altera o comportamento pretendido (mas nunca funcional) da feature `007-audio-stream-migration`.
   - Tipo: alterada

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| RF-01 | O dialplan não deve conter nenhuma `<action application="...">` que invoque diretamente um comando de API sem Application registrada (incluindo o wrapper inválido `application="api"` neste build) | Must | Inspeção do `freeswitch/conf/dialplan/default.xml` não encontra `uuid_audio_stream` nem `application="api"` como action | 🟢 |
| RF-02 | `ESLClient._handle_channel_answer` deve disparar `uuid_audio_stream <uuid> start ws://.../audio-stream/<uuid> stereo 8k {...}` via `send_bgapi` (ou `send_api`) sempre que o evento trouxer `variable_zenith_tenant_id` preenchido | Must | Em chamada real de teste, `fs_cli` confirma `uuid_audio_stream` executado com sucesso (sem "Invalid Application") e o áudio chega no endpoint WebSocket da API | 🟢 |
| RF-03 | O host/porta usado para montar a URL do WebSocket de callback (`ws://<host>/audio-stream/<uuid>`) deve vir de uma configuração centralizada (`src/config.py`), não de um valor duplicado entre `vars.xml` e código Python | Should | Existe uma única fonte de verdade para esse host:porta, referenciada tanto pela config Python quanto documentada na spec | 🟡 |
| RF-04 | Uma chamada real originada de um ramal do Zenith para um destino externo deve completar (não sofrer hangup automático por "Invalid Application") e ter áudio capturado de ponta a ponta | Must | Teste manual: ramal 1001 → fila 30001 conecta, permanece ativa, e a API recebe frames de áudio | 🟢 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| Observabilidade | Falha ao disparar `uuid_audio_stream` via ESL (resposta de erro da API) deve ser logada de forma estruturada, não silenciosa | TD09 (`_reversa_sdd/architecture.md#Dívidas Técnicas`) já aponta logs do ESLClient sem estruturação — não piorar o problema existente | 🟡 |
| Resiliência | Falha ao iniciar a captura de áudio não deve derrubar a chamada (ela deve seguir bridged mesmo sem gravação, registrando o erro) | Nova — hoje qualquer erro nessa etapa (via dialplan) derruba a chamada inteira; a migração para o ESLClient deve evitar repetir esse acoplamento | 🟢 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Chamada real completa com captura de áudio ativa
  Dado um ramal do Zenith registrado no FreeSWITCH
  E o dialplan roteando para `zenith_audio_fork`
  Quando o ramal disca para um destino externo válido
  Então a chamada é atendida e bridgeada ao PBX upstream
  E o ESLClient recebe CHANNEL_ANSWER e dispara uuid_audio_stream com sucesso
  E a API recebe o stream de áudio no WebSocket correspondente ao call_id

Cenário: Comando de API do FreeSWITCH sem Application de dialplan disponível
  Dado um módulo do FreeSWITCH que expõe uma função apenas como comando de API
  Quando um desenvolvedor precisa disparar esse comando por chamada
  Então a invocação é implementada no ESLClient, a partir de um handler de evento de canal
  E nenhuma tentativa de invocação equivalente é adicionada ao XML do dialplan
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|---------------|
| RF-01 | Must | Sem isso, o dialplan continua na configuração quebrada que derruba toda chamada real |
| RF-02 | Must | É a correção funcional central — sem ela não há captura de áudio |
| RF-03 | Should | Reduz duplicação/drift entre `vars.xml` e Python, mas não bloqueia a chamada funcionar |
| RF-04 | Must | Critério de aceite fim-a-fim da feature |
| RNF de resiliência | Should | Evita que a correção introduza um novo modo de falha (chamada cair por erro de captura) |

## 9. Esclarecimentos

> Sessão de dúvidas resolvida sem interação humana, a pedido explícito do usuário para execução
> autônoma do ciclo forward completo (registrado nesta sessão). Decisões abaixo priorizam o
> comportamento observável já estabelecido no legado sobre invenção de mecanismo novo.

1. **Host:porta do callback WebSocket (RF-03):** mantém o mesmo valor já usado em produção
   (`127.0.0.1:8001`, hoje hardcoded em `vars.xml#zenith_api_host`), agora como uma única
   configuração em `src/config.py` (nova chave `AUDIO_STREAM_CALLBACK_HOST`, default
   `"127.0.0.1:8001"`, sobrescrevível por variável de ambiente). `vars.xml` deixa de precisar da
   variável `zenith_api_host`/`audio_fork_dest` já que o dialplan não dispara mais a captura.
   Resolvida sem `[DÚVIDA]` remanescente. 🟡
2. **Comportamento em falha de captura (RNF de resiliência):** a chamada segue bridged mesmo se
   `uuid_audio_stream` falhar — gravação/transcrição é best-effort, o atendimento ao cliente não
   pode ser interrompido por um erro de infraestrutura de captura. O erro é logado de forma
   estruturada (WARNING, com `call_id` e a resposta de erro da API) para permitir detecção via
   observabilidade, evitando repetir o modo de falha atual (chamada inteira derrubada). Resolvida
   sem `[DÚVIDA]` remanescente. 🟢

## 10. Lacunas

- Nenhuma lacuna aberta. Os dois pontos originalmente marcados `[DÚVIDA]` foram resolvidos na seção 9.

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-07-14 | Versão inicial gerada por `/reversa-requirements` | reversa |
