# Impacto no legado — feature 014-captura-wav-16k

Data: 2026-08-17
Âncora: `_reversa_sdd/architecture.md` e `_reversa_sdd/domain.md`

## Arquivos e componentes afetados

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|---|---|---|---|---|
| `src/telephony/esl_client.py` | Telephony / ESL | regra-alterada | HIGH | Solicita captura estéreo em 16 kHz e mantém o início no `CHANNEL_ANSWER`. |
| `src/audio/ingestor.py` | Audio ingestion | regra-alterada | HIGH | Troca buffer integral em RAM por escrita incremental e publicação atômica de `.raw`. |
| `src/audio/recording_lifecycle.py` | Recording lifecycle | componente-novo | HIGH | Introduz leases renováveis e exclusão cross-stage por owner para captura, conversão e SMB. |
| `src/audio/capacity.py` | Recording capacity | componente-novo | HIGH | Reserva capacidade e aplica histerese sem interromper o SIP. |
| `src/workers/audio_uploader.py` | Audio upload | regra-alterada | HIGH | Converte PCM16 16 kHz para WAV atômico e preserva o raw até consumo/TTL. |
| `src/workers/smb_sync.py` | SMB backup | regra-alterada | HIGH | Publica `stereo.wav`, verifica checksum, confirma consumo e mantém chamadas ocupadas/incompletas invisíveis ao log. |
| `src/workers/audio_cleanup.py` | Audio cleanup | regra-alterada | HIGH | Separa finais consumidos, TTL e temporários órfãos observados em duas rodadas. |
| `src/workers/recording_consumers.py` | Recording consumers | componente-novo | MEDIUM | Registra confirmação atômica por consumidor. |
| `src/config.py` | Configuração | delta-de-contrato-externo | MEDIUM | Expõe consumidores, leases, capacidade e margens como settings. |
| `src/utils/telemetry.py` | Telemetria | regra-nova | MEDIUM | Mede reservas, modo degradado, cleanup e falhas de lease. |
| `docker-compose.app.yml` | Infraestrutura de gravação | delta-de-dados | HIGH | Amplia o tmpfs de 512 MiB para 2 GiB e distribui as novas settings. |
| `tests/test_recording_capacity_integration.py` e testes colocalizados | Testes | regra-nova | MEDIUM | Provam formato, atomicidade, concorrência, cleanup e capacidade. |

## Diff conceitual por componente

O caminho SIP continua sendo B2BUA e a captura continua disparada pela aplicação via ESL. A
mudança ocorre depois do estabelecimento: o áudio deixa de ser acumulado integralmente em RAM,
passa por nomes transitórios, é publicado como raw final e convertido para WAV PCM16 mono 16 kHz.

O backup SMB deriva um WAV estéreo, publica por temporário remoto com checksum e só então marca o
consumo. Cleanup e capacidade passam a cooperar por leases, confirmações e margem projetada.
Leases de owners distintos se excluem entre todos os estágios; operações compostas reutilizam o
mesmo owner, eliminando a janela entre captura/conversão e reivindicação SMB. O
dialplan e os profiles introduzidos pela feature 012 não foram alterados pela 014.

## Regras preservadas

- R37: cleanup continua executando a cada 15 minutos.
- R40: falha de conversão preserva o `.raw` e degrada sem perder o áudio.
- R42: captura continua iniciada pela aplicação via ESL no `CHANNEL_ANSWER`, não pelo dialplan.
- R43: pares do frame continuam sendo `tx` e ímpares continuam sendo `rx`.
- R52: apenas `INSTANCE_ID == 1` consome o stream ESL.
- R55: somente recursos Docker com prefixo `zenith-`/`zenith_` foram tocados.

## Regras modificadas

- R38: tmpfs de gravações passa de 512 MiB para 2 GiB, ainda em RAM.
- R39: canais deixam de ser MP3 mono 8 kHz e passam a WAV PCM16 mono 16 kHz.
- R41: o layout mantém tenant/chamada/canal, mas o final muda de `.mp3` para `.wav` e ganha
  estados transitórios explícitos.

## Observação sobre a feature 012

A feature 012 causou uma regressão anterior ao remover o fallback global de tenant/PBX do
dialplan. A correção `6ff0ec7` restaurou o contexto condicionalmente. Em 2026-08-17, chamadas reais
para ATA e ramal simples comprovaram bridge upstream, criação de Call e captura; a indisponibilidade
observada antes do teste era a whitelist do VitalPBX para o novo IP público.
