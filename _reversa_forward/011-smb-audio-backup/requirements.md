# Requirements: SMB Audio Backup para Auditoria

> Identificador: `011-smb-audio-backup`
> Data: `2026-07-27`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

Copiar o áudio de cada chamada para um storage externo SMB/CIFS (\\192.168.50.240\backup$\Audios_Atendimento) como **um único MP3 estéreo**, com `tx` e `rx` em canais separados para permitir extração posterior, permitindo que a equipe de auditoria acesse os dados **em paralelo** ao sistema Zenith. A cópia usa retry automático quando a rede cai e throttling de banda para não degradar a LAN. Cada arquivo é nomeado com timestamp, os 6 primeiros caracteres do `call_id` e origem/destino para facilitar buscas rápidas por período ou ramal.

## 2. Contexto a partir do legado

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `_reversa_sdd/architecture.md#Papel do FreeSWITCH` | FreeSWITCH é B2BUA — gravação de áudio já funciona ponta a ponta (validada em feature 010), áudios armazenados em `/data/recordings/{tenant}/{call_id}/` (tmpfs, 512MB, retenção ~2h) | 🟢 |
| `_reversa_sdd/workers/audio-upload/design.md` | Workers ARQ já executam tarefas assíncronas periódicas. O padrão Strategy para desacoplamento já existe em `src/services/base.py`; a integração S3 anterior foi removida | 🟢 |
| `_reversa_sdd/architecture.md#Stack Tecnológica` | Sistema usa Redis Streams para eventos, Docker Compose para orquestração, async/await com `asyncio.to_thread()` para I/O não-bloqueante | 🟢 |
| Feature 010 (record-real-call-audio-e2e) | Gravação E2E já validada em produção (2026-07-23). Áudios capturam voz real. Pré-requisito: retenção deve aumentar de ~1h para 2h para cobrir janela de retry | 🟢 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| Auditor (equipe externa) | Avaliar qualidade de atendimento em paralelo ao sistema de interfonia | Acessa via \\192.168.50.240 com permissão READ-ONLY, busca áudios por data e ramal (origem/destino), escuta conversa real para validar conformidade |
| Operador de QA | Investigar chamada com problema relatada pelo cliente | Busca por data-hora-origem-destino no share SMB, encontra arquivo em segundos (nomeação temporal facilita), baixa e reproduz para análise |
| Administrador de TI | Monitorar saúde da cópia de backup | Observa fila de pendentes (fila > 100 = alerta), latência média de cópia, status de falhas consecutivas via Prometheus |

## 4. Regras de negócio novas ou alteradas

1. **RN-01:** Todo áudio gravado deve ser disponibilizado no storage SMB em até 5 minutos de espera pelo ciclo do worker mais 30 segundos para a operação de cópia, a menos que o SMB esteja indisponível (nesse caso, retentar automaticamente enquanto o arquivo permanecer em disco local). 🟢
   - Tipo: nova
   - Justificativa: Auditoria requer acesso "quase em tempo real" aos dados

2. **RN-02:** Áudios organizados por tenant (cliente) primeiro, depois por data (YYYY-MM-DD), facilitando isolamento de dados multi-tenant e buscas por período. 🟢
   - Tipo: nova
   - Justificativa: Clientes diferentes devem ter acesso apenas aos seus áudios

3. **RN-03:** Nomeação de arquivo inclui timestamp até segundos + os 6 primeiros caracteres do `call_id` + origem + destino, permitindo ordenação cronológica e identificação rápida do ramal + destino da chamada sem consultar banco de dados. O arquivo remoto é único e estéreo: canal esquerdo `tx` (agente) e canal direito `rx` (cliente), preservando separação posterior. 🟢
   - Tipo: nova
   - Formato: `{YYYY-MM-DD}-{HH}-{MM}-{SS}-{call_id[0:6]}-{origem}-{destino}.mp3`

