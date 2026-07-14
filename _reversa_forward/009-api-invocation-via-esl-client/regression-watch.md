# Regression Watch: Invocação de comandos de API do FreeSWITCH via ESL client

> Identificador: `009-api-invocation-via-esl-client`

## Watch principal

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|--------------------------|-------------------------------|----------------------|--------------------|
| W001 | `_reversa_sdd/telephony/design.md#6` (GAP-DIALPLAN-02) | Dialplan não contém nenhuma `<action>` que invoque `uuid_audio_stream` diretamente nem via `application="api"` | presença (grep negativo) | `grep -n 'uuid_audio_stream\|application="api"' freeswitch/conf/dialplan/default.xml` retorna alguma linha |
| W002 | `_reversa_sdd/telephony/design.md#6` (GAP-DIALPLAN-03) | `bridge` em `zenith_audio_fork` usa `sofia/gateway/upstream-${sip_from_user}/...`, nunca `sofia/external/...` | presença | `grep -n 'sofia/external' freeswitch/conf/dialplan/default.xml` retorna alguma linha |
| W003 | `src/telephony/esl_client.py` (`_handle_channel_answer`) | `_handle_channel_answer` chama `_start_audio_capture`, que dispara `uuid_audio_stream ... start` via `send_bgapi` | presença | `grep -n '_start_audio_capture' src/telephony/esl_client.py` não encontra a definição ou a chamada |
| W004 | `src/config.py` (`Settings`) | `AUDIO_STREAM_CALLBACK_HOST` existe em `Settings` | presença | `grep -n 'AUDIO_STREAM_CALLBACK_HOST' src/config.py` retorna vazio |

## Observações

- Achado durante a validação real desta feature, sem peso de regressão (é sobre infraestrutura
  externa ao repositório, não sobre código do Zenith): o destino de teste `30001` no VitalPBX
  respondeu `200 OK` imediato sem tocar e sem áudio real, terminando por timeout de mídia do
  FreeSWITCH (`REQUESTED_CHAN_UNAVAIL` após 30s). Não vira watch item porque não há regra de código
  do Zenith a proteger aqui — é uma pendência de configuração do VitalPBX, fora do escopo deste
  ciclo. Se investigado no futuro, registrar como feature/GAP separado, não como regressão desta.

## Histórico de re-extrações

_Nenhuma re-extração (`/reversa`) executada desde a geração deste arquivo._

## Arquivadas

_Nenhum item arquivado ainda._
