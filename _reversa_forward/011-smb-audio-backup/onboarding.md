# Onboarding: validar SMB Audio Backup

> Identificador: `011-smb-audio-backup`
> Objetivo: provar transporte, estéreo separável, resiliência, segurança e SLA.

## Pré-requisitos

- Servidor SMB acessível pela LAN.
- Nome NetBIOS real do servidor.
- Conta do worker com mkdir/write/rename/read/delete no diretório de destino.
- Conta separada do grupo `auditores` com READ-ONLY.
- Uma chamada de teste com voz distinta nos sentidos `tx` e `rx`.
- Nenhum segredo deve ser registrado neste documento.

## Configuração

Preencher no `.env` privado:

```dotenv
SMB_ENABLED=true
SMB_HOST=192.168.50.240
SMB_PORT=445
SMB_IS_DIRECT_TCP=true
SMB_CLIENT_NAME=ZENITH
SMB_SERVER_NAME=<nome-netbios-real>
SMB_DOMAIN=
SMB_USE_NTLM_V2=true
SMB_SIGN_OPTIONS=2
SMB_SHARE=backup$
SMB_PATH=Audios_Atendimento
SMB_USERNAME=<conta-worker>
SMB_PASSWORD=<segredo>
SMB_BANDWIDTH_LIMIT_MBS=5
SMB_TRANSFER_LOG_PATH=/data/smb_logs/smb_transfer_log.json
SMB_SYNC_INTERVAL_MINUTES=5
```

## Validação automatizada

1. Executar testes unitários e integração.
2. Confirmar cobertura ≥ 80%.
3. Validar `docker compose -f docker-compose.app.yml config`.
4. Confirmar que todos os recursos novos usam prefixo `zenith-`/`zenith_`.
5. Confirmar que um segundo ciclo simultâneo retorna `already_running`.
6. Confirmar recuperação observável de log JSON vazio e corrompido.
7. Confirmar que geração estéreo + cópia são canceladas ao esgotar o orçamento global de 30 s.
8. Confirmar lease UTC de 120 s, renovação a cada 30 s e alerta para conteúdo inválido.

## Validação E2E

1. Iniciar apenas os serviços `zenith-*` necessários.
2. Realizar uma chamada de teste.
3. Confirmar `tx.mp3`, `rx.mp3` e `stereo.mp3` no tmpfs.
4. Confirmar que nenhum nome final surge antes do término do ffmpeg.
5. Aguardar no máximo 5 min + 30 s.
6. Localizar um único MP3 remoto:

```text
{tenant}/{YYYY-MM-DD}/{YYYY-MM-DD}-{HH}-{MM}-{SS}-{call_id[0:6]}-{origem}-{destino}.mp3
```

7. Comparar SHA256 local/remoto.
8. Inspecionar com `ffprobe`: dois canais, 8 kHz.
9. Extrair canal esquerdo e direito separadamente com ffmpeg.
10. Confirmar voz `tx` somente à esquerda e `rx` somente à direita.
11. Confirmar remoção do `stereo.mp3` local após o checksum, mantendo `tx.mp3` e `rx.mp3`.
12. Forçar colisão divergente do nome curto e confirmar o sufixo `call_id[6:10]` sem overwrite.

## Falhas e recuperação

### SMB offline

1. Bloquear somente a conexão do container `zenith-smb-sync` ao host/porta configurados.
2. Confirmar status `pending`, retry 1s/2s/4s e ausência de exceção não tratada.
3. Após cinco falhas consecutivas, confirmar circuit breaker de 5 min.
4. Restaurar a conexão e confirmar convergência para `done`.

### Conversão falha

1. Simular erro do ffmpeg preservando `.raw`.
2. Confirmar que nenhum MP3 remoto parcial é publicado.
3. Confirmar retry de conversão, métrica e log sem conteúdo sensível.
4. Restaurar ffmpeg e confirmar criação atômica dos monos, estéreo e backup.

### Throttle

1. Configurar `SMB_BANDWIDTH_LIMIT_MBS=1`.
2. Copiar arquivo grande no único processo.
3. Confirmar média próxima de 1 MB/s, com margem operacional documentada.

### ACL

