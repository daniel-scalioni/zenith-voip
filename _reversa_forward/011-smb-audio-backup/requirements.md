# Requirements: SMB Audio Backup para Auditoria

> Identificador: `011-smb-audio-backup`
> Data: `2026-07-27`
> Pasta da extração reversa: `specs/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

Copiar áudios de chamadas (rx.mp3 + tx.mp3) para um storage externo SMB/CIFS (\\192.168.50.240\backup$\Audios_Atendimento) logo após gravação, permitindo que equipe de auditoria acesse os dados **em paralelo** ao sistema Zenith, com retry automático quando a rede cai e throttling de banda para não degradar a LAN. Cada arquivo é nomeado com timestamp e origem/destino para facilitar buscas rápidas por período ou ramal.

## 2. Contexto a partir do legado

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `specs/architecture.md#Papel do FreeSWITCH` | FreeSWITCH é B2BUA — gravação de áudio já funciona ponta a ponta (validada em feature 010), áudios armazenados em `/data/recordings/{tenant}/{call_id}/` (tmpfs, 512MB, retenção ~2h) | 🟢 |
| `specs/workers/audio-upload/design.md` | Workers ARQ já executam tarefas assíncronas periódicas (upload S3, cleanup de áudio). Padrão de Strategy pattern para desacoplamento já existe em `src/services/base.py` | 🟢 |
| `specs/architecture.md#Stack Tecnológica` | Sistema usa Redis Streams para eventos, Docker Compose para orquestração, async/await com `asyncio.to_thread()` para I/O não-bloqueante | 🟢 |
| Feature 010 (record-real-call-audio-e2e) | Gravação E2E já validada em produção (2026-07-23). Áudios capturam voz real. Pré-requisito: retenção deve aumentar de ~1h para 2h para cobrir janela de retry | 🟢 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| Auditor (equipe externa) | Avaliar qualidade de atendimento em paralelo ao sistema de interfonia | Acessa via \\192.168.50.240 com permissão READ-ONLY, busca áudios por data e ramal (origem/destino), escuta conversa real para validar conformidade |
| Operador de QA | Investigar chamada com problema relatada pelo cliente | Busca por data-hora-origem-destino no share SMB, encontra arquivo em segundos (nomeação temporal facilita), baixa e reproduz para análise |
| Administrador de TI | Monitorar saúde da cópia de backup | Observa fila de pendentes (fila > 100 = alerta), latência média de cópia, status de falhas consecutivas via Prometheus |

## 4. Regras de negócio novas ou alteradas

1. **RN-01:** Todo áudio gravado deve ser copiado para o storage SMB dentro de 30 segundos após a conclusão da gravação, a menos que o SMB esteja indisponível (nesse caso, retentar automaticamente enquanto o arquivo permanecer em disk local). 🟢
   - Tipo: nova
   - Justificativa: Auditoria requer acesso "quase em tempo real" aos dados

2. **RN-02:** Áudios organizados por tenant (cliente) primeiro, depois por data (YYYY-MM-DD), facilitando isolamento de dados multi-tenant e buscas por período. 🟢
   - Tipo: nova
   - Justificativa: Clientes diferentes devem ter acesso apenas aos seus áudios

3. **RN-03:** Nomeação de arquivo inclui timestamp até segundos + call_id + origem + destino, permitindo ordenação cronológica e identificação rápida do ramal + destino da chamada sem consultar banco de dados. 🟢
   - Tipo: nova
   - Formato: `{YYYY-MM-DD}-{HH}-{MM}-{SS}-{call_id}-{origem}-{destino}-{tx|rx}.mp3`

4. **RN-04:** Se conexão SMB cair durante cópia, a operação aborta com graceful retry; arquivo entra em fila de pendentes e será retentado a cada rodada do worker (5-10min) enquanto o arquivo não for deletado (até 2h de retenção local). 🟡
   - Tipo: nova
   - Justificativa: Rede LAN é instável; retentar sem bloquear é estratégia apropriada

5. **RN-05:** Cópia para SMB **não bloqueia** fluxo principal de gravação; execução é assíncrona via worker ARQ em thread separada (`asyncio.to_thread()`). 🟢
   - Tipo: nova
   - Justificativa: Falha de SMB não deve degradar disponibilidade de gravação

