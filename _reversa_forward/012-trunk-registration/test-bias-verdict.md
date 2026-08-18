# Veredito independente de testes — feature 012

> Gate: T021, revisão pré-Green
> Data: 2026-08-03

## Revisores reais

- Claude Code 2.1.220, modelo `sonnet`, modo somente leitura, lente de segurança e isolamento multi-tenant.
- OpenCode 1.17.18, modelo `opencode/deepseek-v4-flash-free`, modo somente leitura solicitado, lente de contratos FreeSWITCH/XML Curl/ESL/migration/CSV.

Nenhum dos revisores editou o workspace e nenhum segredo real foi fornecido ou lido.

## Convergência

Ambos encontraram os mesmos quatro bloqueios substantivos:

1. O teste estático da migration proibia `tenant_`, tornando também `tenant_id` ilegal e incentivando uma implementação ofuscada.
2. Os testes do callback e do router não provavam autenticação HTTP, tenant-scoping, `no-store`, falha fechada e erros sanitizados.
3. Os testes Redis reafirmavam valores fixados no mock, sem provar a idempotência de `SADD`/`SREM`.
4. A importação não provava dry-run, reexecução idempotente nem falha estrutural antes de persistir.

Também convergiram na ausência de provas para colisão global de `(sip_profile, auth_username)`, prefixo duplicado no tenant e indisponibilidade ESL.

## Correções aplicadas antes do Green

- Migration: a condição impossível foi removida; foi acrescentada execução repetida em PostgreSQL descartável, inspeção de tabelas públicas e prova de que nenhum schema tenant é criado.
- Callback: foram acrescentados testes HTTP para Basic ausente, `no-store`, not-found, colisão DB/legado fail-closed e 503 sanitizado sem canário.
- API administrativa: foram acrescentados RBAC e prova de que o tenant vem somente do token.
- Redis/ESL: um fake com semântica real de conjunto substituiu os retornos tautológicos; TTL de 24 h e indisponibilidade ESL passaram a ser contratos.
- Importação: foram acrescentados dry-run sem persistência, reexecução via upsert idempotente e erro estrutural antes de qualquer escrita.
- Serviço: foram acrescentadas colisão global opaca entre tenants e duplicidade de prefixo dentro do tenant.
- Profiles: o teste agora verifica `accept-blind-auth=false` nos profiles-alvo e preservação do 5062, em vez de procurar uma referência impossível ao módulo dentro do profile.

## Divergências e decisão

Claude classificou o teste de equivalência do 5062 pelo provider legado como bloqueante; DeepSeek o tratou como parte do gate integrado. A decisão é mantê-lo no gate T055, que exige comparação integral do `extensions.xml` e registro legado real no ambiente isolado. Antes disso, o provider permanece coberto unitariamente e a colisão entre fontes falha fechado no callback.

Testes de concorrência Redis/ESL, parsing XML estrutural das configurações e maior profundidade de `None`/encoding permanecem como reforços pós-Green do T048. Eles não substituem os checkpoints reais T042–T046/T055.

## Veredito

Os bloqueios pré-Green foram incorporados aos testes e o Red foi revalidado: 52 falhas esperadas por implementação ausente e 1 teste de banco isolado pulado porque o DSN seguro não está configurado no ambiente local. O núcleo pode iniciar; a confirmação final continua condicionada ao veredito pós-Green T048, cobertura, Alembic e checkpoints reais.

## Adendo independente T042 — envelope e eventos reais

Após o spike isolado, `opencode/deepseek-v4-flash-free` e `opencode/nemotron-3-ultra-free` revisaram o delta em modo somente leitura. Uma tentativa com Claude Sonnet não produziu resposta no timeout e foi descartada, sem substituir seu resultado por inferência.

Os revisores identificaram viés inicial: o endpoint era testado com `sip_profile_name`/`user`, não com o envelope real; `key_value` tinha duplo papel; precedência de aliases e `sofia::expire` real não estavam cobertos. As correções adicionaram:

- teste HTTP ponta a ponta com `sip_profile`, `sip_auth_username` e `key_value` como domínio;
- teste de precedência dos campos canônicos e rejeição de domínio como username;
- regressão do `method=POST` literal;
- fixture do evento `sofia::expire` com `profile-name` e `user`/`username`.

Revisão final independente: nenhum bloqueio restante no escopo T042; 26 testes focados verdes. Este adendo não antecipa o gate pós-Green T048, que continua condicionado ao E2E dos ATAs e à auditoria de segredos.

## Adendo independente T043 — prefixo opcional e importação individual

