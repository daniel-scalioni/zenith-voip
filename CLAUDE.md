# Reversa

> Framework de Engenharia Reversa instalado neste projeto.

## Regra permanente de execução

Sempre montar um plano antes de executar ações (mudanças de config, código, infra, comandos remotos via SSH, etc.) e apresentá-lo ao usuário antes de sair executando, mesmo quando o usuário já autorizou execução autônoma da tarefa em si.

## Como usar

Digite `reversa` para ativar o Reversa e iniciar ou retomar a análise do projeto.

## Comportamento ao ativar

Quando o usuário digitar `reversa` sozinho em uma mensagem:

1. Ative o skill `reversa` disponível em `.agents/skills/reversa/SKILL.md`
2. Leia o SKILL.md na íntegra e siga exatamente as instruções do Reversa

## Regra não-negociável

Nunca apague, modifique ou sobrescreva arquivos pré-existentes do projeto legado.
O Reversa escreve **apenas** em `.reversa/` e `_reversa_sdd/`.

## 🏛️ Padrões do Projeto

### 🌐 Idioma
Respostas, docs e comentários em **pt-BR**. Código, variáveis e funções em **inglês**.

### 🟦 Stack
`Python 3.12+` · `FastAPI` · `Pydantic v2` (`pydantic-settings`) · `SQLAlchemy 2.0 (async, asyncpg)` · `Alembic` · `arq` (workers + cron sobre Redis) · `redis` · `pytest` + `pytest-asyncio` · `greenswitch`/ESL bruto (FreeSWITCH) · `Docker Compose`

### 🧱 Organização por domínio
```
src/
├── api/          → routers FastAPI, auth (JWT), middlewares (rate limit), websockets
├── audio/        → ingestão de stream de áudio (mod_audio_fork)
├── telephony/    → integração FreeSWITCH via ESL (eventos, whisper mode, filler audio)
├── services/     → regras de negócio + acesso a dados (Repository genérico em services/base.py)
├── database/     → models SQLAlchemy (multi-tenant: schema público + schema por tenant) e engine/sessions
├── workers/      → jobs e cron jobs arq (upload/cleanup de áudio, persistência de transcript, pós-chamada)
├── events/       → publish/consume sobre Redis Streams
├── ai/           → grafos LangGraph, cache, detecção de anomalia
├── extraction/   → camadas de extração (regex + LLM)
├── observability/, utils/ → telemetria (OpenTelemetry/Prometheus)
└── config.py     → Settings (pydantic-settings, single source de configuração via env)
```
Esta é a organização real do projeto: **por domínio/funcionalidade**, não por camada arquitetural genérica (`presentation/application/domain/infrastructure`). Não force essa separação em quatro pastas — ela não existe aqui e não deve ser introduzida sem decisão explícita registrada em ADR (`_reversa_sdd/adrs/`).

**Convenção transversal que se aplica, dentro de cada domínio:**
- Rotas/handlers de entrada (FastAPI routers, ESL event handlers, WebSocket handlers) ficam finos — delegam para `services/` ou `workers/`.
- `services/` concentra regra de negócio e acesso a dados via `Repository` (nunca SQL solto em rota/handler).
- `database/models.py` não importa nada de `api/`, `telephony/` ou `workers/` (sem ciclo de dependência domínio → entrada).

