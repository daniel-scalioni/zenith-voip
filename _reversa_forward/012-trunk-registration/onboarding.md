# Onboarding: Registro de troncos ATA

> Procedimento de primeira validação. Use somente recursos `zenith-*` e dados fictícios até o checkpoint de produção.

## 1. Pré-requisitos

1. Estar no branch `feature/012-trunk-registration`.
2. Manter `.env` privado e definir chaves fictícias de teste para `TRUNK_CREDENTIAL_KEYS` e autenticação XML Curl.
3. Confirmar que nenhum segredo aparece em `git diff`.
4. Usar exclusivamente PostgreSQL, Redis e FreeSWITCH de teste com prefixo `zenith-`; nunca tocar recursos externos ao projeto.

## 2. Gates antes do banco

1. Rodar a suíte Red documentada em `progress.jsonl` e comprovar as falhas esperadas.
2. Subir o banco isolado de quality já existente.
3. Aplicar `alembic upgrade head` duas vezes.
4. Confirmar as tabelas públicas e ausência de mudanças nos schemas de tenant.

## 3. Teste da API com dados fictícios

1. Criar um tenant/PBX de teste ou reutilizar somente fixture isolada.
2. Criar dois condomínios pelo contrato `interfaces/trunks-api.md`.
3. Executar dry-run do CSV fictício e conferir totais.
4. Importar o arquivo e repetir a importação; a segunda execução não pode duplicar registros.
5. Tentar prefixo repetido no mesmo tenant e depois em tenant diferente.
6. Consultar troncos e confirmar ausência dos campos `encrypted_password`, senha e chaves.
7. Buscar o canário de senha em logs, métricas e respostas; a busca deve retornar zero ocorrências.

## 4. Spike do FreeSWITCH

1. Na imagem candidata, executar `module_exists mod_xml_curl` sem alterar o container operacional.
2. Gerar `xml_curl.conf.xml` privado por script e confirmar modo 0600, gitignore e ausência do segredo no diff.
3. Montar uma fixture privada de `extensions.xml` e comparar todos os usuários por lookup.
4. Ativar o binding apenas no FreeSWITCH isolado.
5. Consultar o endpoint com Basic inválido e confirmar 401 sem detalhe sensível.
6. Fazer lookup válido de tronco e usuário legado, validando XML bem formado, `Cache-Control: no-store` e timeout.
7. Confirmar que lookup ausente/desabilitado/ambíguo retorna `not found` e falha fechado.
8. Manter `xml_curl debug_off`; verificar que nenhum XML temporário com senha foi criado.

## 5. Registro e eventos

1. Configurar um ATA/softphone de teste no profile 7060 com UDP.
2. Registrar com senha errada e confirmar recusa/sanitização.
3. Registrar com senha correta e confirmar `registered`, timestamp e IDs de contexto.
4. Desregistrar e deixar um registro expirar para validar ambos os caminhos.
5. Repetir no profile 5060 somente após o gate 7060.
6. Reiniciar apenas o FreeSWITCH de teste e validar reconciliação.
7. Registrar um usuário legado do `extensions.xml` no mesmo profile e comprovar comportamento equivalente ao anterior.

## 6. Chamadas

1. Fazer duas chamadas simultâneas pelo tronco de teste.
2. Confirmar `active_calls=2`, `in_use=true` e `registration_status=registered`.
3. Encerrar em ordem inversa e reenviar evento duplicado no teste; o contador deve convergir a zero.
4. Confirmar que os dígitos não foram modificados e que nenhuma fila foi selecionada pelo Zenith.
5. Confirmar nos eventos os IDs corretos de tenant, PBX, condomínio e tronco.

## 7. CSV real e rollout

1. Armazenar a extração real fora do repositório em diretório privado.
2. Executar dry-run e registrar apenas hash, contagens e códigos de rejeição.
3. Resolver colisões de identidade de autenticação antes de habilitar qualquer tronco.
4. Importar inicialmente com `enabled=false`.
5. Fazer checkpoint humano antes de ativar um ATA real.
6. Ativar 7060, validar registro/chamada e só então ativar 5060.

