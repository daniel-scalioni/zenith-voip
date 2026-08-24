---
spec:
  component: dialplan-upstream-routing-addendum
  layer: telephony
  status: active
  version: 1.0.0
  language: xml
  patterns: [event-driven]
  inputs:
    - {name: dialed_destination, type: string, from: registered-sip-endpoint}
  outputs:
    - {name: upstream_call_leg, type: SIP, to: vitalpbx}
  dependencies:
    - {component: esl-integration, layer: telephony}
    - {component: upstream-registration-fix, layer: telephony}
  events_produced: [CHANNEL_CREATE, CHANNEL_ANSWER, CHANNEL_HANGUP]
  updated_at: 2026-08-24
---

# Adendo corretivo 009: VitalPBX como autoridade de roteamento

## Origem

- Feature: `009-api-invocation-via-esl-client`
- Incidente: chamada `1001 -> 1003` encerrada localmente pelo FreeSWITCH com SIP `480`
- Data da evidência: `2026-08-24`
- Evidência sanitizada: o INVITE autenticado chegou ao profile `internal-7060`, recebeu `100 Trying`
  e `480 Temporarily Unavailable`, sem qualquer INVITE de saída ao VitalPBX
- SHA-256 do PCAP privado: `9126bb727d818ecaf1d710d9b4d6ad63d8f4f2bb41c5a4ed3b29f852aab2f2a6`

## Vigência

**Active desde 2026-08-24.** A chamada real `1001 -> 1003` comprovou bridge upstream,
atendimento e captura de áudio RX/TX após o deploy por `reloadxml`.

## Causa raiz

A extensão `local_extension`, avaliada antes de `zenith_audio_fork`, casa todo destino
`1xxx` e tenta `bridge user/<destino>@<dominio>`. O número `1003` existe no VitalPBX, mas não está
registrado localmente no FreeSWITCH. Como a primeira extensão correspondente encerra a avaliação
do contexto, `zenith_audio_fork` nunca executa e o VitalPBX não recebe a chamada.

O problema não é registro ou conectividade do originador: `upstream-1001` estava `REGED/UP`, e
destinos que não casavam `1xxx`, como `1140100` e `3101001`, já atravessavam o mesmo gateway.

## Delta de contrato

1. O VitalPBX é a autoridade de roteamento de **todo destino telefônico**, qualquer que seja o
   tamanho ou prefixo do número.
2. Toda chamada entre endpoints, inclusive quando ambos também estiverem registrados no
   FreeSWITCH, deve atravessar `zenith_audio_fork` e o gateway `upstream-${sip_from_user}`.
3. O FreeSWITCH preserva os dígitos recebidos. Não seleciona ramal, fila ou destino final.
4. A extensão `local_extension` deixa de existir. Não há bridge `user/...` no contexto `default`.
5. Rotas locais ficam restritas a comandos técnicos explicitamente reservados, não a números de
   negócio:
   - `*9196`: teste de eco local, substitui o código numérico `9196`;
   - `*88`: linkage manual do Zenith;
   - `play:filler`: pseudo-destino interno não numérico para áudio de preenchimento.
6. O número `9196`, sem asterisco, volta a ser destino telefônico comum e segue ao VitalPBX.

## Requisitos funcionais

| ID | Requisito | Prioridade | Critério de aceite |
|---|---|---|---|
| R-009-A01 | Encaminhar todo `destination_number` puramente numérico para `sofia/gateway/upstream-${sip_from_user}/${destination_number}`. | Must | Testes com `1003`, `9196`, `30001`, `1140100` e `3101001` resolvem para o mesmo bridge upstream, sem alteração dos dígitos. |
| R-009-A02 | Remover qualquer precedência baseada em `1xxx` e qualquer bridge `user/...` no contexto `default`. | Must | Parse do XML não encontra extensão `local_extension`, expressão `^(1\d{3})$` nem bridge `user/`. |
| R-009-A03 | Reservar o eco local exclusivamente em `*9196`. | Must | `*9196` executa `answer` e `echo`; `9196` casa a rota numérica upstream. |
| R-009-A04 | Preservar `*88` e `play:filler` como rotas técnicas locais. | Must | O XML mantém as duas extensões e nenhuma delas contém bridge upstream. |
| R-009-A05 | Preservar a captura e o contexto de tenant para chamadas entre quaisquer ramais. | Must | Chamada real `1001 -> 1003` gera CHANNEL_ANSWER no canal Zenith, WebSocket de áudio e par WAV por canal. |

## TDD e validação operacional

1. Red: provar que o dialplan atual ainda contém `local_extension`, usa `9196` para eco e impede a
   política de roteamento universal.
2. Green: alterar somente `freeswitch/conf/dialplan/default.xml` para satisfazer o contrato.
3. Rodar `pytest -v tests src`.
4. Obter revisão independente de bordas e viés dos testes.
5. Publicar somente o dialplan no host e executar `reloadxml`, sem reiniciar o FreeSWITCH.
6. Confirmar que `upstream-1001` continua `REGED/UP`.
7. Capturar uma chamada real `1001 -> 1003` e comprovar INVITE de saída para o VitalPBX, resposta
   não gerada pela antiga rota local e áudio preservado para o GT.

## Restrições

- Não modificar gateways, profiles, credenciais ou regras do VitalPBX.
- Não enviar PCAP com material SIP sensível ao Git.
- Não reiniciar nem remover containers.
- Falha na captura de áudio continua best-effort e não pode derrubar a chamada.

## Evidência de validação operacional

- Data/hora: `2026-08-24 14:41:18 UTC`
- Classificação: validação operacional de roteamento; não compõe o Ground Truth da feature 013
- Fluxo: `1001 -> FreeSWITCH -> VitalPBX -> 1003`
- UUID Zenith: `966a7023-22b6-4ee0-8bd8-4049a475e163`
- Sinalização upstream: `INVITE 1003 -> 100 Trying -> 180 Ringing -> 200 OK`
- Encerramento: `BYE -> 200 OK` nos dois lados
- Duração de mídia RX/TX: `24,84 s`
- Formato dos dois WAV: `PCM S16LE`, mono, `16 kHz`
- Tamanho de cada WAV: `794.958 bytes`
- Captura SIP privada: SHA-256
  `5dca7f63f6ab3dc2564330044fdf056764d546c4eac02517174d2f66a2c945e7`
- Teste focal: `4 passed`
- Suíte canônica na linha de integração atual: `451 passed, 29 skipped`
- Parecer independente: `APROVADO` pelo Gemini CLI 3.7 após correção das ressalvas

## Rastreabilidade

- `_reversa_forward/009-api-invocation-via-esl-client/requirements.md#4-regras-de-negocio-novas-ou-alteradas`
- `_reversa_forward/009-api-invocation-via-esl-client/roadmap.md#3-decisoes-tecnicas`
- `_reversa_sdd/telephony/design.md#5-dialplan-extensions-do-contexto-default-ordem-importa`
- `freeswitch/conf/dialplan/default.xml`
- `tests/test_trunk_dialplan.py`
