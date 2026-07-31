# Roadmap: SMB Audio Backup para Auditoria

> Identificador: `011-smb-audio-backup`
> Data: `2026-07-27`
> Requirements: `_reversa_forward/011-smb-audio-backup/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

Adicionar um worker ARQ periódico e de processo único (`src/workers/smb_sync.py`) que, a cada cinco minutos, encontra pares `tx.mp3`/`rx.mp3` publicados atomicamente no tmpfs. O worker gera um único `stereo.mp3` local temporário com `tx` no canal esquerdo e `rx` no direito, publica esse artefato por rename atômico e o copia para SMB com nome cronológico e os seis primeiros caracteres do `call_id`.

O uploader atual passa a publicar cada MP3 mono por rename atômico. Se restar `.raw`, o fluxo de sincronização retenta a conversão e registra falha observável. A cópia SMB usa `pysmb==1.2.14`, Direct TCP/445 configurável, NTLMv2 e nomes NetBIOS explícitos. Retry, circuit breaker, checksum, log persistente e throttle compartilhado no único processo isolam falhas do SMB da gravação. Um spike manual já confirmou conectividade, autenticação e permissões de mkdir/write/read/rename/delete da conta técnica; a compatibilidade do cliente Python continua pendente.

## 2. Princípios aplicados

`.reversa/principles.md` não existe. Foram aplicados os princípios confirmados em `_reversa_sdd/architecture.md` e as regras do projeto.

| Princípio | Como a feature se relaciona | Status |
|-----------|------------------------------|--------|
| Isolamento de tenant | Diretório remoto começa por `{tenant}` e consultas usam o schema do tenant | respeita |
| Processamento assíncrono | Cópia, conversão e retry rodam em worker ARQ fora da cadeia crítica | respeita |
| Privacidade local | Áudio permanece na LAN privada e credenciais ficam fora de código/logs | respeita |
| Spec-first e TDD | Spec SDD antecede testes; testes antecedem cada mudança de código | respeita |
| Recursos Docker `zenith-*` | Container, volume e rede permanecem exclusivos deste projeto | respeita |

Não há conflito de princípio identificado.

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|---------------|--------------------------|-------------|
| D-01 | Worker ARQ pull a cada 5 min | Isola SMB da gravação; satisfaz SLA de 5 min + 30 s | Hook síncrono; mount CIFS no host | 🟢 |
| D-02 | Uploader publica `tx.mp3` e `rx.mp3` via arquivo temporário + `os.replace` | Nome final passa a significar arquivo completo | Idade fixa; dupla leitura de tamanho | 🟢 |
| D-03 | Worker gera `stereo.mp3` com ffmpeg: esquerda=`tx`, direita=`rx` | Mantém separação posterior e preserva intermediários mono | Dois arquivos remotos; mixagem mono | 🟢 |
| D-04 | Nome remoto `{timestamp}-{call_id[0:6]}-{origem}-{destino}.mp3` | Decisão explícita do usuário; busca humana rápida | UUID completo; sufixos tx/rx | 🟢 |
| D-05 | Retry de `.raw` reutiliza conversão atômica; falha gera log e métrica | Fecha a ausência silenciosa da regra legada R40 | Ignorar; copiar raw | 🟢 |
| D-06 | `pysmb==1.2.14`, SMB2 automático, Direct TCP padrão em 445, NTLMv2 | Defaults explícitos e reversíveis; porta 445 e permissões foram confirmadas manualmente, mas o cliente Python ainda requer E2E | 139/NetBIOS como default; mount CIFS | 🟡 |
| D-07 | `SMB_CLIENT_NAME` default `ZENITH`, `SMB_SERVER_NAME` obrigatório quando habilitado | `SMBConnection` exige identidade local/remota válida | Inferir nome remoto silenciosamente | 🟢 |
| D-08 | Uma réplica e uma operação SMB por vez; throttle global somente no processo | Corresponde ao deploy aprovado, sem coordenação Redis artificial | Rate limiter distribuído | 🟢 |
| D-09 | Log JSON em `/data/smb_logs/smb_transfer_log.json`, com escrita atômica, estados pending/done/failed e poda após 7 dias | Retry sobrevive ao restart sem nova tabela e falhas permanentes ficam auditáveis | Estado em memória; tabela PostgreSQL | 🟢 |
| D-10 | Escrita remota `.tmp` → rename + SHA256 contra `stereo.mp3` local | Arquivo final nunca aparece parcial | Sobrescrita direta; checksum dos monos | 🟢 |
| D-11 | ACL é pré-requisito operacional verificável: worker WRITE, auditor READ-ONLY | Aplicação não controla ACL do servidor | Considerar ACL fora do critério de pronto | 🟢 |
| D-12 | Retenção local sobe de ~1 h para ~2 h | Amplia janela de retry sem mudar cron de cleanup | Retenção indefinida; 1 h atual | 🟢 |
| D-13 | Cada ciclo usa identidade fixa/lock e retorna `already_running` quando outro ciclo ainda está ativo | Evita duas execuções do cron processarem a mesma chamada | Confiar apenas em uma réplica | 🟢 |
| D-14 | O worker mantém lease local UTC de 120 s, renovado a cada 30 s; lease inválido/corrompido expira com alerta | Impede o cleanup de remover uma chamada em processamento e permite recuperar abandono | Lock sem expiração; coordenação Redis | 🟢 |
| D-15 | Throttle escreve por chunks com `storeFileFromOffset`: primeiro chunk em offset 0 com truncamento, seguintes com offsets crescentes sem truncar | A API existe no cliente escolhido e permite limitar vazão sem remontar o arquivo | `storeFile` integral; mount CIFS | 🟢 |
| D-16 | Log vazio/corrompido é preservado para diagnóstico e recuperado como estado vazio observável | Um JSON inválido não pode derrubar permanentemente o cron | Falhar todo ciclo; sobrescrever silenciosamente | 🟢 |
| D-17 | Em colisão divergente do nome de seis caracteres, tentar uma única vez sufixo `call_id[6:10]`; nova colisão falha sem sobrescrever | Preserva o nome aprovado e evita perda silenciosa | UUID completo sempre; sobrescrever | 🟢 |
| D-18 | `stereo.mp3` local é removido somente após checksum remoto confirmado; os monos permanecem até o cleanup | Reduz pressão no tmpfs sem comprometer retry ou consumidores existentes | Manter estéreo por 2 h; remover monos | 🟢 |
| D-19 | Geração estéreo e cópia compartilham timeout global bloqueante de 30 s por arquivo | Mantém implementação e E2E dentro do SLA aprovado | Timeout de 60 s; 30 s apenas como meta | 🟢 |
| D-20 | Uploader, cleanup e SMB usam filas ARQ exclusivas (`zenith:audio-upload`, `zenith:audio-cleanup`, `zenith:smb-sync`); o deploy recarrega também as APIs que hospedam o produtor | Containers separados ainda disputam a fila default; E2E real perdeu o job de upload por `function not found`, e o segundo E2E mostrou que reiniciar só os workers mantém o produtor antigo em memória | Registrar todas as funções em todos os workers; worker único | 🟢 |

## 4. Premissas

Não há marcadores `[DÚVIDA]` no requirements. O spike confirmou a conta técnica WRITE e as operações básicas. Compatibilidade `pysmb`, nome NetBIOS remoto, SHA256 do round-trip, ACL negativa da conta de auditoria e desempenho serão confirmados no E2E.

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-----------------|--------|
| Workers ARQ | `_reversa_sdd/architecture.md#Fluxo-Principal-de-uma-Chamada` | regra-alterada | Novo `smb_sync` periódico e isolamento de uploader/cleanup/SMB por fila Redis |
| Audio uploader | `_reversa_sdd/code-analysis.md#10-workers--Background-Jobs` | regra-alterada | Conversão MP3 passa a publicar por rename atômico e fica reutilizável para retry |
| Recordings tmpfs | `_reversa_sdd/domain.md#Gravação-e-retenção` | regra-alterada | Novo `stereo.mp3` derivado e retenção ~2 h |
| Configuração | `_reversa_sdd/dependencies.md#Dependências-Core` | contrato-novo | Settings `SMB_*` e `pysmb==1.2.14` |
| Observabilidade | `_reversa_sdd/architecture.md#Stack-Tecnológica` | contrato-novo | Métricas de backup e conversão pendente |
| Persistência de chamada | `_reversa_sdd/state-machines.md#Call-Chamada-Telefônica` | regra-alterada | `caller_number` e `callee_number` passam a ser preenchidos |
| Docker Compose | `_reversa_sdd/code-analysis.md#12-infra--Infraestrutura` | contrato-alterado | `zenith-smb-sync`, `zenith_smb_logs` e retenção |
| SMB externo | `_reversa_sdd/c4-context.md#Sistemas-Externos` | contrato-novo | Servidor SMB e auditoria entram na fronteira externa |

