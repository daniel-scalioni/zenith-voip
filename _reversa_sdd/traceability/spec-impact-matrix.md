# Spec Impact Matrix — zenith-voip

> Gerado pelo Architect — 2026-06-19
> **Re-extração incremental — 2026-07-27** — ver seção "Deltas 2026-07" ao final
> Escala: 🟢 CONFIRMADO | 🟡 INFERIDO | 🔴 LACUNA

## Propósito

Mapear o impacto entre componentes do sistema: qual módulo impacta qual, e quais artefatos de especificação são afetados.

## Matriz de Impacto entre Módulos

```
                     Impacta ──────────────────────────────────────────>
         │ api  ai  audio  database  events  extraction  observability  services  telephony  workers  widget  infra
─────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────
api      │  -   ✅   ✅     ✅        ✅        ✅           ✅            ✅        ✅         ✅      ✅     ✅
ai       │  ✅   -    ❌     ✅        ❌        ✅           ❌            ❌        ❌         ❌      ✅     ❌
audio    │  ✅   ❌   -      ❌        ✅        ❌           ❌            ❌        ✅         ❌      ❌     ❌
database │  ✅   ✅   ✅     -         ❌         ✅          ✅            ❌        ✅         ✅      ✅     ❌
events   │  ✅   ❌   ✅     ❌        -          ❌           ❌            ❌        ❌         ✅      ❌     ❌
extraction│ ✅   ✅   ❌     ✅        ❌         -            ❌            ❌        ❌         ❌      ❌     ❌
observ.  │  ✅   ❌   ❌     ❌        ❌         ❌           -             ❌        ❌         ❌      ❌     ✅
services │  ✅   ✅   ✅     ❌        ❌         ✅           ❌            -         ❌         ✅      ✅     ❌
telephony│  ✅   ❌   ✅     ✅        ✅         ❌           ❌            ❌        -          ❌      ❌     ❌
workers  │  ✅   ❌   ✅     ✅        ✅         ❌           ❌            ❌        ❌         -       ❌     ❌
widget   │  ✅   ✅   ❌     ❌        ❌         ❌           ❌            ❌        ❌         ❌      -      ❌
infra    │  ✅   ✅   ✅     ✅        ✅         ✅           ✅            ✅        ✅         ✅      ✅     -
```

✅ = Impacta / ❌ = Não impacta

## Impacto por Módulo

### api
**Impactado por:** ai, audio, database, events, extraction, observability, services, telephony, workers, widget, infra
**Impacta:** ai, audio, database, events, extraction, observability, services, telephony, workers, widget, infra
**Artefatos:** `c4-context.md`, `c4-containers.md`, `c4-components.md`, `erd-complete.md`
**Descrição:** Módulo central — qualquer mudança em qualquer outro módulo pode exigir alterações na API (novos endpoints, mudanças de schema, etc.)

### ai
**Impactado por:** api, database, extraction, services
**Impacta:** api, database, widget
**Artefatos:** `domain.md`, `state-machines.md`
**Descrição:** Mudanças nos algoritmos de IA afetam a API (novos insights) e o widget (novos alertas)

### audio
**Impactado por:** api, events, telephony
**Impacta:** api, events
**Artefatos:** `code-analysis.md`, `data-dictionary.md`, `flowcharts/telephony-flow.md`
**Descrição:** Mudanças no formato de áudio ou streaming afetam a ingestão via API e a publicação de eventos

### database
**Impactado por:** api, ai, extraction, telephony, workers
**Impacta:** api, ai, audio, extraction, observability, telephony, workers, widget
**Artefatos:** `erd-complete.md`, `data-dictionary.md`
**Descrição:** Schema do banco impacta virtualmente todos os módulos — mudanças exigem migrações e atualização em múltiplos consumidores

### events
**Impactado por:** api, audio, workers
**Impacta:** api, audio, workers
**Artefatos:** `code-analysis.md`, `flowcharts/workers-flow.md`
**Descrição:** Estrutura de eventos (streams, payloads) impacta produtores e consumidores

### extraction
**Impactado por:** api, database, services
**Impacta:** api, ai, database
**Artefatos:** `domain.md`, `code-analysis.md`
**Descrição:** Padrões de extração impactam a API (novos endpoints de consulta), a IA (novos campos no consenso) e o banco (novas colunas)

### observability
**Impactado por:** api, database, infra
**Impacta:** api, infra
**Artefatos:** `code-analysis.md`
**Descrição:** Métricas e tracing impactam a instrumentação da API e a configuração de infraestrutura

### services
**Impactado por:** api, database
**Impacta:** api, ai, audio, extraction, workers, widget
**Artefatos:** `code-analysis.md`, `domain.md`
**Descrição:** Serviços de STT/TTS/LLM impactam os consumidores (workers, widget, API)