4. **RN-04:** Se a conexão SMB cair durante a cópia, a operação aborta com graceful retry; o arquivo entra em fila de pendentes e será retentado a cada rodada do worker (5min) enquanto não for deletado localmente (até 2h de retenção). 🟢
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
| RF-01 | Detectar o par `tx.mp3` + `rx.mp3` pronto em `/data/recordings/{tenant}/{call_id}/`, combiná-lo em um único MP3 estéreo e copiar para `\\192.168.50.240\backup$\Audios_Atendimento\{tenant}\{YYYY-MM-DD}\{YYYY-MM-DD}-{HH}-{MM}-{SS}-{call_id[0:6]}-{origem}-{destino}.mp3` | Must | Worker inicia a cada 5min, detecta o par pronto em tmpfs e disponibiliza o arquivo estéreo em até 5min + 30s de cópia | 🟢 |
| RF-02 | Registrar em arquivo de log persistente (`/data/smb_logs/smb_transfer_log.json`) o estado das transferências, para evitar retransferência e possibilitar recuperação automática se SMB cai | Must | Log contém call_id, tenant_id, origem, destino, rx_path, tx_path, status (`pending`\|`done`\|`failed`) e timestamp. Ao reiniciar, pula itens `done`, retenta `pending` e preserva `failed` para auditoria | 🟢 |
| RF-03 | Se SMB está indisponível, enfileirar arquivo como pending e retentar automaticamente a cada ciclo do worker (5min) enquanto arquivo não for deletado | Must | Simular queda de SMB (`ifdown` ou firewall bloqueado), verificar que worker não gera exceção, tenta novamente no próximo ciclo | 🟢 |
| RF-04 | Implementar retry com exponential backoff (1s, 2s, 4s) + Circuit Breaker (5 falhas consecutivas → sleep 5min) para evitar thrashing se SMB fica lento | Must | Cada retry marcado em log com timestamp. Circuit Breaker evita tentativas em série rápida | 🟢 |
| RF-05 | Validar integridade do MP3 estéreo copiado via checksum SHA256: comparar o hash do artefato estéreo local temporário com o arquivo no SMB e deletar o remoto se houver divergência | Must | Checksum calculado pós-escrita, comparado, erro registrado com sugestão de retransferência | 🟢 |
| RF-06 | Aplicar throttling de banda compartilhado por todas as cópias do único processo `zenith-smb-sync`: ler `SMB_BANDWIDTH_LIMIT_MBS` do `.env` (padrão 5MB/s) e enviar chunks por `storeFileFromOffset`, com offset crescente e truncagem somente no primeiro chunk | Must | Com uma única réplica e limite de 1MB/s, medir throughput dentro da margem; falha entre chunks é retomada sem duplicar/corromper bytes. Escala horizontal exige nova decisão arquitetural | 🟢 |
| RF-07 | Permitir equipe de auditoria acessar o share SMB com permissão READ-ONLY, sem poder modificar/deletar arquivos | Must | Configurar ACL do servidor SMB: grupo `auditores` tem Read-only na pasta `/Audios_Atendimento`. Teste: tentar `rm` com conta auditoria, deve falhar | 🟢 |
| RF-08 | Limpeza automática: remover entradas do log com status=done após 7 dias e recuperar de arquivo vazio/JSON corrompido sem perder silenciosamente o último estado válido | Should | Log não cresce indefinidamente; corrupção é isolada para diagnóstico e o worker continua em modo seguro | 🟢 |
| RF-09 | Só considerar a gravação pronta após o produtor concluir `tx.mp3` e `rx.mp3` por rename atômico; se a conversão para MP3 falhar e restar `.raw`, retentar a conversão e emitir alerta enquanto a chamada não estiver apta ao backup | Must | O worker nunca copia arquivo ainda em escrita; falha de conversão permanece visível e é retentada até sucesso ou expiração da retenção local | 🟢 |
| RF-10 | Antes do E2E, configurar manualmente o `.env` privado do deploy com endpoint SMB e credencial da conta técnica WRITE; a credencial READ-ONLY dos auditores permanece separada e fora do Zenith | Must | `.env` contém host, porta, modo Direct TCP, nomes NetBIOS, share, path, usuário e senha técnica; `.env.example` contém somente placeholders; nenhum segredo aparece em Git, specs ou logs | 🟢 |
| RF-11 | Impedir sobreposição de ciclos do cron e proteger uma chamada em processamento contra o cleanup por lease UTC de 120 s, renovado a cada 30 s | Must | Segundo ciclo retorna `already_running`; cleanup ignora lease válido; lease expirado, inválido ou corrompido volta a ser elegível e gera alerta | 🟢 |
| RF-12 | Após checksum remoto confirmado, remover o `stereo.mp3` local derivado, preservando `tx.mp3` e `rx.mp3` até a retenção normal | Must | O artefato estéreo não ocupa tmpfs durante toda a retenção e pode ser regenerado dos monos se necessário | 🟢 |
| RF-13 | Isolar os workers ARQ operacionais em filas exclusivas: uploader=`zenith:audio-upload`, cleanup=`zenith:audio-cleanup`, SMB=`zenith:smb-sync`; o produtor de gravação publica explicitamente na fila do uploader | Must | Nenhum dos três workers usa `arq:queue`; job de upload não pode ser retirado por cleanup/SMB e crons não podem ser retirados pelo uploader | 🟢 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| Desempenho | Disponibilidade: até 5min de espera pelo ciclo + menos de 30s para gerar e copiar o MP3 estéreo (assumindo arquivo ~2-5MB, rede LAN local 100Mbps) | Contrato de RNF: auditoria requer acesso "quase em tempo real" | 🟡 |
| Desempenho | Worker inicia a cada 5min. Geração estéreo + cópia têm timeout global bloqueante de 30 s por arquivo | Satisfaz o SLA de até 5min + 30s e aborta operação presa sem aprovar entrega atrasada | 🟢 |
| Confiabilidade | Falha de SMB não deve impedir gravação local em `/data/recordings/`. Gravação é operação crítica; cópia é best-effort | Padrão: separar crítico (gravação) de best-effort (backup remoto) | 🟢 |
| Confiabilidade | Workers ARQ separados por container também devem ser separados por fila Redis; nome de fila faz parte do contrato produtor/consumidor | E2E real provou que containers distintos ainda disputam a fila default | 🟢 |
| Segurança | Credenciais SMB (username, password) armazenadas em `.env` (gitignored), NUNCA em código ou logs. Senhas nunca aparecem em debug output | Segue o padrão atual de configuração por ambiente do projeto; a integração S3 anterior foi removida | 🟢 |
| Segurança | Credenciais de acesso ao SMB (username, password) nunca aparecem em logs ou debug output. SMB trafega em LAN privada (192.168.x.x), criptografia não é necessária | Padrão de segurança: dados sensíveis em rede privada sem exposição pública | 🟢 |
| Compatibilidade | Usar `pysmb==1.2.14` com negociação SMB2 automática, Direct TCP configurável (padrão porta 445), NTLMv2 e nomes NetBIOS configuráveis; compatibilidade final depende de E2E com o servidor real | Mantém defaults explícitos e reversíveis sem assumir a configuração do servidor | 🟡 |
| Observabilidade | Logs estruturados com timestamp, call_id, tenant_id, status (success\|fail), bytes transferidos, latency_ms. Um log por operação | Rastreabilidade: auditor consegue justificar "quando copiou este arquivo?" | 🟢 |
| Observabilidade | Métricas Prometheus: `smb_backup_success_total`, `smb_backup_failed_total`, `smb_backup_latency_seconds`, `smb_backup_queue_size`. Alertas: fila > 100, latência > 10s, falha consecutiva > 5 | Monitoramento contínuo: oncall consegue detectar degradação de backup | 🟡 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Áudio gravado é combinado em estéreo e copiado automaticamente para SMB
  Dado uma chamada concluída com arquivos rx.mp3 + tx.mp3 em /data/recordings/akom/{call_id}/
  E SMB está online e acessível
  E ambos os arquivos foram publicados por rename atômico
  E worker SMB está rodando (executando a cada 5min)
  Quando o worker inicia seu ciclo de sincronização
  Então um único MP3 estéreo aparece em \\192.168.50.240\backup$\Audios_Atendimento\akom\{YYYY-MM-DD}\
  E o canal esquerdo contém tx e o canal direito contém rx
  E cada canal pode ser extraído posteriormente sem mistura com o outro
  E nomeação respeita {YYYY-MM-DD}-{HH}-{MM}-{SS}-{call_id[0:6]}-{origem}-{destino}.mp3
  E checksum SHA256 do arquivo no SMB coincide com o artefato estéreo local
  E a disponibilidade total respeita até 5min de espera + 30s de processamento e cópia