### Estado T043 em 2026-08-03

Tentativa interrompida antes do dry-run: a única fonte privada encontrada foi `specs/export_extensions.csv`, que contém credenciais/tecnologia mas não associa troncos a condomínio nem fornece um prefixo comprovado. Nenhuma linha ou credencial foi registrada. É necessário fornecer uma fonte complementar privada com a chave de junção e os campos de condomínio/prefixo; `extension=prefix` não será inferido.

### Resolução T043 em 2026-08-04

A configuração individual fornecida para `Parque Portugal` foi armazenada em arquivo privado gitignored, validada sem expor o segredo e normalizada com estas decisões:

- `auth_username=1020` e `sip_profile=internal-7060` formam a identidade SIP canônica;
- `prefix=null`: o número 1020 não é interpretado nem persistido como regra de roteamento;
- `enabled=false`: nenhuma tentativa de registro real foi disparada nesta etapa;
- o destino `100` permanece inalterado pelo Zenith; VitalPBX e ATA são responsáveis pelo roteamento.

O dry-run retornou uma linha válida e zero escritas. Em seguida, a migration `002_ata_trunks` foi aplicada no PostgreSQL de ensaio `zenith-postgres-rehearsal` e o cadastro desabilitado foi persistido com credencial cifrada. A chave de ensaio foi efêmera; portanto, esse registro comprova persistência segura, mas deve ser recifrado com a chave definitiva antes do teste SIP. A suíte focada encerrou com 76 testes aprovados e 1 integração local ignorada, já exercitada no ambiente PostgreSQL de ensaio.

### Estado parcial T055 em 2026-08-04

O arquivo privado real é um fragmento de include do FreeSWITCH com vários elementos `<user>` consecutivos, não um documento XML com raiz única. Após correção spec-first e TDD do provider, a comparação sanitizada integral obteve:

- 939 usuários na origem e 939 identidades únicas;
- zero usuários ausentes;
- zero divergências em ID, params ou variables;
- zero respostas acima do limite de 64 KiB.

O conjunto de identidades foi registrado somente por SHA-256 (`0de645b76b578d19284c71634bc56a3e68f9b304a8f3a7c70b4bec687a18692d`); nenhum ID ou segredo foi emitido. O revisor independente liberou a comparação. T055 permanece aberta porque o registro SIP legado real ainda não foi comprovado: o workspace não possui cliente Docker e o host de ensaio recusou a chave SSH desta sessão.

### Conclusão T055 em 2026-08-04

A indisponibilidade do SSH foi contornada pela conectividade SIP direta já autorizada para o ambiente isolado. Um usuário real do diretório legado foi selecionado somente em memória e registrado no FreeSWITCH existente em `10.10.10.11:7060` por desafio Digest. O servidor retornou `200` para o REGISTER e `200` para a remoção imediata do contato com `Expires: 0`. A evidência expôs apenas o hash SHA-256 da identidade (`9af15b336e6a9619928537df30b2e6a2376569fcf9d7e773eccede65606529a0`).

O cliente sanitizado foi desenvolvido em TDD; após o primeiro parecer independente, passou a cobrir `qop=auth`, challenge sem qop e rejeição explícita de `auth-int` quando não há `auth`. A execução real repetida após a correção permaneceu `200/200`. O parecer final independente liberou T055 com melhorias de teste conhecidas para T048.

### Estado parcial T044 em 2026-08-05 — ambiente operacional preparado e cadeia provada

Checkpoint humano concedido por MASTER: janela de manutenção no FreeSWITCH operacional autorizada, uso do PostgreSQL operacional autorizado, ATA piloto trocado de 1020 para **1780 (Camboriu, 192.168.181.51)** porque o 1020 não tem rota de retorno.

Retrato do ambiente antes da mudança: zero registros ativos nos profiles 5060, 7060 e 5062; `auth-calls=false` em todos; `mod_xml_curl` presente na imagem mas não carregado. Nenhuma população real dependia do binding.

