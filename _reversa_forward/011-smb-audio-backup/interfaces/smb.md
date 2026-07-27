# Interface: SMB/CIFS Audio Backup

> Identificador: `011-smb-audio-backup`
> Tipo: Arquivo (Rede)
> Protocolo: SMB/CIFS (Windows File Sharing)
> Data: `2026-07-27`

## Contrato de acesso

### Endpoint SMB

```
\\192.168.50.240\backup$\Audios_Atendimento
├── {tenant}/
│   └── {YYYY-MM-DD}/
│       └── {YYYY-MM-DD}-{HH}-{MM}-{SS}-{call_id}-{origem}-{destino}-{tx|rx}.mp3
```

### Credenciais

| Campo | Valor | Localização |
|-------|-------|------------|
| Host | 192.168.50.240 | `.env` SMB_HOST |
| Share | backup$ | `.env` SMB_SHARE |
| Username | zenith_backup | `.env` SMB_USERNAME |
| Password | (segredo) | `.env` SMB_PASSWORD |

### Operações suportadas

| Operação | Ator | Descrição | Permissão |
|----------|------|-----------|-----------|
| Escrita de arquivo | Worker Zenith | Copiar rx.mp3 + tx.mp3 para `{tenant}/{YYYY-MM-DD}/` | WRITE |
| Leitura de arquivo | Auditoria | Abrir, baixar, reproduzir arquivos `.mp3` | READ |
| Renomeação | Nenhum | Bloqueado por ACL | DENY |
| Deleção | Nenhum | Bloqueado por ACL | DENY |
| Mkdir | Worker Zenith | Criar pasta `{tenant}/{YYYY-MM-DD}/` se não existir | WRITE |

## Formato de arquivo

### Entrada (origem → SMB)

**Arquivo 1:** `rx.mp3` do diretório `/data/recordings/{tenant}/{call_id}/`
- Codec: MP3 (validado por mediainfo/ffprobe)
- Tamanho: 2-5 MB (típico: 3MB para 30s conversa)
- Taxa de bits: 128 kbps (configurado em feature 010)
- Duração: Corresponde à duração real da chamada

**Arquivo 2:** `tx.mp3` do mesmo diretório
- Mesmas specs que rx.mp3 (sinal transmitido)

### Nomeação de destino

```
{YYYY-MM-DD}-{HH}-{MM}-{SS}-{call_id}-{origem}-{destino}-{tx|rx}.mp3

Exemplo: 2026-07-27-14-35-42-abc123def456-1001-20991-rx.mp3
         └─ Data    └─Hora  └─call_id └─orig └─dest  └─chan
```

**Mapeamento de campos:**
- `YYYY-MM-DD`: Data da chamada (de `Call.start_time`)
- `HH-MM-SS`: Hora da chamada (de `Call.start_time`)
- `call_id`: UUID da chamada (primeiros 12 caracteres para brevidade, full 36 em log local)
- `origem`: Ramal que originou a chamada (de `Call.extension_origin`)
- `destino`: Ramal/número destino (de `Call.extension_destination`)
- `tx|rx`: Canal de áudio (transmit ou receive)

## Tratamento de erro

### Casos de falha esperados

| Caso | HTTP-like status | Ação do worker |
|------|-----------------|---------|
| SMB offline (rede indisponível) | 0 (sem conexão) | Retry com exponential backoff (1s, 2s, 4s), enfileirar como pending |
| Autenticação falha (credenciais erradas) | 403 Forbidden | Falhar imediatamente, alertar, NÃO retentar |
| Permissão negada (pasta read-only) | 403 Forbidden | Falhar, investigar ACL no servidor SMB |
| Espaço em disco cheio (servidor SMB) | 507 Insufficient Storage | Retry após 5min (circuit breaker), alertar oncall |
| Arquivo já existe (duplicata) | 409 Conflict | Validar checksum, se match = OK (idempotente), se diff = erro |
| Conexão timeout | 408 Request Timeout | Aumentar timeout, retentar |
| Arquivo incompleto em trânsito | 0 (escrita abortada) | Deletar `.tmp` no SMB, retentar |

### Recuperação

