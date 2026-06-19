# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-05-27

### Added

- Transcrição bidirecional de chamadas com fallback automático entre engines de IA
- Extração inteligente de dados (CPF, RG, placa, telefone) com detecção de dados sensíveis
- Correção contextual via IA local (Ollama + Mistral 7B) — sem envio de dados para nuvem
- Consenso automático em 3 ciclos (extrai → revisa → decide)
- Detecção de anomalias de tom (agressivo, estresse) via Whisper
- Widget Tauri desktop para operadores (sempre-on-top, system tray)
- Copiloto de recomendações baseado em sentimento da chamada
- Integração com GEAR para Dados Sensíveis
- Relatórios e métricas de desempenho (Grafana + Prometheus)
- Multitenancy físico (schemas isolados por tenant no PostgreSQL)
- Múltiplos PBX por tenant com registro SIP automático (ESL listener)
- WebSocket bidirecional para chamadas em tempo real
- Sistema de planos com rate limiting por tenant
- Worker ARQ de limpeza de gravações com retenção configurável
- Suporte a FreeSWITCH on-premise com proxy SIP e Registration Forwarding
- Deploy automatizado com controle de revisões via Git tags
- Separação de ambientes (staging/production) com docker-compose modular