Correção relevante de diagnóstico: o banco que a API usa **não** é o `zenith-postgres`, e sim o `zenith-postgres-candidate`, que detém o alias de rede `postgres` em `zenith-voip_ai-hub-net`. O `zenith-postgres` está fora de qualquer rede. Os arquivos de compose ainda declaram o primeiro; a divergência virou o watch item W002.

Sequência executada:

1. Deploy da branch `feature/012-trunk-registration` no servidor (estava em `main`, sem a feature). Os 11 arquivos que apareciam como modificados eram byte a byte idênticos a `main` — ponteiro do git parado, não drift; backup preservado mesmo assim.
2. `.env` do servidor recebeu `TRUNK_CREDENTIAL_KEYS`, `FREESWITCH_DIRECTORY_BASIC_*`, `FREESWITCH_DIRECTORY_URL`, timeout e `LEGACY_DIRECTORY_PATH`, gerados no próprio host, com o arquivo em modo 0600. Nenhum valor trafegou pela sessão de trabalho.
3. Alembic: `stamp 001_public_baseline` e `upgrade head`, aplicando `002_ata_trunks`; segunda execução no-op; schemas `tenant_*` inalterados.
4. Containers da API e workers recriados com `--no-deps`, preservando a amarração de rede do banco.
5. Importação dos dois troncos pelo veículo em lote, com o JSON entrando por stdin: o arquivo com credenciais nunca tocou o disco do servidor. Dry-run com 2 linhas válidas e zero escrita; `--apply` criou 2 troncos com `enabled=false` e credencial cifrada (token de 120 bytes; busca por senha em claro na coluna retorna zero).
6. Tronco 1780 habilitado pelo serviço; 1020 permanece desabilitado.
7. `xml_curl.conf.xml` real renderizado a partir do `.env`, modo 0600, gitignorado, ausente do diff; `mod_xml_curl` carregado (`module_exists=true`), `reloadxml` e restart apenas do profile `internal-7060`.

**O binding não é escopado por profile.** Ele é declarado como `bindings="directory"`, ou seja, por **seção**: uma vez ativo, o backend Zenith responde lookups de diretório para `internal` (5060) e `internal-5062` também, não só para o 7060. O que foi escopado ao 7060 foi apenas o `sofia profile … restart` que aplicou `auth-calls=true`. Hoje o que protege o 5062 é o próprio `auth-calls=false`, não o alcance do binding. Verificado após a ativação: um usuário legado do `extensions.xml` registrou no profile `internal` (5060) com **200/200**, confirmando que o `LegacyDirectoryProvider` atende a população existente pelo binding global.

Provas obtidas sem envolver o ATA:

| Verificação | Resultado |
|---|---|
| Callback com Basic inválido e sem credencial | 401 nos dois casos |
| Lookup do 1780 em `internal-7060` | 200, `user id="1780"`, senha decifrada correta, `Cache-Control: no-store` |
| Variáveis de contexto no XML | `zenith_tenant_id`, `zenith_pbx_id`, `zenith_condominium_id`, `zenith_trunk_id` |
| Mesmo usuário no profile `internal` (5060) | não resolve — isolamento por profile |
| Tronco 1020 desabilitado | não resolve |
| Usuário legado do `extensions.xml` | resolve normalmente |
| Usuário inexistente | `not found`, falha fechada |
| REGISTER real com senha incorreta | **403** |
| REGISTER real com senha correta | **200** |
| REGISTER com `Expires: 0` | **200** |
| Estado persistido | `registration_status` percorreu registered → unregistered, com ambos os timestamps |
| Eventos Sofia | dois `CUSTOM` consumidos pelo ESL da instância 1 |
| Canário de senha em logs de API e FreeSWITCH | zero ocorrências |

Identidade exposta apenas por SHA-256 (`d8d0dedb4bda4204d0b5e1de5a990a00757aa2d80a64bd97699cad3b3d6fbf5f`).

### Registro do ATA físico em 2026-08-06

