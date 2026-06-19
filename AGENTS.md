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
`Node.js 20+` · `TypeScript 5.5+` · `tsx` · `biome` · `vitest + @vitest/coverage (≥80%)` · `pino` · `zod` · `bullmq (+ ioredis)`

### 🧱 Arquitetura em Camadas
```
src/
├── presentation/   → API, CLI, consumers (entrada do mundo externo)
├── application/    → Use cases, DTOs, ports (orquestração)
├── domain/         → Entities, Value Objects, domain services, events (regras de negócio)
└── infrastructure/ → Repositories, cache, messaging, clients externos (implementação concreta)
```
**Regras:** `presentation → application → domain` · `infrastructure → domain|application` · `domain` não importa nada externo.

### 📐 Design Patterns
| Pattern | Onde aplicar |
|---------|-------------|
| **Singleton** | Pool de conexões DB (usar módulo com lazy init, não classe Singleton) |
| **Factory** | Criação condicional de objetos (ex: processadores por tipo) |
| **Strategy** | Algoritmos intercambiáveis (ex: cálculo de SLA, formato de saída) |
| **Observer** | Eventos de domínio, notificações desacopladas |
| **Repository** | Toda persistência/serviço externo — domain nunca vê SQL ou HTTP |
| **DI** | Injeção por construtor (proibido service locator) |

### 📋 SDD (Spec-Driven Development)
1. **Spec primeiro** — todo código exige spec em `_reversa_sdd/sdd/<componente>.md`
2. **Front Matter YAML** no topo de cada spec (legível pelo harness):
```yaml
---
spec:
  component: queue-evaluator    # identificador único
  layer: application            # presentation | application | domain | infrastructure
  status: active                # active | draft | deprecated
  version: 1.0.0
  language: typescript
  patterns: [strategy, observer]
  inputs: [{name, type, from}]
  outputs: [{name, type, to}]
  dependencies: [{component, layer}]
  events_produced: [StateChanged]
  updated_at: 2026-05-28
---
```
3. **Alterar spec antes do código** — violação alterar código sem spec correspondente
4. **Harness lê só o FM** via script auxiliar antes de decidir se lê a spec inteira

### 🔍 Descoberta de Caminhos (Path Discovery)
Caminhos NÃO são fixados nas instruções. Na primeira execução:
1. Script de discovery varre o projeto e gera `.reversa/project-map.json`
2. O JSON contém: diretório de specs, camadas encontradas, scripts auxiliares, config files
3. Consulte sempre o `project-map.json` — se um caminho não existir, o map retorna `null`
4. Reexecute o discovery se o projeto mudar estruturalmente

### 🧪 Quality Gates (bloqueantes)
```
biome check src/   → zero warnings
tsc --noEmit       → sem Any implícito
vitest run --coverage --coverage.thresholds.lines=80
```

### 🚫 Anti-Padrões
`console.log()` → `pino` · `import *` · herança > 2 níveis → composição · God Class · `any` sem tipo explícito · métodos > 20 linhas · SQL no domínio · `catch` genérico · secrets hardcoded

### 🧠 Legibilidade
Nomes que revelam intenção · máximo 2 níveis de indentação · ≤ 20 linhas por método · comentários só para o "porquê"

