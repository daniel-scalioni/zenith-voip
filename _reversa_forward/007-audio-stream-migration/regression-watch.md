# Regression Watch: Migração de mod_audio_fork para mod_audio_stream

> Identificador: `007-audio-stream-migration`

## Itens de observação

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|--------------------------|-------------------------------|------------------------|---------------------|
| W001 | `freeswitch/conf/sip_profiles/internal.xml`, `internal-7060.xml`, `internal-5062.xml` | Todos os profiles de entrada continuam `RUNNING` após qualquer rebuild/restart do container `freeswitch` motivado por mudanças de módulo | presença | `sofia status` mostra algum profile de entrada fora de `RUNNING` após deploy desta feature ou futuras |
| W002 | `freeswitch/Dockerfile` | O build da imagem FreeSWITCH usa por padrão os `.deb` vendorizados em `freeswitch/vendor/debs/`, sem exigir o repositório SignalWire estar disponível | presença | Build falha quando o repositório SignalWire está fora do ar, mesmo com `.deb` vendorizados presentes |
| W003 | `freeswitch/conf/dialplan/default.xml` (extensão `zenith_audio_fork`) | O comando de captura de áudio usa `uuid_audio_stream` (não mais `uuid_audio_fork`), apontando para `ws://zenith-api-1:8000/audio-stream` | presença | Dialplan volta a referenciar `uuid_audio_fork` ou aponta para URL diferente sem atualização correspondente em `src/audio/ingestor.py` |
| W004 | `src/audio/ingestor.py::_split_stereo_frame` | O payload recebido de `mod_audio_stream` é compatível com o de-interleaving PCM16 existente — **pendente de validação real** (ver Observações) | confiança | Uma chamada real mostra tx/rx trocados, corrompidos, ou o WebSocket nunca recebe dados |

## Observações (confidência 🟡/🔴, sem peso de regressão)

- 🔴 **T009 bloqueado nesta sessão**: não havia serviço `zenith-api-1`/FastAPI rodando no ambiente de produção (10.10.10.11) nem ramal registrado no momento da execução, então a validação end-to-end do payload de áudio (RF-04) não pôde ser executada. **Ação necessária antes de confiar cegamente em W004**: rodar uma chamada real assim que a aplicação Zenith estiver deployada nesse host, e atualizar este arquivo com o resultado.
- 🟡 Eventos novos gerados por `mod_audio_stream` (`mod_audio_stream::connect`, `::disconnect`, `::error`) não são consumidos por `src/telephony/esl_client.py` hoje — não é regressão, é oportunidade de observabilidade futura fora do escopo desta feature.

## Histórico de re-extrações

_Vazio — será preenchido na próxima execução de `/reversa` (extração reversa)._

## Arquivadas

_Vazio._
