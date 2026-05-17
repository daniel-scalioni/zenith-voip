Parecer Técnico sobre o Projeto — Architecture RFC
Contexto Identificado
Com base no documento anexado, trata-se de um sistema Mission Critical On-Premises com requisitos de:

Segurança física rigorosa
Processamento em tempo real (Agent Assist)
Extração de entidades durante chamadas telefônicas (CPF, Placa, etc.)
Latência < 1 segundo para exibição ao operador 
architecture_rfc.md
⚠️ Limitação Importante
O contexto disponível do arquivo está parcialmente carregado — apenas trechos dos dilemas foram fornecidos, sem detalhes completos sobre:

Stack tecnológica utilizada (linguagens, frameworks, banco de dados)
Diagrama de arquitetura completo
Dilemas 1 e 3 (apenas o Dilema 2 está visível no contexto)
Por isso, meu parecer será focado no que foi disponibilizado, com ressalvas onde necessário.

📋 Parecer sobre o Dilema 2 (único visível): Extração em Tempo Real
"O operador precisa que, enquanto o morador dita um CPF ou Placa no telefone, essa entidade apareça na tela em < 1 segundo" 
architecture_rfc.md

Análise das Opções:
❌ Opção A — Regex / NLP Local Contínuo
Recomendação: Desaconselhada como solução única

PRÓS
CONTRAS
Latência ~0ms
Frágil com fala hesitada
Custo zero
Alta taxa de falso-negativo
Funciona offline
Manutenção de regexes complexa
O próprio documento reconhece a fragilidade: "falha ao lidar com fala hesitada" 
architecture_rfc.md
 — e em ambiente de callcenter, hesitação é a norma, não a exceção.

❌ Opção B — LLM em Chunks por Silêncio
Recomendação: Desaconselhada como solução primária

PRÓS
CONTRAS
Lida bem com hesitação
Custo alto de tokens
Alta acurácia semântica
Latência perceptível
Flexível
Dependência de API externa (problema em On-Premises)
Em contexto Mission Critical On-Premises, depender de LLM externo por chunk introduz:

Risco de disponibilidade
Custo operacional crescente
Potencial violação de compliance de dados sensíveis (CPF é dado pessoal — LGPD)
✅ Opção C — Abordagem Mista (Triage)
Recomendação: FORTEMENTE RECOMENDADA

Esta é claramente a arquitetura correta para o contexto apresentado 
architecture_rfc.md
:


Collapse
Save
Copy
1
2
3
4
5
6
7
8
9
10
11
12
13
Fluxo sugerido:

Deepgram Stream
      │
      ▼
[Regex/Detector Local]  ──── padrão não suspeito ──→ descarta
      │
  padrão suspeito detectado
      │
      ▼
[LLM Local / Self-hosted]  →  JSON validado  →  Tela do Operador
      │                                              ▲
      └── SLA: higienização em ~300-500ms ───────────┘
Por quê C é superior:

Latência controlada: O regex filtra ~90% dos chunks sem custo, o LLM só é invocado quando necessário
Custo drasticamente menor: Tokens consumidos apenas em hits reais
Compatível com On-Premises: O LLM pode ser self-hosted (ex: Llama 3, Mistral via Ollama/vLLM)
LGPD/Compliance: Dados sensíveis não saem da infraestrutura física
Resiliência: Se o LLM falhar, o regex ainda captura padrões simples como fallback
🏗️ Recomendações Arquiteturais Gerais
Com base no contexto de Mission Critical + Real-Time + On-Premises:

