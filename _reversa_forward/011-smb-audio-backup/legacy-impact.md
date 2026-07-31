# Impacto no legado: SMB Audio Backup

> Data: `2026-07-31`
> Feature: `011-smb-audio-backup`
> Âncora: `_reversa_sdd/architecture.md` + `_reversa_sdd/domain.md`
> Estado: codificação concluída; gates operacionais de ambiente pendentes

## Arquivos afetados

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|-----------------|------------|------|------------|---------------|
| `src/workers/smb_sync.py` | Workers ARQ | componente-novo | HIGH | Publica áudio em storage externo e controla integridade/retry |
| `src/workers/audio_uploader.py` | Audio uploader | regra-alterada | HIGH | MP3 final passa a significar conversão concluída por rename atômico |
| `src/workers/audio_cleanup.py` | Audio cleanup | regra-alterada | HIGH | Cleanup respeita lease SMB válido |
| `src/config.py` | Settings | delta-de-contrato-externo | MEDIUM | Novas configurações SMB validadas |
| `src/utils/telemetry.py` | Observabilidade | regra-nova | LOW | Métricas SMB sem alta cardinalidade |
| `src/services/calls.py` | Persistência de chamada | delta-de-dados | MEDIUM | Passa a preencher campos caller/callee já existentes |
| `src/telephony/esl_client.py` | Integração FreeSWITCH ESL | regra-alterada | MEDIUM | Encaminha metadados presentes no CHANNEL_ANSWER |
| `docker-compose.app.yml` | Infraestrutura | componente-novo | HIGH | Novo `zenith-smb-sync`, volume de log e retenção de duas horas |
| `requirements.txt` | Dependências | delta-de-contrato-externo | MEDIUM | Adiciona `pysmb==1.2.14` |
| `.env.example` | Configuração | delta-de-contrato-externo | MEDIUM | Documenta contrato sem segredos |
| `_reversa_sdd/database/migrations/*` | Banco/multitenancy | regra-nova | HIGH | Define baseline pública, restore e isolamento antes do código |
| `_reversa_sdd/adrs/011-baseline-publica-e-provisionamento-tenant.md` | Arquitetura de dados | regra-nova | HIGH | Decide responsabilidades Alembic/tenant e preserva o banco atual |
| `docker-compose.quality.yml` | Infraestrutura de testes | componente-novo | HIGH | Banco e runner exclusivos, sem porta publicada |

## Diff conceitual

### Workers ARQ

Surge um worker pull independente da gravação. Ele deriva estéreo dos monos, usa publicação SMB
temporária, checksum antes e depois do rename, retry/circuit breaker, throttle, lock de ciclo e lease
por chamada. O log persistente permite idempotência após restart. Uploader, cleanup e SMB passam a
consumir filas ARQ exclusivas; o produtor de gravação publica diretamente em
`zenith:audio-upload`, eliminando consumo cruzado e `function not found`.

### Audio uploader e cleanup

O uploader deixa de escrever diretamente no nome MP3 final. O cleanup mantém sua varredura por
mtime, mas não remove chamadas cobertas por lease válido. A retenção configurada passa de cerca de
uma para duas horas.

### Persistência e telefonia

Nenhuma migration foi criada: `caller_number`, `callee_number` e `started_at` já existiam. O evento
ESL passa a alimentar os dois números quando presentes e preserva a assinatura anterior quando
ausentes.

### Contrato externo SMB

O Zenith passa a escrever em storage LAN usando conta técnica. O artefato remoto é MP3 estéreo
separável, organizado por tenant/data e nunca aceito como concluído sem checksum.

### Migrations e banco de qualidade

A recuperação dos gates passa a usar baseline Alembic restrita ao schema `public`; schemas de
tenant são provisionados explicitamente. Teste, rehearsal e candidato terão recursos distintos.
O PostgreSQL operacional e seu volume permanecem intocados porque a porta publicada impede provar
exclusividade externa absoluta. Nesta rodada só foram criadas specs e configuração de qualidade;
nenhum banco ou container foi criado.

## Regras 🟢 preservadas

- R37: cleanup continua executando a cada 15 minutos.
- R40: falha de conversão continua preservando `.raw`.
- R41: `RECORDINGS_PATH/<tenant>/<call>/<channel>.mp3` continua sendo o layout dos monos.
- O processamento SMB permanece fora da cadeia crítica de gravação.
- Isolamento por tenant permanece explícito no diretório remoto e na consulta de metadados.
- ADR-001: o modelo schema-per-tenant permanece; a baseline pública não cria tabelas de negócio.

## Regras 🟢 modificadas

- R38: a cópia local continua em tmpfs, mas passa a existir uma segunda cópia persistente no
  storage SMB da LAN.
- R39: `tx.mp3` e `rx.mp3` continuam monos separados; agora existe também um `stereo.mp3`
  transitório e um MP3 estéreo remoto derivado, sem mixar os canais.
- Retenção operacional: o default local passa de aproximadamente uma para duas horas, e o estéreo
  derivado é removido logo após checksum remoto confirmado.
- Processo de migration: Alembic passa a ser responsável apenas por estruturas globais; o
  provisionamento físico de tenant torna-se uma operação explícita e testável.
