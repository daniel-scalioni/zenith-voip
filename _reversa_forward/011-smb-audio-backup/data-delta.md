# Data Delta: SMB Audio Backup

> Identificador: `011-smb-audio-backup`
> Data: `2026-07-27`

## Mudanças no modelo de dados

### No PostgreSQL

**Nenhuma mudança.** O multi-tenancy já existe em `specs/erd-complete.md#Call table`. Cada tenant tem schema próprio, e os áudios já são organizados por `call_id` (UUID FK para `public.calls`).

### No FileSystem (novo)

**Arquivo local de rastreamento:** `/data/smb_transfer_log.json`

```json
[
  {
    "call_id": "abc123def456",
    "tenant_id": "akom",
    "origem": "1001",
    "destino": "20991",
    "rx_path": "/data/recordings/akom/abc123def456/rx.mp3",
    "tx_path": "/data/recordings/akom/abc123def456/tx.mp3",
    "status": "done",
    "timestamp_created": "2026-07-27T14:35:42Z",
    "timestamp_transferred": "2026-07-27T14:35:52Z",
    "bytes_transferred": 245120,
    "sha256_rx": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "sha256_tx": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "attempts": 1,
    "last_error": null
  }
]
```

**Estrutura:** Array de objetos, cada um representa uma tentativa de transferência.

**Políticas:**
- Escrita: Após cópia bem-sucedida + checksum validado, marcar `status=done`
- Leitura: Ao iniciar worker, ler log, pular itens com `status=done`
- Limpeza: Ao finalizar worker, remover entradas com `status=done` + `timestamp_transferred < (agora - 7 dias)`
- Arquivo deletado antes de copiar: Remover entrada do log (cleanup cron já deletou)

### No Docker Volume (novo)

**Named volume `zenith-smb-logs`** para persistir `/data/smb_transfer_log.json` entre restarts do worker.

Configuração em `docker-compose.yml`:
```yaml
volumes:
  zenith-smb-logs:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: ./data/smb_logs
```

### No Storage Remoto (SMB)

**Estrutura de pastas criada pelo worker:**

```
\\192.168.50.240\backup$\Audios_Atendimento\
├── akom\                                      # tenant
│   ├── 2026-07-27\                            # YYYY-MM-DD
│   │   ├── 2026-07-27-14-35-42-abc123-1001-20991-rx.mp3
│   │   ├── 2026-07-27-14-35-42-abc123-1001-20991-tx.mp3
│   │   └── ...
│   ├── 2026-07-26\
│   └── ...
└── outro-tenant\
    ├── 2026-07-27\
    └── ...
```

**Nomeação padrão:** `{YYYY-MM-DD}-{HH}-{MM}-{SS}-{call_id}-{origem}-{destino}-{tx|rx}.mp3`

Exemplo: `2026-07-27-14-35-42-abc123-1001-20991-rx.mp3`
- Data: 2026-07-27
- Hora: 14:35:42
- call_id: abc123 (primeiros 6 caracteres para brevidade, completo em log local)
- Origem: 1001
- Destino: 20991
- Canal: rx (receive) ou tx (transmit)

### Índices / Constraints

Nenhum índice novo necessário. O log local é JSON plano (não há queryable structure).

## Migrações

**Nenhuma migração de banco de dados é necessária.** O worker cria a pasta `/data/smb_logs/` e o arquivo `smb_transfer_log.json` no primeiro ciclo.

### Inicialização do volume

1. Docker Compose cria named volume `zenith-smb-logs`
2. Container `zenith-smb-sync` monta em `/data/smb_logs`
3. Worker inicializa em `on_startup()`: 
   - Se `/data/smb_transfer_log.json` não existe, criar array `[]` (vazio)
   - Se existe, carregar e usar para resumir transferências pendentes

### Tamanho esperado

- 100 chamadas/dia × 2 arquivos (rx + tx) = 200 entradas
- Cada entrada: ~400 bytes JSON
- 200 entradas × 400 bytes = 80KB/dia
- Retenção: 7 dias → máximo 560KB
- Margem de segurança: 10MB volume suficiente

## Considerações de performance

- **Read on startup:** O(n) onde n = número de entradas pending. Típicamente < 100 (fila máxima > 100 = alerta).
- **Write on success:** O(1) append + rewrite (ou stream append se JSON streaming usado).
- **Cleanup:** O(n) scan, remove matched entries, rewrite.
- **Recomendação:** Implementar limpeza em thread separada ou cron job, não blocar worker principal.

## Backup e retenção

- **Volume local:** Persistido em Docker named volume. Backup via `docker volume inspect` ou incluído em snapshots host.
- **Storage remoto:** Já backupado pelo operador da máquina 192.168.50.240 (fora do escopo Zenith).
- **Retenção local:** 7 dias automático (cleanup).
- **Retenção remoto (SMB):** Indefinida (operador decide).

## Conformidade

- **LGPD:** Dados de voz são pessoais. Armazenamento remoto (SMB) deve estar em contrato de processamento com o cliente. Não é responsabilidade do Zenith verificar (contratos com clientes).
- **Auditoria:** Log local permite rastreabilidade completa (quando, quem, sucesso/falha). Registra tentativas de erro para investigação.