## 6. Delta no modelo de dados

- Nenhuma migração PostgreSQL: `started_at`, `caller_number` e `callee_number` já existem.
- Novo estado persistente em `/data/smb_logs/smb_transfer_log.json`.
- Novo artefato transitório `{call_dir}/stereo.mp3`; fontes mono continuam preservadas até o cleanup.
- Detalhe completo em `_reversa_forward/011-smb-audio-backup/data-delta.md`.

## 7. Delta de contratos externos

| Contrato | Tipo | Arquivo de detalhe |
|----------|------|--------------------|
| SMB/CIFS Audio Backup | arquivo de rede | `_reversa_forward/011-smb-audio-backup/interfaces/smb.md` |

## 8. Plano de migração

1. Criar `_reversa_sdd/workers/smb-backup/design.md` antes do código.
2. Adicionar testes Red para settings, métricas e publicação atômica.
3. Adicionar `pysmb==1.2.14`, settings e contrato `.env.example`.
4. Executar mini-spike pelo próprio `pysmb`, incluindo assinatura, Direct TCP, escrita por offset, rename e checksum.
5. Implementar rename atômico e retry de conversão no uploader.
6. Implementar geração estéreo e worker SMB com timeout global de 30 s, log recuperável, retry, circuit breaker, checksum, throttle local, exclusão de ciclos e lease UTC 120 s renovado a cada 30 s.
7. Preencher origem/destino no registro da chamada.
8. Adicionar `zenith-smb-sync`, volume `zenith_smb_logs` e retenção de ~2 h.
9. Registrar a configuração privada já aplicada e a evidência do spike manual da conta WRITE.
10. Testar a conta de auditoria READ-ONLY.
11. Escrever testes Red do contrato de filas e isolar uploader, cleanup e SMB.
12. Redeployar os três workers; jobs antigos não serão reenfileirados.
13. Validar E2E com nova chamada, checksum, canais L/R, retry, SLA, throttle, colisão, lease e ACL.
14. Atualizar specs/resultados e executar `/reversa-sync`.

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Nome NetBIOS remoto incorreto | alto | médio | Setting obrigatório quando SMB habilitado + teste de conexão |
| Servidor incompatível com defaults | alto | baixo | E2E antes do deploy; porta/Direct TCP/NTLMv2 configuráveis |
| Apenas um canal fica pronto | alto | médio | Não gerar estéreo; manter pending, retentar e alertar |
| Retry de `.raw` nunca converge | alto | baixo | Métrica, circuit breaker e expiração explícita pela retenção |
| Colisão de `call_id[0:6]` | médio | baixo | Incluir timestamp/origem/destino; detectar destino existente com checksum divergente |
| SMB indisponível por mais de 2 h | alto | médio | Alertar fila/circuit breaker; registrar expiração sem sucesso |
| ACL permite escrita ao auditor | alto | baixo | Teste negativo obrigatório de delete/rename |
| `stereo.mp3` aumenta uso do tmpfs | médio | médio | Cleanup ~2 h, fila monitorada e tmpfs observado |
| Segredo aparece em exceção da biblioteca | alto | baixo | Nunca interpolar credenciais; sanitizar erros e manter INFO |
| Ciclos cron se sobrepõem | alto | médio | Identidade fixa/lock; segundo ciclo retorna `already_running` |
| Cleanup remove chamada durante transferência | alto | médio | Lease timestampado; cleanup respeita lease válido e recupera expirado |
| Queda durante escrita remota deixa parcial | alto | médio | Nome `.tmp`, offsets explícitos, checksum e rename somente ao final |
| JSON vazio/corrompido paralisa retries | alto | baixo | Preservar cópia diagnóstica, recuperar estado vazio e emitir métrica/log |
| Colisão real após truncar `call_id` | médio | baixo | Comparar checksum; tentar sufixo `call_id[6:10]`; nunca sobrescrever divergente |
| Geração + cópia excedem o SLA | alto | médio | Orçamento único de 30 s com cancelamento observável e permanência em pending |
| Relógio ou lease local inválido | alto | baixo | Timestamp UTC, renovação a cada 30 s e tratamento como expirado com alerta |
| Worker retira job de função não registrada | alto | confirmado | Filas exclusivas por worker e teste de roteamento produtor/consumidor |

