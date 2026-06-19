# Requirements: Alta Escala, Isolamento Multitenant e PBX Múltiplos

> Identificador: `002-escala-eventos`
> Data: `2026-05-21`
> Pasta da extração reversa: `specs/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

Esta feature define os requisitos funcionais e não funcionais necessários para estruturar o sistema Zenith para suportar alta escala em produção, com isolamento absoluto entre múltiplos inquilinos (multitenancy) que operam múltiplos servidores de PBX IP, ao mesmo tempo em que avalia a viabilidade da continuidade da arquitetura baseada em eventos. A arquitetura baseada em eventos se confirma como altamente recomendável para esta escala, pois isola o tráfego em tempo real da telefonia SIP das latências de persistência em banco de dados e dos tempos de inferência de inteligência artificial (STT, LLM e TTS).

## 2. Contexto a partir do legado

A infraestrutura e as decisões arquiteturais da Zenith apoiam-se em modelos pré-existentes mapeados no legado:

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `specs/architecture-guide.md#6-barramento-de-eventos-redis-streams` | Desacoplamento de tarefas por meio de barramento de eventos utilizando Redis Streams para assegurar que chamadas não percam dados caso workers sofram indisponibilidade. | 🟢 |
| `specs/architecture-guide.md#5-async-do-comeco-ao-fim` | Emprego de chamadas assíncronas de ponta a ponta para otimizar o processamento de I/O em tempo real. | 🟢 |
| `src/database/models.py#Call` | O modelo de persistência `calls` possui estrutura inicial contendo o discriminador de inquilino `tenant_id` para fins de controle básico de separação de registros. | 🟢 |
| `specs/apresentacao_comercial.html#SLIDE 4 — ARQUITETURA` | O SwitchPBX atua como um proxy transparente de desvio na linha telefônica do ramal sem alterar as configurações locais do PABX do cliente. | 🟢 |

## 3. Personas e cenários de uso

A operação em grande escala envolve as seguintes personas:

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| **Atendente (Operador)** | Deseja efetuar e receber chamadas de forma transparente sem atrasos de áudio, com o widget de checklist POP atualizando instantaneamente. | Realizar e receber mais de 500 chamadas diárias com áudio bidirecional e processamento de IA em tempo real estável. |
| **Administrador do Cliente (Tenant Admin)** | Deseja gerenciar de forma autônoma as conexões de múltiplos servidores PABX pertencentes à sua empresa e alocar os ramais SIP aos atendentes ativos. | Vincular três servidores PABX diferentes à mesma conta corporativa, isolando totalmente os dados de ligações das demais empresas. |
| **Engenheiro de Infraestrutura (SRE / SysOps)** | Deseja manter o sistema ativo, escalando workers assíncronos e garantindo que picos de chamadas simultâneas não causem perda de eventos ou lentidão no banco de dados. | Monitorar o barramento assíncrono durante horários de pico e garantir isolamento de banco de dados para novos clientes ativados na plataforma. |

## 4. Regras de negócio novas ou alteradas

O sistema de alta escala deve seguir regras estritas de isolamento e mapeamento:

1. **RN-01: Rastreamento Dinâmico de Ramal SIP (Nova)** 🟢
   - Origem no legado: N/A
   - Tipo: Nova
   - Descrição: O sistema deve rastrear de forma dinâmica qual atendente (identificado por UUID) está utilizando qual ramal SIP e PBX. Como não há controle sobre o PBX de terceiros onde os ramais são registrados, a associação será feita de forma automática: o proxy transparente SwitchPBX (FreeSWITCH) interceptará mensagens SIP `REGISTER` e `INVITE` para mapear o ramal ao IP/sessão de origem, cruzando essa informação com a sessão WebSocket ativa do Widget do atendente conectada a partir do mesmo IP, mantendo fallback de vinculação manual expressa por código rápido (`*88` no softphone).

2. **RN-02: Isolamento Absoluto de Dados Multitenant (Alterada)** 🟢
   - Origem no legado: `src/database/models.py#Call` (onde `tenant_id` era apenas um campo opcional).
   - Tipo: Alterada
   - Descrição: Os dados de chamadas, áudio, transcrições e análises de um determinado inquilino (`tenant_id`) devem possuir isolamento físico completo. O sistema adotará a estratégia Database-per-Tenant, com bases de dados ou schemas distintos por inquilino, eliminando qualquer risco regulatório ou mistura de dados.

