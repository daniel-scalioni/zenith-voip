# Investigation: SMB Audio Backup

> Identificador: `011-smb-audio-backup`
> Data: `2026-07-27`

## Pesquisa de fundo

### Estado real do áudio

O FreeSWITCH envia PCM16 estéreo 8 kHz. `AudioIngestor` separa amostras pares como `tx` e ímpares como `rx`; no hangup, `audio_uploader.py` grava e converte cada canal para MP3 mono. O novo contrato não altera captura nem de-interleaving: deriva um MP3 estéreo para auditoria a partir dos dois monos completos.

### Publicação atômica

O ffmpeg não deve gravar diretamente no nome consumido por outro worker. A saída será `tx.tmp.mp3`/`rx.tmp.mp3`, seguida de `os.replace` para `tx.mp3`/`rx.mp3`. Para o artefato combinado, o mesmo padrão produz `stereo.tmp.mp3` e publica `stereo.mp3`.

### Estéreo separável

O ffmpeg recebe `tx.mp3` como primeira entrada e `rx.mp3` como segunda, usando `amerge=inputs=2` e saída de dois canais. O contrato fixa canal esquerdo como `tx` e direito como `rx`. O onboarding extrai cada canal com `-map_channel`/filtro equivalente e compara duração/energia.

### Compatibilidade `pysmb`

A documentação oficial de `SMBConnection` registra:

- SMB2 é usado quando suportado, com fallback automático para SMB1;
- Direct TCP usa porta 445; NetBIOS over TCP usa 139;
- `my_name` identifica o cliente e `remote_name` precisa corresponder ao servidor;
- NTLMv2 é default, mas a política do servidor não é autodetectável;
- uma conexão não deve executar operações concorrentes.

Fontes:

- https://pysmb.readthedocs.io/en/latest/api/smb_SMBConnection.html
- https://pypi.org/project/pysmb/

### Validação multi-LLM

DeepSeek, North e Laguna convergiram em manter transporte e nomes configuráveis e adiar a compatibilidade final ao E2E. Afirmações sem apoio documental sobre TLS, SMB3 e exposição automática de senha foram descartadas. Gemini, Nemotron e MiMo não produziram resposta aproveitável nessa consulta.

## Alternativas avaliadas

| Alternativa | Vantagem | Desvantagem | Escolha |
|-------------|----------|-------------|---------|
| Worker ARQ pull a cada 5 min | Isolado da gravação | Latência de até 5 min | ✅ |
| Hook pós-gravação | Menor latência | Acopla SMB à cadeia crítica | ❌ |
| Mount CIFS | API de arquivo simples | Pode bloquear host; exige privilégio | ❌ |
| Dois MP3 remotos | Sem recodificação | Não atende contrato estéreo | ❌ |
| Mix mono | Um arquivo simples | Destrói separabilidade | ❌ |
| Estéreo derivado dos monos | Preserva canais e cadeia atual | Recodificação adicional | ✅ |
| Tracker Redis distribuído | Limite entre réplicas | Complexidade sem necessidade | ❌ |
| Limite compartilhado no processo | Suficiente para uma réplica | Não escala horizontalmente | ✅ |
| Porta 139 por default | Compatibilidade NetBIOS | Legado e exige modo diferente | ❌ |
| Direct TCP/445 configurável | Default moderno e explícito | Exige nome remoto correto | ✅ |

## Padrões aplicáveis

1. Strategy: `SMBBackupStrategy` encapsula conexão e operações remotas.
2. Módulo singleton lazy: limiter/circuit breaker compartilhados no processo.
3. Worker ARQ: cron e I/O bloqueante via `asyncio.to_thread`.
4. Atomic publish: tempfile no mesmo diretório + `os.replace`.
5. Retry: `tenacity` com tentativas 1s, 2s e 4s.
6. Observer: métricas e logs estruturados, sem segredo.
7. Repository: metadados de chamada consultados fora de rotas/handlers.

## Decisões não óbvias

1. Os monos locais continuam existindo porque STT e diagnóstico podem depender deles; o estéreo é derivado.
2. Nome final só aparece depois do rename, eliminando heurística de mtime.
3. O checksum compara o estéreo local com o remoto, não os monos com o remoto.
4. `.raw` não é enviado: a conversão é retentada e a falta permanece visível.
5. O truncamento de `call_id` para seis caracteres é compensado por timestamp/origem/destino e detecção de colisão.
6. ACL do auditor é responsabilidade do servidor, mas sua prova é requisito da entrega.

## Lacunas que só o E2E fecha

- `SMB_SERVER_NAME`, domínio/workgroup e política NTLM do servidor real;
- aceitação de Direct TCP/445;
- permissão real de mkdir/store/rename/delete;
- duração da recodificação estéreo e da leitura remota para SHA256;
- comportamento quando o share fica sem espaço;
- pressão do artefato estéreo adicional sobre o tmpfs.

## Evidência do spike de storage — 2026-07-28

O usuário configurou o `.env` privado e confirmou manualmente no storage:

- conexão e autenticação;
- acesso ao share e à pasta-base;
- criação de diretório;
- escrita e leitura de arquivo não sensível;
- rename;
- delete e limpeza do diretório de teste.

A porta `192.168.50.240:445` também foi confirmada como alcançável a partir do ambiente.

