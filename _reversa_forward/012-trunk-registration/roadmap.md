# Roadmap: Registro de troncos ATA

> Identificador: `012-trunk-registration`
> Data: `2026-08-01`
> Requirements: `_reversa_forward/012-trunk-registration/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

A mudança adiciona `Condominium` e `ATATrunk` ao schema `public`, mantendo o escopo por tenant e PBX. A API administrativa concentra cadastro e importação CSV por serviços apoiados no `Repository`. A senha SIP é cifrada com chaves rotacionáveis e só é decifrada no endpoint interno que serve o diretório dinâmico do FreeSWITCH. Como o binding `directory` é exclusivo, o endpoint também oferece uma camada de compatibilidade somente leitura para os usuários já existentes em `extensions.xml`; colisões falham fechado. O consumidor ESL passa a ouvir os eventos Sofia reais e mantém o estado de registro; chamadas ativas são representadas por conjuntos idempotentes de UUIDs no Redis. As variáveis de tenant/PBX deixam de vir de `vars.xml` e passam a acompanhar o usuário ATA autenticado, sem alterar dígitos nem a bridge upstream existente.

## 2. Princípios aplicados

Não existe `.reversa/principles.md`. Foram aplicados os princípios confirmados em `_reversa_sdd/architecture.md#Princípios Arquiteturais` e os padrões obrigatórios do projeto.

| Princípio | Como a feature se relaciona | Status |
|-----------|------------------------------|--------|
| Isolamento de tenant | Chaves, consultas, constraints e respostas são tenant-scoped. | respeita |
| Repository | Regras e acesso a dados ficam em `src/services/trunks.py`, não nos routers ou handlers ESL. | respeita |
| Observer/event-driven | Estado operacional nasce de eventos Sofia e de canal, processados idempotentemente. | respeita |
| Singleton de módulo | Cliente de diretório/estado reutiliza `event_bus`, `esl_client` e `settings`; nenhuma classe Singleton explícita. | respeita |
| Spec-first e TDD | Specs SDD e testes Red antecedem migrations e código. | respeita |
| Segredos fora de artefatos | CSV real, senhas e chaves ficam em arquivos privados gitignored; docs usam apenas fixtures fictícias. | respeita |

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|---------------|--------------------------|-------------|
| D-01 | Criar `Condominium` e `ATATrunk` no schema `public`. | Tenant e PBX já vivem no schema público; o FreeSWITCH precisa resolver configuração entre tenants sem trocar `search_path`. | tabela por schema de tenant; JSON em PBX | 🟢 |
| D-02 | Usar `mod_xml_curl`, limitado ao binding `directory`, como autoridade de lookup, servindo troncos ATA do banco e usuários legados do `extensions.xml` privado. | O binding é exclusivo; a compatibilidade explícita preserva os registros existentes enquanto novos troncos usam o banco. | substituir todos os usuários de uma vez; consultar PostgreSQL diretamente do FreeSWITCH | 🟢 |
| D-03 | Carregar `mod_xml_curl` como primeiro item de `modules.conf.xml`, antes do `mod_sofia`, e validar sua presença no build/healthcheck. | O binding precisa existir antes do consumidor; `pre_load_modules.conf.xml` causou segfault reproduzível na imagem 1.10.12 durante T042. | pre-load incompatível; load tardio; assumir presença da imagem | 🟢 |
| D-04 | Proteger o endpoint XML com HTTP Basic dedicado, acesso via loopback do host, bloqueio explícito no proxy público, timeout de 2 s e `Cache-Control: no-store`; gerar o `xml_curl.conf.xml` real como arquivo gitignored e modo 0600 a partir do `.env`. | A resposta contém segredo SIP; nenhum valor Basic pode entrar no XML versionado ou no diff. | endpoint público com JWT; segredo hardcoded; XML estático como nova autoridade | 🟢 |
| D-05 | Cifrar senhas com `MultiFernet`, usando `TRUNK_CREDENTIAL_KEYS` privado e rotação pela ordem das chaves. | `python-jose[cryptography]` já fornece a dependência; rotação evita chave única imutável. | plaintext no banco; hash unilateral, incompatível com resposta de diretório | 🟢 |
| D-06 | Tornar prefixo opcional e único por tenant somente quando preenchido; manter `(sip_profile, auth_username)` único entre todos os troncos e rejeitar colisão legada. | O VitalPBX/ATA executa o roteamento e pode não exportar prefixo. A credencial identifica o tronco sem inventar dígitos; desabilitar não libera identidade silenciosamente. | usar auth username como prefixo; exigir export inexistente; usar IP de origem | 🟢 |
| D-07 | Manter `enabled` e histórico de registro no PostgreSQL; manter UUIDs de chamadas ativas em conjuntos Redis por tronco. | `SADD`/`SREM` tornam eventos duplicados idempotentes e `SCARD` impede contador negativo. | incrementar/decrementar inteiro; estado exclusivamente em memória | 🟢 |
| D-08 | Consumir `CUSTOM sofia::register`, `sofia::unregister` e `sofia::expire`, preservando temporariamente os eventos legados já assinados. | O catálogo oficial documenta esses eventos e cabeçalhos; `expire` cobre ausência de unregister explícito. | depender apenas de `SOFIA_REGISTER`; polling contínuo | 🟢 |
| D-09 | Reconciliar registros e canais no boot e após reconexão ESL por comandos Sofia controlados, marcando `unknown` antes da reconciliação. | Evita falso `registered` após janelas sem eventos. | confiar no estado persistido; exigir novo REGISTER | 🟡 |
| D-10 | Retornar variáveis `zenith_tenant_id`, `zenith_pbx_id`, `zenith_condominium_id` e `zenith_trunk_id` no usuário do diretório. | Remove a dependência de valores globais fixos e permite identificar eventos/canais. | inferir por prefixo; manter `vars.xml` fixo | 🟢 |
| D-11 | Preservar o dialplan de números e a bridge upstream; alterar apenas a origem das variáveis de contexto. | O escopo aprovado proíbe manipulação de dígitos e fila no Zenith. | novo roteador de chamadas; fila por condomínio | 🟢 |
| D-12 | Aceitar cadastro individual a partir de configuração privada e preservar o importador CSV opcional, ambos idempotentes pela identidade SIP quando não houver prefixo. | O VitalPBX não exporta troncos no ambiente real; exigir CSV bloquearia o rollout. | inferir prefixo; copiar segredo para XML; remover suporte CSV | 🟢 |
| D-13 | Não expor operação de exclusão física na primeira versão; desabilitar é o mecanismo de retirada. | Preserva auditoria e evita apagar um tronco durante chamada ou registro ativo. | DELETE imediato; cascade automático | 🟢 |
| D-14 | Implementar `LegacyDirectoryProvider` somente leitura, com parsing XML seguro, cache invalidado por `mtime` e resposta sem trunk metadata. | `mod_xml_curl` não faz fallback para arquivos; a camada preserva ramais existentes sem migrá-los nem alterar seu contrato. | ignorar usuários atuais; duplicar todos no banco nesta feature | 🟢 |