### 📐 Design Patterns (já em uso neste projeto)
| Pattern | Onde está aplicado |
|---------|--------------------|
| **Repository** | `src/services/base.py::Repository` — genérico (`ModelType`), usado por `src/services/calls.py` e pelos routers de CRUD (`src/api/routers/pbxs.py`) |
| **Strategy** | `src/services/base.py` — `STTStrategy`/`TTSStrategy`/`LLMStrategy`, implementadas por `stt_deepgram.py`/`stt_whisper.py`/`tts_service.py`/`tts_fallback.py` |
| **Factory** | `src/services/base.py::Factory` — `create_pipeline(tenant_id)` monta o conjunto de strategies por tenant |
| **Singleton (módulo, lazy init)** | Instâncias globais a nível de módulo: `settings` (`config.py`), `esl_client` (`telephony/esl_client.py`), `audio_ingestor` (`audio/ingestor.py`), `event_bus` (`events/redis_streams.py`), engine/`async_session_factory` (`database/database.py`). Nunca usar classe Singleton explícita — seguir esse padrão de módulo. |
| **Observer / Event-driven** | `src/events/redis_streams.py` (publish) + handlers de evento ESL em `telephony/esl_client.py::_process_event` (CHANNEL_ANSWER/HANGUP/SOFIA_REGISTER/...) — desacoplado via Redis Streams, não callback direto |
| **DI** | `Depends()` do FastAPI (sessão de banco, auth/`require_admin_role`, etc.) — não service locator |

### 📋 SDD (Spec-Driven Development)
1. **Spec primeiro, sempre** — toda alteração de código deste projeto exige spec correspondente em `_reversa_sdd/<área>/` (ex: `_reversa_sdd/telephony/`, `_reversa_sdd/workers/audio-upload/`) **antes** do código que ela descreve. O código reflete a spec; a spec nunca é escrita só para descrever o que o código já faz.
2. **Front Matter YAML** no topo de cada spec (legível pelo harness):
```yaml
---
spec:
  component: audio-uploader      # identificador único
  layer: workers                 # api | services | database | telephony | audio | workers | events | ai | extraction
  status: active                 # active | draft | deprecated
  version: 1.0.0
  language: python
  patterns: [repository, strategy]
  inputs: [{name, type, from}]
  outputs: [{name, type, to}]
  dependencies: [{component, layer}]
  events_produced: [CallRecorded]
  updated_at: 2026-06-23
---
```
3. **Alterar spec antes do código** — violação alterar código sem a spec correspondente refletir a mudança primeiro.
4. **Ciclo de evolução**: usar `/reversa-forward` (requirements → clarify → plan → to-do → audit/quality → coding) para qualquer feature ou ajuste novo — mantém versionamento e evita estourar o contexto do modelo. A etapa de código usa o passo nativo `/reversa-coding` do próprio `/reversa-forward`. `/reversa-migrate` é um pipeline diferente (Time de Migração: paradigm-advisor → curator → strategist → designer → inspector), reservado para mudança de paradigma de um sistema legado — não usar para evolução incremental deste projeto.

### 🧪 Quality Gates (bloqueantes)
```
pytest tests/ -v                              → suite de testes (pytest + pytest-asyncio, ver tests/)
alembic upgrade head                          → migrations aplicam sem erro antes de qualquer deploy
```
Não há hoje linter/formatter/type-checker fixado no projeto (`requirements.txt` não pina `ruff`/`black`/`mypy`). Se for adotado um desses, registrar a decisão em ADR (`_reversa_sdd/adrs/`) antes de torná-lo bloqueante aqui.

### 🚫 Anti-Padrões
SQL solto fora de `services/`/`Repository` · `print()` em vez de logging estruturado · `import *` · herança > 2 níveis → preferir composição · God Class · variável de canal FreeSWITCH lida sem checar se foi de fato definida (ver histórico de `pbx_host`/`tenant_id` nunca populados) · segredos hardcoded ou colados em specs/commits (usar arquivo gitignored + `.example`, padrão `freeswitch/signalwire_token.txt`) · `except Exception` genérico sem log do erro original

### 🧠 Legibilidade
Nomes que revelam intenção · máximo 2 níveis de indentação · métodos pequenos e de responsabilidade única · comentários só para o "porquê" (decisão não-óbvia), nunca para o "o quê"

---

## 🎯 O que é Zenith?

**Zenith AI Audio Hub** é um sistema de IA para transcrição e análise de chamadas VoIP em tempo real. Funciona como um **B2BUA (Back-to-Back User Agent)** posicionado entre os interfones/softphones do cliente e o PBX de produção (VitalPBX/GPhone).