1. Com a conta do worker, criar/copy/rename/read no destino.
2. Com a conta de auditoria, ler e baixar.
3. Com a conta de auditoria, tentar delete e rename.
4. Registrar evidência de `permission denied`.

## Evidências a registrar

| Evidência | Resultado |
|-----------|-----------|
| Spike manual mkdir/write/read/rename/delete | confirmado pelo usuário em 2026-07-28 |
| Endpoint TCP/445 | acessível |
| Configuração privada da conta WRITE | presente; valores não registrados |
| Compatibilidade `pysmb`/NetBIOS/NTLMv2 | confirmada em 2026-07-28 |
| Horário de fim da chamada | pendente |
| Horário de disponibilidade SMB | pendente |
| SHA256 local/remoto | confirmado no spike e no `SMBBackupStrategy` real |
| ffprobe estéreo | 8 kHz, 2 canais confirmado com áudio sintético |
| extração tx/rx | confirmado: left/tx 440 Hz e right/rx 880 Hz permaneceram distintos |
| retry/circuit breaker | pendente |
| throttle | 2 MiB a 1 MiB/s em 2,67 s, confirmado no storage real |
| ACL negativa | pendente |
| ausência de segredo em logs | pendente |
| assinatura SMB (`SMB_SIGN_OPTIONS`) | `SIGN_WHEN_REQUIRED` confirmado no spike |
| exclusão de ciclo concorrente | pendente |
| lease válido/expirado contra cleanup | pendente |
| recuperação de JSON vazio/corrompido | pendente |
| colisão e sufixo determinístico | pendente |
| remoção do estéreo após checksum | pendente |
| timeout global de 30 s | pendente |
| lease UTC 120 s / renovação 30 s | pendente |

## Evidência automatizada parcial — 2026-07-28

- 38 testes focados/regressivos passaram antes do veredito independente.
- `src/workers/smb_sync.py` atingiu 85% de cobertura antes das correções adicionais.
- O storage real aceitou publicação pelo código final, checksum do temporário e do final, rename e
  remoção sem resíduo.
- O mapeamento estéreo foi comprovado com sinais distintos e extração dos canais.
- A validação ACL negativa continua pendente por exigir a credencial READ-ONLY dos auditores.
- O Docker CLI não existe neste ambiente; `docker compose ... config` precisa ser executado no host
  de deploy.

## Resultado dos quality gates — 2026-07-28

| Gate | Resultado |
|------|-----------|
| Testes focados da feature | 43 passed |
| Cobertura dos workers alterados | 83,67% |
| `pytest tests/ -v --cov --cov-fail-under=80` | falhou: 9 passed, 21 failed, 4 skipped, cobertura legada 58% |
| Causa dominante da suíte legada | serviços Docker indisponíveis: PostgreSQL, Redis, FastAPI, BunkerWeb e Ollama |
| Falha unitária legada adicional | `test_audio_ingestor` já não preserva buffers após desconexão |
| Docker Compose CLI | não executado: binário `docker` ausente |
| Validação estrutural YAML | passou; serviço/volumes novos usam nomes `zenith-*`/`zenith_` |
| `alembic upgrade head` | não conectou: hostname PostgreSQL indisponível neste ambiente |

O gate bloqueante do projeto precisa ser repetido no host que possui a stack `zenith-*`. Não
considerar os testes de infraestrutura como aprovados a partir desta execução local.

Não marcar a ação E2E como concluída enquanto algum resultado estiver `pendente`.

## Deploy controlado — 2026-07-29

Destino: servidor Docker `10.10.10.11`, projeto Compose
`/home/administrator/zenith-voip`.

| Verificação | Resultado |
|-------------|-----------|
| Escopo de containers | somente `zenith-api-1`, `zenith-api-2`, `zenith-arq-uploader`, `zenith-arq-cleanup` e novo `zenith-smb-sync` recriados |
| Recursos externos ao projeto | não alterados |
| Backup pré-deploy | `.deploy-backups/feature-011-20260729T110452Z` no servidor |
| Sincronização de configuração | 12 chaves `SMB_*` mescladas no `.env` remoto, sem registrar valores |
| `docker compose config --quiet` | passou |
| Build | cinco imagens afetadas construídas com `pysmb==1.2.14` |
| APIs | portas locais 8001 e 8002 responderam HTTP 200 na primeira tentativa |
| Workers | uploader, cleanup e SMB iniciaram e conectaram ao Redis |
| Runtime SMB | import de `pysmb`, settings obrigatórios e `WorkerSettings` passaram |
| Alembic | upgrade não executado: não há migration nova e o banco existente não possui `alembic_version`; aplicar 001–003 tentaria recriar tabelas já existentes |
| Conectividade storage pelo host | falhou por timeout antes da autenticação |
| Conectividade storage pelo container | falhou por timeout antes da autenticação |
| Rota observada | `192.168.50.240` via gateway `10.10.10.1`; ICMP e TCP/445 indisponíveis a partir do host |

