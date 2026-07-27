# Investigation: SMB Audio Backup

> Identificador: `011-smb-audio-backup`
> Data: `2026-07-27`

## Pesquisa de fundo

### Caso de uso: Auditoria paralela
- Equipe de auditoria externa precisa acessar áudios de chamadas sem permissão de escrita
- Dados sensíveis (voz de clientes), acesso READ-ONLY é crítico
- Busca rápida por período/ramal esperada (nomeação cronológica facilita)

### Padrão de workers ARQ já existente
Projeto já usa `src/workers/audio_uploader.py` para upload assíncrono a S3. Padrão aplicável:
- Lê arquivos do tmpfs (retenção ~2h)
- Executa em thread separada via `asyncio.to_thread()` (não bloqueante)
- Loga sucesso/falha com timestamp
- Retry com backoff se falha
- Integra com Redis Streams para notificações

### Protocolos SMB/CIFS em LAN privada
- SMB é protocolo legado (Windows), adequado para file sharing em LAN
- Criptografia (SMBv3 + TLS) é overhead em LAN privada 192.168.x.x
- Bibliotecas Python: `pysmb` (pure Python) vs. `smbclient` (binding de libsmb)
  - `pysmb`: Mais portável, sem dependência de C
  - `smbclient`: Mais rápido, requer libsmb do SO
- Escolha: `pysmb` para portabilidade em Docker

### Throttling de banda em multi-worker
- Múltiplos workers ARQ em paralelo podem somar throughput
- Limite por arquivo não funciona (soma pode explodir)
- Solução: Tracker global de bytes/segundo em Redis, cada worker consulta antes de ler chunk
- Alternativa mais simples: `time.sleep()` calculado após ler 512KB

### Referências externas
- SMB protocol spec: [MS-SMB2](https://docs.microsoft.com/en-us/openspecs/windows_protocols/ms-smb2)
- pysmb docs: https://pysmb.readthedocs.io/
- Zenith workers: `specs/workers/audio-upload/design.md`

## Alternativas avaliadas

| Alternativa | Vantagem | Desvantagem | Escolha |
|-------------|----------|------------|---------|
| Worker ARQ pull (5-10min) | Isolado, seguro, sem bloqueio | Pequena janela se SMB lento | ✅ Escolhida |
| Hook pós-gravação (push) | Imediato | Toca `audio_uploader.py`, risco regressão | ❌ Rejeitada |
| Mount SMB direto | Transparente, sem retry | Requer CAP_SYS_ADMIN, pode congelar se rede falha | ❌ Rejeitada |
| S3 em vez de SMB | Mais seguro, escalável | Fora do scope (já existe upload S3, auditoria quer SMB/CIFS no servidor local) | ❌ Rejeitada |
| Criptografia SMBv3 forçada | Compliance de segurança | LAN privada, latência extra desnecessária | ❌ Rejeitada |
| Secret Manager para credenciais | Segurança máxima | Overkill para LAN privada, já usa `.env` para S3 | ❌ Rejeitada |

## Padrões aplicáveis

1. **Strategy pattern** (`src/services/base.py`): `SMBBackupStrategy` segue estrutura de `S3UploadStrategy`, interface uniforme
2. **Circuit Breaker**: `tenacity` library com `stop_after_attempt(5)` + `wait_exponential()` já usada em código
3. **Retry com backoff**: Mesmo padrão de `audio_uploader.py`
4. **Estrutura de logs**: JSON estruturado com timestamp, call_id, tenant_id (existing pattern)
5. **Prometheus metrics**: `smb_backup_success_total`, `failed_total`, `latency_seconds`, `queue_size` (follow Zenith conventions)

## Decisões não óbvias

1. **Por que arquivo local em vez de BD?** 
   - `/data/smb_transfer_log.json` é simples, auto-limpável, não depende de PostgreSQL. Reduz complessidade.

2. **Por que throttling global e não por arquivo?**
   - Múltiplos workers rodando. Limite individual não previne soma explosão na interface eth0 compartilhada.

3. **Por que nomeação inclui origem-destino se já tem call_id?**
   - call_id é UUID opaco. Auditoria quer "rápido, achei a chamada entre 1001 e 20991 em 2026-07-27 às 14:35".

4. **Por que não cifrar em transit?**
   - Rede 192.168.x.x é privada, interna. Adiciona latência. Compliance não exige (SMB em LAN privada é padrão).

## Fontes consultadas

- `specs/architecture.md#Stack Tecnológica` (Redis Streams, asyncio)
- `specs/workers/audio-upload/design.md` (padrão de worker ARQ)
- `specs/adrs/001-multitenancy-schema-per-tenant.md` (isolamento multi-tenant)
- Feature 010 completion (áudios funcionando ponta a ponta, 2h retenção tmpfs)
- Brainstorming-multiagent 2026-07-26 (pragmatismo MIMO, segurança Gemini)