6. **RN-06:** Bandwidth utilizado na cópia não deve exceder limite configurável (padrão: 5MB/s) para evitar degradação da rede LAN compartilhada. 🟡
   - Tipo: nova
   - Justificativa: Rede é compartilhada; throttling protege contra DoS acidental

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| RF-01 | Detectar arquivo MP3 pronto em `/data/recordings/{tenant}/{call_id}/` (rx.mp3 ou tx.mp3) e copiar para `\\192.168.50.240\backup$\Audios_Atendimento\{tenant}\{YYYY-MM-DD}\{YYYY-MM-DD}-{HH}-{MM}-{SS}-{call_id}-{origem}-{destino}-{tx\|rx}.mp3` | Must | Worker inicia a cada 5-10min, detecta novos .mp3 em tmpfs, copia com nomeação correta para SMB em < 30s por arquivo (latência média) | 🟢 |
| RF-02 | Registrar em arquivo de log local (`/data/smb_transfer_log.json`) quais arquivos foram transferidos com sucesso, para evitar retransferência e possibilitar recuperação automática se SMB cai | Must | Log contém call_id, tenant_id, origem, destino, rx_path, tx_path, status (done\|pending), timestamp. Ao reiniciar worker, pula itens com status=done | 🟢 |
| RF-03 | Se SMB está indisponível, enfileirar arquivo como pending e retentar automaticamente a cada ciclo do worker (5-10min) enquanto arquivo não for deletado | Must | Simular queda de SMB (`ifdown` ou firewall bloqueado), verificar que worker não gera exceção, tenta novamente próximo ciclo | 🟡 |
| RF-04 | Implementar retry com exponential backoff (1s, 2s, 4s) + Circuit Breaker (5 falhas consecutivas → sleep 5min) para evitar thrashing se SMB fica lento | Must | Cada retry marcado em log com timestamp. Circuit Breaker evita tentativas em série rápida | 🟢 |
| RF-05 | Validar integridade do arquivo copiado via checksum SHA256: comparar hash do arquivo original vs. arquivo no SMB, deletar se mismatch | Must | Checksum calculado pós-escrita, comparado, erro registrado com sugestão de retransferência | 🟢 |
| RF-06 | Aplicar throttling de banda GLOBAL: ler credencial `SMB_BANDWIDTH_LIMIT_MBS` do `.env` (padrão 5MB/s), limitar throughput total de cópia (somando todos os workers em paralelo) a esse valor | Must | Monitorar interface eth0 durante cópia (com múltiplos workers simultâneos), verificar que tráfego total não excede limite. Teste: 3 workers paralelos com 1MB/s limit cada = máximo 5MB/s na interface | 🟢 |
| RF-07 | Permitir equipe de auditoria acessar o share SMB com permissão READ-ONLY, sem poder modificar/deletar arquivos | Must | Configurar ACL do servidor SMB: grupo `auditores` tem Read-only na pasta `/Audios_Atendimento`. Teste: tentar `rm` com conta auditoria, deve falhar | 🟢 |
| RF-08 | Limpeza automática: remover entradas do log com status=done após 7 dias de sucesso (mantém log finito) | Should | Log não cresce indefinidamente. Script de limpeza roda ao iniciar worker | 🟢 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| Desempenho | Latência média de cópia: < 30s por arquivo (assumindo arquivo ~2-3MB, rede LAN local 100Mbps) | Contrato de RNF: auditoria requer acesso "quase em tempo real" | 🟡 |
| Desempenho | Worker inicia a cada 5-10min para balancear freshness vs. carga. Timeout global do worker: 60s (abortando se SMB fica preso) | Evita accumulation de tasks se SMB lento | 🟢 |
| Confiabilidade | Falha de SMB não deve impedir gravação local em `/data/recordings/`. Gravação é operação crítica; cópia é best-effort | Padrão: separar crítico (gravação) de best-effort (backup remoto) | 🟢 |
| Segurança | Credenciais SMB (username, password) armazenadas em `.env` (gitignored), NUNCA em código ou logs. Senhas nunca aparecem em debug output | Padrão já aplicado em projeto para S3, esticado para SMB | 🟢 |
| Segurança | Credenciais de acesso ao SMB (username, password) nunca aparecem em logs ou debug output. SMB trafega em LAN privada (192.168.x.x), criptografia não é necessária | Padrão de segurança: dados sensíveis em rede privada sem exposição pública | 🟢 |
| Observabilidade | Logs estruturados com timestamp, call_id, tenant_id, status (success\|fail), bytes transferidos, latency_ms. Um log por operação | Rastreabilidade: auditor consegue justificar "quando copiou este arquivo?" | 🟢 |
| Observabilidade | Métricas Prometheus: `smb_backup_success_total`, `smb_backup_failed_total`, `smb_backup_latency_seconds`, `smb_backup_queue_size`. Alertas: fila > 100, latência > 10s, falha consecutiva > 5 | Monitoramento contínuo: oncall consegue detectar degradação de backup | 🟡 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Áudio gravado é copiado automaticamente para SMB em tempo aceitável
  Dado uma chamada concluída com arquivos rx.mp3 + tx.mp3 em /data/recordings/akom/{call_id}/
  E SMB está online e acessível
  E worker SMB está rodando (executando a cada 5-10min)
  Quando o worker inicia seu ciclo de sincronização
  Então ambos os arquivos (rx.mp3 + tx.mp3) aparecem em \\192.168.50.240\backup$\Audios_Atendimento\akom\{YYYY-MM-DD}\
  E nomeação respeita {YYYY-MM-DD}-{HH}-{MM}-{SS}-{call_id}-{origem}-{destino}-{tx|rx}.mp3
  E checksum SHA256 dos arquivos no SMB coincide com origem
  E latência total < 30s