O deploy está saudável para APIs e workers, mas o E2E da ligação permanece bloqueado até a
rede permitir que `10.10.10.11` alcance `192.168.50.240:445`. Como o timeout ocorre também no
host, não é um problema da bridge Docker nem das credenciais SMB. Após liberar rota/firewall,
repetir primeiro o teste read-only de conexão/listagem e então realizar a ligação.

### Reteste após regra de firewall — 2026-07-29

- A rota permanece `192.168.50.240 via 10.10.10.1`, com origem `10.10.10.11`.
- O gateway `10.10.10.1` responde normalmente.
- Três tentativas TCP/445, com timeout de 5 s, expiraram no host Docker.
- A sessão SMB e a ligação E2E não foram iniciadas porque a conexão TCP ainda não alcança o
  storage.

### Reteste após correção do destino da regra — 2026-07-29

- TCP/445 pelo host `10.10.10.11`: passou.
- TCP/445 pelo container `zenith-smb-sync`: passou.
- Autenticação e listagem read-only do caminho SMB configurado: passaram.
- Worker SMB: `running`, zero reinícios e nenhum erro recente.
- Nenhum arquivo foi criado durante esta validação.
- Ambiente liberado para a ligação E2E.

## Primeira ligação E2E após deploy — 2026-07-29

- ESL recebeu `CHANNEL_ANSWER` e `CHANNEL_HANGUP`.
- A linha `Call` foi criada e o WebSocket de áudio abriu e fechou normalmente.
- `upload_recording_batch` foi enfileirado, mas nenhum MP3 apareceu no tmpfs.
- Resultado ARQ confirmado: `JobExecutionFailed: function 'upload_recording_batch' not found`.
- Cleanup e SMB apresentaram falhas equivalentes para suas funções de cron.
- Causa raiz: os três containers usavam a fila default `arq:queue`; separação por container não
  impede que um worker retire job pertencente a outro.
- Decisão aprovada: filas exclusivas `zenith:audio-upload`, `zenith:audio-cleanup` e
  `zenith:smb-sync`.
- O payload falho não será recuperado. Após TDD e redeploy, executar uma nova ligação.

## Redeploy do isolamento ARQ — 2026-07-30

| Verificação | Resultado |
|-------------|-----------|
| Backup pré-deploy | `.deploy-backups/feature-011-queues-20260730T140323Z` |
| Arquivos sincronizados | somente `audio_uploader.py`, `audio_cleanup.py` e `smb_sync.py` |
| Containers recriados | somente `zenith-arq-uploader`, `zenith-arq-cleanup` e `zenith-smb-sync` |
| Reinícios inesperados | zero |
| Runtime uploader | `queue_name=zenith:audio-upload` |
| Runtime cleanup | `queue_name=zenith:audio-cleanup` |
| Runtime SMB | `queue_name=zenith:smb-sync` |
| Redis MONITOR | cada endereço de cliente consultou exclusivamente sua fila por `ZRANGEBYSCORE` |

## Proteção do PostgreSQL operacional — 2026-07-31

A inspeção foi somente leitura no host `10.10.10.11`. Nenhum container, volume, rede, porta ou
dado foi alterado.