O OpenCode 1.17.18 com `opencode/nemotron-3-ultra-free` revisou código e testes em modo somente leitura. DeepSeek foi descartado após erro 503 antes do parecer; North Mini foi descartado por desvio de escopo; Claude Sonnet foi descartado após 300 segundos sem resposta. Nenhum modelo editou arquivos ou recebeu o segredo privado.

O parecer válido encontrou um defeito reproduzível: `upsert_imported` priorizava o prefixo quando presente, embora `(sip_profile, auth_username)` seja a identidade canônica. Um teste Red reproduziu a busca incorreta; a implementação passou a resolver sempre pela identidade SIP e a suíte focada terminou com 76 testes aprovados e 1 integração local ignorada.

A revisão final confirmou a correção e levantou duas suspeitas bloqueantes que foram refutadas por testes explícitos: o fluxo completo de `update` rejeita identidade pertencente a outro tenant sem escrever, e o parser da configuração individual sempre produz `prefix=None`. Permanecem como reforços de T048 a concorrência real contra constraints PostgreSQL e a tradução explícita de `IntegrityError`; não bloqueiam T043, que persiste um único tronco desabilitado.

Veredito do orquestrador: T043 liberada; ativação SIP permanece condicionada a T055 e ao checkpoint humano T044.

## Adendo independente T055 — fragmentos XML legados

O arquivo privado real revelou uma característica não coberta pelos fixtures iniciais: ele é um fragmento de include com múltiplos `<user>` no nível raiz. O provider falhou fechado antes de qualquer resposta; spec e teste Red foram atualizados antes da implementação da raiz sintética somente em memória.

O `opencode/nemotron-3-ultra-free` revisou a correção em modo somente leitura e liberou a parte de comparação T055. O parecer recomendou fuzzing adicional, validação estrutural e cache por conteúdo; esses reforços seguem para T048. Alertas sobre caixa mista de DTD e `resolve_entities=False` foram descartados por evidência: a busca usa `lower()` e esse parâmetro pertence ao lxml, não ao `xml.etree.ElementTree` empregado aqui.

Resultado sanitizado: 939 identidades únicas, zero ausentes, zero divergências, zero respostas acima de 64 KiB; 77 testes focados verdes e 1 integração local ignorada. T055 continua aberta exclusivamente pela prova de registro SIP legado real.

### Fechamento da prova SIP legada

O primeiro parecer sobre o cliente SIP apontou falta de cobertura para challenge sem qop e confusão potencial entre `auth` e `auth-int`. Os dois casos foram transformados em testes Red e corrigidos; a execução real foi repetida com REGISTER 200 e remoção 200. Uma tentativa de revalidação com Nemotron falhou por `ResourceExhausted` antes do parecer e foi descartada. O modelo independente `opencode/mimo-v2.5-free` revisou o patch final e liberou T055, registrando como melhoria não bloqueante um known-answer test do MD5 e mais caminhos de erro de rede para T048.

Veredito final T055: liberada estritamente para o contrato de comparar todos os usuários e comprovar um registro legado real. Isso não libera o tronco 1020, que permanece desabilitado até o checkpoint humano T044.

## Adendo independente T048 — veredito pós-Green

> Data: 2026-08-08. Escopo: toda a implementação da feature (post-Green), sobre `services/trunks.py`, `trunk_import.py`, `trunk_credentials.py`, `legacy_directory.py`, `api/routers/trunks.py`, `api/freeswitch_directory.py`, `telephony/esl_client.py`, `telephony/trunk_state.py`, `database/models.py`.

### Revisores reais

- Claude Code (CLI, `claude -p --model sonnet`, instância nova, ferramentas restritas a `Read,Grep,Glob`), lente de segurança/isolamento multi-tenant e viés de teste.
- OpenCode 1.17.18, `opencode/nemotron-3-ultra-free`, agente `plan` (somente leitura), lente de contratos FreeSWITCH/XML Curl/ESL/cifra.

Nenhum dos dois editou o workspace; nenhum segredo real foi fornecido.

### Achados confirmados e corrigidos (Claude Code)

