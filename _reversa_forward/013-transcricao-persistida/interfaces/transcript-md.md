# Interface: Arquivo `.md` de transcrição no SMB

> Identificador: `013-transcricao-persistida`
> Tipo: Arquivo de rede (reaproveita a mesma interface SMB de `011-smb-audio-backup`)
> Data: `2026-08-12`

## Endpoint lógico

```text
\\{SMB_HOST}\{SMB_SHARE}\{SMB_PATH}\
└── {tenant}\
    └── {YYYY-MM-DD}\
        ├── {YYYY-MM-DD}-{HH}-{MM}-{SS}-{call_id[0:6]}-{origem}-{destino}.mp3   (já existe, feature 011)
        └── {YYYY-MM-DD}-{HH}-{MM}-{SS}-{call_id[0:6]}-{origem}-{destino}.md   (novo, esta feature)
```

Mesmo nome-base do `.mp3` correspondente, mesma pasta, só troca a extensão (RN-03). Gerado por
`build_remote_directory`/`build_remote_name` (`src/workers/smb_sync.py`, reaproveitados sem
alteração — D-08).

## Configuração

Reaproveita integralmente as variáveis `SMB_*` já documentadas em
`_reversa_forward/011-smb-audio-backup/interfaces/smb.md#Configuração`. Nenhuma variável nova.

## Formato do conteúdo

```markdown
# Transcrição — {call_id}

> Tenant: {tenant} · Data: {YYYY-MM-DD HH:MM:SS} · Origem: {caller} → Destino: {callee}

[00:00:00.000 → 00:00:02.340] **Atendente** (confidence: 0.94)
Zenith Portaria, bom dia.

[00:00:02.500 → 00:00:05.120] **Cliente** (confidence: 0.88)
Bom dia, aqui é da unidade 302.
```

- Segmentos ordenados por `start_time` (intercalando `tx`/`rx` conforme a ordem real da conversa).
- Falante rotulado conforme RN-01: `tx`→"Atendente", `rx`→"Cliente".
- Timestamp `[início → fim]` e `confidence` por segmento — decisão de `/reversa-clarify` (RF-03),
  no mesmo espírito incremental/timestampado da skill do projeto `audio-transcript-long`.
- Segmento sem fala detectada (silêncio) não gera linha.

## Operações

Mesma matriz de permissões já documentada em `011-smb-audio-backup/interfaces/smb.md#Operações` —
o `.md` usa a mesma conta técnica e a mesma conexão `SMBConnection` do `.mp3`, sem escopo de
acesso adicional.

## Idempotência

Reprocessamento do mesmo `call_id` (RF-05) sobrescreve o `.md` existente por completo (upload com
checksum, mesmo padrão do `.mp3` em `011`) — nunca faz append parcial.

## Falhas

Falha na geração ou upload do `.md` é logada em log estruturado por `call_id` (RNF de
Observabilidade, `requirements.md#6`) e não impede nem atrasa a gravação, o upload do `.mp3` nem
o backup SMB (RN-04). O job de transcrição é retentado no próximo ciclo do worker
`arq-transcript` (D-01), mesma semântica de retry já usada por `arq-smb-sync`.