### Topologia SIP: B2BUA com Registration Forwarding

```
Interfone/Softphone (IP local do cliente)
    │  REGISTER ext=1001 → sip:freeswitch:5060
    ▼
FreeSWITCH (10.10.10.11:5060) — profile "internal"
    │  Aceita REGISTER, re-registra upstream
    │  REGISTER ext=1001 → sip.maisalerta.tecnorise.com:PORT
    ▼
VitalPBX (177.71.153.68 / sip.maisalerta.tecnorise.com)
    │  Enxerga ramal como registrado (via FreeSWITCH, transparente)
    ▼
FreeSWITCH captura áudio (mod_audio_fork) → Zenith API → Transcrição/IA
```

**Por que B2BUA:** Um proxy SIP simples encaminha SDP sem tocar em mídia — impossível capturar áudio. O B2BUA termina a chamada em cada lado, reconstrói-a, e controla o áudio. O `mod_audio_fork` só funciona quando FreeSWITCH é a ponte de mídia.

### Infraestrutura

| Componente | Localização | Porta | Função |
|---|---|---|---|
| **VitalPBX** | Cloud (177.71.153.68) | 7060 (PJSIP), 5060 (SIP) | PBX de produção; fonte de verdade dos ramais |
| **FreeSWITCH** | Docker (10.10.10.11) | 5060 (internal), 5065 (upstream) | B2BUA; registra cada ramal upstream |
| **PostgreSQL** | Docker | 5432 | Multi-tenant schema-per-tenant |
| **Redis** | Docker | 6379 | Fila de eventos, cache, mapeamento IP→ext |
| **FastAPI** | Docker | 8000 | API REST, ESL client, transcrição |
| **Deepgram API** | Cloud | HTTPS | STT primário (fallback: Whisper local) |
| **Ollama** | Docker | 11434 | LLM local (Mistral 7B, dados sensíveis nunca saem) |

### Importação de Ramais: `import_extensions.py`

O script `scripts/import_extensions.py` lê o CSV exportado do VitalPBX (`specs/export_extensions.csv`) e gera:
- `freeswitch/conf/directory/extensions.xml` — usuários para autenticação local
- `freeswitch/conf/sip_profiles/upstream/upstream-{ext}.xml` — gateways upstream por ramal

**Dedup:** Se um ramal tem entradas SIP e PJSIP no CSV, PJSIP prevalece (porta 7060). Exemplo: ramal 1001 tem ambas; FreeSwitch usa PJSIP:7060.

**Registro:** Por padrão todos têm `register=false` (seguro para produção). Ativa com `--enable 1001`:
```bash
python3 scripts/import_extensions.py specs/export_extensions.csv --enable 1001
# Depois copiar os arquivos e fazer "sofia profile upstream rescan" no FreeSWITCH
```

### Docker Compose

- **app**: FastAPI (Zenith API) + ESL client
- **freeswitch**: Central telefônica com B2BUA
- **postgres**: Base de dados multi-tenant
- **redis**: Fila de eventos
- **ollama**: LLM local
- **bunkerweb**: Proxy reverso com sticky session

Containers NO MESMO HOST (10.10.10.11), comunicação via Docker network.

### Credenciais e Segurança

| Item | Local | Nota |
|---|---|---|
| SSH server (10.10.10.11) | Usuario `administrator`, senha `&sol53AL` | Para acessar logs/debug do FreeSWITCH |
| JWT_SECRET | `config.py` | ALTERAR em produção (atual: "change-me-in-production") |
| ESL password | `config.py` | Default FreeSWITCH ("ClueCon") — registrado em ADR-005 como to-do |
| Senhas SIP | CSV + senhas salvas em banco (cifradas) | NUNCA commitar `upstream-*.xml` ou `extensions.xml` |
| S3 credentials | `.env` (gitignored) | Via variáveis de ambiente, nunca em commits |