Stack Sugerida (caso não definida):
CAMADA
RECOMENDAÇÃO
STT
Deepgram On-Prem ou Whisper self-hosted
NLP Local
spaCy + regex customizado
LLM Self-hosted
Mistral 7B / Llama 3.1 via vLLM
Orquestração
FastAPI + WebSockets
Mensageria
Redis Streams ou Kafka
Frontend Operador
React com SSE/WebSocket
📌 Conclusão
DILEMA
RECOMENDAÇÃO
Dilema 2
Opção C (Mista/Triage) — melhor equilíbrio custo/latência/segurança
Dilemas 1 e 3
⚠️ Não disponíveis no contexto — favor reenviar o arquivo completo
💡 Para um parecer mais completo, por favor reenvie o arquivo com os Dilemas 1 e 3 e os detalhes da stack atual. Com isso posso avaliar coerência tecnológica, pontos de falha e sugerir melhorias arquiteturais adicionais.


1 Source

architecture_rfc.md
6.1 KB
segue novo arquivo.


claude-sonnet-4-6

Retrieved 1 source
Parecer Técnico Completo — Architecture RFC
Agora com os três dilemas visíveis 
architecture_rfc.md
, segue a análise completa:

🏗️ Contexto do Sistema
Sistema Mission Critical On-Premises com as seguintes features centrais 
architecture_rfc.md
:

Agent Assist em Tempo Real (WebSockets + extração de entidades)
Whisper Mode via FreeSWITCH ESL
Mascaramento de Latência com Filler Audio (PCM local)
Auditoria Pós-Chamada via Webhook (JSON + sentimento)
Dilema 1 — Arquitetura do Barramento de Eventos (Event Bus)
Análise das Opções 
architecture_rfc.md
:
OPÇÃO
LATÊNCIA
PERSISTÊNCIA
COMPLEXIDADE
RISCO
A - Redis Pub/Sub
✅ Mínima
❌ Fire-and-Forget
✅ Baixa
❌ Perda de dados se worker cair
B - RabbitMQ/Kafka
⚠️ Moderada
✅ Total + DLQ
❌ Alta
✅ Mínimo
C - Híbrido
✅ Mínima no RT
✅ Garantida no crítico
⚠️ Média
✅ Baixo
✅ Recomendação: Opção C — Híbrido
A separação de responsabilidades é a chave aqui 
architecture_rfc.md
:


Collapse
Save
Copy
1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
Fluxo de Áudio / Agent Assist (tempo real)
─────────────────────────────────────────
FreeSWITCH → Redis Pub/Sub → Worker Transcrição
                                    │
                                    ▼
                            Extração de Entidades
                                    │
                                    ▼
                            WebSocket → Painel

Fluxo de Auditoria (pós-chamada, crítico)
─────────────────────────────────────────
Fim da Chamada → RabbitMQ → Worker Auditoria
                    │              │
                  DLQ ←── falha    ▼
                            JSON → Webhook
Justificativa:

O stream de áudio é naturalmente efêmero — um frame de áudio perdido não invalida a chamada inteira; o Redis serve perfeitamente para isso 
architecture_rfc.md
A auditoria pós-chamada é transacional e irreversível — perder um registro de auditoria tem impacto legal/operacional real; o RabbitMQ com DLQ protege esse fluxo 
architecture_rfc.md
Evita o peso total do RabbitMQ/Kafka no hot path de tempo real, respeitando as restrições de RAM em ambiente Docker On-Premises 
architecture_rfc.md
Dilema 2 — Extração de Entidades em Tempo Real (CPF, Placa)
Operador precisa ver a entidade na tela enquanto o morador ainda fala, com < 1 segundo 
architecture_rfc.md

✅ Recomendação: Opção C — Abordagem Mista (Triage)

Collapse
Save
Copy
1
2
3
4
5
6
7
8
9
10
11
12
Stream Deepgram/Whisper
        │
        ▼
[Regex/Detector Local]
        │
   ┌────┴────┐
padrão       sem padrão
detectado    → descarta chunk
   │
   ▼
[LLM Self-hosted]  →  JSON validado  →  WebSocket → Painel
(Mistral/Llama)
Justificativa:

