# Actions: Invocação de comandos de API do FreeSWITCH via ESL client

> Identificador: `009-api-invocation-via-esl-client`
> Data: `2026-07-14`
> Roadmap: `_reversa_forward/009-api-invocation-via-esl-client/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 11 |
| Paralelizáveis (`[//]`) | 8 |
| Maior cadeia de dependência | 5 (T002 → T005 → T007 → T009 → T011) |

## Fase 1, Preparação

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T001 | Adicionar `AUDIO_STREAM_CALLBACK_HOST: str = "127.0.0.1:8001"` em `Settings` (`src/config.py`) | - | `[//]` | `src/config.py` | 🟢 | `[X]` |
| T002 | Atualizar `_reversa_sdd/telephony/design.md`: registrar o novo padrão geral (comandos de API por-canal sem Application disponível são disparados pelo ESLClient, não pelo dialplan) e fechar `GAP-DIALPLAN-02` com a resolução real (ESLClient via `send_bgapi`, não o wrapper `application="api"` que também se mostrou inválido) | - | `[//]` | `_reversa_sdd/telephony/design.md` | 🟢 | `[X]` |
| T003 | Grep em `freeswitch/conf/` confirmando que `zenith_api_host` e `audio_fork_dest` não são referenciados em nenhum arquivo além da action `uuid_audio_stream` que será removida em T005 | - | `[//]` | `freeswitch/conf/` | 🟢 | `[X]` |

## Fase 2, Testes

<!-- Projeto não pratica TDD formal para este tipo de integração (validação é via teste manual de chamada real, ver Fase 5). Fase omitida sem tabela. -->

## Fase 3, Núcleo

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T004 | Em `_handle_channel_answer` (`src/telephony/esl_client.py`), após `register_stream_metadata`/`create_call_record`, montar `uuid_audio_stream {call_id} start ws://{settings.AUDIO_STREAM_CALLBACK_HOST}/audio-stream/{call_id} stereo 8k {"call_id":"{call_id}"}` e disparar via `self.send_bgapi(...)`; logar WARNING estruturado (com `call_id` e resposta) se o retorno indicar erro | T001, T002 | `[//]` | `src/telephony/esl_client.py` | 🟢 | `[X]` |
| T005 | Remover a `<action application="uuid_audio_stream">`/`<action application="api" data="uuid_audio_stream ...">` da extension `zenith_audio_fork` em `freeswitch/conf/dialplan/default.xml`, mantendo `answer`, os `set` de variáveis `zenith_*` e o `bridge` | T002 | `[//]` | `freeswitch/conf/dialplan/default.xml` | 🟢 | `[X]` |

## Fase 4, Integração

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T006 | Remover `zenith_api_host` e `audio_fork_dest` de `freeswitch/conf/vars.xml` (confirmado órfãos por T003, consumidor removido por T005) | T003, T005 | - | `freeswitch/conf/vars.xml` | 🟢 | `[X]` |
| T007 | Deploy: `scp` de `default.xml` e `vars.xml` corrigidos para o servidor (`administrator@10.10.10.11`) + `docker compose exec freeswitch fs_cli -x 'reloadxml'` | T005, T006 | `[//]` | `freeswitch/conf/` (remoto) | 🟢 | `[X]` |
| T008 | Restart do serviço `fastapi-1` no servidor (`docker compose restart fastapi-1`) para carregar o novo `esl_client.py`/`config.py` | T004 | `[//]` | `fastapi-1` (remoto) | 🟢 | `[X]` |

## Fase 5, Polimento

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T009 | Teste real de chamada ponta a ponta (ramal 1001 → fila 30001) com `fs_cli` ao vivo e logs do `fastapi-1` abertos: confirmar ausência de `Invalid Application`, chamada permanece `ACTIVE`/bridged, e requisição `GET /audio-stream/<uuid>` aparece no log da API | T007, T008 | - | n/a (validação manual) | 🟢 | `[X]` |
| T010 | Grep final em todo o repositório (`freeswitch/`, `src/`) confirmando que não sobrou nenhuma referência a `audio_fork_dest`/`zenith_api_host` após a remoção | T006 | `[//]` | repositório | 🟢 | `[X]` |

## Fase 5 (continuação), ação adicional descoberta em T009

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T011 | Trocar `sofia/external/${destination_number}@${pbx_host}` por `sofia/gateway/upstream-${sip_from_user}/${destination_number}` no `bridge` de `zenith_audio_fork`, deploy (scp + reloadxml) e novo teste real (ramal 1001 → 30001) | T009 | - | `freeswitch/conf/dialplan/default.xml` | 🟢 | `[X]` |

## Notas de execução

- **2026-07-14, durante T009:** primeira chamada real após T001-T008 revelou um bug pré-existente e
  não relacionado ao escopo original desta feature: `bridge` usava o profile `sofia/external/...`,
  que nunca existiu neste FreeSWITCH. Estava mascarado desde o commit inicial do projeto pelos
  GAP-DIALPLAN-01/02 (a chamada sempre morria antes de alcançar o `bridge`). Registrado como
  GAP-DIALPLAN-03 em `_reversa_sdd/telephony/design.md` e D-06 em `roadmap.md`. Ação T011 adicionada
  para corrigir e revalidar, mantendo a numeração de IDs estável (nenhum ID reciclado).
- **2026-07-14, T011 concluída:** deploy do bridge corrigido e novo teste real confirmaram que
  `Invalid Application` e `Invalid Profile` não ocorrem mais — a chamada atende, bridga via
  `sofia/gateway/upstream-1001/30001` e alcança o VitalPBX normalmente (SDP trocado, RTP
  configurado). Escopo desta feature está tecnicamente resolvido.
  Observação separada, fora do escopo deste repositório: o VitalPBX respondeu `200 OK` para
  `30001` **imediatamente, sem tocar** e sem áudio real trafegando; o FreeSWITCH derrubou a perna
  sozinho após 30s por timeout de mídia (`REQUESTED_CHAN_UNAVAIL`). Isso indica que `30001`
  provavelmente não é uma fila/ramal válido e ativo no momento do teste — é configuração do lado
  do VitalPBX, não um bug de código do Zenith. Usuário confirmou (2026-07-14) encerrar esta feature
  aqui e investigar `30001` separadamente, com outro destino de teste.

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-07-14 | Versão inicial gerada por `/reversa-to-do` | reversa |
