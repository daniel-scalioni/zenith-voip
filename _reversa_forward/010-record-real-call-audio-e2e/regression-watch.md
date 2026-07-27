# Regression Watch: Gravação de ligação real com áudio ponta a ponta

> Identificador: `010-record-real-call-audio-e2e`

## Watch principal

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|--------------------------|-------------------------------|----------------------|--------------------|
| W001 | `src/telephony/esl_client.py` (`_read_events`) | Parsing de evento ESL respeita `Content-Length`, nunca faz split ingênuo por `"\n\n"` | presença | `grep -n 'Content-Length' src/telephony/esl_client.py` não encontra o parsing por header |
| W002 | `src/telephony/esl_client.py` (`_read_events`) | Timeout de leitura da conexão de eventos é alto (≥ 300s; não deve voltar a um valor curto tipo 30s) | presença | `sed -n '/async def _read_events/,/async def _process_event/p' src/telephony/esl_client.py \| grep -qE 'timeout=[0-9]{1,2}(\.[0-9]+)?\)'` retorna sucesso (critério corrigido em 2026-07-27: o `grep 'timeout=30'` original casava com `timeout=300.0`, falso positivo; e um grep global pegaria os timeouts curtos legítimos de `connect`/`send_api`, por isso a extração do escopo da função) |
| W003 | `src/telephony/esl_client.py` (`send_api`/`send_bgapi`) | Comandos usam conexão dedicada (`_cmd_reader`/`_cmd_writer`), nunca a conexão de eventos (`self.reader`/`self.writer`) | presença | `send_api`/`send_bgapi` voltam a usar `self.reader`/`self.writer` diretamente |
| W004 | `freeswitch/conf/dialplan/default.xml` (`zenith_audio_fork`) | `set` das variáveis `zenith_*` acontece antes do `answer()` | presença/ordem | `answer()` aparece antes de algum `set(zenith_*)` na extension |
| W005 | `freeswitch/conf/dialplan/default.xml` (`zenith_audio_fork`) | `zenith_tenant_id`/`zenith_pbx_id` usam `$${...}` (pré-processador), não `${...}` (variável de canal) | presença | `grep -n 'zenith_tenant_id=\${tenant_id}"' freeswitch/conf/dialplan/default.xml` (um cifrão só) encontra alguma linha |
| W006 | `src/database/database.py` (`get_tenant_db`) | Há um `await conn.commit()` explícito após o trabalho da sessão, antes do `finally` | presença | `grep -n 'conn.commit' src/database/database.py` retorna vazio |
| W007 | `src/audio/ingestor.py` (`handle_forked_stream`) | Loop usa `websocket.receive()` genérico com checagem de tipo, não `receive_bytes()` direto | presença | `grep -n 'receive_bytes' src/audio/ingestor.py` encontra uso dentro do loop principal |

## Observações

- **GAP-NET-01 (RTP/mídia, fora do escopo de código):** não vira watch item porque não há regra
  de código do Zenith a proteger — é infraestrutura de rede (Mikrotik). Registrado em
  `_reversa_sdd/telephony/design.md#6` como item aberto (🔴). Se resolvido no futuro, o critério de
  validação é: `ffmpeg -af astats` numa gravação real mostra RMS acima do piso de ruído
  (atualmente ≈ -90dB) e duração compatível com a duração real da chamada.

## Histórico de re-extrações

### Re-extração 2026-07-27 (incremental, base 48da5b1 → 0658157)

| ID | Veredito | Observação |
|----|----------|------------|
| W001 | 🟢 verde | `_read_events()` faz framing por `Content-Length` com buffer em `bytes`; sem split por `"\n\n"` no corpo |
| W002 | 🟢 verde | Timeout de leitura é `300.0` (`esl_client.py:132`). O critério de violação do item foi corrigido nesta sessão (autorizado pelo usuário): o `grep 'timeout=30'` original casava com `timeout=300.0` e gerava falso positivo |
| W003 | 🟢 verde | `send_api`/`send_bgapi` delegam a `_send_command()`, que usa `_cmd_reader`/`_cmd_writer` sob `_cmd_lock`; nunca tocam `self.reader`/`self.writer` |
| W004 | 🟢 verde | No dialplan, os quatro `set` de `zenith_*` (linhas 22-25) precedem o `answer` (linha 26) |
| W005 | 🟢 verde | `zenith_tenant_id=$${tenant_id}` e `zenith_pbx_id=$${pbx_id}` — dois cifrões, variáveis globais |
| W006 | 🟢 verde | `await conn.commit()` presente em `database.py:28`, antes do `finally` |
| W007 | 🟢 verde | Loop usa `websocket.receive()` com checagem de tipo (`ingestor.py:42`); `receive_bytes` não aparece |


_Nenhuma re-extração (`/reversa`) executada desde a geração deste arquivo._

## Arquivadas

_Nenhum item arquivado ainda._
