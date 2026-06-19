# Requirements: Worker de Limpeza de Gravações (Audio Cleanup)

> Identificador: `003-limpeza-audio`
> Data: `2026-05-21`
> Confidência: 🟢 CONFIRMADO

## 1. Resumo executivo

Worker ARQ periódico que varre os buckets do MinIO (ou S3 compatível) por inquilino e remove objetos de áudio com mais de N dias de retenção. Execução diária via cron nativo do ARQ.

## 2. Regras de negócio

| ID | Descrição | Tipo | Confidência |
|----|-----------|------|-------------|
| RN-01 | Gravações de áudio devem ser removidas após o período de retenção configurável | Nova | 🟢 |
| RN-02 | A limpeza deve ser isolada por tenant (cada tenant tem seu bucket/prefixo) | Nova | 🟢 |
| RN-03 | A retenção padrão é de 90 dias, configurável via env `AUDIO_RETENTION_DAYS` | Nova | 🟢 |

## 3. Funcionamento

- Executa a cada 24h via `arq.cron`
- Lista objetos no bucket MinIO do tenant
- Filtra por `last_modified < now - AUDIO_RETENTION_DAYS`
- Apaga objetos expirados
- Registra métricas: arquivos apagados, bytes liberados, por tenant
- Se S3 não estiver configurado, ignora silenciosamente (graceful skip)

## 4. Variáveis de ambiente

| Variável | Default | Descrição |
|----------|---------|-----------|
| `AUDIO_RETENTION_DAYS` | 90 | Dias de retenção de gravações |
| `S3_ENDPOINT` | "" | Endpoint do S3/MinIO |
| `S3_ACCESS_KEY` | "" | Access key |
| `S3_SECRET_KEY` | "" | Secret key |
| `S3_BUCKET_PREFIX` | "zenith-audio" | Prefixo dos buckets |

## 5. Critério de aceitação

```gherkin
Cenário: Limpeza diária de gravações expiradas
  Dado que existem gravações com mais de 90 dias no bucket do tenant "tenant_akom"
  Quando o worker de cleanup executa
  Então essas gravações são removidas
  E métricas são registradas com a contagem de arquivos apagados

Cenário: Tenant sem gravações expiradas
  Dado que todas as gravações do tenant "tenant_akom" têm menos de 90 dias
  Quando o worker de cleanup executa
  Então nenhum objeto é apagado
  E a métrica registra 0 arquivos removidos

Cenário: S3 não configurado
  Dado que S3_ENDPOINT está vazio
  Quando o worker de cleanup executa
  Então ele ignora silenciosamente sem erro
```
