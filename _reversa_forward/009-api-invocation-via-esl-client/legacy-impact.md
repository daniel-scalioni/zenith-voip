# Legacy Impact: Invocação de comandos de API do FreeSWITCH via ESL client

> Identificador: `009-api-invocation-via-esl-client`
> Data: `2026-07-14`

## Arquivos afetados

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|------------------|------------|------|------------|----------------|
| `freeswitch/conf/dialplan/default.xml` | Dialplan (`_reversa_sdd/telephony/design.md#5`) | regra-alterada | HIGH | Remove ação inválida (`uuid_audio_stream`/`api`) que derrubava toda chamada real; corrige `bridge` de um profile inexistente (`external`) para o gateway correto (`upstream-${sip_from_user}`) |
| `freeswitch/conf/vars.xml` | Config FreeSWITCH (`_reversa_sdd/telephony/design.md#5`) | regra-removida | LOW | Remove `zenith_api_host`/`audio_fork_dest`, órfãos após a mudança |
| `src/telephony/esl_client.py` | ESLClient (`_reversa_sdd/architecture.md#Fluxo Principal de uma Chamada`) | regra-alterada | HIGH | `_handle_channel_answer` passa a disparar `uuid_audio_stream` via `send_bgapi`, além do que já fazia |
| `src/config.py` | Settings (`_reversa_sdd/architecture.md#Stack Tecnológica`) | componente-novo | LOW | Nova chave `AUDIO_STREAM_CALLBACK_HOST` |
| `_reversa_sdd/telephony/design.md` | Spec de telefonia | regra-nova + regra-alterada | MEDIUM | Documenta o padrão geral (comandos de API por-canal sem Application → ESLClient) e fecha GAP-DIALPLAN-02/03 |

## Diff conceitual por componente

**Dialplan (`zenith_audio_fork`):** antes tentava (sem sucesso, em duas formas diferentes) disparar
captura de áudio inline via Application inexistente, e bridgava para um profile Sofia (`external`)
que nunca existiu neste FreeSWITCH — ambos os defeitos derrubavam toda chamada real desde o primeiro
commit do projeto, mascarados um pelo outro e pelo GAP-DIALPLAN-01 (extensions mortas de scaffolding,
já removidas em correção anterior nesta mesma sessão). Depois: o dialplan fica reduzido a
`answer` → `set` de variáveis de contexto → `bridge` via gateway correto
(`sofia/gateway/upstream-${sip_from_user}/${destination_number}`).

**ESLClient:** ganha uma nova responsabilidade (`_start_audio_capture`, chamada a partir de
`_handle_channel_answer`) que não existia antes — antes o dialplan tentava (e falhava) fazer esse
trabalho sozinho.

## Preservadas

Regras 🟢 do `_reversa_sdd/domain.md` que continuam intactas:
- R24 (Mapeamento SIP→IP expira em 1 hora)
- R25 (Código `*88` dispara linkage manual)
- R26 (Reconexão ESL automática com backoff de 2s)

## Modificadas

Nenhuma regra numerada (`R##`) do `_reversa_sdd/domain.md` foi alterada ou removida por esta feature
— a captura de áudio via `mod_audio_stream` nunca chegou a ser uma regra 🟢 confirmada em código
funcionando (era um comportamento pretendido desde a feature `007-audio-stream-migration`, mas nunca
exercitado por uma chamada real até esta sessão). O impacto real é sobre os GAPs registrados em
`_reversa_sdd/telephony/design.md` (seção "Riscos e Lacunas"), não sobre regras de negócio
confirmadas:
- GAP-DIALPLAN-02: fechado (era ✅ com resolução incorreta desde uma iteração anterior desta mesma
  sessão — corrigido para a resolução real: ESLClient, não o wrapper `application="api"`).
- GAP-DIALPLAN-03: novo, aberto e fechado na mesma sessão (profile `external` inexistente).

## Achado fora do escopo do repositório (não corrigido aqui)

Durante a validação real (T009/T011), a chamada passou a alcançar o VitalPBX corretamente (SDP
trocado, RTP configurado), mas o destino de teste `30001` respondeu com `200 OK` imediato, sem
tocar e sem áudio real — a perna foi derrubada pelo FreeSWITCH após 30s por timeout de mídia
(`REQUESTED_CHAN_UNAVAIL`). Isso indica configuração do lado do VitalPBX (fila/ramal `30001`
possivelmente inválido ou inativo), não um defeito de código no Zenith. Usuário confirmou (2026-07-14)
que a feature pode ser encerrada com esse achado registrado para investigação separada.
