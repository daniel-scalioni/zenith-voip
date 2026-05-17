<!--
Template de corpo do requirements.md
Carregado por /reversa-requirements e atualizado por /reversa-clarify.

REGRAS DE PREENCHIMENTO:
- Mantenha a ordem das seções obrigatórias.
- Não apague seções marcadas como obrigatórias, mesmo quando vazias (use "n/a" se necessário).
- Comentários inline (entre <!-- -->) só devem ser removidos quando a seção correspondente estiver totalmente preenchida.
- Use 🟢 / 🟡 / 🔴 conforme a confidência da fonte do _reversa_sdd/ que sustenta a afirmação.
- Marque com [DÚVIDA] qualquer ponto onde a informação faltar; máximo de três marcadores no documento inicial.
-->

# Requirements: AI Hub for Audio (Zenith VoIP)

> Identificador: `001-ai-audio-hub`
> Data: `2026-05-17`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

Criar uma Camada de Inteligência (Hub de IA) em FreeSWITCH + Python para operações críticas de Portaria Remota (Akom). O Hub suportará processamento a posteriori (auditoria e sentimento) e em tempo real (checklists, extração de entidades e intervenção por voz). A arquitetura seguirá padrões de projeto (POO, microserviços, Strategy) garantindo escalabilidade. Diferente de call centers passivos, a IA atuará ativamente ouvindo chamadas e operando com um "Consenso Multi-Agente" para ações críticas de segurança física (ex: autorizar abertura de porta). A IA poderá agir como um Copiloto silencioso ("Whisper mode"), alertando o operador sobre fúria/estresse, ou operar autonomamente com TTS Local, injetando áudios de "aguarde" para mascarar latência técnica. O barramento de eventos será unificado via Redis Streams, o orquestrador de IA usará LangGraph com checkpointing em Redis para resiliência, e dados sensíveis (CPF, RG) serão processados exclusivamente por LLM local (LGPD). O desenvolvimento priorizará a reutilização de skills e agentes open-source antes de codificação manual.

## 2. Contexto a partir do legado

> Projeto greenfield no paradigma de IA, mas altamente ancorado nas operações reais da portaria remota Akom.

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| Requisito do Usuário | O PBX é fechado (sem acesso a desenvolvimento, apenas configuração). | 🟢 |
| Requisito do Usuário | Exigência arquitetural: Padrões de Projeto e Microserviços. | 🟢 |
| Entrevista (Usuário) | Domínio Crítico: Segurança física (Akom Campinas/SP). Procedimentos variam por condomínio. | 🟢 |
| Entrevista (Usuário) | Necessidade de TTS Local, Consenso Multi-agente, Whisper Mode e reuso de Skills existentes. | 🟢 |
| Peer Review (3 LLMs) | Deepgram como SPOF exige fallback local (Whisper.cpp). Speaker diarization obrigatória. Observabilidade zero é inaceitável. LGPD exige LLM local para dados sensíveis. | 🟢 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| Atendente | Melhorar a performance e assertividade. | Receber dicas e validação de checklist em tempo real na tela do computador durante a ligação. |
| Gestor / Auditor | Garantir a qualidade do atendimento. | Receber relatórios de sentimento e auditoria via webhook após o término da chamada. |
| Sistema Terceiro | Manter os dados atualizados sem trabalho manual. | Receber extrações de entidades (ex: CPF) identificadas pela IA via API. |
| Operador Akom | Manter controle e segurança sob pressão. | Receber conselhos da IA via fone (Whisper) sem o morador ouvir, ou transferir o controle para a IA acalmar/traduzir um morador enfurecido/estrangeiro. |
| Agentes de IA | Tomar decisões seguras baseadas em POPs (Procedimentos Operacionais Padrão). | Agente A (Extrator) levanta intenção de abrir porta; Agente B (Auditor) veta pois a palavra-chave de coação foi detectada. |
| Morador/Visitante | Ser atendido com rapidez e segurança. | Conversa fluida. Se a IA demorar a processar, ouve um áudio dinâmico de espera (ex: "Só um momento, estou checando a autorização..."). |
| DevOps / SRE | Garantir disponibilidade e rastrear problemas. | Monitorar latência STT/LLM, taxa de fallback, e saúde dos containers via Grafana. |

## 4. Regras de negócio novas ou alteradas

