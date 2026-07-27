# Roadmap: SMB Audio Backup para Auditoria

> Identificador: `011-smb-audio-backup`
> Data: `2026-07-27`
> Requirements: `_reversa_forward/011-smb-audio-backup/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

Criar um worker ARQ periódico isolado (`src/workers/smb_sync.py`) que, a cada 5-10 minutos, detecta áudios prontos em `/data/recordings/{tenant}/{call_id}/` (tmpfs, mantido pelo worker de gravação) e os copia para um storage externo SMB/CIFS em `\\192.168.50.240\backup$\Audios_Atendimento\{tenant}\{YYYY-MM-DD}\`. 

**Estratégia de confiabilidade:** A cópia é assíncrona, não bloqueante. Se SMB cai, o worker registra em arquivo local (`/data/smb_transfer_log.json`) quais arquivos estão pending, e retenta automaticamente a cada ciclo enquanto o arquivo não for deletado pela cleanup cron (até 2h de retenção). Throttling global de banda (padrão 5MB/s) protege a rede LAN compartilhada.

**Padrão de implementação:** Estende o mesmo padrão de Strategy (`src/services/base.py`) e workers ARQ (`src/workers/audio_uploader.py`) já usados para upload S3 e cleanup de áudio. Nenhuma mudança arquitetural é necessária.

## 2. Princípios aplicados

| Princípio | Como a feature se relaciona | Status |
|-----------|------------------------------|--------|
| Isolamento multi-tenant (schema-per-tenant) | Cópias organizadas por tenant first (`{tenant}/`), dados de cada cliente isolados no SMB | respeita |
| Desacoplamento via Strategy pattern | Worker usa `SMBBackupStrategy` (novo), segue mesmo padrão de S3 upload | respeita |
| Sem bloqueio da cadeia crítica | Execução em `asyncio.to_thread()`, falha de SMB não afeta gravação | respeita |
| Observabilidade via logs estruturados | Logs de sucesso/falha com call_id, tenant_id, latência, checksum | respeita |
| Dados sensíveis fora de logs | Credenciais SMB em `.env` gitignored, nunca em output/debug | respeita |

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|----------------|--------------------------|-------------|
| D-01 | Worker ARQ periódico (pull, 5-10min) vs. hook pós-gravação (push) | Pull é mais seguro: isolado, sem tocar código crítico de gravação. Push teria tocado `audio_uploader.py`, risco de regressão | Hook pós-gravação (push), mount SMB direto | 🟢 |
| D-02 | Registro persistente em arquivo local (`smb_transfer_log.json`) para retry automático | Rede LAN pode cair; sem registro, perdem-se áudios. Arquivo é resiliente (tmpfs + limpeza automática após 7 dias) | Apenas em-memória, banco de dados dedic | 🟢 |
| D-03 | Nomeação: `{YYYY-MM-DD}-{HH}-{MM}-{SS}-{call_id}-{origem}-{destino}-{tx\|rx}.mp3` | Ordena cronologicamente, facilita busca por período e ramal sem consultar BD | Usar apenas call_id, usar hash | 🟢 |
| D-04 | Throttling GLOBAL de banda (não por arquivo) | Múltiplos workers em paralelo podem somar; limite global protege a interface eth0 compartilhada | Limite por arquivo individual | 🟢 |
| D-05 | Checksum SHA256 pós-escrita, não durante | Simples, eficiente. Escrita atômica (temp→rename) garante arquivo completo antes da validação | Streaming checksum durante cópia | 🟢 |
| D-06 | Retry com exponential backoff (1s, 2s, 4s) + Circuit Breaker (5 falhas → sleep 5min) | Evita thrashing se SMB fica lento. Circuit Breaker reduz carga quando há falha persistente | Retry linear, sem circuit breaker | 🟢 |
| D-07 | Credenciais em `.env` (gitignored), não em Secret Manager | Sistema está em LAN privada (10.10.10.11 ↔ 192.168.50.240). Padrão já aplicado para S3 | Vault/K8s Secrets (overkill para LAN privada) | 🟡 |
| D-08 | Sem criptografia SMB (não forçar SMBv3) | Trafega em LAN privada (192.168.x.x). Criptografia adicionaria latência sem valor real | Forçar SMBv3 + TLS | 🟢 |
| D-09 | Estrutura pasta: `{tenant}/{YYYY-MM-DD}/` | Isolamento por cliente first, depois organização cronológica. Facilita limpeza e conformidade | Apenas `{YYYY-MM-DD}/`, sem tenant | 🟢 |

## 4. Premissas

Nenhuma premissa a partir de `[DÚVIDA]` — todos os pontos foram esclarecidos em sessão de `/reversa-clarify` (vide `requirements.md#9. Esclarecimentos`).

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-----------------|--------|
| Workers ARQ | `specs/workers/audio-upload/design.md` | componente-novo | Novo worker `SMBBackupStrategy` para cópia para SMB, seguindo padrão de `audio_uploader.py` / `audio_cleanup.py` (cron `arq`) |
| Docker Compose | `docker-compose.app.yml` (legado) | contrato-alterado | Novo service `smb-sync` (container `zenith-smb-sync`), volume `zenith_recordings_tmpfs` + novo named volume `zenith_smb_logs` para o log persistido |
| Environment | `.env.example` (legado) | contrato-novo | Variáveis `SMB_*` novas (ENABLED, HOST, SHARE, PATH, USERNAME, PASSWORD, BANDWIDTH_LIMIT_MBS, TRANSFER_LOG_PATH, SYNC_INTERVAL_MINUTES) |
| Configuration | `src/config.py` (legado) | regra-alterada | Adicionar `SMB_*` settings via `pydantic-settings`, ler de `.env`, default `SMB_ENABLED=False` |
| Monitoring | `src/utils/telemetry.py` (legado) | contrato-novo | 4 métricas Prometheus novas (smb_backup_success_total, failed_total, latency_seconds, queue_size), no mesmo arquivo de onde `audio_cleanup.py` já importa suas métricas |
| Persistência de chamada | `src/services/calls.py` + `src/telephony/esl_client.py` | regra-alterada | `caller_number`/`callee_number` passam a ser populados no `CHANNEL_ANSWER` — hoje as colunas existem em `Call` mas ficam sempre `NULL`, e sem elas a nomeação da RN-03 não tem fonte de dado |