Cenário: SMB fica indisponível, worker retenta automaticamente
  Dado uma chamada concluída com rx.mp3 + tx.mp3
  E SMB está OFFLINE (firewall bloqueia porta 445, ou servidor desligado)
  Quando worker tenta copiar
  Então worker registra erro em /data/smb_logs/smb_transfer_log.json com status=pending
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
  E existe uma única réplica do processo zenith-smb-sync
  Quando o processo copia arquivo de 10MB
  Então tempo de cópia é aprox. 10 segundos (não menos, devido ao throttle)
  E interface eth0 não mostra tráfego > 1.2MB/s (margem de segurança)
  E o primeiro chunk trunca o temporário remoto
  E os chunks seguintes usam offsets crescentes sem truncar

Cenário: Arquivo deletado localmente antes de copiar é pulado gracefully
  Dado /data/recordings/akom/{call_id}/rx.mp3 foi deletado pelo cleanup cron
  E smb_transfer_log.json tem entrada status=pending para esse arquivo
  Quando worker tenta acessar o arquivo para copiar
  Então registra "arquivo já deletado, pulando" em log
  E remove entrada de smb_transfer_log.json
  E não gera erro

Cenário: Conversão para MP3 falha antes do backup
  Dado que a gravação preservou somente tx.raw ou rx.raw
  Quando o worker detecta que o par MP3 ainda não está pronto
  Então não copia um áudio parcial para o SMB
  E retenta a conversão para MP3
  E registra métrica e alerta enquanto a conversão não tiver sucesso