O spike não usou `pysmb==1.2.14` e não registrou SHA256. Portanto, ele reduz o risco de ACL e
conectividade, mas não fecha negociação SMB2, `SMB_SERVER_NAME`, NTLMv2, Direct TCP pelo cliente
Python, checksum remoto nem a negação de escrita da conta dos auditores.

## Revisão crítica multi-LLM — 2026-07-28

Foram aceitos os achados que alteram segurança, concorrência ou verificabilidade:

- dependências de preparação precisam obrigar a spec SDD antes de alterações em código/configuração;
- o teste manual com `smbclient` não substitui um mini-spike do cliente `pysmb==1.2.14`;
- ciclos ARQ precisam de exclusão explícita e resultado `already_running`;
- conversão/transferência precisa de lease expirável respeitado pelo cleanup;
- throttle deve usar `storeFileFromOffset`, truncando apenas o primeiro chunk;
- JSON vazio/corrompido precisa de recuperação observável;
- colisões do prefixo de seis caracteres precisam de sufixo determinístico e proibição de overwrite;
- o estéreo derivado deve ser apagado após checksum, preservando os monos.

O cross-check interno também foi incorporado: a afirmação histórica de múltiplos workers foi marcada
como superada no requirements, e a atualização tardia da spec deixou de ser declarada paralela à sua
criação.

### Decisões do clarify pós-auditoria

- O SLA de 30 s é limite bloqueante para geração estéreo + cópia, não apenas meta; o timeout de
  arquivo anterior de 60 s foi descartado.
- O lease usa UTC, dura 120 s e é renovado a cada 30 s. Lease inválido/corrompido é considerado
  expirado com alerta para evitar retenção indefinida.
- O log canônico fica em `/data/smb_logs/smb_transfer_log.json` e admite `pending`, `done` e
  `failed`.

Foram rejeitados ou reclassificados: ausência de código/testes antes da etapa coding não é defeito;
não há ciclo de dependências; publicação atômica já estava planejada; e a alegação de inexistência de
API por offset no `pysmb` é falsa. A documentação oficial registra `storeFileFromOffset` e opções de
assinatura em `SMBConnection`:

- https://pysmb.readthedocs.io/en/latest/api/smb_SMBConnection.html
- https://arq-docs.helpmanual.io/_modules/arq/cron
- https://arq-docs.helpmanual.io/_modules/arq/worker

## Investigação dos gates globais — 2026-07-30

### Evidência local e runtime

- Produção não possui `alembic_version`.
- `upgrade head` iniciou 001/002 e falhou em tabela existente; a transação foi revertida.
- Em banco vazio, 001 e 003 também colidem porque criam tabelas de chamada sem schema explícito.
- Os ramais são arquivos FreeSWITCH gerados por `scripts/import_extensions.py`, não linhas do banco.
- O acoplamento crítico é o UUID de PBX gravado em `freeswitch/conf/vars.xml`.
- A suíte global criou `tenant_test_schema` no banco operacional e não o removeu.

### Cross-check multi-LLM

- Claude Sonnet recomendou baseline pública, volume novo, preservação dos UUIDs, dump restaurado
  antes do corte e banco exclusivo para testes. Achados aceitos.
- DeepSeek classificou corretamente multitenancy como efeito colateral perigoso e recomendou
  separar unit/integration/E2E, mas omitiu parte das falhas WebSocket e interpretou alguns smokes
  de ambiente de forma incompleta. A ordem de isolamento foi aceita; a contagem não.
- Mimo identificou a colisão 001/003 e propôs bons testes de banco vazio, mas sua migration 004
  não poderia executar porque 003 falha antes dela, e a alegação de que Alembic não cria sua tabela
  de versão estava errada. A solução 004 foi rejeitada.

## Inventário Alembic dos ambientes conhecidos — 2026-07-31

O inventário partiu dos caminhos descobertos em `.reversa/context/surface.json`, exemplos
`.env.production.example`/`.env.staging.example`, artefatos de deploy e host operacional já
documentado.

| Ambiente conhecido | Origem da descoberta | Recurso consultado | `public.alembic_version` |
|--------------------|-----------------------|--------------------|--------------------------|
| Workspace local | árvore do projeto | nenhum PostgreSQL local declarado/ativo neste ambiente | não aplicável |
| Deploy operacional `10.10.10.11` | docs de deploy e labels Compose | `zenith-postgres`, banco `zenith` | ausente |
| Production example | `.env.production.example` | alias lógico `postgres`, sem host independente | não é ambiente implantado |
| Staging example | `.env.staging.example` | alias lógico `postgres`, sem host independente | não é ambiente implantado |

Não foi encontrado inventário, DSN ou host de staging/produção adicional. A consulta operacional
foi somente leitura. Como nenhum ambiente conhecido possui revisão aplicada, o squash da cadeia
local inválida pode prosseguir para uma baseline pública. Esta conclusão vale somente para os
ambientes conhecidos em 2026-07-31: se surgir qualquer banco com `alembic_version`, T058/T083/T084
ficam automaticamente suspensas e será necessário criar uma cadeia compatível, sem reescrever o
histórico aplicado.

A ausência de histórico **não** autoriza alterar o PostgreSQL atual. A porta 5433 publicada torna
impossível excluir consumidores externos inativos; por isso a baseline será provada em bancos novos
e o recurso atual continuará intacto.