1. **`POST /trunks/import` não tratava erro de linha** — uma linha ruim no meio do lote (condomínio de outro tenant, identidade duplicada, prefixo malformado) derrubava a requisição inteira com 500, sem reportar `errors[]`/`rejected`, deixando linhas anteriores já commitadas (cada `Repository.create` comita individualmente). Corrigido em conformidade com o contrato **já especificado** em `design.md` ("erros de linha são reportados sem linha bruta ou senha") e `interfaces/trunks-api.md` (`errors:[{"line":7,"code":...,"field":...}]`) — não foi preciso alterar spec, só implementar o que já estava descrito.
2. **`POST /trunks`/`POST /condominiums` não tratavam `ValueError` simples do service** — `invalid_prefix`/`invalid_password`/`invalid_sip_configuration` derrubavam com 500 em vez do `400` já documentado em `design.md#Erros`. Corrigido generalizando o `except` para `ValueError` (que já engloba `ScopeValidationError`/`DuplicateIdentityError` por herança).
3. **Corrida real contra constraint única do Postgres nunca era traduzida (TOCTOU)** — `_ensure_unique` é check-then-act; dois `POST`s concorrentes com mesma identidade, mesmo prefixo ou mesmo `external_id` de condomínio bateriam no `IntegrityError` cru do banco, vazando como 500. Corrigido na camada `Repository` (`services/base.py`): `IntegrityError` do SQLAlchemy vira `IntegrityConstraintError` (genérico, sem acoplar o domínio ao dialeto SQL), traduzido em `TrunkService`/`CondominiumService` para `DuplicateIdentityError`/`ValueError` conforme o nome da constraint.
4. **`TrunkService.update()` não revalidava identidade/prefixo** — inofensivo hoje (o único chamador, `upsert_imported`, nunca muda identidade nem prefixo), mas o método aceita esses campos como mutator genérico. Resolvido pela mesma tradução de `IntegrityConstraintError` do item 3 aplicada também a `update()`: a constraint `ck_ata_trunks_prefix_digits`/os índices únicos do banco continuam protegendo mesmo sem um segundo check-then-act na aplicação (decisão consciente de não duplicar a validação).
5. **Senha só-espaço passava** — `if not password` não pega `" "` (truthy em Python). Corrigido na fonte única de verdade (`TrunkService.create`/`update`, não no parser do CSV) para `if not password or not password.strip()`, cobrindo tanto a importação quanto o `POST /trunks` direto.

Todos os cinco foram verificados contra o código real antes de qualquer teste Red, e cada um ganhou teste Red→Green dedicado (13 testes novos: `test_base.py` ×2, `test_trunks.py` ×6, `test_condominiums.py` ×1, `test_trunk_import.py` ×2, `api/routers/test_trunks.py` ×1, além de reforço em `test_trunks.py` para senha-vazio).

### Achados do OpenCode refutados por evidência

Duas alegações na seção de cifra Fernet estavam **factualmente erradas** e foram descartadas após leitura direta do código: `Fernet(key)` já valida formato/tamanho **no construtor** de `TrunkCredentialCipher.__init__` (dentro do próprio `try`), não "só no primeiro encrypt/decrypt"; e `MultiFernet.rotate()` já tenta descriptografar com **todas** as chaves da lista antes de recriptografar com a primária — não existe a ausência de fallback alegada.

Quatro categorias inteiras foram classificadas como "BLOQUEANTE" pelo OpenCode e reclassificadas para reforço não-bloqueante ou rejeitadas, seguindo o mesmo padrão de decisão explícita já usado nas rodadas T021/T055 deste documento:

- **Concorrência real Redis/ESL** — pede profundidade de teste contra um mecanismo já comprovado por gate real: `_cmd_lock` e a conexão de comando separada existem exatamente para a corrida citada (com o motivo documentado em comentário no próprio código); o caminho reconectar→`_mark_trunks_unknown`→reconfirmar foi provado ponta a ponta no T044 com consumidor ESL cego. O gap de `CHANNEL_ANSWER` durante a janela de reconexão é do pipeline de gravação de chamada, fora do escopo de registro de troncos (feature 012). Reforço, fora de escopo.
- **Parsing XML "inseguro"** — bloquear `<!doctype` já fecha toda declaração `<!ENTITY` (billion-laughs e XXE externo dependem de DTD), refutado por evidência já na rodada T055 deste mesmo documento. O cache por `mtime` (vs. hash de conteúdo) é uma observação real mas estreita sobre um mount somente-leitura de propriedade do root: reforço.
- **Known-answer test de MD5 e caminhos de erro de rede no cliente SIP** — ambos miram `spike/legacy_sip_register.py` e `spike/trunk_sip_register.py`. O próprio propósito documentado desses arquivos é instrumentação de gate (T042–T046), não código de produção; o comando canônico de gate deste projeto exclui explicitamente `_reversa_forward/**/spike/` da coleta. "Mover para `src/telephony/sip_digest.py`" criaria superfície de produção nova sem necessidade — exatamente o que o princípio de não adicionar além do pedido proíbe. Rejeitado.
- **Viés de teste por asserção em chamada interna** (`assert_awaited_once_with` em vez de contrato observável) — parcialmente convergente com o veredito do Claude, mas aponta para um alvo diferente: Claude localizou viés em *caminhos de erro não cobertos que o próprio código também não trata* (acionável, corrigido acima); OpenCode aponta testes que já passam e testam "como" foi chamado. Refatorar testes verdes por estilo, sem defeito de comportamento por trás, não é o escopo de T048. Não implementado.