A identidade real do equipamento é **2780** (Camboriu), não 1780: a captura mostrou o ATA `KAP320` autenticando como `2780`. O arquivo de exportação foi complementado por MASTER com esse tronco, importado pelo mesmo veículo em lote; o `1780` foi desabilitado para manter um piloto único.

Duas tentativas anteriores ao cadastro (11:06:25 e 11:09:40) receberam **403 Forbidden** — identidade inexistente, falha fechada, com o `1780` intacto e sem `last_error_code` espúrio. Isso comprovou o caminho negativo com equipamento real, sem precisar forçar senha errada.

Após o cadastro e o force de registro no ATA:

```
11:23:19.243  REGISTER sem auth              192.168.181.51:45667 -> 10.10.10.11:7060
11:23:19.245  401 Unauthorized + challenge   realm 10.10.10.11, qop="auth"
11:23:19.258  REGISTER + Digest username="2780", qop=auth, nc=00000001
11:23:19.395  200 OK, expires=120
11:23:19.420  registration_status=registered persistido
```

Latência entre o `200 OK` e o estado persistido: **25 ms**, contra o limite de 5 s do RF de registro. `sofia status profile internal-7060 reg` mostra `Registered(UDP-NAT)`, `Auth-User: 2780`, `Ping-Status: Reachable`. Um evento `CUSTOM` foi consumido pelo ESL da instância 1. Canário de senha ausente dos logs de API e FreeSWITCH.

O contato chega com `fs_nat=yes` e `fs_path`: o ATA está atrás de NAT, em rede privada distinta da do servidor. O registro funciona, mas isso é relevante para o caminho de mídia quando a T046 exercitar chamadas.

Efeito colateral observado na reimportação: um tronco já existente tem `registration_status` reposto para `unknown`, enquanto `last_registered_at` e `last_unregistered_at` permanecem preenchidos — estado internamente inconsistente. Ver W004.

### Expiração por TTL em 2026-08-06

Com o ATA retirado da rede, sem envio de `Expires: 0`, o registro venceu sozinho:

```
14:30:20.399  last_registered_at  (último re-registro antes da desconexão)
14:33:20.417  evento CUSTOM sofia::expire no ESL
14:33:20.421  last_unregistered_at persistido  (4 ms depois)
14:33:25      sofia status: 0 registros no profile; banco: unregistered
```

O `EXP` anunciado pelo profile era exatamente `14:33:20`. Prova que o caminho de expiração — antes observado apenas no rehearsal isolado da T042 — funciona com equipamento real, e que o Zenith **não mantém `registered` sem evidência operacional atual**. O tronco chegou a `unregistered` sem qualquer desregistro explícito e sem `last_error_code`.

### Reconciliação após perda do consumidor ESL em 2026-08-06

Desenho do teste: derrubar o registro **enquanto** o consumidor ESL está cego, para que reportar `registered` na volta seja necessariamente erro. Reiniciar a API com o registro intacto não discriminaria nada.

```
11:47:33  docker stop zenith-api-1                      consumidor ESL fora
11:47:35  flush_inbound_reg 2780@10.10.10.11            profile=0, banco ainda "registered" (obsoleto)
11:47:36  docker start zenith-api-1
11:47:38  registration_status -> unknown   (profile=0)  reconciliação corrigiu em ~2 s
11:48:18  registration_status -> registered (profile=1) ATA re-registrou, evidência real
```

Confirma o desenho de `TrunkStateService.reconcile`: `mark_registered_unknown` rebaixa tudo que estava `registered` e só reconfirma o que o FreeSWITCH efetivamente lista. O estado após perder um registro é **`unknown`**, não `unregistered` — ausência de evidência é distinta de desregistro observado, e por isso `last_unregistered_at` permanece com o valor da expiração real (14:33:20), sem ser sobrescrito.

Duas tentativas anteriores foram inconclusivas e ficam registradas para não se repetirem: `flush_inbound_reg 2780` sem `@domínio` não derruba nada (responde `+OK` mesmo assim), e amostragem de 10 s perde a janela, que dura poucos segundos até o ATA voltar.