Regex cobre os 90% de casos simples com latência ~0ms 
architecture_rfc.md
LLM só é invocado em casos ambíguos (fala hesitada, dígitos fragmentados)
Em contexto On-Premises com dados sensíveis (CPF = dado pessoal LGPD), o LLM deve ser self-hosted — dados não saem da infraestrutura física 
architecture_rfc.md
Custo de tokens cai drasticamente com o filtro de triage
📌 Resumo Executivo
DILEMA
RECOMENDAÇÃO
RAZÃO PRINCIPAL
Dilema 1 — Event Bus
C — Híbrido
Redis no hot path RT + RabbitMQ na auditoria crítica 
architecture_rfc.md
Dilema 2 — Extração RT
C — Mista/Triage
Regex como pré-filtro + LLM self-hosted para casos ambíguos 
architecture_rfc.md
Dilema 3
⚠️ Ainda não visível no contexto
Favor confirmar se há um terceiro dilema no arquivo
⚠️ Nota: O Dilema 3 ainda não apareceu no contexto carregado 
architecture_rfc.md
. Se houver um terceiro dilema no documento, por favor cole o trecho diretamente aqui para que eu possa analisá-lo com a mesma profundidade.


1 Source
o dilema 3 do arquivo é este:

DILEMA 3: Granularidade dos Workers (State Management)
Como quebrar a execução Python no Docker para garantir paralelismo sem perder o controle da chamada telefônica inteira?

Opção A (Workers Microserviços Independentes): Um container ouve RTP, joga no Bus. Outro container transcreve, joga no Bus. Outro analisa sentimento, joga no Bus. Escala horizontalmente de forma linda. Contra: Rastrear o estado global de uma ligação e garantir que os dados de fim de chamada juntem tudo exige um gerenciamento de estado (State Store) muito complexo.
Opção B (Orquestrador LangGraph / Agent Central): A entrada de uma chamada instancia um fluxo assíncrono do LangGraph em memória no backend principal. Ele consome o áudio, avança os "nós" e detém o estado inteiro no objeto interno. Contra: Se o container do backend restartar ou crashear abruptamente, todas as ligações em andamento perdem sua "inteligência" (embora o áudio SIP continue roteando no FreeSWITCH, que é o B2BUA resiliente).
Fim do RFC.


claude-sonnet-4-6
Today at 10:11 PM

Retrieved 1 source
Parecer Técnico — Dilema 3: Granularidade dos Workers
O Dilema Central 
architecture_rfc.md
"Como quebrar a execução Python no Docker para garantir paralelismo sem perder o controle da chamada telefônica inteira?"

Este é o dilema mais arquiteturalmente profundo dos três, pois envolve um trade-off clássico em sistemas distribuídos: Escalabilidade vs. Coerência de Estado.

Análise das Opções
Opção A — Workers Microserviços Independentes 
architecture_rfc.md

Collapse
Save
Copy
1
2
3
4
5
[Container RTP] → Bus → [Container Transcrição] → Bus
                                                     │
                                              [Container Sentimento] → Bus
                                                     │
                                              [Container Consenso] → Bus
PRÓS
CONTRAS
✅ Escala horizontal perfeita
❌ Estado global da chamada fragmentado
✅ Falha isolada por container
❌ State Store externo obrigatório e complexo
✅ Deploy independente
❌ Correlacionar eventos da mesma ligação é custoso
✅ Sem SPOF único
❌ Overhead de serialização/deserialização constante


O problema crítico aqui é que uma ligação telefônica é uma sessão com estado contínuo — CPF extraído no minuto 1 precisa estar disponível para o Revisor no minuto 3. Em Workers totalmente independentes, isso exige um State Store externo (ex: Redis com chave call_id), o que adiciona latência e complexidade operacional significativas. 
architecture_rfc.md

Opção B — Orquestrador LangGraph / Agent Central 
architecture_rfc.md

Collapse
Save
Copy
1
2
3
4
5
6
7
8
9
10
11
12
Chamada entra
     │
     ▼
[LangGraph Agent instanciado em memória]
     │
     ├── Nó: Transcrição
     ├── Nó: Extração CPF
     ├── Nó: Análise Sentimento
     ├── Nó: Consenso (Extrator → Revisor → Decisor)
     └── Nó: Auditoria Final
     │