## 4. Premissas

Não há `[DÚVIDA]` pendente no `requirements.md`.

| Premissa | Origem (`requirements.md` seção) | Risco se errada |
|----------|----------------------------------|-----------------|
| O CSV real poderá ser adaptado ao contrato canônico documentado em `interfaces/trunk-csv.md`. | 10. Lacunas | Um layout nativo diferente exigirá apenas novo adaptador de colunas, não mudança do domínio. |
| A imagem final contém `mod_xml_curl.so`; sua presença será um gate antes de ativar a configuração. | 5. RF-05 | Se ausente, o build precisará instalar/copiar o módulo antes do deploy; a ativação fica bloqueada. |

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-----------------|--------|
| database | `_reversa_sdd/architecture.md#Princípios Arquiteturais` | regra-alterada | Adiciona condomínios e troncos públicos com constraints tenant-scoped e segredo cifrado. |
| services | `_reversa_sdd/code-analysis.md#services — Serviços de IA` | componente-novo | `TrunkService` concentra CRUD, importação, criptografia e resolução operacional via Repository. |
| legacy directory adapter | `_reversa_sdd/architecture.md#Papel do FreeSWITCH: B2BUA com Registration Forwarding` | componente-novo | Serve usuários privados existentes no backend exclusivo sem alterar nem persistir novamente suas credenciais. |
| api | `_reversa_sdd/code-analysis.md#api — Interface REST + WebSocket` | contrato-novo | API administrativa de condomínios/troncos e callback interno XML do FreeSWITCH. |
| telephony | `_reversa_sdd/code-analysis.md#telephony — Integração FreeSWITCH` | contrato-alterado | Consome eventos Sofia CUSTOM, reconcilia estado e associa canais a troncos. |
| FreeSWITCH | `_reversa_sdd/architecture.md#Papel do FreeSWITCH: B2BUA com Registration Forwarding` | contrato-alterado | Habilita autenticação de registro e diretório dinâmico nas entradas 5060/7060. |
| dialplan | `_reversa_sdd/code-analysis.md#Fluxo Principal de uma Chamada (atualizado)` | regra-alterada | Usa contexto vindo do usuário autenticado em vez de tenant/PBX globais. |
| observability | `_reversa_sdd/inventory.md#Módulos Identificados` | contrato-alterado | Métricas agregadas de registro/uso e logs sanitizados de transição. |

## 6. Delta no modelo de dados

- Resumo das mudanças: duas tabelas públicas (`condominiums`, `ata_trunks`), índices/constraints de isolamento e campos de histórico operacional; conjuntos Redis efêmeros para UUIDs ativos.
- Detalhe completo em: `_reversa_forward/012-trunk-registration/data-delta.md`

## 7. Delta de contratos externos

| Contrato | Tipo | Arquivo de detalhe |
|----------|------|--------------------|
| Administração de condomínios e troncos | HTTP | `_reversa_forward/012-trunk-registration/interfaces/trunks-api.md` |
| Diretório dinâmico FreeSWITCH | HTTP/XML | `_reversa_forward/012-trunk-registration/interfaces/freeswitch-directory.md` |
| Importação de troncos VitalPBX | arquivo CSV | `_reversa_forward/012-trunk-registration/interfaces/trunk-csv.md` |
| Eventos de registro e chamada | ESL | `_reversa_forward/012-trunk-registration/interfaces/freeswitch-events.md` |

