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