1. **RN-01:** O Hub de IA atuará como um B2BUA (Back-to-Back User Agent) transparente, interceptando o fluxo RTP para análise sem corromper a sinalização com o PBX. 🟢
2. **RN-02:** Chamadas processadas devem obrigatoriamente gerar eventos de fim de chamada (A Posteriori) para iniciar os processos analíticos assíncronos via Redis Streams. 🟢
3. **RN-03:** Em chamadas elegíveis para acompanhamento em tempo real, o áudio transcrito alimentará um motor de inferência veloz que dispara eventos via WebSockets para o front-end do atendente. 🟢
4. **RN-04 (Multi-Agent Consensus — Escopo Restrito):** O pipeline de consenso multi-agente (Extrator -> Revisor -> Decisor) é reservado **exclusivamente para ações que mexem no mundo físico** (abrir porta, liberar acesso). Extração de entidades para Agent Assist usa saída direta do Extrator sem consenso — a decisão final é do operador humano. 🟢
5. **RN-05 (Consciência de Domínio):** O modelo deve carregar o contexto específico do condomínio do morador antes da análise, pois os procedimentos de segurança mudam por cliente. 🟢
6. **RN-06 (Isolamento de Áudio - Whisper):** A IA deve ser capaz de injetar áudio sintético APENAS no canal receptor do Atendente (`uuid_play <agent_uuid>`), mantendo o morador sem escutar. Validação obrigatória via teste de gravação bilateral. 🟢
7. **RN-07 (Gestão de Latência):** Sempre que o fluxo exigir validação profunda (tempo real), o FreeSWITCH injetará um áudio de "processando" para não causar quebra de expectativa no morador. 🟢
8. **RN-08 (LGPD / Compliance):** Dados pessoais (CPF, RG) extraídos da voz devem ser processados exclusivamente por LLM self-hosted (ex: Mistral 7B via Ollama). Nenhum dado sensível pode sair da infraestrutura física do cliente. 🟢
9. **RN-09 (Senhas via DTMF):** Senhas de coação e segurança NÃO passam pelo pipeline de extração de entidades por IA. São coletadas exclusivamente via DTMF (digitação no teclado do telefone) com mascaramento automático e zero persistência em log. 🟢
10. **RN-10 (Speaker Diarization):** A transcrição deve identificar quem falou (morador vs atendente) para garantir precisão na extração e auditoria. 🟢

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| RF-01 | Interceptação de Áudio SIP/RTP | Must | O sistema captura o áudio bilateral (TX/RX) sem quebrar a comunicação entre o Telefone e o PBX. | 🟢 |
| RF-02 | Análise de Sentimento (Pós) | Must | O sistema analisa o áudio após a chamada e identifica o sentimento dominante do cliente. | 🟢 |
| RF-03 | Auditoria de Procedimentos (Pós) | Must | O sistema valida se o roteiro foi cumprido e envia o relatório para um webhook. | 🟢 |
| RF-04 | Transcrição em Tempo Real com Diarização | Must | O áudio é transcrito com identificação de speaker e exibido na interface durante a chamada. | 🟢 |
| RF-05 | Extração de Entidades em Tempo Real (Triage) | Must | Camada 1 (Regex/spaCy) detecta padrões numéricos; Camada 2 (LLM local) higieniza sob demanda. Senhas excluídas. | 🟢 |
| RF-06 | Auto-treinamento e Checklist | Should | O atendente recebe dicas visuais em tempo real conforme fala com o cliente. | 🟡 |
| RF-07 | FreeSWITCH Conference/Forking | Must | O sistema captura áudio bilateral e permite injeção de áudio seletivo (para atendente, morador, ou ambos). | 🟢 |
| RF-08 | Consenso Multi-Agente (Ações Físicas) | Must | A IA Extratora aciona a IA Auditora antes de emitir um webhook de ação crítica. O log armazena o debate. Escopo: somente ações que mexem no mundo físico. | 🟢 |
| RF-09 | Whisper Mode (Copilot Auditivo) | Must | O operador aciona a IA e ela fala instruções diretamente no seu fone, inaudível para a outra ponta. Isolamento validado por teste gravado. | 🟢 |
| RF-10 | TTS (Síntese de Voz) Local | Must | Voz gerada por servidor on-premises. Fallback para WAV pré-gravados se o TTS travar. | 🟢 |
| RF-11 | Áudio Dinâmico de Espera | Must | O sistema toca um áudio confortável enquanto os Agentes tomam decisões complexas. | 🟢 |
| RF-12 | Detecção de Fúria / Anomalia | Should | A IA ouve passivamente e dispara um alerta de tela recomendando a própria ativação se o morador se exaltar. | 🟢 |
| RF-13 | STT com Fallback Local | Must | Se Deepgram timeout > 500ms, o sistema ativa Whisper.cpp local automaticamente via Strategy Pattern. | 🟢 |
| RF-14 | Observabilidade e Health Checks | Must | Métricas de latência STT/LLM (p50/p99), taxa de fallback, saúde dos containers. Dashboard Grafana. Endpoints `/health` e `/ready`. | 🟢 |
| RF-15 | Event Bus via Redis Streams | Must | Barramento unificado de eventos com Consumer Groups e ACK. Sem RabbitMQ. | 🟢 |
| RF-16 | Desktop Widget Overlay (Tauri) | Must | Widget compacto always-on-top (system tray do Windows) mostrando checklist do POP, barra de controle (Copiloto/Pausar IA) e status STT. Aparece automaticamente ao detectar chamada, minimiza ao encerrar. | 🟢 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| Arquitetura | Orientação a Microserviços e POO em camadas | Exigência direta para garantir escalabilidade, manutenibilidade e separação clara de responsabilidades. | 🟢 |
| Design Patterns | Strategy, Observer, Repository, Factory | Strategy (IAs intercambiáveis, STT fallback), Observer (eventos WebSocket), Repository (acesso DB genérico), Factory (pipelines por tenant). | 🟢 |
| Integração | WebSockets e Webhooks | Necessário para fluxo de dados contínuo e callbacks para sistemas terceiros. | 🟢 |
| Segurança | Operação Mission-Critical (Fail-safe) | Portaria remota envolve vidas. Erros da IA não podem abrir portas inadvertidamente. Bypass humano obrigatório. | 🟢 |
| Segurança | TLS/SRTP + JWT + Segregação de Rede | SIP com SRTP obrigatório, API com JWT + rate limiting, VLAN separada para o AI Hub. | 🟢 |
| Compliance | LGPD — Dados sensíveis processados localmente | CPF/RG processados exclusivamente por LLM self-hosted. Senhas coletadas via DTMF. Zero persistência de senhas. | 🟢 |
| Resiliência | Checkpointing do LangGraph via Redis | Estado do orquestrador persistido a cada transição de nó. Em crash, estado recuperado pelo `call_id`. | 🟢 |
| Resiliência | Multi-instância FastAPI (2x) + BunkerWeb WAF | Sharding por `hash(call_id)`. Um crash afeta 50% das chamadas, não 100%. | 🟢 |
| Observabilidade | OpenTelemetry + Prometheus + Grafana | Tracing distribuído, métricas de latência, alertas de degradação. | 🟢 |
| Produtividade | Reuso de Agentes e Skills | "Não defina nada que possa ser melhor definido com um agente/skill já existente". Procurar soluções open-source prontas antes de codar do zero. | 🟢 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Processamento a Posteriori Bem Sucedido
  Dado que o telefone IP X completou uma chamada através do Hub
  Quando a chamada é encerrada
  Então o sistema publica evento de fim de chamada no Redis Streams
  E o worker Arq consome o evento e processa sentimento + auditoria
  E após processamento, dispara um payload JSON para o webhook configurado