Chamada cai → Agent morre
PRÓS
CONTRAS
✅ Estado coeso em memória
❌ SPOF — crash do container = perda de inteligência de todas as calls ativas
✅ Debugabilidade superior
❌ Não escala horizontalmente sem sharding manual
✅ Grafo de execução natural para Consenso Multi-Agente
❌ Memory pressure cresce linearmente com calls simultâneas
✅ LangGraph é feito exatamente para este padrão
❌ Restart de deploy vira janela de degradação


✅ Recomendação: Opção B com Mitigações de Resiliência
Justificativa
O documento já aponta a própria solução para o contra da Opção B 
architecture_rfc.md
:

"embora o áudio SIP continue roteando no FreeSWITCH, que é o B2BUA resiliente"

Isso significa que o que se perde num crash não é a chamada em si, mas a inteligência dela — e isso é mitigável com uma estratégia de checkpointing leve:

Arquitetura Recomendada: B + Checkpointing

Collapse
Save
Copy
1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
Chamada entra no FreeSWITCH (resiliente, B2BUA)
          │
          ▼
[LangGraph Agent — instância por call_id]
          │
          ├── A cada nó completado:
          │     └── Persiste snapshot mínimo no Redis
          │         { call_id, cpf_extraido, sentimento, timestamp }
          │
          ├── Nó: Transcrição ──────────────────────────────────┐
          ├── Nó: Extração Entidades (Triage + LLM)             │
          ├── Nó: Sentimento                                    │
          ├── Nó: Consenso Multi-Agente [1]                     │
          │     (Extrator → Revisor → Decisor)                  │
          └── Nó: Auditoria → RabbitMQ → Webhook [1]           │
                                                                │
          Em caso de crash do container:                        │
          └── Ao reiniciar, reconstrói estado do Redis ◄────────┘
              para calls ainda ativas
Por que não a Opção A pura?
O requisito de Consenso Multi-Agente 
architecture_rfc.md
 é o argumento decisivo:

"Nenhuma ação crítica (abrir porta) pode ser executada baseada no output de um único LLM. A arquitetura exige um fluxo Extrator → Revisor → Decisor"

Este fluxo é inerentemente stateful e sequencial dentro de uma mesma chamada. Implementá-lo com Workers totalmente independentes exigiria:

Cada Worker lendo/escrevendo estado no Redis a cada passo
Lógica de orquestração distribuída reimplementada manualmente
O que basicamente seria... um LangGraph reinventado de forma pior
📊 Resumo Executivo dos 3 Dilemas
DILEMA
RECOMENDAÇÃO
RAZÃO PRINCIPAL
Dilema 1 — Event Bus
C — Híbrido
Redis no hot path RT + RabbitMQ na auditoria crítica 
architecture_rfc.md
Dilema 2 — Extração RT
C — Mista/Triage
Regex como pré-filtro + LLM self-hosted para ambiguidade 
architecture_rfc.md
Dilema 3 — State Management
B + Checkpointing
LangGraph para coesão de estado + Redis snapshot para resiliência 
architecture_rfc.md


💡 Consideração Final sobre a Stack
A combinação das três recomendações forma uma arquitetura coerente e bem fundamentada para o contexto Mission Critical On-Premises 
architecture_rfc.md
:


Collapse
Save
Copy
1
2
3
4
5
6
7
8
FreeSWITCH (B2BUA resiliente)
    │
    ├── Redis Pub/Sub ──→ LangGraph Agent (por call)
    │   [hot path RT]          │
    │                    checkpoints leves → Redis KV
    │
    └── RabbitMQ ──→ Worker Auditoria → Webhook JSON
        [pós-chamada]
O maior risco do projeto não está nos dilemas individuais, mas na disciplina de não misturar os caminhos — manter o hot path de áudio sempre no Redis sem deixar dados críticos de auditoria passarem por ele.