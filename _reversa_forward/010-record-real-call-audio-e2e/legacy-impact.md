# Legacy Impact: Gravação de ligação real com áudio ponta a ponta

> Identificador: `010-record-real-call-audio-e2e`
> Data: `2026-07-15`

## Arquivos afetados

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|------------------|------------|------|------------|----------------|
| `src/telephony/esl_client.py` | ESLClient (`_reversa_sdd/architecture.md#Fluxo Principal de uma Chamada`) | regra-alterada | CRITICAL | 6 bugs corrigidos (GAP-ESL-04 a -08): parsing de protocolo, timeout de conexão, corrida de leitura, handshake, disparo duplicado. Nenhum evento de canal real era processado com sucesso antes desta feature. |
| `src/database/database.py` | Database engine/sessions (`_reversa_sdd/architecture.md#Stack Tecnológica`) | regra-alterada | CRITICAL | GAP-DB-01: nenhum registro `Call` era persistido de verdade em nenhuma chamada real anterior — rollback silencioso por falta de commit explícito na `Connection`. |
| `src/audio/ingestor.py` | AudioIngestor (`_reversa_sdd/audio/legacy-mapping.md`) | regra-alterada | HIGH | GAP-WS-01: primeira vez que `mod_audio_stream` conseguiu conectar de verdade revelou crash por assumir que toda mensagem WebSocket é binária. |
| `freeswitch/conf/dialplan/default.xml` | Dialplan (`_reversa_sdd/telephony/design.md#5`) | regra-alterada | CRITICAL | GAP-VARS-01 (sintaxe de variável errada) + GAP-DIALPLAN-04 (ordem de ações errada) — juntos, garantiam que `zenith_tenant_id` nunca chegasse populado no evento `CHANNEL_ANSWER`, bloqueando toda a cadeia de gravação desde o primeiro commit do projeto. |
| `src/main.py` | Bootstrap da aplicação | componente-novo | MEDIUM | `logging.basicConfig()` nunca existia — pré-requisito para qualquer log estruturado do projeto (`logger.warning`/`.exception`) aparecer de fato. |
| `_reversa_sdd/telephony/design.md` | Spec de telefonia | regra-nova | MEDIUM | 9 novos GAPs documentados (GAP-VARS-01, GAP-DIALPLAN-04, GAP-ESL-04 a -08, GAP-DB-01, GAP-WS-01), mais GAP-NET-01 aberto (bloqueio de rede RTP). |

## Diff conceitual por componente

**ESLClient:** deixa de ser um cliente ESL "de fachada" (conectava, mas nunca processava evento
real com sucesso) e passa a ser funcionalmente correto: protocolo bem formado (`Content-Length`),
conexão de eventos estável (sem reconexão espúria), conexão de comandos isolada e com handshake
correto. Esse conjunto de bugs é anterior a qualquer trabalho desta sessão — a feature
`009-api-invocation-via-esl-client` só conseguiu corrigir os erros de dialplan/API porque nunca
chegou a exercitar o caminho completo do ESLClient com uma chamada real que sobrevivesse tempo
suficiente.

**Banco de dados:** `get_tenant_db` sempre teve esse bug de commit — nenhuma feature anterior que
dependia de `Call`/`tenant_akom.calls` (retenção de áudio, transcript, etc.) jamais persistiu
dado real em produção, porque nenhuma delas foi validada com uma chamada real completa até agora.

**Dialplan:** a combinação GAP-VARS-01 + GAP-DIALPLAN-04 existe desde os commits mais antigos do
projeto (`48da5b1`, `cfd12b5`) — nenhuma delas foi pega antes porque, até `009`, a chamada sempre
morria bem antes de `answer()` sequer ser alcançado.

## Preservadas

Regras 🟢 do `_reversa_sdd/domain.md` que continuam intactas: R24 (mapeamento SIP→IP), R25
(`*88` manual linkage), R26 (reconexão ESL — agora com timeout corrigido, comportamento mais
próximo do pretendido pela regra original), R27 (widget auto-reconnect, não tocado).

## Modificadas

Nenhuma regra numerada do `domain.md` foi alterada — o impacto é inteiramente sobre GAPs de
infraestrutura (ver tabela em `_reversa_sdd/telephony/design.md#6`), não sobre regras de negócio
já confirmadas.

## Achado fora do escopo do repositório (não corrigido aqui)

GAP-NET-01: toda a cadeia de software confirmada funcionando ponta a ponta, mas o áudio capturado
é silêncio digital (RMS ≈ -90dB). Packet capture mostra apenas 1 pacote RTP real em ~6s de
chamada — sinalização SIP correta, mídia bloqueada. Suspeita de firewall/NAT no roteador Mikrotik
para a faixa de portas RTP (paralelo ao incidente de sinalização SIP resolvido em 2026-07-08).
Requer acesso ao Mikrotik, fora do escopo deste repositório.