Cenário: SMB fica indisponível, worker retenta automaticamente
  Dado uma chamada concluída com rx.mp3 + tx.mp3
  E SMB está OFFLINE (firewall bloqueia porta 445, ou servidor desligado)
  Quando worker tenta copiar
  Então worker registra erro em /data/smb_transfer_log.json com status=pending
  E não trava nem gera exceção não-tratada
  Quando SMB volta online
  E worker inicia novo ciclo
  Então arquivo é retentado automaticamente, eventual sucesso registrado com status=done

Cenário: Auditoria acessa arquivos com permissão READ-ONLY
  Dado que equipe de auditoria tem credenciais SMB com acesso ao share
  Quando eles acessam \\192.168.50.240\backup$\Audios_Atendimento\akom\2026-07-27\
  Então conseguem ler, baixar e reproduzir arquivos
  E NÃO conseguem deletar, renomear ou modificar nenhum arquivo (permissão negada)

Cenário: Throttling de banda protege a rede
  Dado SMB_BANDWIDTH_LIMIT_MBS=1 no .env (1MB/s limit)
  Quando worker copia arquivo de 10MB
  Então tempo de cópia é aprox. 10 segundos (não menos, devido ao throttle)
  E interface eth0 não mostra tráfego > 1.2MB/s (margem de segurança)

Cenário: Arquivo deletado localmente antes de copiar é pulado gracefully
  Dado /data/recordings/akom/{call_id}/rx.mp3 foi deletado pelo cleanup cron
  E smb_transfer_log.json tem entrada status=pending para esse arquivo
  Quando worker tenta acessar o arquivo para copiar
  Então registra "arquivo já deletado, pulando" em log
  E remove entrada de smb_transfer_log.json
  E não gera erro
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|---------------|
| RF-01 (cópia básica) | Must | Objetivo principal da feature: fazer cópia chegar ao SMB |
| RF-02 (registro em log local) | Must | Sem log, não há retry automático em caso de falha |
| RF-03 (retry se SMB cai) | Must | Rede LAN é instável; sem retry, perde dados |
| RF-04 (exponential backoff + circuit breaker) | Must | Sem isso, thrashing na rede se SMB lento |
| RF-05 (checksum) | Must | Sem validação, auditoria não confia nos dados |
| RF-06 (throttling global) | Must | Protege rede compartilhada da degradação de banda (múltiplos workers paralelos) |
| RF-07 (READ-ONLY auditoria) | Must | Segurança crítica: auditoria não pode deletar provas |
| RF-08 (limpeza de log) | Should | Housekeeping, evita crescimento infinito de log |
| RNF Desempenho (< 30s) | Should | Meta de latência, não bloqueador |
| RNF Segurança (credenciais isoladas) | Must | Credenciais não em logs, LAN privada não requer crypto |
| RNF Observabilidade (métricas Prometheus) | Should | Monitoramento, facilita debug futuro |

## 9. Esclarecimentos

**Sessão 1 (2026-07-27):**
- **RF-07 (ACL):** Confirmado — READ-ONLY do servidor SMB é para a equipe de auditoria (destino), não origem. Dados locais acessíveis via tmpfs no mesmo servidor.
- **Criptografia SMB:** Removida — trafega em LAN privada (192.168.x.x), criptografia desnecessária.
- **RF-06 (Throttling):** Refinado como GLOBAL (soma de todos os workers), não por arquivo.

Resultado: **0 [DÚVIDA] pendentes.** Requirements pronto para plano.

## 10. Lacunas

Nenhuma lacuna pendente. Todos os pontos foram esclarecidos:

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-07-27 | Esclarecimentos: RF-07 confirmada (ACL no servidor SMB), criptografia removida (LAN privada), RF-06 refinado como throttling global. 0 [DÚVIDA] pendentes | daniel.scalioni |
| 2026-07-27 | Versão inicial gerada por `/reversa-requirements` a partir de especificação validada via `/brainstorming-multiagent` | reversa |