| Propriedade observada | Evidência sanitizada |
|-----------------------|----------------------|
| Container | `zenith-postgres`, imagem `postgres:16-alpine` |
| Labels Compose | projeto `zenith-voip`, serviço `postgres`, diretório `/home/administrator/zenith-voip` |
| Volume RW | `zenith-voip_zenith_postgres_data` em `/var/lib/postgresql/data` |
| Containers anexados ao volume | somente `zenith-postgres` |
| Rede | `zenith-voip_ai-hub-net`; membros observados têm prefixo `zenith-` |
| Porta publicada | `5433` do host para `5432/tcp`, em todas as interfaces por binding vazio |
| Clientes ativos observados | `zenith-api-1`, `zenith-api-2` e `zenith-arq-cleanup`, mapeados pelos IPs da rede Compose |
| Limite da evidência | a porta publicada impede excluir consumidores externos inativos ou não observados |

### Regra de proteção bloqueante

O `zenith-postgres`, sua configuração, porta e volume atual **não podem** ser parados, recriados,
reconfigurados, removidos ou reutilizados por testes, rehearsal ou candidato. Também são proibidos
`docker compose down -v`, `docker volume rm`, `DROP DATABASE` e `DROP SCHEMA` sobre o recurso
operacional. Todo banco novo terá container, volume e rede próprios, prefixados `zenith-`, sem porta
publicada no host.

## Manifesto sanitizado pré-migração — 2026-07-31

Hashes servem apenas para comparar identidade/conjunto antes e depois. UUIDs, números de ramal,
nomes, senhas e conteúdo de chamadas não foram registrados.

| Conjunto | Contagem | Manifesto |
|----------|----------|-----------|
| `public.tenants` | 1 | MD5 dos UUIDs ordenados: `bc08184bb0586c48a4ba21997d1dbc96` |
| `public.pbxs` | 1 | MD5 dos UUIDs ordenados: `12715c62c82c91e865e2f2c3f2233504` |
| `tenant_akom.calls` | 9 | MD5 dos UUIDs ordenados: `adb72d9ddda49c5d973a70da97b2f104` |
| `tenant_akom.transcripts` | 0 | conjunto vazio |
| `tenant_akom.call_insights` | 0 | conjunto vazio |
| `tenant_akom.stt_metrics` | 0 | conjunto vazio |
| Gateways gerados | 939 | SHA-256 dos nomes de arquivos ordenados: `8daf38023609ac90d45d97423d6143172293a7c6cc92d5ea126d24b7c1fea552` |
| Gateways ativos | 1 | SHA-256 dos nomes ativos ordenados: `58fbc17e6cb8f986aee209bc746915a7b07b5d56a81d01f49a3e1802e6f1f29b` |
| CSV privado de origem | — | SHA-256: `612a665954ea1f807d908beb175944bd7920fde13ff46b588189001bbdbc1ede` |
| Directory XML gerado | 939 usuários | SHA-256: `d73a38c1ae74e38a4659d94bc23a5b555018c06732336c1ee0d7defabf810e75` |

O manifesto pós-restore e pós-importação deve repetir o mesmo algoritmo. Divergência em qualquer
contagem ou hash é `NO-GO`; não se troca o DSN dos serviços.
| Fila default | `arq:queue` sem jobs; não consultada pelos três workers durante a amostra |
| APIs | 8001 e 8002 responderam HTTP 200 |
| FreeSWITCH | não reiniciado; permaneceu healthy |

O redeploy e o isolamento runtime estão confirmados. T055 permanece em andamento até uma nova
ligação provar upload, geração estéreo e transferência SMB sem `function not found`.

### Segunda ligação — produtor FastAPI não recarregado (2026-07-30)

A ligação abriu o WebSocket e gerou `upload_recording_batch` no hangup, mas o job ficou pendente em
`arq:queue`. Os três workers já estavam isolados e, corretamente, não consumiram a fila default.
A inspeção confirmou que o produtor é executado dentro das APIs, cujos processos não haviam sido
reiniciados no redeploy parcial. Correção operacional: rolling restart de `zenith-api-1` e
`zenith-api-2`; preservar a ligação movendo somente o job identificado dessa chamada para
`zenith:audio-upload`. O job falho da primeira ligação não será recuperado.

#### Resultado final da segunda ligação

