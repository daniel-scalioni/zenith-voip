# Zenith AI Audio Hub

> Instruções de projeto para agentes de IA. Este é o arquivo canônico — `CLAUDE.md` é um symlink para ele, portanto qualquer harness que leia um dos dois vê exatamente o mesmo conteúdo. Edite sempre `AGENTS.md`.

## Regra permanente de execução

Sempre montar um plano antes de executar ações (mudanças de config, código, infra, comandos remotos via SSH, etc.) e apresentá-lo ao usuário antes de sair executando, mesmo quando o usuário já autorizou execução autônoma da tarefa em si.

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

### Serviços do Docker Compose

- **app**: FastAPI (Zenith API) + ESL client
- **freeswitch**: Central telefônica com B2BUA
- **postgres**: Base de dados multi-tenant
- **redis**: Fila de eventos
- **ollama**: LLM local
- **bunkerweb**: Proxy reverso com sticky session

Containers NO MESMO HOST (10.10.10.11), comunicação via Docker network. A política de nomes e isolamento está em [🐳 Docker & Containers](#-docker--containers-regra-crítica).

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

### Credenciais e Segurança

| Item | Local | Nota |
|---|---|---|
| SSH server (10.10.10.11) | Usuario `administrator`, chave `~/.ssh/id_ed25519` (senha local/sudo em `.claude/deploy-access.local.md`, gitignored) | Para acessar logs/debug do FreeSWITCH |
| JWT_SECRET | `config.py` | ALTERAR em produção (atual: "change-me-in-production") |
| ESL password | `config.py` | Default FreeSWITCH ("ClueCon") — registrado em ADR-005 como to-do |
| Senhas SIP | CSV + senhas salvas em banco (cifradas) | NUNCA commitar `upstream-*.xml` ou `extensions.xml` |
| S3 credentials | `.env` (gitignored) | Via variáveis de ambiente, nunca em commits |

---

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
4. **Ciclo de evolução**: usar `/reversa-forward` (requirements → clarify → plan → to-do → audit/quality → coding → sync) para qualquer feature ou ajuste novo — mantém versionamento e evita estourar o contexto do modelo. A etapa de código usa o passo nativo `/reversa-coding` do próprio `/reversa-forward`; emendas curtas na feature ativa usam `/reversa-add`. `/reversa-migrate` é um pipeline diferente (Time de Migração: paradigm-advisor → curator → strategist → designer → inspector), reservado para mudança de paradigma de um sistema legado — não usar para evolução incremental deste projeto.

### 🔴 TDD (Test-Driven Development) — obrigatório

#### Fluxo Red → Green → Refactor
1. **Red** — escreva o teste que falha *antes* de implementar qualquer código
2. **Green** — escreva o mínimo de código para o teste passar
3. **Refactor** — melhore sem quebrar os testes

#### Estrutura de testes
- Arquivo: `test_<componente>.py` no mesmo diretório do arquivo testado
- Nomenclatura: `def test_<verbo>_<comportamento>()`
- Padrão **AAA**: `# Arrange` / `# Act` / `# Assert` — cada bloco separado por linha em branco
- Mocks: use `pytest.MonkeyPatch` ou `unittest.mock` apenas em *ports* (interfaces externas); nunca mocke código de domínio
- Framework: `pytest` + `pytest-asyncio`

Os testes vivem em **dois lugares**: `tests/` (suíte transversal) e `src/**/test_*.py` (ao lado do código testado, o caso majoritário). Ver [🧪 Quality Gates](#-quality-gates-bloqueantes) para o comando que coleta ambos.

#### Escopo por camada
| Camada | Tipo de teste | O que mockar |
|--------|--------------|--------------|
| `services/` | Unitário com mocks | Repositórios, clientes externos (ESL, Redis, S3) |
| `database/` | Integração | Substituir conexão real por test double ou banco de teste temporário |
| `api/` | Integração com TestClient | Sessão de banco, autenticação |
| `workers/` | Unitário com mocks | Redis, banco, S3 |
| `ai/`, `extraction/` | Unitário puro | Nada — funções determinísticas |

#### Cobertura mínima
- Toda nova feature: ≥ 80% de linhas cobertas (gate bloqueante, ver abaixo)
- Toda correção de bug: teste de regressão obrigatório, nomeando explicitamente o cenário

#### Veredito de LLM independente (anti-viés) — obrigatório

Quando o mesmo agente escreve código **e** testes, existe risco sistêmico de viés: os testes cobrem o que foi implementado, não necessariamente o que deveria funcionar.

**Regra:** após escrever testes para código que você mesmo gerou, chame `advisor()` com os arquivos de código e teste abertos no contexto e a pergunta explícita:

> "Há casos de borda não cobertos? Os testes estão viesados para esta implementação específica?"

O advisor deve verificar:
- Casos de borda ausentes (`None`, `{}`, `[]`, valores-limite, concorrência, erros de rede)
- Testes que testam o *como* em vez do *o quê* (acoplamento à implementação interna)
- Cenários de falha não testados (caminho infeliz)
- Se a cobertura ≥ 80% é real ou inflada por testes triviais que não provam comportamento

**Sem o veredito do advisor**, testes escritos pelo mesmo agente que gerou o código são considerados 🟡 (inferidos) nas specs SDD — não 🟢 confirmados.

### 🧪 Quality Gates (bloqueantes)

Este é o bloco canônico de gates do projeto — não duplique estes comandos em outras seções.

```
pytest -v tests src                           → suíte principal (ambos os caminhos, sempre)
pytest -v tests src --cov=src --cov-fail-under=80  → cobertura mínima de 80% (nova feature)
alembic upgrade head                          → migrations aplicam sem erro antes de qualquer deploy
```

**Passe sempre `tests src` — nem só `tests/`, nem a raiz nua.** Os testes vivem nos dois lugares e a maioria está em `src/` (~25 arquivos contra ~13 em `tests/`), então `pytest tests/` isolado deixa a maior parte da suíte de fora e dá falsa sensação de verde. Já `pytest` sem caminho nenhum é pior: o `pytest.ini` não define `testpaths`, e a coleta da raiz varre também `_reversa_forward/**/spike/`, onde há teste que abre conexão SIP real contra o host de deploy (`10.10.10.11:7060`) — spikes de feature não são gate.

`sidecar/` é um componente à parte, com `requirements.txt` e Dockerfile próprios; seu `test_watcher.py` importa `watcher` como módulo de topo e só roda de dentro da pasta (`cd sidecar && pytest -v`). Não faz parte do gate principal.

`pytest-cov` não está em `requirements.txt`: vem de `requirements-quality.txt` (`pytest-cov==7.0.0`), que precisa ser instalado antes de usar as flags `--cov`.

Não há hoje linter/formatter/type-checker fixado no projeto (nem `requirements.txt` nem `requirements-quality.txt` pinam `ruff`/`black`/`mypy`). Se for adotado um desses, registrar a decisão em ADR (`_reversa_sdd/adrs/`) antes de torná-lo bloqueante aqui.

### 🚫 Anti-Padrões
SQL solto fora de `services/`/`Repository` · `print()` em vez de logging estruturado · `import *` · herança > 2 níveis → preferir composição · God Class · variável de canal FreeSWITCH lida sem checar se foi de fato definida (ver histórico de `pbx_host`/`tenant_id` nunca populados) · segredos hardcoded ou colados em specs/commits (usar arquivo gitignored + `.example`, padrão `freeswitch/signalwire_token.txt`) · `except Exception` genérico sem log do erro original

### 🧠 Legibilidade
Nomes que revelam intenção · máximo 2 níveis de indentação · métodos pequenos e de responsabilidade única · comentários só para o "porquê" (decisão não-óbvia), nunca para o "o quê"

---

## 🐳 Docker & Containers (Regra Crítica)

### Prefixo do projeto

Todo projeto DEVE definir um **prefixo único** para seus recursos Docker (containers, volumes, networks, imagens). O prefixo deve identificar o **projeto**, não a empresa (todos os projetos são da Akom — `akom-` sozinho é genérico demais e não isola nada).

**Prefixo definido para ESTE projeto:**

| Recurso | Prefixo | Exemplo |
|---|---|---|
| Containers | `zenith-` | `zenith-api-1`, `zenith-arq-uploader`, `zenith-postgres` |
| Volumes / Networks (compose) | `zenith_` | `zenith_recordings_tmpfs`, `zenith_ollama_data` |
| Imagens locais | `zenith-` | `zenith-voip-freeswitch:latest` |

Qualquer ajuste, criação ou remoção de recurso Docker deste projeto usa **sempre** este prefixo. Se um novo projeto for iniciado, a primeira tarefa de infra é definir o prefixo dele nesta mesma seção do `AGENTS.md` correspondente.

### Obrigações

- **Prefixo obrigatório:** conforme a tabela acima, para containers, volumes, networks e imagens deste projeto
- **Isolamento:** nunca reutilizar ou tocar em containers de outro projeto, mesmo que disponíveis
- **Confirmação:** se um container necessário já existe em outro projeto, sempre solicitar confirmação ao usuário antes de reutilizar ou criar um novo
- **Documentação:** containers, redes e volumes devem estar claramente marcados com prefixo no `docker-compose.yml`

### Regras não-negociáveis

1. **Containers são exclusivos do projeto** — nunca reutilize containers, volumes ou serviços de outros projetos (Redis, PostgreSQL, etc.), a menos que o usuário diga explicitamente para reutilizar
2. **Nunca toque em recursos fora do prefixo do projeto** — proibido parar, remover, reiniciar ou modificar containers de terceiros, mesmo para resolver conflito de porta. Servidores de deploy são compartilhados com outros stacks (ex.: 10.10.10.11 roda `zenith-*`, `sre_*`, `hermes*`, `freeswitch`, `portainer`)
3. **Comandos em massa são proibidos** — nunca use `docker rm -f`, `docker stop`, `docker prune` ou loops sobre TODOS os containers. Sempre filtre pelo prefixo: `docker ps --filter "name=zenith-"`
4. **Conflito de porta:** se uma porta estiver ocupada por container de terceiro, **mude a porta do NOSSO serviço** no docker-compose.yml — nunca derrube o container alheio

### Exemplo

```yaml
services:
  zenith-postgres:
    image: postgres:16-alpine
    container_name: zenith-postgres
    volumes:
      - zenith_postgres_data:/var/lib/postgresql/data

volumes:
  zenith_postgres_data:
    driver: local
```

---

## 🔍 Descoberta de Caminhos (Path Discovery)

Caminhos NÃO são fixados nas instruções. O projeto já possui um mecanismo de descoberta implementado em `.reversa/context/`:
- `surface.json` — varredura superficial: linguagens, frameworks, entry points, arquivos de configuração, módulos, integrações
- `modules.json` — análise detalhada por módulo: propósito, arquivos principais, funções, entidades, regras de negócio, dependências

### Como consultar

Sempre consulte `.reversa/context/surface.json` antes de assumir caminhos no projeto:
- `config_files` → lista de arquivos de configuração do projeto
- `docker` → arquivos compose e Dockerfile
- `modules` → camadas/layers encontradas
- `entry_points` → pontos de entrada da aplicação

O diretório de specs SDD é `_reversa_sdd/`, definido em `.reversa/config.toml` na chave `[output] folder`.

Reexecute a descoberta se o projeto mudar estruturalmente (novas pastas, frameworks, etc.).

---

## 🧭 Reversa

> Framework de Engenharia Reversa instalado neste projeto.

### Como usar

Use o fluxo adequado no chat:

- `/reversa` — descobrir e documentar um sistema existente
- `/reversa-new` — criar PRD e specs para um projeto novo
- `/reversa-forward` — implementar ou evoluir código a partir das specs
- `/reversa-migrate` — planejar a migração de um sistema legado
- `/reversa-docs` — gerar o mini-site visual da documentação
- `/reversa-agents-help` — consultar o catálogo completo de agentes

### Comportamento ao ativar

Quando o usuário digitar `/reversa` ou a palavra `reversa` sozinha em uma mensagem:

1. Ative o skill `reversa` disponível em `.agents/skills/reversa/SKILL.md` — este é o caminho canônico; as entradas em `.claude/skills/` são symlinks para `.agents/skills/`
2. Leia o SKILL.md na íntegra e siga exatamente as instruções do Reversa

### Regra não-negociável

Nunca apague, modifique ou sobrescreva arquivos pré-existentes do projeto legado.
O Reversa escreve **apenas** em `.reversa/`, `_reversa_sdd/`, `_reversa_forward/` e `_reversa_docs/`.
