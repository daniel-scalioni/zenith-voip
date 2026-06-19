# Roadmap: Alta Escala, Isolamento Multitenant e PBX Múltiplos

> Identificador: `002-escala-eventos`
> Data: `2026-05-21`
> Requirements: `_reversa_forward/002-escala-eventos/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

Esta feature implementa o suporte a grande escala na Zenith VoIP adotando três pilares:
1. **Isolamento Multitenant Físico (Database-per-Tenant)**: Roteamento dinâmico de conexões assíncronas do SQLAlchemy com schemas dedicados no PostgreSQL para garantir blindagem absoluta contra vazamento de dados de clientes corporativos.
2. **Intermediação SIP e Rastreamento via SwitchPBX (FreeSWITCH)**: Padronizaremos o modelo utilizando o padrão de **Registration Forwarding / Passthrough (Proxy de Registro Transparente)**. O softphone do atendente (ex: no GEAR admin) é configurado para registrar-se no SwitchPBX, que retransmite o registro de forma transparente para o PBX original do cliente (ex: VitalPBX), mantendo o ramal ativo ("verde") no monitoramento do cliente. Isso garante que a sinalização e mídias das chamadas (INVITE/RTP) passem obrigatoriamente pelo SwitchPBX, onde mapeamos a vinculação `ramal_sip -> IP/porta` no Redis e efetuamos o espelhamento do áudio bidirecional via `mod_audio_fork` para a IA Zenith. Mantemos o **Inline SIP Trunk Loop** como fallback caso a alteração de domínio no softphone não seja possível. Há também fallback para redes sob NAT compartilhado através de discagem direta do código `*88` no softphone do atendente.
3. **Barramento de Eventos (Redis Streams) e IA Híbrida**: O uso de Redis Streams se confirma como pilar ideal para sustentar mais de 500 chamadas/dia por atendente. Implementaremos STT na nuvem (Deepgram) para chamadas ativas de baixíssima latência (<500ms de latência de transcrição), mantendo processamentos pesados e assíncronos de LLM (Mistral local via Ollama) e TTS secundário (Piper local) desacoplados via Workers ARQ.

## 2. Princípios aplicados

Respeitamos as seguintes premissas de projeto da Zenith:

| Princípio | Como a feature se relaciona | Status |
|-----------|------------------------------|--------|
| **I. Desacoplamento Assíncrono** | Toda a lógica pesada de transcrição e IA é isolada do fluxo RTP de voz do FreeSWITCH usando o Redis Streams e Workers ARQ. | respeita |
| **II. Segurança e Isolamento de Dados** | A decisão de isolamento físico total por schemas dedicados no banco de dados impede cruzamento acidental ou injeção de dados entre inquilinos. | respeita |

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|----------------|--------------------------|-------------|
| **D-01** | Isolamento Físico via Schemas PostgreSQL separados. | Segurança regulatória e blindagem total dos dados de ligações corporativas e análises. | Isolamento lógico com coluna discriminadora única (descartado pelo risco de contaminação em queries). | 🟢 |
| **D-02** | Intermediação via Registration Forwarding (Passthrough Proxy) e IP WebSocket matching. | Como o software de portaria (GEAR G-Phone) permite configurar o domínio do VoIP, apontamos para o SwitchPBX, que retransmite o registro de forma transparente para manter os ramais verdes (ativos) no VitalPBX original. | Loop de SIP Trunk no PBX original (mantido como fallback se a troca de domínio no softphone não for viável). | 🟢 |
| **D-03** | Arquitetura de IA Híbrida (Deepgram SaaS + Ollama Local + Piper Local). | STT em nuvem elimina latência em tempo real para o atendente, enquanto LLM/TTS locais evitam custos exorbitantes de tráfego volumoso. | IA 100% local (descartada por gargalo de hardware com 10+ atendentes concorrentes) ou IA 100% nuvem (descartada pelo custo). | 🟢 |

## 4. Premissas

Todas as dúvidas de negócio e técnicas foram totalmente elucidadas no `/reversa-clarify`, logo não há premissas de dúvidas ativas nesta feature.

## 5. Delta arquitetural

Componentes do legado mapeados no `specs/architecture-guide.md` que serão alterados:

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-----------------|--------|
| **Database Router** | `src/database/database.py` | contrato-alterado | Adicionar o roteador assíncrono multi-tenant para direcionar as queries SQLAlchemy baseando-se no schema do inquilino (`search_path`). |
| **ESL Registrar Interceptor** | `src/telephony/esl_client.py` | regra-alterada | Registrar manipulador de eventos ESL para capturar SIP `REGISTER` e `INVITE` bem-sucedidos e salvar `ramal -> IP` no Redis. |
| **WebSocket Matcher** | `src/api/websockets.py` | regra-alterada | No handshake do WebSocket do widget, obter o IP local e efetuar o casamento com os ramais conhecidos do mesmo IP no Redis Cache. |

## 6. Delta no modelo de dados

- **Resumo das mudanças**: Adição de tabelas de configuração de inquilino (schemas) e múltiplos PBXs. Atualização da tabela `calls` para conter `pbx_id` com chave estrangeira e migração via Alembic utilizando múltiplos schemas em lote.
- **Detalhe completo em**: `_reversa_forward/002-escala-eventos/data-delta.md`

## 7. Delta de contratos externos

| Contrato | Tipo | Arquivo de detalhe |
|----------|------|--------------------|
| **PBX Management API** | HTTP REST | `_reversa_forward/002-escala-eventos/interfaces/api_pbxs.md` |
| **Widget WS Event Stream** | WebSocket | `_reversa_forward/002-escala-eventos/interfaces/websockets.md` |

## 8. Plano de migração

1. **Estrutura de Multi-Schema**: Criar script utilitário em Python que varre a tabela central `tenants` e executa dinamicamente o `alembic upgrade head` apontando para o respectivo schema dedicado no Postgres.
2. **Backfill de Chamadas Existentes**: Exportar registros de `calls` legados na tabela compartilhada `public` e inseri-los no schema do respectivo inquilino `public` ou dedicados.
3. **Provisionamento do Redis**: Criar estruturas de chave no Redis para expirar registros de mapeamento `ramal_sip -> IP` após 3600 segundos (tempo típico de re-registro SIP).

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| **Agentes sob o mesmo IP público (NAT)** | alto | média | O widget apresentará um botão visual "Vincular meu ramal" de um clique. O atendente clica e liga para `*88` no softphone. A chamada interceptada no SwitchPBX casa instantaneamente com a sessão WebSocket sob sinalização expressa. |
| **Gargalo no PostgreSQL com 100+ schemas** | médio | baixa | Implementação de pool de conexões dinâmicas utilizando PGBouncer para otimizar os file descriptors abertos no banco. |
| **Latência ou timeout na API STT Deepgram** | alto | baixa | Manter o AutoFallbackSTT local (Whisper.cpp) mapeado em `specs/architecture-guide.md#3-strategy-pattern-para-servicos` como fallback ativo. |

## 10. Critério de pronto

- [ ] Todas as ações do `actions.md` marcadas `[X]`
- [ ] `data-delta.md` estruturado com as migrations descritas
- [ ] `interfaces/` descrevendo os payloads JSON e WebSockets
- [ ] `onboarding.md` descrevendo os comandos de teste do multi-tenant físico
- [ ] `regression-watch.md` gerado

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-05-21 | Versão inicial gerada por `/reversa-plan` | reversa |