### Correção adicional pós-segunda revisão do advisor

Antes de commitar, o advisor apontou que o achado 1 do Claude foi corrigido só para o caminho CSV — `import_trunk_json_batch` (usado de verdade pelo `scripts/import_operational_trunks.py` no T044 para os troncos reais 1020/1780) tem o mesmo padrão de loop sem proteção, mas sob uma cláusula de spec **mais rígida**: `design.md#Importação VitalPBX Exportada` já exigia "tudo-ou-nada: qualquer item inválido rejeita a importação inteira, sem persistir nenhum item", que o código não cumpria (um `DuplicateIdentityError` no item 2 de 3 deixaria o item 1 persistido).

Corrigido com um pré-voo de validação: `TrunkService.validate_importable()` (novo método, reaproveita `_validate_create_inputs` extraído de `create()`) valida cada item do lote — incluindo unicidade, escopo e senha — **sem persistir nada**; só depois de todos os itens passarem é que o segundo laço persiste de fato. Resíduo aceito e documentado: uma corrida verdadeiramente concorrente entre o pré-voo e a persistência (janela pequena, mesma classe do TOCTOU do achado 3) ainda pode, em tese, deixar um item anterior persistido se uma outra requisição colidir nesse intervalo exato — mitigado pela mesma tradução de `IntegrityConstraintError`, não eliminado por transação. Não abre watch item por ser um refinamento do mesmo risco já aceito no achado 3, não um caso novo.

Também ajustados dois pontos de menor risco identificados na mesma revisão: o fallback de `_translate_trunk_integrity_error` rotulava qualquer constraint não reconhecida como `duplicate_auth_identity`, o que classificaria uma violação de FK (`condominium_id` apagado entre a validação de escopo e a escrita) como 409 em vez de 404 — corrigido para detectar `fkey`/`foreign key` na mensagem e traduzir para `ScopeValidationError("condominium_not_found")`; e `CondominiumService.update()` (hoje inalcançável via HTTP, `PATCH /condominiums/{id}` também é W006) passou a traduzir `IntegrityConstraintError` para `duplicate_external_id`, simetricamente ao que já foi feito em `TrunkService.update()`.

Spec-first: o contrato "constraint violation nunca escapa crua, é traduzida na fronteira do Repository" não estava descrito em nenhuma spec antes desta correção — adicionado a `_reversa_sdd/database/trunk-registry/design.md#Contrato Repository` (v1.1.0 → v1.2.0) antes do código correspondente, não depois.

6 testes Red adicionais (3 para `validate_importable`, 1 para o pré-voo tudo-ou-nada do lote, 1 para tradução de FK, 1 para `CondominiumService.update`), todos verdes.

### Suite completa

`pytest -v tests src` após todas as correções deste gate: **230 passed, 29 skipped, 10 failed, 3 errors de coleta** — mesma contagem de falhas/erros pré-existentes documentada no T056 (`smb`, `piper`, `langgraph`, `deepgram` ausentes do ambiente; nada relacionado a esta feature). Nenhuma regressão nova introduzida pelas correções deste gate.

### Veredito

Os cinco bloqueios reais do Claude, mais o gap do lote JSON encontrado numa segunda passada do advisor, convergiram para código+spec+teste corrigidos. As divergências do OpenCode foram resolvidas por evidência direta no código ou por decisão explícita de escopo, documentada acima. T048 fecha a feature 012 para o T049 (suíte global + cobertura + Alembic).

## Reavaliação independente — Fase 7 (2026-08-18)

A primeira revisão da correção W002/W004/W006/W007 foi **NO-GO** e reproduziu três HIGH:
movimentação de tronco cross-tenant/PBX, colisão de identidade com o diretório legado e erro Redis
propagado depois do commit de POST/PATCH. Também apontou payloads vazios/nulos e leitura Redis
sequencial. Todos ganharam contrato e testes antes da correção.

A segunda revisão, sobre o código corrigido, foi **GO**, sem CRITICAL/HIGH/MEDIUM. O revisor rodou
92 testes focados e probes próprios para os dois tipos de cross-scope, mudança isolada de profile,
RedisError em POST/PATCH/GET, clears anuláveis, reimportação e Compose/env. Ressalvas LOW: cutover
runtime não executável sem Docker neste ambiente e possibilidade de fan-out/log por item em listas
muito grandes; não bloqueiam o contrato atual.