## 6. Delta no modelo de dados

**Resumo:** Nenhuma mudança no schema do PostgreSQL (multi-tenant já existe). Nova estrutura é arquivo local (`/data/smb_transfer_log.json`) — não é banco de dados estruturado.

- **Arquivo local:** `/data/smb_transfer_log.json` contém array de objetos `{call_id, tenant_id, origem, destino, rx_path, tx_path, status, timestamp}`
- **Armazenamento:** Volume named em Docker Compose (persistido entre restarts do worker)
- **Limpeza:** Cron job no worker remove entradas com `status=done` após 7 dias
- **Detalhe completo:** `_reversa_forward/011-smb-audio-backup/data-delta.md`

## 7. Delta de contratos externos

| Contrato | Tipo | Arquivo de detalhe |
|----------|------|--------------------|
| SMB/CIFS | Arquivo (rede) | `_reversa_forward/011-smb-audio-backup/interfaces/smb.md` |

## 8. Plano de migração

1. **Preparação infra:** Provisionar share SMB em 192.168.50.240 (já existe), criar ACL para grupo `auditores` com READ-ONLY
2. **Código:** Implementar `src/workers/smb_sync.py` com `SMBBackupStrategy`, adicionar settings em `src/config.py`, criar métricas em `src/observability/metrics.py`
3. **Dependências:** Adicionar `pysmb` ou `smbclient` a `requirements.txt`
4. **Docker:** Novo service `zenith-smb-sync` em `docker-compose.yml`, volumes (tmpfs recordings + named volume log)
5. **Environment:** Adicionar 6 variáveis SMB_* ao `.env.example`
6. **Teste:** Validar cópia em < 30s, retry automático ao cair SMB, throttling com múltiplos workers
7. **Deploy:** Rolling restart de `zenith-smb-sync` (não afeta `zenith-api` nem `zenith-arq-uploader`)

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| SMB indisponível por tempo maior que a retenção do áudio | Perda de áudios não copiados | médio | Retenção real hoje é ~1h (`AUDIO_RETENTION_DAYS=0.0417` no `docker-compose.app.yml`) com cleanup a cada 15min; feature aumenta para ~2h (`0.0833`) para ampliar a janela de retry. Alertar se fila > 100 |
| `caller_number`/`callee_number` continuam `NULL` para chamadas antigas | Nomeação sem origem/destino em áudios já gravados | alto (para o histórico) | Fallback explícito no worker: mtime do arquivo para data/hora e literal `desconhecido` para ramal ausente — nunca falhar a cópia por metadado faltando |
| Rede degradada (SMB lento) | Worker timeout, retenções acumuladas | médio | Circuit Breaker aborta após 5 falhas; throttling protege interface eth0 |
| Auditoria tenta deletar arquivo no SMB | Comprometimento de prova | baixo | ACL READ-ONLY no servidor SMB (controle fora do código Zenith) |
| Múltiplos workers paralelos excedem throttle | Rede pico > limite | baixo | Throttling global (não por arquivo); monitor interface eth0 em produção |
| Log local (`smb_transfer_log.json`) fica enorme | Disk space issue no tmpfs | baixo | Limpeza automática após 7 dias; estimativa: 100 chamadas/dia × 3 semanas = máx 5MB |
| Checksum mismatch após cópia | Arquivo corrompido no SMB | muito baixo | Deletar arquivo SMB e retentar; log estruturado registra evento para investigação |

## 10. Critério de pronto

- [ ] `src/workers/smb_sync.py` implementado e testado (retry, throttle, checksum)
- [ ] `src/config.py` estendido com SMB_* settings (envvar binding)
- [ ] `src/observability/metrics.py` com 4 métricas Prometheus novas
- [ ] `docker-compose.yml` com novo service `zenith-smb-sync` + volumes
- [ ] `.env.example` atualizado com 6 variáveis SMB_*
- [ ] `requirements.txt` com `pysmb` ou `smbclient`
- [ ] Teste E2E: chamada real → arquivo no SMB em < 30s
- [ ] Teste de falha: SMB offline → retry automático ao voltar
- [ ] Teste de throttle: 3 workers paralelos + SMB_BANDWIDTH_LIMIT_MBS=5 → interface não excede 5MB/s
- [ ] Todas as ações em `actions.md` marcadas `[X]`
- [ ] `regression-watch.md` gerado (regredir se worker fica offline, se SMB cai, se throughput explode)
- [ ] (Recomendado) Re-extração reversa confirma sem regressão vermelha

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-07-27 | Versão inicial gerada por `/reversa-plan` | reversa |
