# Data Delta: SMB Audio Backup

> Identificador: `011-smb-audio-backup`
> Data: `2026-07-27`

## PostgreSQL

Nenhuma migração. O modelo `Call` já contém:

| Campo | Uso novo |
|-------|----------|
| `started_at` | timestamp do nome/diretório remoto |
| `caller_number` | origem no nome remoto |
| `callee_number` | destino no nome remoto |

`create_call_record` passa a preencher os dois últimos campos a partir do evento ESL, mantendo fallback `desconhecido`.

## Filesystem local

### Estado existente preservado

```text
/data/recordings/{tenant}/{call_id}/
├── tx.mp3
└── rx.mp3
```

### Delta

```text
/data/recordings/{tenant}/{call_id}/
├── tx.mp3             # publicado por tx.tmp.mp3 → os.replace
├── rx.mp3             # publicado por rx.tmp.mp3 → os.replace
├── stereo.mp3         # transitório: left=tx, right=rx; publicação atômica
└── .smb-processing    # lease JSON UTC: expira em 120 s, renovado a cada 30 s
```

Arquivos `.raw` permanecem somente quando a conversão falha. O worker retenta a conversão antes de gerar o estéreo.

## Log persistente

Local: `/data/smb_logs/smb_transfer_log.json`, no volume `zenith_smb_logs`.

```json
[
  {
    "source_key": "akom/call-uuid",
    "tenant_id": "akom",
    "call_id": "call-uuid",
    "caller_number": "1001",
    "callee_number": "20991",
    "tx_path": "/data/recordings/akom/call-uuid/tx.mp3",
    "rx_path": "/data/recordings/akom/call-uuid/rx.mp3",
    "stereo_path": "/data/recordings/akom/call-uuid/stereo.mp3",
    "remote_dir": "akom/2026-07-27",
    "remote_name": "2026-07-27-14-35-42-call-u-1001-20991.mp3",
    "status": "pending",
    "attempts": 1,
    "sha256": null,
    "created_at": "2026-07-27T14:35:42Z",
    "transferred_at": null,
    "last_error": null
  }
]
```

### Estados

```text
pending → done
   │
   ├──→ pending  (falha recuperável)
   └──→ failed   (origem expirou ou configuração inválida)
```

- `done`: checksum validado; podar após 7 dias.
- `pending`: retentar no próximo ciclo.
- `failed`: manter 7 dias para auditoria e alerta.
- Escrita do JSON: arquivo temporário no mesmo diretório + `os.replace`.
- JSON vazio ou inválido: mover para nome diagnóstico timestampado, emitir log/métrica e iniciar estado vazio.
- Caminho canônico: `/data/smb_logs/smb_transfer_log.json`.

### Lease local

- Campos mínimos: `call_id`, `updated_at` UTC e `expires_at` UTC.
- Validade: 120 s; renovação pelo worker a cada 30 s.
- Lease ausente ou expirado não bloqueia cleanup.
- Lease inválido/corrompido é preservado para diagnóstico, tratado como expirado e gera alerta.

## Storage remoto

```text
\\{host}\{share}\{base_path}\
└── {tenant}\
    └── {YYYY-MM-DD}\
        └── {YYYY-MM-DD}-{HH}-{MM}-{SS}-{call_id[0:6]}-{origem}-{destino}.mp3
```

Cada arquivo tem dois canais: left=`tx`, right=`rx`.

## Volume Docker

Nome único: `zenith_smb_logs`.

```yaml
volumes:
  zenith_smb_logs:
```

Montagem: `/data/smb_logs`. O volume `zenith_recordings_tmpfs` é reutilizado pelo worker em leitura/escrita porque o worker produz `stereo.mp3` e pode retentar conversão.

## Constraints e idempotência

- Chave lógica: `tenant_id + call_id`.
- Destino existente com mesmo SHA256: sucesso idempotente.
- Destino existente com SHA256 divergente: colisão/erro; não sobrescrever silenciosamente.
- Na primeira colisão divergente, tentar uma vez o nome com sufixo `-{call_id[6:10]}`; se também divergir, falhar.
- `call_id[0:6]` não é chave primária; o log mantém UUID completo.
- Não há índice ou migration.

## Retenção

- Gravações mono: aproximadamente 2 h (`0.0833` dia).
- Estéreo local: somente até o checksum remoto ser confirmado; em falha, permanece para retry até o cleanup.
- Log `done`/`failed`: 7 dias.
- SMB remoto: política do operador, fora do Zenith.

## Delta planejado para recuperação dos gates

O banco atual não será alterado durante a preparação. O candidato será construído em volume novo:

| Objeto | Estado atual | Estado candidato |
|--------|--------------|------------------|
| `public.alembic_version` | ausente | revisão baseline pública |
| `public.tenants` | 1 linha | mesma linha e mesmo UUID |
| `public.pbxs` | 1 linha | mesma linha e mesmo UUID |
| `tenant_akom.calls` | 9 linhas | mesmas linhas e UUIDs |
| demais tabelas do tenant | vazias | criadas com tipos/constraints atuais |
| `tenant_test_schema` | schema vazio criado por teste | não migrado; testes passam a usar banco dedicado |

O dump validado é a fonte de restauração. O CSV privado continua sendo a fonte dos ramais
FreeSWITCH e não será incluído em specs, logs ou commits.

## LGPD

Voz e metadados pessoais permanecem na LAN, mas passam a existir em um segundo sistema. A ACL e a retenção remota precisam fazer parte do acordo operacional do cliente.