Cenário: Configuração privada do storage precede o E2E
  Dado que o administrador possui uma conta técnica com permissão WRITE
  E os auditores possuem credencial separada READ-ONLY
  Quando o ambiente é preparado para o teste E2E
  Então o .env privado recebe endpoint e credencial da conta técnica
  E o .env.example mantém somente placeholders
  E nenhuma credencial de auditoria ou senha real é registrada no repositório

Cenário: Novo ciclo não sobrepõe sincronização ainda ativa
  Dado que um ciclo zenith-smb-sync ainda está processando
  Quando o cron tenta iniciar o ciclo seguinte
  Então o segundo ciclo retorna already_running
  E não abre nova conexão SMB nem modifica o log

Cenário: Cleanup respeita lease de chamada em processamento
  Dado um diretório de chamada antigo com lease SMB UTC válido por 120 segundos
  Quando o cleanup percorre o tmpfs
  Então não remove tx.mp3, rx.mp3 nem stereo.mp3
  E o worker renova o lease a cada 30 segundos enquanto processa
  Mas um lease expirado volta a ser elegível para cleanup
  E um lease inválido ou corrompido é tratado como expirado e gera alerta

Cenário: Colisão no identificador curto não sobrescreve áudio
  Dado dois call_id diferentes com os mesmos seis primeiros caracteres
  E o nome-base remoto já existe com SHA256 diferente
  Quando a segunda chamada é publicada
  Então o nome recebe também call_id[6:10]
  E nenhum arquivo existente é sobrescrito

Cenário: Log JSON corrompido entra em recuperação segura
  Dado smb_transfer_log.json vazio ou inválido
  Quando o worker carrega o estado
  Então preserva o arquivo corrompido para diagnóstico
  E inicializa estado seguro sem marcar transferências como done

Cenário: Estéreo local é transitório
  Dado que o checksum remoto foi confirmado
  Quando a transferência é marcada done
  Então stereo.mp3 local é removido
  E tx.mp3 e rx.mp3 permanecem até o cleanup normal

Cenário: Workers ARQ não roubam jobs entre si
  Dado que uploader, cleanup e SMB estão executando simultaneamente
  E uma nova chamada enfileira upload_recording_batch
  Quando os workers consultam suas filas
  Então somente zenith-arq-uploader pode retirar o job de zenith:audio-upload
  E cron:run_cleanup permanece em zenith:audio-cleanup
  E cron:run_smb_sync permanece em zenith:smb-sync
  E nenhum resultado contém "function not found"
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|---------------|
| RF-01 (cópia básica) | Must | Objetivo principal da feature: fazer cópia chegar ao SMB |
| RF-02 (registro em log local) | Must | Sem log, não há retry automático em caso de falha |
| RF-03 (retry se SMB cai) | Must | Rede LAN é instável; sem retry, perde dados |
| RF-04 (exponential backoff + circuit breaker) | Must | Sem isso, thrashing na rede se SMB lento |
| RF-05 (checksum) | Must | Sem validação, auditoria não confia nos dados |
| RF-06 (throttling do processo único) | Must | Protege a rede sem introduzir coordenação distribuída fora do escopo aprovado |
| RF-07 (READ-ONLY auditoria) | Must | Segurança crítica: auditoria não pode deletar provas |
| RF-08 (limpeza de log) | Should | Housekeeping, evita crescimento infinito de log |
| RF-09 (publicação atômica + retry de conversão) | Must | Impede cópia truncada e ausência silenciosa quando o ffmpeg falha |
| RF-10 (configuração privada do storage) | Must | O E2E depende de endpoint e conta técnica WRITE sem expor segredos |
| RF-11 (exclusão mútua + lease) | Must | Evita dois ciclos concorrentes e corrida destrutiva com cleanup |
| RF-12 (estéreo local transitório) | Must | Controla a pressão no tmpfs de 512 MB |
| RNF Desempenho (< 30s) | Should | Meta de latência, não bloqueador |
| RNF Segurança (credenciais isoladas) | Must | Credenciais não em logs, LAN privada não requer crypto |
| RNF Observabilidade (métricas Prometheus) | Should | Monitoramento, facilita debug futuro |