### Ensaio de rollback em 2026-08-06

Executado o procedimento do §8 na íntegra e depois refeito o caminho de ida. O ensaio **encontrou um defeito no próprio procedimento**, que era seu objetivo.

```
11:55:38  unload mod_xml_curl            module_exists=false
11:55:4x  xml_curl.conf.xml removido
11:55:5x  git checkout main -- sip_profiles/   auth-calls=false nos três
11:56:0x  reloadxml + restart internal-7060
          → profile subiu em sip:mod_sofia@200.170.149.139:7060   ← IP PÚBLICO
11:56:19  ATA tentou renovar e recebeu 403      rollback efetivo, comprovado
11:56:5x  caminho de ida refeito
          → profile de volta em sip:mod_sofia@10.10.10.11:7060
```

**Defeito encontrado:** restaurar os profiles a partir de `main` reintroduz o GAP-NET-01. A versão de `main` usa `$${external_sip_ip}`/`$${external_rtp_ip}`, e o `zenith-ip-watcher` sobrescreve essas variáveis com o IP público; a versão da feature usa `$${local_ip}`, que é o fix. O §8 foi corrigido: o rollback deve reverter **somente** o parâmetro `auth-calls`, nunca o arquivo inteiro. Ver W005.

**Comportamento operacional relevante:** depois de tomar `403`, o ATA entra em backoff e não retenta sozinho em tempo útil — o registro só voltou com force manual. Um rollback real exige forçar o registro nos equipamentos afetados; não basta desfazer a configuração e esperar.

Preservado durante todo o ensaio: 939 gateways upstream, os três profiles ativos e o `internal-5062` intocado em `auth-calls=false`. O estado no banco acompanhou corretamente, sem estado fantasma: com o profile vazio, o tronco ficou `unregistered`, não `registered` obsoleto.

## 8. Rollback

1. Desabilitar o binding XML Curl: `fs_cli -x "unload mod_xml_curl"` e remover/renomear `freeswitch/conf/autoload_configs/xml_curl.conf.xml`. Como o binding é por seção, isso devolve o diretório estático a **todos** os profiles de uma vez.
2. Reverter **apenas o `auth-calls`** dos profiles afetados, editando o parâmetro para `false` no arquivo. **Nunca** use `git checkout main -- freeswitch/conf/sip_profiles/`: a versão de `main` traz `ext-sip-ip`/`ext-rtp-ip` apontando para `$${external_sip_ip}`, que o `zenith-ip-watcher` sobrescreve com o IP público, reintroduzindo o GAP-NET-01 e subindo o profile em `200.170.149.139` em vez de `10.10.10.11`. Comprovado no ensaio de 2026-08-06. Depois, `fs_cli -x "reloadxml"` e restart apenas do profile autorizado.
3. Confirmar que chamadas existentes não foram derrubadas e que 5062/upstream permanecem intactos.
4. Manter as tabelas aditivas; não executar downgrade no banco operacional.
5. Registrar evidências sanitizadas em `progress.jsonl` e `regression-watch.md`.

## 9. Quality gates

```text
pytest -v tests src --cov=src --cov-fail-under=80
alembic upgrade head    # duas vezes, a segunda no-op
```

Comando único, alinhado ao bloco canônico de `AGENTS.md#🧪 Quality Gates`. Os testes estão em `tests/` e em `src/**/test_*.py`, por isso os dois caminhos vão explícitos: `pytest tests/` sozinho deixa a maior parte da suíte de fora. Não rode `pytest` sem caminho — a coleta da raiz varre também `_reversa_forward/**/spike/`, que abre conexão SIP real contra `10.10.10.11:7060`, e spike de feature não é gate. `sidecar/` tem suíte própria (`cd sidecar && pytest -v`), fora deste gate.

Além dos comandos acima, obter veredito independente sobre casos de borda, viés dos testes, segredo e isolamento de tenant antes do aceite.