3. **RN-03: Suporte a Múltiplos PBXs por Cliente (Nova)** 🟢
   - Origem no legado: `specs/apresentacao_comercial.html#SLIDE 4 — ARQUITETURA`
   - Tipo: Nova
   - Descrição: Um cliente corporativo (inquilino) pode gerenciar um ou mais PABXs em sua operação. Cada ligação deve possuir rastreabilidade clara que a vincule ao PABX de origem, além do inquilino.

4. **RN-04: Desacoplamento Assíncrono de Telefonia (Nova)** 🟢
   - Origem no legado: `specs/architecture-guide.md#6-barramento-de-eventos-redis-streams`
   - Tipo: Nova
   - Descrição: Para suportar alta carga diária, o SwitchPBX (FreeSWITCH) não deve efetuar requisições síncronas bloqueantes de banco de dados ou processamento de arquivos. Toda a lógica de extração, análise de sentimentos e persistência final deve ocorrer de forma assíncrona por meio do barramento de eventos.

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| **RF-01** | Rastrear o ramal ativo do atendente em tempo real de forma automática. | Must | O proxy SwitchPBX mapeia `ramal_sip -> IP` a partir de interceptação de tráfego SIP e o backend cruza com a conexão WebSocket ativa do widget no mesmo IP, registrando `atendente_id -> ramal_sip -> pbx_id` no cache Redis. | 🟢 |
| **RF-02** | Configurar e gerenciar múltiplos servidores PABX vinculados a um único inquilino. | Must | O painel do administrador permite cadastrar múltiplos `pbx_id` sob um único `tenant_id`. | 🟢 |
| **RF-03** | Separar os dados de chamadas e transcrições por inquilino em nível de banco de dados separado. | Must | Cada inquilino possui sua própria base ou schema físico independente, e as queries são direcionadas dinamicamente com base no `tenant_id` autenticado, impossibilitando mistura de dados. | 🟢 |
| **RF-04** | Ingestão imediata de chamadas no barramento assíncrono. | Must | A resposta a eventos SIP de ligação pelo SwitchPBX deve ocorrer em menos de 10 milissegundos, empacotando os metadados para envio imediato ao barramento Redis Streams. | 🟢 |
| **RF-05** | Filtro de eventos do barramento assíncrono por PBX e Tenant. | Should | Cada mensagem trafegada no Redis Streams contém metadados obrigatórios de `tenant_id` e `pbx_id` no cabeçalho do evento. | 🟢 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| **Desempenho** | A latência de recepção e despacho de áudio no SwitchPBX deve ser inferior a 10ms. | Essencial para manter o fluxo RTP limpo e sem distorções sonoras durante picos de chamadas simultâneas. | 🟢 |
| **Escalabilidade** | A infraestrutura deve suportar mais de 500 chamadas por atendente ao dia, com 10 atendentes simultâneos (total diário acumulado de no mínimo 5.000 chamadas). | Necessário para atender à volumetria reportada pela operação do cliente Akom e permitir crescimento horizontal. | 🟢 |
| **Segurança** | Garantir isolamento físico completo com estratégia Database-per-Tenant de credenciais e conexões SIP. | Impede sequestro de sessões VoIP, vazamento de logs de áudio e interrupção da telefonia de clientes corporativos. | 🟢 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Registro dinâmico de ramal SIP do atendente ao conectar
  Dado que o Atendente "Carlos" com UUID "atend-123" realiza login no sistema
  E informa que utilizará o ramal "4001" da PBX "pabx-principal"
  Quando o sistema valida a conexão no painel Zenith
  Então a tabela de sessões ativas associa "atend-123" ao ramal "4001" da PBX "pabx-principal"
  E as chamadas recebidas neste ramal passam a exibir alertas no widget do atendente "Carlos"

Cenário: Isolamento de consultas de chamadas entre diferentes inquilinos
  Dado que o Inquilino "Empresa A" (ID: "tenant-aaa") possui chamadas salvas no banco
  E o Inquilino "Empresa B" (ID: "tenant-bbb") possui chamadas salvas no banco
  Quando o Administrador do Inquilino "Empresa A" solicita o relatório de chamadas concluídas
  Então o sistema executa a consulta isolada garantindo que apenas registros do ID "tenant-aaa" sejam retornados
  E nenhum registro do ID "tenant-bbb" aparece no resultado da consulta

Cenário: Tenant gerencia múltiplos PBXs simultaneamente
  Dado que o inquilino "tenant-aaa" possui cadastrados os PBXs "PABX-Matriz" e "PABX-Filial"
  Quando o ramal "5002" do PBX "PABX-Matriz" inicia uma chamada de voz
  E o ramal "9005" do PBX "PABX-Filial" também inicia uma chamada de voz
  Então o sistema armazena as duas chamadas sob o mesmo ID "tenant-aaa"
  E identifica individualmente as origens de cada chamada como provenientes do respectivo "PABX-Matriz" e "PABX-Filial"