### telephony
**Impactado por:** api, audio, database, events
**Impacta:** api, audio, database, events
**Artefatos:** `flowcharts/telephony-flow.md`, `state-machines.md`, `domain.md`
**Descrição:** Integração FreeSWITCH impacta fluxo de chamadas, eventos e persistência

### workers
**Impactado por:** api, database, events, services
**Impacta:** api, database, events
**Artefatos:** `flowcharts/workers-flow.md`, `code-analysis.md`
**Descrição:** Workers consomem eventos e persistem dados — mudanças afetam scheduling, filas e schema

### widget
**Impactado por:** api, ai, database, services
**Impacta:** api
**Artefatos:** `code-analysis.md`
**Descrição:** UI do operador impacta os endpoints WebSocket e o formato de dados servidos

### infra
**Impactado por:** api, observability
**Impacta:** api, ai, audio, database, events, extraction, observability, services, telephony, workers, widget
**Artefatos:** `deployment.md`
**Descrição:** Configuração de infraestrutura (Docker, rede, GPU) impacta todos os módulos

## Matriz de Artefatos vs Módulos

| Artefato | api | ai | audio | database | events | extraction | observability | services | telephony | workers | widget | infra |
|----------|:---:|:--:|:-----:|:--------:|:------:|:----------:|:-------------:|:--------:|:---------:|:-------:|:------:|:-----:|
| `architecture.md` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `c4-context.md` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `c4-containers.md` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `c4-components.md` | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| `erd-complete.md` | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `code-analysis.md` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `data-dictionary.md` | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `domain.md` | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| `state-machines.md` | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| `permissions.md` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `dependencies.md` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `flowcharts/*` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ |
| `adrs/*` | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| `legacy-mapping/*` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

## Legenda

| Símbolo | Significado |
|---------|-------------|
| ✅ | Impacto direto (mudanças no módulo exigem alterações no artefato) |
| ❌ | Sem impacto direto |

## Notas

- A matriz considera impacto **direto** entre módulos. Impacto indireto (ex: mudança no database que afeta widget através da API) não é marcado.
- Módulos com alta centralidade (`api`, `database`) merecem atenção redobrada em mudanças.
- Para estimar impacto de uma mudança, percorra a linha do módulo modificado na matriz.


---

## Deltas 2026-07 (re-extração incremental)

### Módulo novo: `sidecar`

| Relação | Direção | Natureza |
|---|---|---|
| `sidecar` → `infra` | impacta | Reescreve `vars-external-ip.xml` no volume de config do FreeSWITCH |
| `sidecar` → `telephony` | impacta | `sofia profile upstream restart` derruba e re-registra os gateways |
| `infra` → `sidecar` | impactado por | Depende de `network_mode: host` e do volume `./freeswitch/conf` |

`sidecar` **não importa nada de `src/`** — não há acoplamento de código com nenhum módulo,
apenas acoplamento operacional (arquivo de config compartilhado + ESL).

### Arestas que mudaram de natureza

| Aresta | Antes | Agora |
|---|---|---|
| `telephony` → `audio` | Registrava metadados no ingestor | Registra metadados **e dispara a captura** via `bgapi`; o registro virou o mecanismo de autorização do WebSocket |
| `telephony` → `services` | inexistente | 🆕 `esl_client` chama `create_call_record`/`finalize_call_record` |
| `telephony` → `workers` | inexistente | 🆕 `esl_client` chama `enqueue_recording_upload` no hangup |
| `telephony` → `database` | indireta | Agora escreve no schema do tenant a cada chamada |
| `workers` → `infra` | S3 externo | Filesystem local em tmpfs — passou a depender do volume e do `ffmpeg` na imagem |
| `services` → `infra` | Microserviço `piper-tts` | TTS in-process: o modelo ONNX virou dependência do processo FastAPI |
| `ai` → `events` | Checkpoint durável no Redis | 🔻 aresta **removida**: `MemorySaver` não toca o Redis (ADR-008) |

### Artefatos com maior superfície de impacto nesta re-extração

| Artefato | Deltas que o tocam |
|---|---|
| `_reversa_sdd/telephony/legacy-mapping.md` | D-01, D-12, D-14, D-15 |
| `_reversa_sdd/infra/legacy-mapping.md` | D-08, D-12, D-13, D-14 |
| `_reversa_sdd/workers/legacy-mapping.md` | D-03, D-04 |
| `_reversa_sdd/code-analysis.md` | todos |

### Risco de acoplamento introduzido

`telephony` passou a depender diretamente de `services`, `workers`, `database` **e** `audio`
dentro de um único handler de evento (`_handle_channel_answer` / `_handle_channel_hangup`).
🟡 O `ESLClient` acumulou responsabilidade de orquestração do ciclo de vida da chamada, o que
o aproxima de uma God Class — anti-padrão listado no `CLAUDE.md`. Candidato natural a
extração de um `CallLifecycleService` se o handler continuar crescendo.
