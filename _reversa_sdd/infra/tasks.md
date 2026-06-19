# Infraestrutura, Tarefas de Implementação

> Gerado pelo Writer — 2026-06-19

## Tarefas

- [ ] T-01, Configurar Docker Compose com 14 serviços
  - Origem: `docker-compose.yml`, `docker-compose.app.yml`, `docker-compose.infra.yml`
  - Critério: todos os containers sobem e se comunicam
  - Confiança: 🟢

- [ ] T-02, Configurar BunkerWeb com sticky session (X-Call-ID)
  - Origem: `docker-compose.app.yml:136-138`
  - Critério: requisições com mesmo X-Call-ID roteadas para mesma instância
  - Confiança: 🟢

- [ ] T-03, Configurar FreeSWITCH (dialplan + SIP profiles)
  - Origem: `freeswitch/conf/`
  - Critério: chamadas SIP roteadas corretamente
  - Confiança: 🟢

- [ ] T-04, Implementar deploy.sh com rollback
  - Origem: `deploy.sh`
  - Critério: deploy com backup e rollback automático
  - Confiança: 🟢

- [ ] T-05, Configurar Prometheus + Grafana + Loki
  - Origem: `prometheus.yml`, `grafana/dashboards/ai-hub.json`
  - Critério: métricas e logs coletados e visualizados
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, Testar startup de todos os containers
- [ ] TT-02, Testar sticky session BunkerWeb
- [ ] TT-03, Testar deploy e rollback
- [ ] TT-04, Testar coleta de métricas Prometheus

## Lacunas Pendentes (🔴)

- JWT_SECRET, ESL password e S3 credentials expostos — migrar para secrets management
- FreeSWITCH em network_mode host — considerar isolamento de rede