Cenário: Interceptação em Tempo Real com Extração Triage
  Dado que o atendente inicia uma chamada via Hub
  Quando o cliente fala uma informação chave (como um CPF)
  Então o Regex/spaCy detecta o padrão numérico em < 100ms
  E o LLM local (Mistral) higieniza e valida o dado em < 500ms
  E exibe o CPF formatado no painel do atendente via WebSocket

Cenário: Fallback de STT Ativado
  Dado que o Deepgram está indisponível ou com latência > 500ms
  Quando o sistema detecta o timeout
  Então ativa automaticamente o Whisper.cpp local via Strategy Pattern
  E a transcrição continua sem interrupção visível para o operador

Cenário: Ativação do Whisper Mode sob tensão
  Dado que o morador grita e o Atendente recebe alerta de Fúria na tela
  Quando o Atendente clica em "Copiloto Áudio"
  Então a IA consulta os POPs do Condomínio
  E sintetiza voz (Local TTS) injetando "Acalme o morador" apenas no fone do Atendente
  E a gravação bilateral confirma que o morador NÃO ouviu o áudio

Cenário: Consenso Negado para Abertura
  Dado que a IA autônoma atende a ligação
  E o morador pede para abrir a porta usando a palavra correta, mas com tom de estresse extremo
  Quando o Agente Extrator propõe a abertura
  Então o Agente Auditor recusa a ação baseada na análise de sentimento/estresse
  E o Hub transfere a ligação imediatamente para um Operador Humano Sênior

