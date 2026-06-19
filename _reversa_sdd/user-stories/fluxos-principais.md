# User Stories — Fluxos Principais

> Gerado pelo Writer — 2026-06-19

## US-01: Agente acompanha chamada em tempo real

**Como** operador de call center
**Quero** ver a transcrição da chamada em tempo real no widget
**Para** acompanhar o diálogo entre cliente e agente sem precisar escutar o áudio

**Critérios de Aceitação:**
- Widget conecta via WebSocket ao iniciar
- Transcrição aparece em até 2s após fala
- Canais tx (agente) e rx (cliente) identificados
- Alertas de anomalia destacados visualmente

## US-02: Admin gerencia PBXs

**Como** administrador do tenant
**Quero** cadastrar e listar as centrais PBX do meu tenant
**Para** configurar a integração telefônica

**Critérios de Aceitação:**
- Autenticação JWT obrigatória
- Apenas tenant_admin pode acessar
- PBX criado com name, host, port
- Listagem filtrada por tenant

## US-03: Sistema detecta anomalia em chamada

**Como** operador
**Quero** ser alertado quando o cliente estiver alterado (fúria/estresse)
**Para** tomar ações preventivas

**Critérios de Aceitação:**
- Anomalia detectada se score >= 3
- Alerta visual no widget com severidade (warning/danger)
- Notificação em tempo real via WebSocket

## US-04: Sistema valida entidades por consenso

**Como** sistema
**Quero** validar entidades extraídas em até 3 ciclos de consenso
**Para** garantir que apenas dados corretos sejam persistidos

**Critérios de Aceitação:**
- Entidades extraídas por regex
- Revisadas e validadas pelo grafo LangGraph
- Se sentiment < -0.3, rejeitado
- Máximo 3 iterações

## US-05: STT com fallback automático

**Como** sistema
**Quero** transcrever áudio com fallback automático se Deepgram falhar
**Para** garantir continuidade mesmo com instabilidade do provider cloud

**Critérios de Aceitação:**
- Deepgram é tentado primeiro (timeout 500ms)
- Fallback para Whisper se timeout ou confidence baixa
- Métrica de fallback registrada

## US-06: Operador faz linkage manual

**Como** operador
**Quero** discar *88 no softphone para vincular meu widget ao ramal
**Para** que o sistema identifique automaticamente minha chamada

**Critérios de Aceitação:**
- Código *88 detectado pelo ESL Client
- Sessão "awaiting_linkage" criada no Redis (TTL 120s)
- Widget vinculado ao ramal SIP

## US-07: Limpeza automática de áudio antigo

**Como** administrador
**Quero** que áudios com mais de 90 dias sejam deletados automaticamente
**Para** economizar espaço em disco e custos de S3

**Critérios de Aceitação:**
- Cleanup roda diariamente às 03:00
- Objetos com > 90 dias deletados em lotes de 1000
- Bucket por tenant respeitado
