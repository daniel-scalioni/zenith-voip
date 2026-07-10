# Regression Watch: Migração de mod_audio_fork para mod_audio_stream

> Identificador: `007-audio-stream-migration`

## Itens de observação

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|--------------------------|-------------------------------|------------------------|---------------------|
| W001 | `freeswitch/conf/sip_profiles/internal.xml`, `internal-7060.xml`, `internal-5062.xml` | Todos os profiles de entrada continuam `RUNNING` após qualquer rebuild/restart do container `freeswitch` motivado por mudanças de módulo | presença | `sofia status` mostra algum profile de entrada fora de `RUNNING` após deploy desta feature ou futuras |
| W002 | `freeswitch/Dockerfile` | O build da imagem FreeSWITCH usa por padrão os `.deb` vendorizados em `freeswitch/vendor/debs/`, sem exigir o repositório SignalWire estar disponível | presença | Build falha quando o repositório SignalWire está fora do ar, mesmo com `.deb` vendorizados presentes |
| W003 | `freeswitch/conf/dialplan/default.xml` (extensão `zenith_audio_fork`), `freeswitch/conf/vars.xml` | O comando de captura de áudio usa `uuid_audio_stream`, apontando para `ws://${zenith_api_host}/audio-stream/${uuid}` — `zenith_api_host` (`127.0.0.1:8001`) existe porque o FreeSWITCH roda em `network_mode: host` e não resolve nomes de container Docker (`zenith-api-1`) | presença | Dialplan volta a usar hostname de container Docker direto, ou `zenith_api_host` é removido de `vars.xml` sem atualizar o dialplan |
| W004 | `src/audio/ingestor.py::_split_stereo_frame`, `src/main.py::audio_stream` | O payload recebido de `mod_audio_stream` é compatível com o de-interleaving PCM16 existente; a rota WebSocket `/audio-stream/{call_id}` precisa estar registrada em `src/main.py` (não existia antes desta feature — GAP novo descoberto e corrigido) | presença | Rota removida de `main.py`, ou tx/rx aparecem trocados/corrompidos nos eventos `audio_chunk` |

## Observações (confidência 🟡/🔴, sem peso de regressão)

- 🟢 **T009 validado em 2026-07-10**: `zenith-api-1` buildado e rodando (`healthy`) pela primeira vez neste host (após features `008-piper-tts-standalone` remover os bloqueios de dependência). Validação feita com um cliente WebSocket direto simulando o payload binário PCM16 estéreo que `mod_audio_stream` envia — Redis Streams confirmou dois eventos `audio_chunk` (`channel: tx`, `channel: rx`, 320 bytes cada) para um frame de 640 bytes enviado, confirmando o de-interleaving correto. **Não foi originada uma chamada telefônica real** (bridged para VitalPBX) para evitar custo/risco desnecessário — o caminho de código exercitado é idêntico ao que uma chamada real usaria.
- 🟢 **Gap adicional descoberto e corrigido nesta sessão**: a rota WebSocket `/audio-stream` nunca tinha sido registrada em `src/main.py` — `AudioIngestor.handle_forked_stream` existia mas não estava conectado a nenhum endpoint FastAPI. Adicionada como `/audio-stream/{call_id}` (path param, não mais metadata-only), com o dialplan atualizado para incluir `${uuid}` na URL.
- 🟡 Eventos novos gerados por `mod_audio_stream` (`mod_audio_stream::connect`, `::disconnect`, `::error`) não são consumidos por `src/telephony/esl_client.py` hoje — não é regressão, é oportunidade de observabilidade futura fora do escopo desta feature.

## Histórico de re-extrações

_Vazio — será preenchido na próxima execução de `/reversa` (extração reversa)._

## Arquivadas

_Vazio._
