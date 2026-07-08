# Data Delta: Detecção Dinâmica de IP Externo

> Feature: `005-dynamic-external-ip`
> Data: `2026-06-29`

## Resumo

Nenhuma mudança no modelo de dados do PostgreSQL. Não há novas tabelas, colunas, índices, migrações Alembic ou seeds.

## Configuração (env vars)

Novas variáveis de ambiente para o sidecar:

| Variável | Obrigatória | Descrição | Exemplo |
|----------|-------------|-----------|---------|
| `EXTERNAL_IP_ENDPOINT` | Sim | URL do endpoint HTTP que retorna o IP público | `http://services.akom.com.br` |
| `FREESWITCH_ESL_HOST` | Não (default `127.0.0.1`) | Host ESL do FreeSWITCH. Com `network_mode: host` no sidecar, usar `127.0.0.1`. Se a rede for bridge, usar `172.20.0.1` (gateway Docker, igual ao FastAPI) | `127.0.0.1` |
| `FREESWITCH_ESL_PORT` | Não (default `8021`) | Porta ESL do FreeSWITCH | `8021` |
| `FREESWITCH_ESL_PASSWORD` | Sim | Senha ESL — mesmo valor de `FREESWITCH_ESL_PASSWORD` em `src/config.py` (default `ClueCon`; trocar em produção) | - |
| `POLL_INTERVAL` | Não (default `60`) | Intervalo em segundos entre verificações | `60` |
| `MOCK_EXTERNAL_IP` | Não | IP fixo para testes (dev); quando setado, não consulta endpoint nem grava `vars-external-ip.xml` dinâmico | `189.112.222.244` |

Nenhuma dessas variáveis requer migration ou schema de banco.

## Volume obrigatório para o sidecar

O serviço `ip-watcher` deve montar:

```yaml
volumes:
  - ./freeswitch/conf:/etc/freeswitch
```

Isso permite ao sidecar escrever `vars-external-ip.xml` no mesmo diretório que o FreeSWITCH usa como `/etc/freeswitch`, garantindo que `reloadxml` enxergue o arquivo include gerado.

## Histórico

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-06-29 | Versão inicial | reversa |