## 8. Plano de migração

1. Criar e aprovar as specs SDD de `trunk-registry`, `trunk-admin` e `trunk-registration`.
2. Escrever testes Red de modelo, serviço, API, XML, eventos, segurança e configuração FreeSWITCH.
3. Adicionar migration pública `002_ata_trunks`, validar upgrade repetido no banco isolado e ensaiar downgrade sem dados reais.
4. Implementar modelos, criptografia, serviços e API administrativa sem ativar autenticação nos profiles.
5. Validar `mod_xml_curl` na imagem, gerar a configuração privada por script e configurar callback interno com fixture fictícia; manter binding desativado em produção.
6. Provar que o backend devolve os usuários legados atuais de forma equivalente e que colisões com troncos ATA são bloqueadas.
7. Importar uma extração privada de troncos em rehearsal e comparar contagens/constraints sem exibir credenciais.
8. Ativar diretório dinâmico primeiro no profile 7060, registrar um usuário legado e um ATA piloto, validar eventos, consulta e chamada.
9. ~~Ativar no profile 5060 após o piloto, preservando 5062 e gateways upstream.~~ **Descoposto em 2026-08-07:** o profile 5060 hospeda troncos PSTN externos reais; ativação de ATA nesse profile fica para feature dedicada futura. Ver `requirements.md#9-esclarecimentos`.
10. Remover o uso das variáveis globais de tenant/PBX somente após os metadados por tronco estarem comprovados em chamada E2E no profile 7060.
11. Manter rollback: restaurar profiles anteriores, remover o binding e recarregar XML; as tabelas novas podem permanecer inativas.

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| `mod_xml_curl` ausente na imagem | alto | médio | Gate de build/runtime antes de alterar profiles; não ativar produção sem `module_exists`. |
| Callback indisponível impede novos registros | alto | médio | Duas APIs healthy, timeout curto, rollout por profile e rollback sem migration reversa. |
| Binding exclusivo omite usuário legado | crítico | baixo | Provider legado obrigatório, comparação de todos os IDs e piloto legado antes da ativação. |
| Colisão de username no mesmo profile | alto | médio | Constraint operacional, relatório de importação e ativação bloqueada até resolver conflito. |
| Vazamento de senha em log/XML/debug | crítico | baixo | Cifra, sanitização, endpoint interno, `no-store`, debug XML desligado e teste de regressão por canário secreto. |
| Evento perdido deixa estado incorreto | médio | médio | Estado `unknown` na desconexão e reconciliação no boot/reconnect. |
| Evento duplicado produz contador inválido | médio | médio | Conjuntos Redis por UUID e testes de duplicidade/ordem. |
| Escopo cruza tenants por prefixo repetido | crítico | baixo | Tenant do JWT nas APIs e IDs autenticados nas variáveis de canal; nunca resolver apenas por prefixo. |
| Alteração do profile interrompe ramais atuais | alto | médio | Piloto em 7060, rescan/restart controlado por profile e rollback imediato do XML. |
| CSV real diverge do contrato | médio | médio | Dry-run, aliases explícitos e amostra privada antes da importação efetiva. |

## 10. Critério de pronto

- [ ] Specs SDD ativas e anteriores ao primeiro código
- [ ] Todos os testes Red demonstrados antes do Green
- [ ] Migration aplica duas vezes no banco isolado sem tocar `zenith-postgres`
- [ ] CRUD/importação comprovam isolamento de tenant e idempotência
- [ ] Senha ausente de respostas, logs, métricas, erros e artefatos
- [ ] `mod_xml_curl` presente, endpoint não acessível pelo proxy público e timeout comprovado
- [ ] Configuração Basic real gitignored/0600 e nenhum segredo no diff
- [ ] Todos os usuários legados resolvidos pelo backend e um registro legado real preservado
- [ ] Registro/desregistro/expiração reais comprovados no profile 7060 (5060 descoposto em 2026-08-07 — troncos PSTN externos reais no profile, ver `requirements.md#9-esclarecimentos`)
- [ ] Chamadas simultâneas e eventos duplicados não produzem contador negativo
- [ ] Chamada E2E preserva dígitos e recebe IDs de tenant/PBX/condomínio/tronco corretos
- [ ] Rollback de configuração ensaiado sem excluir dados
- [ ] Suite global com cobertura ≥ 80% e veredito independente sem bloqueios
- [ ] Todas as ações do `actions.md` marcadas `[X]`
- [ ] `cross-check.md` sem CRITICAL nem HIGH
- [ ] `regression-watch.md` gerado
- [ ] Adendo pós-coding gerado por `/reversa-sync`

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-08-01 | Versão inicial gerada por `/reversa-plan` | reversa |
| 2026-08-07 | Item 9 do plano de migração e critério de pronto ajustados: ativação real restrita ao profile 7060, 5060 descoposto (troncos PSTN externos reais descobertos no profile) | reversa |