## 10. Critério de pronto

- [ ] Spec SDD ativa e alinhada ao contrato estéreo
- [ ] Testes Red → Green → Refactor para cada mudança
- [ ] `tx.mp3`/`rx.mp3` publicados atomicamente
- [ ] MP3 remoto único com tx à esquerda e rx à direita, separável por ffmpeg
- [ ] Retry de `.raw` observável e sem ausência silenciosa
- [ ] SMB E2E validado com `pysmb==1.2.14`
- [ ] Mini-spike `pysmb` comprova assinatura, offsets, rename e checksum antes da estratégia
- [ ] Ciclo concorrente retorna `already_running`
- [ ] Cleanup respeita lease válido e recupera lease expirado
- [ ] Lease UTC dura 120 s, renova a cada 30 s e invalidez gera alerta
- [ ] Geração estéreo + cópia abortam ao atingir o timeout global de 30 s
- [ ] JSON vazio/corrompido é recuperado sem perda silenciosa da evidência
- [ ] Colisão divergente usa o sufixo definido e nunca sobrescreve
- [ ] `stereo.mp3` local é removido após checksum e preservado em falha
- [ ] SLA de 5 min + 30 s comprovado
- [ ] Checksum, idempotência, throttle e circuit breaker comprovados
- [ ] Conta de auditoria falha ao deletar/renomear
- [ ] Cobertura ≥ 80% e quality gates executados
- [ ] Todas as ações do `actions.md` marcadas `[X]`
- [ ] `cross-check.md` sem CRITICAL nem HIGH
- [ ] `regression-watch.md` gerado
- [ ] Re-extração reversa executada e sem regressão vermelha (recomendado)

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-07-27 | Plano regenerado após clarify: estéreo separável, rename atômico, retry raw, pysmb 1.2.14 e processo único | reversa |
| 2026-07-28 | Spike manual incorporado: conta WRITE e operações básicas confirmadas; pysmb/NetBIOS/checksum permanecem no E2E | reversa |
| 2026-07-28 | Revisão crítica multi-LLM e cross-check incorporados: ordem spec-first, mini-spike Python, lock/lease, offsets, recuperação do log, colisão e retenção transitória | reversa |
| 2026-07-28 | Clarify pós-auditoria propagado: timeout 30 s, lease 120/30 s UTC e contrato definitivo do log | reversa |
| 2026-07-30 | Plano de recuperação dos gates preparado: baseline Alembic pública, banco/testes isolados e corte por volume novo | reversa |

