# Infraestrutura — Docker e Deploy

> Gerado pelo Writer — 2026-06-19

## Visão Geral

Infraestrutura Docker, deploy com controle de revisão, configuração FreeSWITCH e stack de monitoramento (Prometheus, Grafana, Loki).

## Responsabilidades

- Orquestrar 14 containers Docker
- Proxy reverso BunkerWeb com sticky session (X-Call-ID)
- Reserva de GPU para Ollama
- Configuração FreeSWITCH (dialplan, SIP profiles)
- Deploy automatizado com rollback
- Stack de monitoramento

## Regras de Negócio

- Duas instâncias FastAPI para HA 🟢
- Sticky session via X-Call-ID (BunkerWeb) 🟢
- GPU reservada para Ollama 🟢
- FreeSWITCH em network_mode host 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade |
|----|-----------|-----------|
| RF-01 | Orquestrar containers via Docker Compose | Must |
| RF-02 | Configurar proxy reverso com sticky session | Must |
| RF-03 | Reservar GPU para Ollama | Must |
| RF-04 | Configurar FreeSWITCH (dialplan, SIP) | Must |
| RF-05 | Automatizar deploy com controle de revisão | Should |
| RF-06 | Configurar Prometheus + Grafana + Loki | Should |

## Rastreabilidade

| Arquivo | Propósito | Cobertura |
|---------|-----------|-----------|
| `docker-compose.yml` | Orquestração principal | 🟢 |
| `docker-compose.app.yml` | Serviços da aplicação | 🟢 |
| `docker-compose.infra.yml` | Serviços de infraestrutura | 🟢 |
| `Dockerfile` | Build da aplicação | 🟢 |
| `deploy.sh` | Deploy automatizado | 🟢 |
| `prometheus.yml` | Config Prometheus | 🟢 |
| `freeswitch/conf/` | Config FreeSWITCH | 🟢 |