## 9. Esclarecimentos

**Sessão 1 (2026-07-27):**
- **RF-07 (ACL):** Confirmado — READ-ONLY do servidor SMB é para a equipe de auditoria (destino), não origem. Dados locais acessíveis via tmpfs no mesmo servidor.
- **Criptografia SMB:** Removida — trafega em LAN privada (192.168.x.x), criptografia desnecessária.
- **RF-06 (Throttling):** ~~Refinado como GLOBAL entre workers~~ — superado na Sessão 3 pela decisão de processo único.

Resultado: **0 dúvidas pendentes.** Requirements pronto para plano.

**Sessão 2 (2026-07-27):**
- **Q:** Qual deve ser o SLA entre o fim da gravação e a disponibilidade no SMB?
  **R:** Até 5 minutos de espera pelo ciclo do worker mais 30 segundos de processamento e cópia.
- **Q:** Como comprovar que o MP3 terminou de ser escrito antes da cópia?
  **R:** O produtor grava com nome temporário e publica por rename atômico ao finalizar.
- **Q:** O que fazer quando a conversão falhar e existir somente `.raw`?
  **R:** Retentar a conversão para MP3 e alertar enquanto falhar.
- **Q:** Quantos caracteres do `call_id` devem aparecer no nome remoto?
  **R:** Os 6 primeiros caracteres.
- **Q:** Qual versão da dependência deve ser fixada?
  **R:** `pysmb==1.2.14`.
- **Q:** Como `tx` e `rx` devem ser armazenados no SMB?
  **R:** Em um único MP3 estéreo, com `tx` no canal esquerdo e `rx` no canal direito, permitindo separação posterior.

Resultado: **6 decisões integradas e 0 dúvidas pendentes.**

**Sessão 3 (2026-07-28):**
- **Q:** Como a configuração real do storage deve entrar no fluxo de entrega?
  **R:** Como ação manual obrigatória antes do E2E: preencher o `.env` privado com IP, nome NetBIOS, share, pasta e conta técnica WRITE; auditores usam credencial separada READ-ONLY.
- **Decisões anteriores reafirmadas:** uma única réplica/processo para o throttle e ciclo fixo de 5 minutos.
- **Próxima investigação acordada:** pausar o avanço do forward e executar um spike controlado de escrita/leitura/remoção no storage antes de regenerar o plano.

Resultado: **3 decisões alinhadas e 0 dúvidas pendentes.**

**Sessão 4 (2026-07-28):**
- **Q:** Como interpretar o SLA após o worker iniciar?
  **R:** Geração estéreo e cópia devem terminar em até 30 s; o timeout global também é 30 s.
- **Q:** Qual deve ser a duração e renovação do lease?
  **R:** Lease UTC de 120 s, renovado a cada 30 s; inválido ou corrompido é tratado como expirado com alerta.
- **Q:** Qual é o caminho definitivo do log?
  **R:** `/data/smb_logs/smb_transfer_log.json`, no volume persistente planejado.
- **Q:** Quais estados o log deve admitir?
  **R:** `pending`, `done` e `failed`.

Resultado: **4 dúvidas resolvidas e 0 dúvidas pendentes.**

## 10. Lacunas

Nenhuma lacuna pendente. Todos os pontos foram esclarecidos:

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-07-28 | Esclarecimentos pós-auditoria: timeout global de 30 s, lease UTC 120 s/renovação 30 s, caminho persistente e estados do log | reversa |
| 2026-07-28 | Revisão multi-LLM: lock de ciclo, lease contra cleanup, chunks por offset, recuperação de JSON, colisão determinística e estéreo transitório | reversa |
| 2026-07-28 | Esclarecimentos: processo único, ciclo fixo de 5min, configuração privada manual e spike SMB antes de retomar o plano | reversa |
| 2026-07-27 | Esclarecimentos: SLA 5min+30s, publicação atômica, retry de conversão, call_id curto, pysmb 1.2.14 e MP3 estéreo tx/rx separável | reversa |
| 2026-07-27 | Esclarecimentos: RF-07 confirmada (ACL no servidor SMB), criptografia removida (LAN privada), RF-06 refinado como throttling global. 0 dúvidas pendentes | daniel.scalioni |
| 2026-07-27 | Versão inicial gerada por `/reversa-requirements` a partir de especificação validada via `/brainstorming-multiagent` | reversa |
