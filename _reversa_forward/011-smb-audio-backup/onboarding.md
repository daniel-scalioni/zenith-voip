# Onboarding: SMB Audio Backup

> Identificador: `011-smb-audio-backup`
> Data: `2026-07-27`
> Público: QA / Desenvolvedor testando a feature pela primeira vez

## Pré-requisitos

1. ✅ Ambiente Docker Compose rodando (10.10.10.11)
2. ✅ Chamadas reais sendo gravadas em `/data/recordings/` (feature 010 ativa)
3. ✅ Server SMB acessível em 192.168.50.240 com share `backup$` criado
4. ✅ Credenciais SMB válidas (username `zenith_backup`, password X)

## Passo 1: Configurar credenciais

```bash
# No arquivo .env do projeto (gitignored):
SMB_HOST=192.168.50.240
SMB_SHARE=backup$
SMB_PATH=Audios_Atendimento
SMB_USERNAME=zenith_backup
SMB_PASSWORD=<seu_password_aqui>
SMB_BANDWIDTH_LIMIT_MBS=5
```

**Verificação:** Salvar e fazer:
```bash
docker-compose config | grep SMB_
# Deve listar as 6 variáveis
```

## Passo 2: Iniciar o worker

```bash
# No servidor 10.10.10.11
docker-compose up -d zenith-smb-sync

# Verificar logs
docker-compose logs -f zenith-smb-sync
# Esperado: "Worker SMB iniciado", "Conectado ao SMB"
```

## Passo 3: Originar uma chamada real

Do ramal 1001 (3CXPhone ou softphone local), discar para um destino no VitalPBX:
- Destino: 20991 (ou ramal que atenda)
- Duração: ~30 segundos de conversa
- Encerrar a chamada

**Verificação nos logs do worker:**
```
2026-07-27T14:35:50.000Z [INFO] Detectado rx.mp3 em /data/recordings/akom/abc123/
2026-07-27T14:35:52.000Z [INFO] Cópia concluída em 2s, checksum OK
2026-07-27T14:35:53.000Z [INFO] Entrada no log: status=done
```

## Passo 4: Verificar arquivo no SMB

**Via Windows Explorer ou terminal Linux:**
```bash
# Terminal (Linux com cifs-utils instalado):
sudo mount -t cifs -o username=zenith_backup //192.168.50.240/backup$ /mnt/test
ls -la /mnt/test/Audios_Atendimento/akom/2026-07-27/
# Esperado: 2 arquivos
#  2026-07-27-14-35-42-abc123-1001-20991-rx.mp3
#  2026-07-27-14-35-42-abc123-1001-20991-tx.mp3
```

**Ou Windows Explorer:**
- Conectar a \\192.168.50.240\backup$
- Navegar até Audios_Atendimento/akom/2026-07-27/
- Ver os 2 arquivos

## Passo 5: Validar checksum

```bash
# No servidor 10.10.10.11, verificar log local:
cat /data/smb_logs/smb_transfer_log.json | jq '.[0]'

# Esperado: status=done, sha256_rx e sha256_tx preenchidos
{
  "call_id": "abc123...",
  "status": "done",
  "sha256_rx": "e3b0c4...",
  "sha256_tx": "e3b0c4..."
}
```

## Passo 6: Testar retry (SMB offline)

```bash
# 1. Simular SMB offline
sudo iptables -A OUTPUT -d 192.168.50.240 -j DROP

# 2. Originar nova chamada
# (Ramal 1001 → 20991, ~30s)

# 3. Verificar logs do worker
docker-compose logs zenith-smb-sync
# Esperado: "Conexão falhou", "Arquivo enfileirado como pending"

# 4. Remover bloqueio
sudo iptables -D OUTPUT -d 192.168.50.240 -j DROP

# 5. Esperar próximo ciclo do worker (5-10min)
# Ou forçar: docker-compose exec zenith-smb-sync trigger_sync

# 6. Verificar retry bem-sucedido
docker-compose logs zenith-smb-sync | grep "retry.*success"
```

## Passo 7: Testar throttling

```bash
# 1. No .env, ajustar limit baixo:
SMB_BANDWIDTH_LIMIT_MBS=1

# 2. docker-compose restart zenith-smb-sync

# 3. Originar 3+ chamadas em paralelo (3 softwares 3CX ao mesmo tempo)

# 4. Monitorar tráfego no servidor:
iftop -n
# Ou
sar -n DEV 1
# Esperado: tráfego SMB nunca excede ~1.2MB/s (margem de segurança)

# 5. Verificar latência de cópia aumentada (proporcional ao limite):
cat /data/smb_logs/smb_transfer_log.json | jq '.[] | .bytes_transferred, .timestamp_transferred'
```

## Passo 8: Testar arquivo deletado antes de copiar

```bash
# 1. Originar uma chamada curta (10s, feche rápido)

# 2. Monitorar: Assim que rx.mp3 + tx.mp3 aparecerem em /data/recordings/akom/{call_id}/
#    E antes do worker copiar, simule delete manual:
rm /data/recordings/akom/{call_id}/*.mp3

# 3. Verificar logs:
docker-compose logs zenith-smb-sync | grep "já deletado"
# Esperado: "arquivo já deletado, pulando, removido do log"
```

## Troubleshooting

| Sintoma | Diagnóstico | Solução |
|---------|-----------|---------|
| Worker não inicia | `docker-compose logs zenith-smb-sync` mostra erro de import | Verificar `requirements.txt` tem `pysmb` ou `smbclient` |
| "Conexão recusada" ao SMB | Firewall/Network | `telnet 192.168.50.240 445` deve conectar |
| Checksum mismatch | Arquivo corrupto em trânsito | Retentar (próximo ciclo), investigar packet loss |
| Fila > 100 | SMB sobrecarregado ou offline | Monitorar 192.168.50.240, aumentar SMB_BANDWIDTH_LIMIT_MBS? |
| Arquivo aparece em SMB mas metadata errado | Parsing de call_id/origem/destino | Verificar nomeação vs. requirements.md#RN-03 |

## Métricas esperadas

```bash
# Via Prometheus (se configurado):
curl http://localhost:9090/metrics | grep smb_backup

# Esperado:
smb_backup_success_total{tenant="akom"} 5
smb_backup_failed_total{tenant="akom"} 0
smb_backup_latency_seconds_bucket{le="5"} 3
smb_backup_queue_size 0
```

## Checklist de aceitação

- [ ] Worker `zenith-smb-sync` rodando sem erro
- [ ] Chamada real 1001 → 20991 gera 2 arquivos no SMB em < 30s
- [ ] Nomeação dos arquivos segue `{YYYY-MM-DD}-{HH}-{MM}-{SS}-{call_id}-{origem}-{destino}-{tx|rx}.mp3`
- [ ] Checksum validado (SHA256 match local vs. SMB)
- [ ] Retry automático funciona (SMB offline → reatentativa ao voltar)
- [ ] Throttling global (múltiplos workers não excedem 5MB/s)
- [ ] Arquivo deletado antes de copiar é pulado gracefully
- [ ] Auditoria consegue acessar (READ-ONLY) via \\192.168.50.240\backup$
- [ ] Métricas Prometheus alimentadas

## Próximas sessões

Se tudo passou, feature está pronta para merge. Se houver falhas, abrir issue com:
1. Logs do worker (`docker-compose logs zenith-smb-sync`)
2. Verificação de connecção SMB (`telnet 192.168.50.240 445`)
3. Snapshots do `/data/smb_logs/smb_transfer_log.json`
