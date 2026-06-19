# Investigation: Desempenho e Multitenancy na Evolução do Zenith VoIP

> Identificador: `002-escala-eventos`
> Data: `2026-05-21`

## 1. Viabilidade da Arquitetura por Eventos em Alta Escala

A principal questão levantada neste ciclo forward é se a arquitetura baseada em eventos continua viável frente a um cenário de alta volumetria (>500 chamadas/dia por atendente com 10+ atendentes concorrentes, resultando em mais de 5.000 ligações/dia).

Após análise técnica, **a arquitetura baseada em eventos não é apenas viável, mas estritamente necessária**. 

### Por que manter o Barramento de Eventos (Redis Streams)?
1. **Desacoplamento de I/O em Tempo Real**: O proxy de telefonia (SwitchPBX/FreeSWITCH) lida com tráfego SIP/RTP sensível a tempo e latência. Executar escritas síncronas em banco de dados ou chamadas de IA síncronas bloquearia o loop de telefonia, resultando em jitter, perda de pacotes de áudio e quedas na chamada.
2. **Escalabilidade Assíncrona de IA (STT, LLM, TTS)**:
   - **Ingestão**: O ingestor empacota fluxos de áudio WebSocket e despacha para o Redis Streams instantaneamente. O tempo de gravação no barramento é `<1ms`.
   - **Workers Independentes**: O processamento pós-chamada (sumarização via Ollama, persistência em PostgreSQL, alertas adicionais) é processado por Workers ARQ de forma assíncrona. Se o volume de chamadas explodir temporariamente, o Redis Streams retém os eventos no barramento e os workers processam em fila ordenadamente sem estourar o banco de dados.
3. **Resiliência a Falhas**: Se o banco de dados PostgreSQL sofrer indisponibilidade momentânea ou travamento de locks, as chamadas telefônicas em curso **não caem**, e os eventos de áudio já capturados não se perdem. Eles são retidos de forma persistente e estruturada no Redis Streams até que a conexão de escrita Postgres seja restabelecida.

### Capacidade do Redis Streams vs Volume Exigido
- **Volume Exigido**: 5.000 chamadas/dia. Considerando uma média de 3 minutos por chamada e chunks de áudio de 200ms, temos:
  - $5000 \times 180 \text{s} = 900.000$ segundos de áudio por dia.
  - Com chunks de áudio despachados a cada 200ms: $900.000 / 0.2 = 4.500.000$ eventos/dia.
  - Média de eventos por segundo: $4.500.000 / 86400 \approx 52 \text{ eventos/segundo (EPS)}$.
  - EPS de pico (estimado com 50% de concorrência simultânea): $\approx 350 \text{ EPS}$.
- **Capacidade do Redis Streams**: O Redis Streams em hardware dev modesto suporta confortavelmente mais de **80.000 EPS** de escrita e consumo. A volumetria da operação da Akom consome apenas uma fração mínima (`<0.5%`) da capacidade máxima do Redis Streams, garantindo folga de desempenho excepcional.

---

## 2. Abordagem de Multitenancy: Isolamento Físico (Database-per-Tenant)

O requisito de isolamento estrito de dados onde múltiplos clientes possuem PBXs cujas bases de dados não podem se misturar levou à decisão pelo **Isolamento Físico via Schemas Diferentes (Database-per-Tenant)** no PostgreSQL.

### Avaliação de Alternativas de Isolamento

| Critério | Isolamento Lógico (Coluna `tenant_id` + RLS) | Isolamento Físico (Schema por Tenant) |
|---|---|---|
| **Segurança e Blindagem** | Média (risco de bugs de aplicação ou falhas de RLS exporem dados de outros inquilinos). | **Máxima** (dados vivem em namespaces físicos separados. Erros de aplicação não cruzam schemas). |
| **Custo de Infraestrutura** | Baixo (um único pool de conexões e tabelas compartilhadas). | Médio (criação de múltiplos schemas requer gerenciamento dinâmico de conexões). |
| **Complexidade de Migração** | Baixa (Alembic tradicional). | Média (exige script para varrer inquilinos e rodar migrations isoladas por schema). |
| **Portabilidade Regulatória** | Dificulta backup/restauração e deleção de dados (ex.: LGPD) de um único cliente. | **Facilita** (exclusão do schema limpa 100% dos dados físicos daquele cliente instantaneamente). |

### Decisão Arquitetural
Adotaremos a estratégia **Database-per-Tenant via Schemas do PostgreSQL**. Rotearemos as conexões assíncronas do SQLAlchemy dinamicamente em nível de middleware/sessão da aplicação baseando-se no `tenant_id` fornecido pelo JWT ou evento:
```python
# Roteamento Dinâmico conceitual no FastAPI
async def get_db_session(request: Request):
    tenant_id = request.state.tenant_id
    # Executa a query para setar o search_path da conexão SQLAlchemy
    async with engine.connect() as conn:
        await conn.execute(text(f"SET search_path TO tenant_{tenant_id}"))
        # Retorna a sessão vinculada a essa conexão
```

---

## 3. Rastreamento Dinâmico de Ramais e PBXs

A associação automática do atendente com seu ramal SIP ativo sem controle administrativo sobre o PABX de terceiros será resolvida via **IP Matching** auxiliado por **Dial-in Linkage**.

### Funcionamento do IP Matching
1. **Interceptação SIP**: O SwitchPBX (FreeSWITCH) atua como proxy transparente. Toda vez que o softphone do atendente envia um pacote SIP `REGISTER` para o PBX original, ou inicia um `INVITE` (chamada), o SwitchPBX intercepta e dispara um evento ESL (Event Socket Library).
2. **Registro de Origem**: O módulo `telephony/esl_client.py` captura esse evento, extrai o ramal (`From`) e o IP/Porta de origem do pacote SIP e grava no Redis cache com expiração automática (`SETEX ramal_sip_ip:<IP> <ramal> 3600`).
3. **Casamento no WebSocket**: Quando o atendente abre o widget e loga via WebSocket `/api/v1/widget/ws`, o FastAPI lê o IP público/local da conexão WebSocket. Ele busca no Redis o IP correspondente e encontra o `ramal` mapeado. A associação é efetuada instantaneamente e de forma invisível.

### Mitigação para Ambientes NAT Compartilhados (Call Centers)
Quando múltiplos agentes compartilham o mesmo IP público de internet de saída:
- **O IP Matching falharia** porque o Redis veria o mesmo IP para múltiplos ramais e sessões WebSocket.
- **Solução de Fallback (Dial-In)**: No widget, se a associação automática falhar ou retornar colisão, o widget exibirá a mensagem "Clique aqui para vincular ramal". O atendente clica no widget e efetua uma discagem rápida no softphone para o código `*88` interceptado pelo SwitchPBX. O SwitchPBX dispara o evento de ligação `*88` com o ramal dele. Como o atendente acabou de clicar em "Vincular" no widget, o backend FastAPI casa a chamada ativa daquele ramal com a sessão WebSocket sob o mesmo token JWT instantaneamente, gravando a relação persistente em cache.
