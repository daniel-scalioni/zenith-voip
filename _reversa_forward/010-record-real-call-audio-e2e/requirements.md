# Requirements: Gravação de ligação real com áudio ponta a ponta

> Identificador: `010-record-real-call-audio-e2e`
> Data: `2026-07-14`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

Validar, com uma chamada real e voz humana de verdade, que o Zenith consegue: originar uma ligação
de um ramal registrado no FreeSWITCH, alcançar um destino no VitalPBX que efetivamente toca e é
atendido, manter áudio bidirecional real, e capturar/gravar esse áudio ponta a ponta (`mod_audio_stream`
→ WebSocket → API → armazenamento). É o critério de aceite fim-a-fim que a feature
`009-api-invocation-via-esl-client` deixou pendente: ela corrigiu os bugs de código que impediam a
chamada de completar, mas o destino de teste usado (fila `30001`) não produziu uma chamada
efetivamente atendida por um humano.

## 2. Contexto a partir do legado

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `_reversa_forward/009-api-invocation-via-esl-client/legacy-impact.md#Achado fora do escopo` | Chamada real (ramal 1001 → fila 30001) alcança o VitalPBX corretamente (SDP trocado, RTP configurado), mas a perna cai por timeout de mídia do FreeSWITCH após 30s (`REQUESTED_CHAN_UNAVAIL`), sem nunca tocar | 🟢 |
| `specs/export_extensions.csv` (coluna `static_queues`) | `30001` aparece como fila estática associada a dezenas de ramais (89 ocorrências no CSV, ex.: ramal `9999` tem `static_queues=30029\|30001`) — é uma fila real e amplamente referenciada no VitalPBX, não um destino inválido/inexistente | 🟡 |
| `_reversa_sdd/telephony/design.md#5. Dialplan` | `zenith_audio_fork` bridga via `sofia/gateway/upstream-${sip_from_user}/${destination_number}`, usando o gateway individual já registrado do ramal que originou a chamada (corrigido em `009`) | 🟢 |
| `_reversa_sdd/architecture.md#Papel do FreeSWITCH` | FreeSWITCH é B2BUA — termina a chamada do ramal e reabre uma nova perna para o VitalPBX; qualquer problema de mídia (RTP) fica isolado nessa segunda perna, sem afetar diretamente a primeira | 🟢 |
| `_reversa_sdd/adrs/006-b2bua-registration-forwarding.md` | Cada ramal se registra individualmente upstream — precedente de já ter existido um bloqueio de rede (Mikrotik) só na sinalização SIP, corrigido em 2026-07-08 (ver memória de sessões anteriores); mídia RTP usa faixa de portas diferente e pode ter uma regra de firewall distinta não coberta por aquela correção | 🟡 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| Operador do call center | Fazer uma ligação normal e saber que ela está sendo gravada/transcrita | Disca de um ramal Zenith para um número/fila real, a outra ponta atende, os dois conversam, e a gravação fica disponível depois |
| Desenvolvedor do Zenith | Confirmar que a captura de áudio (`mod_audio_stream`) funciona com tráfego de voz real, não só com o esqueleto de sinalização | Precisa de um caso de teste reproduzível com um destino que realmente toca, para não confundir "chamada não cai mais com erro" com "chamada e gravação funcionam de verdade" |

## 4. Regras de negócio novas ou alteradas

1. **RN-01:** Uma chamada é considerada validada fim-a-fim apenas quando: (a) o destino toca e é
   atendido por um humano, (b) há áudio bidirecional real (não apenas RTP configurado/silêncio), e
   (c) o arquivo de gravação resultante contém voz audível de ambos os lados. 🟢
   - Tipo: nova (critério de aceite explícito que não existia antes desta feature)