| Verificação | Resultado |
|-------------|-----------|
| Captura | `CHANNEL_ANSWER`, WebSocket e `CHANNEL_HANGUP` observados |
| Publicação inicial | produtor antigo publicou o job desta ligação em `arq:queue` |
| Correção do runtime | rolling restart das duas APIs; ambas retornaram healthy/HTTP 200 |
| Preservação do teste | somente o job identificado desta ligação foi movido atomicamente para `zenith:audio-upload` |
| Uploader | consumiu em 0,86 s; `j_complete=1`, `j_failed=0`; criou `tx.mp3` e `rx.mp3` |
| Filas após consumo | default, uploader, cleanup e SMB com zero jobs pendentes |
| Erro antigo | nenhum novo `function not found` ou `JobExecutionFailed` |
| SMB | uma tentativa; estado `done`; checksum remoto confirmado |
| Arquivo remoto | MP3, 8 kHz, 2 canais, layout stereo, 14,184 s |
| Separação | canais PCM distintos; correlação esquerdo↔tx `0,998776` e direito↔rx `0,993804` |
| Privacidade | identificadores e números completos omitidos deste registro operacional |

Durante a inspeção, um comando `find -printf` incompatível com o utilitário do container teve o
erro ocultado e levou à hipótese temporária de que o tmpfs nomeado não era compartilhado. O log
persistente provou que a cópia havia concluído às 22:05:01, antes de qualquer troca de montagem.
A alteração experimental para `/dev/shm` e o teste baseado nessa premissa foram revertidos; o
Compose voltou ao volume nomeado tmpfs limitado a 512 MB. A validação correta mostrou os cinco
containers montando o mesmo volume e o E2E confirmou a comunicação uploader → SMB.

## Quality gates após o E2E — 2026-07-30

| Gate | Resultado |
|------|-----------|
| Docker Compose combinado | passou (`config --quiet`) |
| Testes focados da feature | 43 passaram |
| Cobertura focada dos três workers | 83,86%, acima do mínimo de 80% |
| Suíte global `tests/` | 18 passaram, 14 falharam, 2 ignorados |
| Cobertura global | 65,07%, abaixo do mínimo de 80% |
| Alembic | bloqueado: banco possui tabelas existentes, mas não possui `alembic_version`; `upgrade head` tenta criar `tenants` novamente |
| Integridade após tentativa Alembic | transação revertida; `alembic_version` continua ausente e os dados existentes foram preservados |

As falhas globais são anteriores e abrangem BunkerWeb/ESL, multitenancy, loop assíncrono Redis,
mocks WebSocket e teste antigo do ingestor. O gate T037 permanece aberto: corrigir ou fazer
baseline do histórico Alembic e recuperar a suíte global exige escopo próprio, pois afeta módulos
fora da feature 011. Nenhum `alembic stamp` foi executado.

## Runbook preparado para recuperação dos gates

Este runbook ainda não autoriza operações destrutivas.

### Checkpoint A — antes de código

1. Confirmar que produção é o único ambiente relevante sem `alembic_version`.
2. Registrar ADR da baseline pública.
3. Criar testes Red para banco vazio, segunda execução e topologia por tenant.
4. Criar banco PostgreSQL de teste exclusivo com prefixo `zenith-`.

### Checkpoint B — antes do ensaio

1. Gerar dump lógico integral pelo PostgreSQL 16 do projeto.
2. Registrar checksum do dump sem expor dados.
3. Restaurar em instância temporária e comparar UUIDs/contagens.
4. Confirmar backup privado do CSV e das configurações FreeSWITCH atuais.
5. Capturar manifesto sanitizado: 939 ramais e conjunto ativo.

### Checkpoint C — antes do corte

1. Baseline e provisionamento passam em banco vazio e na segunda execução.
2. Restore preserva 1 tenant, 1 PBX, 9 chamadas e seus UUIDs.
3. Suíte global passa com cobertura ≥ 80% usando banco de teste.
4. Volume PostgreSQL candidato usa prefixo Zenith e o volume anterior permanece intocado.
5. Usuário aprova explicitamente o cutover.

### Cutover reversível

1. Pausar somente escritores `zenith-*`.
2. Apontar PostgreSQL do projeto ao volume candidato já validado.
3. Subir PostgreSQL, APIs e workers de forma controlada.
4. Regerar os ramais a partir do CSV privado e comparar o manifesto antes de recarregar o profile.
5. Executar health/readiness, smoke de tenant/PBX, ligação curta e E2E SMB.
6. Em qualquer divergência, reapontar ao volume anterior; nenhum volume é removido.
