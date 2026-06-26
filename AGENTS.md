# Reversa

> Framework de Engenharia Reversa instalado neste projeto.

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