1. **Arquivo incompleto:** Escrita atômica (temp → rename) garante aparência instantânea
2. **Checksum mismatch:** Deletar arquivo SMB, retentar cópia
3. **Retry automático:** Circuit Breaker ativa após 5 falhas consecutivas, aguarda 5min
4. **Log persistente:** Todos os erros registrados em `/data/smb_transfer_log.json`

## Idempotência e duplicação

**Idempotência:** SIM, implementada via checksum

- Se mesmo arquivo for copiado 2x (retry duplicado), segundo resultado será: comparar SHA256 local vs. SMB
  - Se match: Ignorar (idempotente)
  - Se diff: Erro, investigar (corrupção)

**Prevenção de duplicata:**
- Worker marca arquivo no log com `status=done` APÓS checksum validado
- Ciclo seguinte pula itens com `status=done`
- Log é persistido em named volume, sobrevive restarts

## Contrato de timeout

| Operação | Timeout | Razão |
|----------|---------|-------|
| Conexão inicial (SMB) | 10s | Handshake TCP/445 |
| Autenticação | 5s | Negotiation |
| Mkdir (criar pasta) | 5s | File operation |
| Escrita de chunk (512KB) | 30s | Dependendo de largura de banda |
| Validação de checksum | 10s | Hash computation |
| Total por arquivo | 60s | Abort se timeout (circuit breaker) |

## Integridade de dados

### Checksum validação

1. **Antes de copiar:** Calcular SHA256 do arquivo original em `/data/recordings/{tenant}/{call_id}/{rx|tx}.mp3`
2. **Após copiar:** Ler arquivo do SMB, recalcular SHA256
3. **Comparação:** Se match, marcar `status=done` no log; se diff, deletar arquivo SMB e retentar

### Hash algorithm

- **Algoritmo:** SHA256 (160 bits)
- **Representação:** Hexadecimal (64 caracteres)
- **Armazenamento:** Campo `sha256_rx` e `sha256_tx` em `/data/smb_transfer_log.json`

## Rate limiting e throttling

### Banda global

- **Limite padrão:** 5 MB/s (configurável via `SMB_BANDWIDTH_LIMIT_MBS`)
- **Escopo:** Todas as cópias SMB em paralelo (não por arquivo)
- **Implementação:** `time.sleep()` calculado após ler chunk de 512KB
  - Tempo ideal = (bytes_lidos / 1024 / 1024) / limite_mbs
  - Dormir = tempo_ideal - tempo_real_passado

### Limite de concurrent connections

- **Max simultâneos:** 1 conexão SMB por worker (thread separada via `asyncio.to_thread()`)
- **Recomendação:** 1 worker `zenith-smb-sync`, não múltiplos (throttling global assume 1 worker)

## Observabilidade

### Logs estruturados

Cada operação registra em `/data/smb_transfer_log.json`:
```json
{
  "call_id": "abc...",
  "tenant_id": "akom",
  "status": "done|pending|error",
  "timestamp_created": "ISO 8601",
  "timestamp_transferred": "ISO 8601",
  "bytes_transferred": 245120,
  "sha256_rx": "hex",
  "sha256_tx": "hex",
  "attempts": 3,
  "last_error": "Connection timeout: ..."
}
```

### Métricas Prometheus

- `smb_backup_success_total` (counter, label: tenant)
- `smb_backup_failed_total` (counter, label: tenant)
- `smb_backup_latency_seconds` (histogram, label: tenant)
- `smb_backup_queue_size` (gauge, label: tenant)

## Segurança

### Credenciais

- Nunca hardcoded (apenas `.env` gitignored)
- Nunca em logs (filtro regex no logger)
- Nunca em metrics (anônimizadas)

### Acesso remoto

- ACL no servidor SMB: Grupo `auditores` com READ-ONLY
- Auditorores não podem deletar (compliance de prova)

### Confidencialidade de dados

- Dados sensíveis (voz) transitam em LAN privada (192.168.x.x)
- Sem criptografia (overhead em LAN, não necessário)
- Responsabilidade do cliente garantir segurança física da rede e do servidor SMB

## Monitoramento recomendado

```yaml
Alertas:
  - fila > 100 arquivos (possível SMB offline/lento)
  - latência > 10s (degradação de rede)
  - falha consecutiva > 5 (circuit breaker ativado)
  - erro de autenticação (verificar credenciais .env)
```
