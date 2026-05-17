# Request for Comments (RFC): Zenith - AI Audio Hub (Portaria Remota)

## 1. Visão Geral e Contexto de Negócio
**Projeto:** Zenith VoIP - AI Audio Hub
**Cliente:** Akom (Campinas/SP) - Operação de Portaria Remota Mission-Critical.
**Objetivo:** Interceptar o fluxo de áudio SIP entre interfones/telefones IP e o PBX legado (VitalPBX/Asterisk), aplicando inteligência artificial em tempo real e a posteriori.
**Restrição Principal:** Tolerância ZERO a alucinações críticas. Uma falha da IA não pode abrir uma porta indevidamente ou ignorar uma senha de coação. Toda ação final precisa de validação por consenso multi-agente e/ou bypass humano.

## 2. Diagrama de Arquitetura (Topologia Atual Proposta)

```mermaid
graph TD
    %% Entidades Externas
    T[Interfone IP / SIP] <-->|SIP/RTP| FS(FreeSWITCH - B2BUA)
    FS <-->|SIP/RTP| PBX(VitalPBX Legado)
    
    %% AI Hub Stack
    subgraph AI Hub (Microservices Docker On-Premises)
        FS -.->|mod_audio_fork (UDP/WS)| API[FastAPI Orchestrator]
        API -.->|Event Socket Library (ESL)| FS
        API <-->|State/PubSub| REDIS[(Redis)]
        API <-->|Persistência| DB[(PostgreSQL + JSONB)]
        
        %% Módulos Internos API
        API -->|Streaming Audio| STT[Deepgram STT]
        STT -->|Transcript| API
        API -->|Prompting| LLM[LangGraph / OpenAI / Local LLMs]
        LLM -->|Consenso/Insight| API
        API -->|Texto| TTS[Piper TTS / Local TTS]
        TTS -->|PCM Audio| API
    end
    
    %% Operador
    API -.->|WebSockets (Live Transcript/Alertas)| FRONT[Agent Assist UI]
    FRONT -.->|Comandos (Whisper Mode)| API
```

## 3. Stack Tecnológica Base (Decidida)
- **Infraestrutura:** Docker On-Premises (Devido à latência, a operação deve rodar no servidor local do cliente).
- **SBC/Media Server:** FreeSWITCH (mod_audio_fork para enviar o RTP ao backend, ESL para injetar áudios via Conference/Eavesdrop).
- **Backend:** Python 3.12+ com FastAPI. Processamento estritamente assíncrono (asyncio).
- **Banco de Dados:** PostgreSQL para o Repository pattern (tabelas relacionais base + colunas JSONB para payloads dinâmicos de IA). Redis para Pub/Sub e WebSockets state.
- **Motores de IA:** 
  - STT: Deepgram (API Externa com latência <300ms)
  - TTS: Piper TTS ou Coqui XTTS rodando On-Premises via microserviço REST.
  - LLM Orchestration: LangGraph para gerenciar o consenso Multi-Agente.

## 4. Requisitos Centrais (Features)
1. **Agent Assist em Tempo Real:** Transcrição ao vivo + extração de entidades (ex: CPF) indo direto para o painel (Frontend) via WebSockets.
2. **Whisper Mode (Sussurro):** O backend instrui o FreeSWITCH via ESL a tocar áudio APENAS para a perna (leg) do Operador.
3. **Mascaramento de Latência (Filler Audio):** Enquanto o LLM processa ("pensando"), o FreeSWITCH toca um áudio PCM local para o morador ("Só um momento...").
4. **Auditoria Pós-Chamada:** Toda chamada gera um JSON com análise de sentimento e check de procedimentos, enviado via Webhook para sistemas terceiros.

---

## 5. Dilemas Arquiteturais Abertos (Para Análise da IA)

Prezado Assistente (LLM), atue como um Arquiteto de Software Sênior. Considere as restrições (On-premises, Python, Mission-Critical, Baixa Latência) e forneça seu parecer técnico indicando qual opção (A, B ou C) devemos seguir para cada dilema abaixo, justificando os trade-offs.

### DILEMA 1: Arquitetura do Barramento de Eventos (Event Bus)
Como devemos gerenciar as mensagens internas (Audio recebido -> Transcrito -> Extração -> Auditoria) para paralelismo?
- **Opção A (Redis Pub/Sub):** Leve, baixíssima latência. Já temos na infra. O problema é ser *Fire-and-Forget*; se o worker de transcrição cair, a frase da ligação é perdida para sempre.
- **Opção B (RabbitMQ / Apache Kafka):** Mensageria corporativa, entrega garantida e persistência (DLQ). Protege contra quedas, mas exige muita RAM e gestão pesada no servidor Docker local do cliente.
- **Opção C (Híbrido):** Redis apenas para o túnel ultrarrápido (Agent Assist e streaming RTP) e RabbitMQ apenas para eventos a posteriori (Auditoria de fim de chamada).

### DILEMA 2: Mecânica de Extração de Entidades em Tempo Real
O operador humano precisa que CPFs e Placas de Carro pulem na tela < 1s após o morador falar. Como processar a extração no fluxo contínuo?
- **Opção A (Regex / NLP Local Contínuo):** Um script parser (Expressões Regulares) roda localmente a cada chunk recebido. Custo zero, ultrarrápido. Contra: Falha feio com hesitações verbais do morador ("meu cpf éeee pera... nove dois... não, oito dois").
- **Opção B (LLM em Chunks Assíncronos):** A cada "silêncio" na voz, despacha o texto acumulado para um LLM menor e rápido (GPT-4o-mini). Interpreta maravilhosamente correções e contextos. Contra: Pode encarecer muito a fatura de tokens no fim do mês e engasgar a tela.
- **Opção C (Triage Mista):** O Regex escuta passivamente. Se achar "suspeita" de um dado contínuo (ex: encontra a palavra "CPF" ou uma cadeia de 4 números juntos), ele delega *aquele trecho específico* ao LLM para higienização e validação.

### DILEMA 3: Granularidade dos Workers (State Management)
Como quebrar a execução Python no Docker para garantir paralelismo sem perder o controle da chamada telefônica inteira?
- **Opção A (Workers Microserviços Independentes):** Um container ouve RTP, joga no Bus. Outro container transcreve, joga no Bus. Outro analisa sentimento, joga no Bus. Escala horizontalmente de forma linda. Contra: Rastrear o estado global de uma ligação e garantir que os dados de fim de chamada juntem tudo exige um gerenciamento de estado (State Store) muito complexo.
- **Opção B (Orquestrador LangGraph / Agent Central):** A entrada de uma chamada instancia um fluxo assíncrono do LangGraph em memória no backend principal. Ele consome o áudio, avança os "nós" e detém o estado inteiro no objeto interno. Contra: Se o container do backend restartar ou crashear abruptamente, todas as ligações em andamento perdem sua "inteligência" (embora o áudio SIP continue roteando no FreeSWITCH, que é o B2BUA resiliente).

---
**Fim do RFC.**
