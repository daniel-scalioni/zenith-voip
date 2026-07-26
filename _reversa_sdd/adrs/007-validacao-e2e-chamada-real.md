# ADR-007: Validação E2E de Chamada Real — Descoberta e Resolução de 9 GAPs de Infraestrutura

**Data:** 2026-07-15
**Status:** Aceito (concluído em produção 2026-07-23)
**Contexto:** zenith-voip — primeira execução ponta a ponta de uma chamada VoIP com gravação de áudio

---

## Contexto

Desde o commit inicial (2026-05-17), o projeto Zenith tinha arquitetura de B2BUA, pipeline de código, schema de banco de dados e infra Docker bem formada. Porém, **nenhuma chamada real jamais havia sido testada ponta a ponta** até 2026-07-14.

Quando a validação E2E foi executada (origém → 1001 → VitalPBX, retorno), descobriu-se que:

1. **Nenhum evento de canal real era processado** — todos descartados silenciosamente pelo ESLClient
2. **Nenhum registro `Call` jamais foi persistido** — toda escrita ao banco era revertida sem exceção
3. **O dialplan tinha bugs estruturais** que impediam o fluxo de gravação de ser alcançado
4. **Variáveis de contexto não existiam** no instante crítico do evento `CHANNEL_ANSWER`

Esses 9 bugs não foram introduzidos nesta sessão — eram **preexistentes desde o início do projeto**, nunca exercitados por falta de testes E2E com chamada real.

---

## Decisão

**Corrigir todos os bugs encontrados até conseguir:**
1. Conexão ESL processando eventos de canal real de forma confiável
2. Registro `Call` persistido no banco após chamada completa
3. Áudio capturado em arquivo MP3 (RX + TX)

A decisão foi iterativa e investigativa — cada correção revelava o próximo bug. O resultado final é que **a cadeia completa de software (dialplan → ESL → WebSocket → BD → arquivo) está funcionando ponta a ponta** pela primeira vez no histórico do projeto.

---

## Bugs encontrados e corrigidos

| ID | Componente | Tipo | Descrição | Resolução |
|----|-----------|----|-----------|-----------|
| GAP-VARS-01 | `freeswitch/conf/dialplan/default.xml` | Sintaxe | `${tenant_id}` (1 cifrão) resolvido sempre vazio — sintaxe errada para variáveis globais de pré-processador | Trocar para `$${tenant_id}` (2 cifrões) |
| GAP-DIALPLAN-04 | `freeswitch/conf/dialplan/default.xml` | Lógica | Variáveis `zenith_*` definidas **depois** de `answer()`, mas `CHANNEL_ANSWER` dispara **no** `answer()` → variáveis nunca chegavam populadas ao evento | Reordenar: todos os `set` antes de `answer()` |
| GAP-ESL-04 | `src/telephony/esl_client.py` | Timeout | Leitura com timeout de 30s causava reconexão desnecessária a cada ~30-40s em ociosidade, perdendo eventos | Aumentar para 300s |
| GAP-ESL-05 | `src/telephony/esl_client.py` | Framing | Split ingênuo por `"\n\n"` descartava todo evento de canal real como "non-JSON" | Implementar framing por `Content-Length` |
| GAP-ESL-06 | `src/telephony/esl_client.py` | Concorrência | Comandos e eventos usavam mesma conexão TCP → corrida de leitura | Separar em 2 conexões: `_connect_command()` + `_connect_events()` |
| GAP-ESL-07 | `src/telephony/esl_client.py` | Handshake | Saudação ESL (`auth/request`) não consumida antes de mandar `auth` | Ler e descartar saudação antes de autenticar |
| GAP-DB-01 | `src/database/database.py` | Transação | `session.commit()` não commitava a `Connection` — tudo revertido ao sair do `async with engine.connect()` | Adicionar `await conn.commit()` explícito |
| GAP-WS-01 | `src/audio/ingestor.py` | WebSocket | `receive_bytes()` em loop não tratava frame de texto (controle) → crash ao conectar de verdade | Usar `receive()` genérico, filtrando tipo de frame |
| LOG-01 | `src/main.py` | Setup | `logging.basicConfig()` nunca existia → nenhum log estruturado do projeto tinha garantia de aparecer | Adicionar setup de logging no bootstrap |

---

## Impacto: O que mudou

**Arquivos modificados (antes de 2026-07-15):**
- `src/telephony/esl_client.py` — 6 bugs críticos do protocolo ESL
- `src/database/database.py` — correção de transação de BD
- `src/audio/ingestor.py` — tratamento de WebSocket
- `freeswitch/conf/dialplan/default.xml` — 2 bugs de dialplan
- `src/main.py` — logging setup

**Nada foi introduzido novo** — foram **regressões de design/implementação pré-existentes**, corrigidas por primeira validação E2E.

---

## Validação

**Teste realizado (2026-07-14):**
- Chamada originada: ramal 1001 (3CX softphone local) → VitalPBX upstream
- Duração: ~6 segundos
- Resultado: Registro `Call` persistido com status `completed`, arquivos RX/TX criados
- Constatação: Conteúdo de áudio é **silêncio digital puro** (RMS ≈ -90dB, ~0.2s útil)
  - Packet capture revela: apenas **1 pacote RTP real** trafegando em 6s de chamada
  - Sinalização SIP está **100% correta** (INVITE/OK/ACK/BYE registrados)
  - **Conclusão:** bloqueio é de rede (RTP), não de código — registrado como **GAP-NET-01** (fora do escopo)

**Validação repetida (2026-07-23):**
- Após rebuild + redeploy de produção (confirmação de `mod_audio_stream` carregado)
- Mesmos resultados: gravação E2E confirmada funcionando, áudio silencioso por GAP-NET-01

---

## Riscos e mitigações

| Risco | Impacto | Mitigação |
|-------|--------|-----------|
| Regressão em chamadas existentes | Alto | Validação contínua com ramal 1001; alertas em logs de erro ESL |
| Novo bloqueio de rede descoberto | Médio | Monitoramento de RTP com ferramentas de captura; packet capture em próximas chamadas |
| Timeout de 300s afeta detecção de desconexão | Baixo | Desconexão real já é detectada por EOF no read(); timeout é proteção contra hang do kernel |

---

## Próximos passos

1. **GAP-NET-01:** Investigação de rede (Mikrotik, iptables, SDP de negociação RTP) — requer acesso fora do escopo deste repo
2. **Monitoramento:** Alertas na API para falha silenciosa de `uuid_audio_stream` (ver `regression-watch.md` da feature 010)
3. **Testes continuados:** Cada release do projeto deve ter validação de chamada E2E antes de deploy

---

## Referências

- `_reversa_forward/010-record-real-call-audio-e2e/` — detalhamento completo de cada correção
- `_reversa_sdd/telephony/design.md` — documentação dos GAPs e status
- `_reversa_sdd/gaps.md` — registry consolidado (GAP-NET-01 em GAP-24)
- Commit que iniciou a investigação: `fb490b8` (merge de 010-record-real-call-audio-e2e)
- Commit de conclusão em produção: `6629263` (docs: documenta causa raiz do GAP-NET-01)

---

## Decisões preservadas (não alteradas)

- **ADR-006 (B2BUA Registration Forwarding):** Padrão arquitetural mantido intacto
- **ADR-001 (Multitenancy schema-per-tenant):** Modelo de dados funcionando conforme especificado
- **Regras de negócio em `_reversa_sdd/domain.md`:** Nenhuma foi tocada — impacto é 100% de infraestrutura