2. **RN-02:** Diagnóstico de falha de mídia (RTP configurado mas sem áudio perceptível) deve
   diferenciar explicitamente entre problema de roteamento/destino (destino errado ou inválido) e
   problema de caminho de mídia (RTP bloqueado/NAT/firewall) antes de propor uma correção — os dois
   têm sintomas parecidos (chamada "conecta" mas não funciona) e causas completamente diferentes,
   como já ocorreu no histórico deste projeto com o bloqueio Mikrotik de sinalização SIP
   (`_reversa_sdd/telephony/packet-capture-debug.md`). 🟡
   - Origem no legado: generaliza a lição registrada em `packet-capture-debug.md` para mídia, não só
     sinalização.
   - Tipo: nova

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| RF-01 | Identificar um destino de teste no VitalPBX que garantidamente toca e pode ser atendido por um humano no momento do teste (ramal individual de alguém disponível, não uma fila sem agentes online) | Must | Uma chamada de teste para esse destino toca audivelmente do lado de quem atende | 🔴 [DÚVIDA] |
| RF-02 | Confirmar, via packet capture (mesma técnica usada para o debug do Mikrotik em 2026-07-08), se o RTP enviado pelo VitalPBX de volta ao FreeSWITCH está realmente chegando na perna `sofia/upstream/...` | Must | Captura mostra pacotes RTP bidirecionais entre `10.10.10.11` e `177.71.153.68` durante uma chamada de teste | 🟢 |
| RF-03 | Se RF-02 confirmar bloqueio de mídia, corrigir a regra de firewall/roteamento (Mikrotik) para a faixa de portas RTP usada pelo profile `upstream` | Must (condicional a RF-02) | Nova captura confirma RTP bidirecional sem perda | 🟡 |
| RF-04 | Confirmar que o áudio capturado por `mod_audio_stream` chega ao WebSocket da API (`/audio-stream/{call_id}`) com conteúdo de voz real audível (não silêncio/ruído) durante uma chamada bem-sucedida | Must | Arquivo de gravação resultante, ao ser reproduzido, contém a voz de quem atendeu e de quem originou a chamada | 🟢 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| Observabilidade | O diagnóstico desta feature deve deixar rastro reproduzível (comandos de packet capture, logs relevantes) documentado em `investigation.md`, não só a conclusão | Facilita debug futuro de problemas de mídia semelhantes — mesmo padrão que faltou documentar durante o incidente Mikrotik original | 🟡 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Chamada real com áudio bidirecional gravado
  Dado um ramal do Zenith registrado no FreeSWITCH
  E um destino no VitalPBX que uma pessoa real vai atender
  Quando o ramal disca para esse destino
  Então o destino toca e é atendido
  E as duas partes conseguem se ouvir normalmente durante a conversa
  E, ao final, existe um arquivo de gravação com a voz de ambos os lados

Cenário: Falha de mídia é diagnosticada corretamente antes de qualquer correção
  Dado uma chamada que "conecta" mas não produz áudio audível
  Quando o diagnóstico é conduzido
  Então packet capture confirma ou descarta bloqueio de RTP antes de qualquer mudança de código ou config
  E a causa raiz identificada (roteamento vs. mídia) é registrada em investigation.md antes da correção
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|---------------|
| RF-01 | Must | Sem um destino de teste confiável, não dá pra validar nada nesta feature |
| RF-02 | Must | Diagnóstico correto evita corrigir a coisa errada (repetir o padrão de duas causas simultâneas já visto no debug de registro) |
| RF-03 | Must (condicional) | Só necessário se RF-02 confirmar bloqueio |
| RF-04 | Must | É o critério de aceite final: gravação com voz real |

## 9. Esclarecimentos

> Nenhuma sessão de dúvidas registrada ainda. Rode `/reversa-clarify` quando houver `[DÚVIDA]` pendente.

## 10. Lacunas

- 🔴 [DÚVIDA] Qual ramal/número usar como destino de teste garantidamente disponível agora? O
  usuário precisa indicar um ramal de alguém que possa atender durante o teste (ex.: um segundo
  ramal físico, celular pessoal cadastrado como ramal, ou confirmar que algum membro da fila `30001`
  está de fato registrado/online neste momento).

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-07-14 | Versão inicial gerada por `/reversa-requirements` | reversa |