Cenário: Atendente tenta acessar ramal pertencente a outro inquilino
  Dado que o Atendente "Carlos" com UUID "atend-123" pertence ao inquilino "tenant-aaa"
  Quando ele tenta registrar e se conectar ao ramal "4001" pertencente à PBX da "Empresa B" (ID: "tenant-bbb")
  Então o sistema Zenith rejeita a solicitação de conexão
  E emite um alerta de segurança por tentativa de violação de limite de tenant
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|---------------|
| **RF-01** (Rastrear ramal ativo) | Must | Fundamental para direcionar checklist POP e análises em tempo real para a tela do atendente correto. |
| **RF-02** (Configurar múltiplos PBXs) | Must | Regra essencial da operação de múltiplos clientes Zenith que possuem filiais ou infraestruturas distribuídas. |
| **RF-03** (Separar dados de inquilinos) | Must | Requisito regulatório de segurança e privacidade essencial para que o produto possa ser comercializado em escala SaaS. |
| **RF-04** (Ingestão assíncrona de chamadas) | Must | Sem o desacoplamento assíncrono via barramento de eventos, o SwitchPBX sofreria gargalos de I/O na telefonia sob carga elevada. |
| **RF-05** (Filtro de metadados no barramento) | Should | Auxilia na otimização da entrega e divisão de carga dos workers dedicados a transcrições específicas. |

## 9. Esclarecimentos

### Sessão 2026-05-21

- **Q: [Segurança / Isolamento]** Qual deve ser a estratégia de multitenancy para isolar os dados das chamadas, áudios e transcrições de clientes distintos?
  **R:** **Isolamento Físico Total (Database-per-Tenant)**. Adotaremos schemas ou instâncias PostgreSQL físicas distintas para cada inquilino (`tenant_id`), eliminando qualquer risco regulatório de vazamento ou contaminação cruzada de dados de chamadas e transcrições de IA.
  
- **Q: [Escopo / Regra de Negócio]** Como deve ocorrer a associação do atendente com seu ramal SIP ativo e o respectivo PBX no início de sua jornada de trabalho se não temos controle direto sobre o registro do PBX de terceiros?
  **R:** **Vínculo Dinâmico e Detecção Automática (Abordagem Híbrida)**. Como o SwitchPBX (FreeSWITCH) atua como um proxy transparente interceptando tráfego SIP, ele mapeará automaticamente os registros `REGISTER` e requisições `INVITE` correlacionando `ramal_sip -> IP/porta` de origem no Redis. Quando o atendente logar no Widget via WebSocket, o backend cruza os IPs locais do cliente para realizar o vínculo automático `atendente_id -> ramal_sip`. Como fallback para redes complexas (NAT múltiplo), o atendente poderá clicar em "Vincular" no widget e discar o código rápido `*88` do seu softphone para validar instantaneamente a associação.

- **Q: [Infraestrutura / Latência]** Para suportar a escala de 10+ atendentes concorrentes (>500 chamadas/dia por atendente) com processamento de IA em tempo real, qual abordagem de hardware/serviços de IA devemos adotar?
  **R:** **Modelo Híbrido**. Utilizaremos STT na nuvem (Deepgram de alta performance comercial e baixíssima latência) para processamento em tempo real do áudio de chamadas ativas. Em contrapartida, as tarefas de LLM (sumarização, extração de entidades) e TTS secundário utilizarão serviços locais (Ollama e Piper TTS) otimizados de baixo custo rodando em hardware dev apropriado ou fallbacks SaaS pré-configurados.

- **Q: Onde serão configurados os ramais que serão ouvidos pelo FreeSwitchPBX?**
  **R:** Os ramais **não** necessitam de cadastro ou configuração estática individual no FreeSWITCH (SwitchPBX). Eles continuam configurados e gerenciados unicamente no PBX de terceiros do cliente (ex.: VitalPBX). O SwitchPBX atua como proxy transparente interceptando de forma dinâmica qualquer tráfego SIP de ramais ativos que cruzem sua rota, espelhando os canais de áudio via `mod_audio_fork`. O Zenith apenas mapeia administrativamente no banco as associações de atendentes a esses ramais para fins de exibição no widget.

