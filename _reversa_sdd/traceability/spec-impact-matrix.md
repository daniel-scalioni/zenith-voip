# Spec Impact Matrix — zenith-voip

> Gerado pelo Architect — 2026-06-19
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