Cenário: Coleta de Senha via DTMF
  Dado que o morador precisa informar uma senha de segurança
  Quando o sistema solicita a digitação
  Então a senha é coletada via DTMF (teclas do telefone)
  E a senha NÃO é processada pelo pipeline de IA
  E a senha NÃO é persistida em nenhum log
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|---------------|
| Pipeline de Captura de Áudio (SBC/Proxy) | Must | É o alicerce fundamental do projeto (MVP Fase 1). |
| Análise de Sentimento e Auditoria (Pós) | Must | Requisito analítico primário para provar valor da extração. |
| Estrutura de Microserviços e Design Patterns | Must | Requisito arquitetural inegociável exigido pelo usuário. |
| STT com Fallback Local (Whisper.cpp) | Must | Deepgram como SPOF é inaceitável para operação Mission-Critical. |
| Speaker Diarization | Must | Sem identificar quem fala, extração e auditoria são imprecisas. |
| Observabilidade (OTel + Prometheus + Grafana) | Must | Sistema que decide abrir portas sem telemetria é inaceitável. |
| Redis Streams (Event Bus unificado) | Must | Barramento único, persistente, com ACK e Consumer Groups. |
| Extração de Entidades RT (Triage Mista) | Must | Operador precisa ver CPF em tela em < 1s. |
| LLM Local Self-hosted (LGPD) | Must | Dados sensíveis não saem da infraestrutura. |
| Segurança (TLS/SRTP/JWT) | Must | Mission-Critical exige criptografia end-to-end. |
| Captura de Áudio e Whisper Mode (FreeSWITCH) | Must | Core da arquitetura de telefonia avançada. |
| Pipeline Multi-Agente (LangGraph + Checkpointing) | Must | Vital para segurança + resiliência a crashes. |
| Multi-instância FastAPI + BunkerWeb WAF | Must | Mitigação de SPOF do orquestrador. |
| TTS Local de Baixa Latência + Fallback WAV | Must | Para operações fluídas na ponta (Akom). |
| Áudio Dinâmico de Espera | Must | Evita abandono de chamada durante latência da IA. |
| Agent Assist com WebSockets (Tempo Real) | Must | Componente avançado do painel do atendente. |
| Alertas passivos de Fúria na Tela | Should | Excelente UX, mas depende do backend já funcional. |
| Auto-treinamento e Checklist | Should | Valor agregado após o core estar estável. |

## 9. Esclarecimentos

### Sessão 2026-05-16
- **Protocolo de Áudio:** Confirmado o uso de **G.711 (alaw/ulaw)** para máxima compatibilidade com o hardware atual (Intelbras, Hikvision, VitalPBX, Khomp). O FreeSWITCH fará a transcodificação interna para PCM Linear 16kHz para alimentar os motores de IA.
- **Persistência:** Abordagem híbrida utilizando **PostgreSQL** (Relacional + campos JSONB), permitindo a robustez do Repository Pattern com a flexibilidade necessária para metadados de IA.
- **Hospedagem:** Deploy inicial em **Infraestrutura Local (On-Premises)**, utilizando Docker para facilitar a portabilidade futura para Nuvem.
- Contexto de Segurança (Akom) altera o peso das decisões de IA (necessidade de consenso multi-agente).
- Utilização de TTS Local e "Whisper Mode" definidos como pilares do projeto.
- **Desenvolvimento Agêntico:** Procurar e instalar skills/agentes já existentes na internet ou localmente antes de codar do zero.

### Sessão 2026-05-17 (Peer Review + Frontend)
- **Frontend (Desktop Widget):** Tauri (Rust shell + HTML/CSS/JS) como overlay always-on-top no Windows. Consome ~15MB RAM (usa WebView2 nativo). Escopo MVP: checklist do POP + barra de controle + status STT. Transcrição ao vivo e script guiado por IA são funcionalidades futuras, NÃO do MVP.
- **Histórico de Chamadas:** Persiste apenas no banco de dados (PostgreSQL). Dashboard de consulta é funcionalidade futura.
- **Event Bus:** Redis Streams unificado (sem RabbitMQ). Consumer Groups com ACK para pós-chamada.
- **Worker Pós-Chamada:** Arq (asyncio-nativo, integra com Redis Streams).
- **Resiliência:** LangGraph com RedisSaver (checkpointing a cada nó). 2 instâncias FastAPI com BunkerWeb WAF.
- **LGPD:** LLM local (Mistral 7B via Ollama) obrigatório para dados sensíveis. Senhas via DTMF.
- **STT Fallback:** Whisper.cpp local ativado automaticamente se Deepgram falhar.
- **Speaker Diarization:** Deepgram `diarize:true` + rotulação por canal no ingestor.
- **Observabilidade:** OpenTelemetry + Prometheus + Grafana.
- **Segurança:** TLS/SRTP no FreeSWITCH, JWT + rate limiting na API, VLAN segregada.

## 10. Lacunas

- n/a

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-05-16 | Versão inicial gerada por `/reversa-requirements` integrando arquitetura sugerida. | reversa |
| 2026-05-16 | Atualização profunda incorporando contexto Akom, Multi-agent e Whisper Mode. | reversa |
| 2026-05-17 | Revisão geral: Peer Review de 3 LLMs. Adicionados RF-13 a RF-15, RN-08 a RN-10, RNFs de Segurança/LGPD/Resiliência/Observabilidade. | reversa |