- **Q: Onde eu preciso configurar o IP do FreeSwitchPBX? No PBX do cliente ou nos ramais? Ou ele apenas escuta passivamente como Wireshark?**
  **R:** O FreeSWITCH (SwitchPBX) é um elemento ativo de sinalização (B2BUA/Proxy SIP) e **não** atua como Wireshark (escuta passiva). Para cenários onde há controle total da infraestrutura, os ramais ou softphones podem apontar para o SwitchPBX como seu Outbound Proxy ou servidor principal, e este encaminha as conexões para o PBX original (`${pbx_host}`). Contudo, para cenários de **Portaria Remota** com softphones de operadores integrados a softwares de terceiros e interfones IP legados, adotamos o padrão de **Loop de SIP Trunk / Gateway Inline (detalhado na próxima resposta)**, configurado diretamente no PBX do cliente (ex.: VitalPBX), evitando qualquer alteração nas configurações individuais de ramais ou aplicativos locais.

- **Q: [Portaria Remota / Registro SIP] Como integrar o SwitchPBX sem alterar softphones de operadores sob softwares proprietários e mantendo a exibição de ramais "Verdes" (registrados) no VitalPBX?**
  **R:** Padronizaremos o modelo utilizando o padrão de **Registration Forwarding / Passthrough (Proxy de Registro Transparente)** como nossa abordagem principal, mantendo o Loop de SIP Trunk como uma alternativa secundária de fallback:
  1. **Configuração Simples no Softphone (GEAR / G-PHONE)**: Como exemplo, o software de portaria (ex: GEAR admin) permite configurar o "IP ou Domínio do VOIP", alteramos este campo para apontar para o SwitchPBX (FreeSWITCH). O usuário (`20065`) e a senha (`20!@...`) permanecem os mesmos.
  2. **Proxy e Encaminhamento de Registro (Registration Forwarding)**: Quando o softphone envia o pacote `REGISTER` para o SwitchPBX, o FreeSWITCH atua de forma transparente como um proxy retransmissor: ele intercepta a mensagem, extrai as credenciais e encaminha o registro para o PBX original do cliente (ex: `sip.maisalerta.tecnorise.com`).
  3. **Registro Verde no PBX**: O PBX original aceita o registro e responde com `200 OK`. Isso garante que o ramal permaneça ativo e listado como "registrado/verde" no painel de monitoramento do VitalPBX do cliente.
  4. **Fluxo Natural de Mídia e Captura**: Toda a sinalização e mídias das chamadas (INVITE/RTP) passam obrigatoriamente pelo SwitchPBX, permitindo que o `mod_audio_fork` faça a interceptação do áudio bidirecional para a IA Zenith em tempo real, sem necessidade de alterações complexas nas rotas de dialplan do VitalPBX original.
  *Fallback:* Caso o sistema de portaria não permita alterar o domínio SIP nas configurações do softphone, utilizaremos o padrão **Inline SIP Trunk Loop (Loop por Trunk SIP)**, onde os desvios e retornos das chamadas ocorrem via trunks SIP configurados no VitalPBX do cliente.

- **Q: Vai ter uma interface web para gerenciamento do FreeSwitchPBX dentro do Zenith? Ou as configurações serão apenas no FreeSwitch mesmo?**
  **R:** As configurações de baixo nível de telefonia do FreeSWITCH (portas, profiles, codecs) são estáticas e tratadas como Infraestrutura como Código (IaC) no container. O painel administrativo do Zenith contará apenas com telas de gerenciamento simples para o administrador do cliente cadastrar os hosts de seus PBXs originais (`api_pbxs.md`) e associar ramais/atendentes. Não haverá interface web para gerenciar parâmetros internos do FreeSWITCH diretamente no Zenith, mantendo a operação simples e protegida contra falhas de configuração de telefonia.

- **Q: Onde os dados de áudio serão gravados? Em algum storage local ou em nuvem para futura análise de qualidade?**
  **R:** Para suportar a alta escala de mais de 5.000 ligações diárias, a gravação de áudio em tempo real é armazenada temporariamente em um buffer local do servidor de telefonia. Em seguida, um worker assíncrono (Worker ARQ) faz o upload em lote para um **Object Storage (compatível com S3, como AWS S3, Google Cloud Storage ou MinIO local)** configurado de forma isolada por inquilino (`tenant_id`), respeitando a diretriz de isolamento físico total de dados e mantendo o armazenamento dos servidores de aplicação leve e de alta performance.

## 10. Lacunas

> Nenhuma lacuna ou dúvida pendente nesta versão. Todas as decisões de arquitetura e escopo foram esclarecidas.

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-05-21 | Versão inicial gerada por `/reversa-requirements` avaliando escala e arquitetura de eventos | reversa |
| 2026-05-21 | Esclarecimento de dúvidas arquiteturais de escala, isolamento multitenant e ramais automáticos via `/reversa-clarify` | reversa |
