# Regression Watch: Gravação de ligação real com áudio ponta a ponta

> Identificador: `010-record-real-call-audio-e2e`

## Watch principal

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|--------------------------|-------------------------------|----------------------|--------------------|
| W001 | `src/telephony/esl_client.py` (`_read_events`) | Parsing de evento ESL respeita `Content-Length`, nunca faz split ingênuo por `"\n\n"` | presença | `grep -n 'Content-Length' src/telephony/esl_client.py` não encontra o parsing por header |
| W002 | `src/telephony/esl_client.py` (`_read_events`) | Timeout de leitura da conexão de eventos é alto (não deve voltar a ser um valor curto tipo 30s) | presença | `grep -n 'timeout=30' src/telephony/esl_client.py` encontra alguma ocorrência no contexto de `_read_events` |
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

_Nenhuma re-extração (`/reversa`) executada desde a geração deste arquivo._

## Arquivadas

_Nenhum item arquivado ainda._