## 12. Plano de recuperação dos quality gates

### Decisões

| ID | Decisão | Justificativa | Confiança |
|----|---------|---------------|-----------|
| D-22 | Recriar o banco em volume PostgreSQL novo, mantendo o volume atual como rollback | Evita qualquer operação destrutiva sobre o único estado conhecido | 🟢 |
| D-23 | Preservar UUIDs de tenant/PBX e as 9 chamadas existentes | FreeSWITCH referencia o PBX por UUID; regenerar UUID quebra persistência silenciosamente | 🟢 |
| D-24 | Regerar e validar os 939 ramais após o corte, embora eles não residam no PostgreSQL | Condição do usuário e prova de que a telefonia permaneceu íntegra | 🟢 |
| D-25 | Substituir 001–003 por baseline pública somente se nenhum ambiente tiver histórico Alembic | A cadeia atual colide em banco vazio; não há histórico no ambiente conhecido | 🟡 |
| D-26 | Executar testes de multitenancy em banco `zenith-*` exclusivo | A suíte atual criou schema de teste no banco operacional e não possui teardown | 🟢 |
| D-27 | Manter cobertura global de 80%, classificando testes antes de alterar produção | Decisão A/A do usuário; evita codificar para expectativas obsoletas | 🟢 |

### Fases preparadas

1. Inventário de todos os ambientes quanto a histórico Alembic.
2. ADR e promoção da spec de migrations para `active`.
3. Três recursos separados e sem porta publicada: teste, rehearsal e candidato.
4. Testes Red da topologia de migrations e isolamento da suíte.
5. Baseline pública e provisionamento de tenant no candidato vazio.
6. Dump lógico, restore verificado no rehearsal e rollback ensaiado.
7. Testes de cobertura global escritos por LLM independente e revisados módulo a módulo.
8. Checkpoint humano; somente então rolling cutover das duas APIs e três workers.
9. Reimportação/verificação dos ramais e chamada smoke.

### No-go

- Dump não restaurável ou contagens/UUIDs divergentes.
- Qualquer ambiente conhecido com migrations aplicadas sem plano compatível.
- `alembic upgrade head` ou segunda execução falhar.
- Testes ainda apontarem para o banco operacional.
- Cobertura global abaixo de 80%.
- Manifesto sanitizado dos ramais divergir do estado atual.
- Rollback não tiver sido comprovado antes do cutover.
