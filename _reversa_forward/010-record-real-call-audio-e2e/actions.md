# Actions: Gravação de ligação real com áudio ponta a ponta

> Identificador: `010-record-real-call-audio-e2e`
> Data: `2026-07-14/15`
> Roadmap: n/a — feature investigativa, decomposta retroativamente conforme os bugs foram
> encontrados por teste real ao vivo (packet capture + logs em tempo real), não por planejamento
> prévio. Cada ação abaixo corresponde a um bug real encontrado e corrigido nesta sessão.

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 9 |
| Paralelizáveis (`[//]`) | 0 (cada bug só ficou visível depois do anterior ser corrigido) |
| Maior cadeia de dependência | 9 (investigação sequencial) |

## Fase 3, Núcleo (bugs de infraestrutura, na ordem em que foram descobertos e corrigidos)

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T001 | Adicionar `logging.basicConfig()` em `src/main.py` — sem isso nenhum log estruturado do projeto (incluindo os `logger.warning` já existentes) tinha garantia de aparecer em lugar nenhum | - | - | `src/main.py` | 🟢 | `[X]` |
| T002 | Envolver o dispatch de eventos em `ESLClient._process_event` com `try/except Exception: logger.exception(...)` — exceções dentro de handlers de evento matavam o loop de eventos inteiro silenciosamente (GAP-ESL-04/05/06 só ficaram visíveis depois desse log existir) | T001 | - | `src/telephony/esl_client.py` | 🟢 | `[X]` |
| T003 | Aumentar timeout de leitura de `_read_events` de 30s para 300s (GAP-ESL-04: reconexão desnecessária a cada ~30-40s de ociosidade, janela de perda de eventos) | T002 | - | `src/telephony/esl_client.py` | 🟢 | `[X]` |
| T004 | Corrigir framing do protocolo ESL em `_read_events` para respeitar `Content-Length` em vez de split por `"\n\n"` (GAP-ESL-05: todo evento de canal real era descartado como "non-JSON" desde sempre) | T003 | - | `src/telephony/esl_client.py` | 🟢 | `[X]` |
| T005 | Separar conexão de comandos (`_connect_command`/`_send_command`) da conexão de eventos (GAP-ESL-06: corrida de leitura entre `send_bgapi` e o loop de eventos na mesma conexão) | T004 | - | `src/telephony/esl_client.py` | 🟢 | `[X]` |
| T006 | Consumir a saudação inicial do ESL (`Content-Type: auth/request`) antes de enviar `auth`, em `connect()` e `_connect_command()` (GAP-ESL-07) | T005 | - | `src/telephony/esl_client.py` | 🟢 | `[X]` |
| T007 | Trocar `${tenant_id}`/`${pbx_id}` por `$${tenant_id}`/`$${pbx_id}` no dialplan (GAP-VARS-01: variável de canal vs. variável global de pré-processador) | T006 | - | `freeswitch/conf/dialplan/default.xml` | 🟢 | `[X]` |
| T008 | Reordenar `zenith_audio_fork`: todos os `set` de variáveis `zenith_*` antes do `answer()` (GAP-DIALPLAN-04: `CHANNEL_ANSWER` disparava antes das variáveis existirem no canal) | T007 | - | `freeswitch/conf/dialplan/default.xml` | 🟢 | `[X]` |
| T009 | Corrigir `get_tenant_db` para commitar a `Connection` explicitamente, não só a `Session` (GAP-DB-01: nenhum `Call` nunca persistia, rollback silencioso ao sair do `async with engine.connect()`) | T008 | - | `src/database/database.py` | 🟢 | `[X]` |

## Fase 4, Integração

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T010 | Corrigir `AudioIngestor.handle_forked_stream` para tratar frame de texto (controle) separado de frame binário (áudio) via `websocket.receive()` genérico (GAP-WS-01: `KeyError: 'bytes'` na primeira vez que `mod_audio_stream` conseguiu conectar de verdade) | T009 | - | `src/audio/ingestor.py` | 🟢 | `[X]` |
| T011 | Mover `_start_audio_capture` para dentro do `if tenant_id:` em `_handle_channel_answer` (GAP-ESL-08: disparo duplicado, uma vez por perna da chamada bridgeada) | T010 | - | `src/telephony/esl_client.py` | 🟢 | `[X]` |

## Fase 5, Polimento / Validação

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T012 | Validar end-to-end: chamada real (1001 → 20991) gera registro em `tenant_akom.calls` (status `completed`) e arquivos `rx.mp3`/`tx.mp3` em `/data/recordings/akom/<call_id>/` | T011 | - | n/a (validação manual) | 🟢 | `[X]` |
| T013 | Confirmar via `ffprobe`/`ffmpeg astats` se o áudio gravado contém voz real ou silêncio | T012 | - | n/a (validação manual) | 🟢 | `[X]` |

## Notas de execução

- **Resultado de T012/T013:** a cadeia de software (dialplan → ESLClient → `uuid_audio_stream` →
  WebSocket → `AudioIngestor` → upload → banco → MP3) está **confirmada funcionando ponta a ponta**
  pela primeira vez no histórico do projeto — `call_id` persistido com `status=completed`,
  arquivos `rx.mp3`/`tx.mp3` criados. Porém o conteúdo de áudio é silêncio digital puro
  (RMS ≈ -90dB, ~0.2s de duração útil). Packet capture (ver `investigation.md`) confirma apenas
  1 pacote RTP real trafegado em ~6s de chamada — a causa é de rede (RTP não chega), não de
  código. Registrado como **GAP-NET-01** (🔴 aberto) em `_reversa_sdd/telephony/design.md`,
  fora do escopo deste repositório (requer acesso ao roteador Mikrotik).
- Esta feature não fecha 100% do objetivo original (voz real audível na gravação), mas resolve
  8 bugs de infraestrutura reais e pré-existentes (nenhum deles introduzido nesta sessão, todos
  presentes desde commits anteriores — só nunca tinham sido exercitados por uma chamada real).

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-07-15 | Versão gerada retroativamente por `/reversa-coding` a partir da investigação ao vivo | reversa |
