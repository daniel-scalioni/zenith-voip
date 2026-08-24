# Épico 2 — Qualidade do Atendimento

> Planejamento registrado em 2026-08-12, depois do fechamento do Épico 1 (FreeSWITCH/telefonia,
> features `001`-`012` do forward). Ordem de épicos do projeto: FreeSWITCH → **Qualidade do
> Atendimento** → Widget → Observabilidade.
>
> Este documento é planejamento pré-forward — nenhuma das features abaixo tem ainda
> `requirements.md` formal em `_reversa_forward/`. Quebra validada via `/brainstorming-multiagent`
> (lentes: pragmatismo — DeepSeek/OpenCode; arquitetura/acoplamento — Codex CLI; risco técnico —
> Nemotron/OpenCode), a partir de evidência de código lida diretamente em `src/`.

## Por que este épico não parte do zero

O domínio `ai/` já tem scaffolding real, mas nada está conectado ponta a ponta — mesma classe de
problema de várias GAPs do Épico 1 (ex. GAP-23, ESL client nunca conectado):

- `src/ai/anomaly_detector.py::AnomalyDetector.analyze()` — implementado/testado, nunca chamado em produção.
- `src/ai/consensus_graph.py::ConsensusGraph.run()` — implementado/testado, nunca chamado; usa `MemorySaver` (volátil) em vez de `RedisSaver`.
- `src/workers/post_call.py::post_call_workflow` — `analyze_sentiment`/`audit_procedure` são stubs (GAP-02); a função nunca é enfileirada por ninguém; não há worker `arq-post-call` no compose.
- `src/database/models.py::CallInsight` — nunca instanciado em lugar nenhum de `src/`.
- `src/ai/pops_cache.py::POPsCache` — funcional, nunca consultado.

## Q1 — Pipeline pós-chamada real

Objetivo do bloco: fazer o texto transcrito de uma chamada virar, de fato, sinais de qualidade
persistidos e entregues — hoje esse caminho existe só como código desconectado. Quebrado em 8
features atômicas, cada uma com escopo mínimo, dependência explícita da anterior e comunicação
entre elas via evento no Redis Stream (não chamada direta).

| ID | Feature | Objetivo | Status |
|----|---------|----------|--------|
| F1 | Transcrição persistida | Garantir que o texto transcrito da chamada chega e é persistido de forma confiável (`Transcript`/`transcript_persist.py`), sem nenhuma análise — base de dado real para tudo que vem depois. | ✅ Persistência implementada, testada (gate 448 passed, cobertura 90,81%) e validada em produção com chamada real (`.md` + `Transcript`). Qualidade literal e papel do falante permanecem em correção no adendo draft da 013. |
| F2 | Trigger pós-chamada + worker rodando | Ligar `post_call_workflow` a um hook real (hangup/evento de F1) e subir o worker `arq-post-call` ausente no compose, provando a infra ponta a ponta em produção antes de trocar qualquer stub por lógica real. | Pendente |
| F3 | Anomalia determinística persistida | Popular a primeira linha real de `CallInsight` (`anomaly_detected`/scores) usando `AnomalyDetector` em lote sobre o texto já persistido, sem LLM e sem depender do Ollama. | Pendente |
| F4 | Sentimento real via Ollama | Substituir o stub `analyze_sentiment` por análise real via LLM local, gravando `sentiment`/`sentiment_score`/`summary` na mesma linha de `CallInsight` (upsert por `call_id`, idempotente a reprocessamento de job). | Pendente |
| F5 | Auditoria de POP real | Substituir o stub `audit_procedure` por checagem real contra o checklist de POP, usando `pops_cache.py` via snapshot tirado no `CHANNEL_ANSWER` (não o cache "vivo" horas depois). | Pendente |
| F6 | Alerta de anomalia em tempo real conectado | Ligar `AnomalyDetector.analyze()` ao caminho de STT ao vivo (fora do hot path do WebSocket de áudio), para o alerta de fúria/estresse disparar durante a chamada real, não só em teste. | Pendente |
| F7 | Consenso multi-agente para ações críticas | Ligar `ConsensusGraph.run()` a um gatilho real, resolvendo antes a troca `MemorySaver` → `RedisSaver`/checkpoint durável. **Pendente de decisão do usuário**: pode não ser "qualidade do atendimento" (medir/auditar) e sim "participação ativa" (Fase 3 do roadmap original) — depende de integração de ação física (ex. abertura de porta) ainda não definida; candidato a sair do Épico 2. | Pendente |
| F8 | Webhook de relatório com entrega confirmada | Fechar GAP-04 (webhook fire-and-forget) especificamente para o relatório de qualidade entregue à persona Gestor/Auditor — outbox/retry/DLQ, nunca síncrono no fim do pipeline. | Pendente |

## Contexto herdado de F1 para F2+

F1 (`013-transcricao-persistida`) entregou a base de dado real sobre a qual F2+ constroem:

- `Transcript` persistido de forma transacional (advisory lock + delete/insert) por `call_id`,
  com `speaker` derivado do mapeamento `tx`/`rx` vigente e `extra_metadata` — é a fonte de texto que
  F2 (`post_call_workflow`) deve ler, em vez de qualquer stub. A semântica atendente/cliente é
  provisória e F2+ não deve tratá-la como comprovada antes dos gates QR-05/QR-06 do adendo 013.
- Estágio/heartbeat `transcription` no lifecycle de gravação (`recording_lifecycle.py`) e
  consumidor obrigatório configurável — F2 pode seguir o mesmo padrão de estágio para o hook de
  hangup, em vez de inventar um novo mecanismo de trigger.
- Worker `zenith-arq-transcript` dedicado, fila exclusiva `zenith:transcript`, best-effort
  (falha isolada não bloqueia gravação/backup) — mesmo padrão de isolamento que o worker
  `arq-post-call` ausente (GAP-02) deveria adotar ao subir.
- `.md` consolidado publicado via `smb_sync.py` — não é insumo de F2 (que lê do banco, não do
  arquivo), mas confirma que o padrão de reaproveitar `smb_sync.py` para saída derivada já está
  validado em produção.

## Próximo passo

F1 concluída, testada e validada em produção (ver `_reversa_forward/013-transcricao-persistida/`).
Rodar `/reversa-requirements` para F2 (Trigger pós-chamada + worker rodando) como próxima feature
formal do Épico 2 em `_reversa_forward/`, quando o usuário confirmar.
