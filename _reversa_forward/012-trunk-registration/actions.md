# Actions: Registro de troncos ATA

> Identificador: `012-trunk-registration`
> Data: `2026-08-01`
> Roadmap: `_reversa_forward/012-trunk-registration/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 55 |
| Paralelizáveis (`[//]`) | 22 |
| Maior cadeia de dependência | 15 |

## Fase 1, Preparação

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T001 | Criar a spec SDD ativa de persistência para `Condominium`, `ATATrunk`, constraints, cifra e migration antes de código | - | [//] | `_reversa_sdd/database/trunk-registry/design.md` | 🟢 | [X] |
| [//] T002 | Criar a spec SDD ativa da API administrativa, importação CSV e endpoint interno sem exposição de segredo | - | [//] | `_reversa_sdd/api/trunk-admin/design.md` | 🟢 | [X] |
| [//] T003 | Criar a spec SDD ativa de autenticação Sofia, eventos, reconciliação e metadados por tronco | - | [//] | `_reversa_sdd/telephony/trunk-registration/design.md` | 🟢 | [X] |
| [//] T004 | Verificar somente leitura se a imagem candidata contém `mod_xml_curl` e registrar versão/resultado sem alterar o FreeSWITCH operacional | - | [//] | `_reversa_forward/012-trunk-registration/investigation.md` | 🟡 | [X] |
| T005 | Mapear uma amostra privada da exportação exclusiva de troncos para o CSV canônico, registrando apenas headers e contagens sanitizadas | T004 | - | `_reversa_forward/012-trunk-registration/investigation.md` | 🟡 | [X] |
| [//] T006 | Documentar placeholders de `TRUNK_CREDENTIAL_KEYS` e credencial XML Curl sem valor real | T001, T002 | [//] | `.env.example` | 🟢 | [X] |

## Fase 2, Testes

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T007 | Escrever testes Red dos modelos, FKs, checks e unicidade de prefixo/identidade no banco isolado | T001 | [//] | `src/database/test_trunk_models.py` | 🟢 | [X] |
| [//] T008 | Escrever testes Red da migration em banco vazio, banco com tenant/PBX e segunda aplicação no-op | T001 | [//] | `src/database/test_trunk_migrations.py` | 🟢 | [X] |
| [//] T009 | Escrever testes Red de cifra, decifra, rotação, chave ausente e token corrompido sem vazar canário | T001 | [//] | `src/services/test_trunk_credentials.py` | 🟢 | [X] |
| [//] T010 | Escrever testes Red do serviço de condomínios para isolamento, coerência de PBX e idempotência | T001 | [//] | `src/services/test_condominiums.py` | 🟢 | [X] |
| [//] T011 | Escrever testes Red do serviço de troncos para escopo, constraints, disable e atualização sem senha | T001 | [//] | `src/services/test_trunks.py` | 🟢 | [X] |
| [//] T012 | Escrever testes Red do importador CSV para dry-run, aliases, limites, erros por linha, idempotência e rollback | T002 | [//] | `src/services/test_trunk_import.py` | 🟢 | [X] |
| [//] T013 | Escrever testes Red da API administrativa para RBAC, tenant-scoping, 404 opaco, 409 e ausência de segredo | T002 | [//] | `src/api/routers/test_trunks.py` | 🟢 | [X] |
| [//] T014 | Escrever testes Red do callback XML para Basic auth, allowlist, XML escaping, not-found, no-store, timeout e canário | T002, T003 | [//] | `src/api/test_freeswitch_directory.py` | 🟢 | [X] |
| [//] T015 | Escrever testes Red de normalização dos eventos register/unregister/expire e transições idempotentes | T003 | [//] | `src/telephony/test_trunk_state.py` | 🟢 | [X] |
| T016 | Acrescentar testes Red de conjuntos Redis para chamadas duplicadas, fora de ordem, UUID ausente, TTL e contador não negativo | T015 | - | `src/telephony/test_trunk_state.py` | 🟢 | [X] |
| T017 | Acrescentar testes Red da reconciliação no boot/reconnect com respostas parciais, ambíguas e indisponíveis | T016 | - | `src/telephony/test_trunk_state.py` | 🟡 | [X] |
| [//] T018 | Escrever testes Red de configuração XML e renderer privado para pre-load, binding sem segredo versionado, modo 0600, profiles 5060/7060 autenticados e 5062 intacto | T003, T006 | [//] | `tests/test_trunk_freeswitch_config.py` | 🟢 | [X] |
| [//] T019 | Escrever teste Red para o dialplan preservar dígitos/bridge e não usar tenant/PBX globais | T003 | [//] | `tests/test_trunk_dialplan.py` | 🟢 | [X] |
| [//] T020 | Escrever testes Red das métricas agregadas sem labels de tenant, username, prefixo, IP ou segredo | T003 | [//] | `src/utils/test_trunk_telemetry.py` | 🟢 | [X] |
| [//] T053 | Escrever testes Red do provider legado para equivalência de usuários, XML malicioso, cache por mtime, arquivo ausente e colisão fail-closed | T002, T003 | [//] | `src/services/test_legacy_directory.py` | 🟢 | [X] |
| T021 | Obter revisão independente pré-Green sobre bordas, isolamento, autenticação e viés dos testes Red, corrigindo bloqueios antes do núcleo | T007, T008, T009, T010, T011, T012, T013, T014, T015, T016, T017, T018, T019, T020, T053 | - | `_reversa_forward/012-trunk-registration/test-bias-verdict.md` | 🟢 | [X] |

## Fase 3, Núcleo

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T022 | Implementar `Condominium` e `ATATrunk` com relationships e constraints declarativas para tornar T007 verde | T007, T021 | - | `src/database/models.py` | 🟢 | [X] |
| T023 | Implementar a revision pública `002_ata_trunks` alinhada aos modelos para tornar T008 verde | T008, T022 | - | `alembic/versions/002_ata_trunks.py` | 🟢 | [X] |
| [//] T024 | Implementar `TrunkCredentialCipher` com MultiFernet, rotação e erros sanitizados para tornar T009 verde | T009, T021 | [//] | `src/services/trunk_credentials.py` | 🟢 | [X] |
| T025 | Implementar serviços de condomínio e tronco via Repository com validação transitiva e invalidação de cache | T010, T011, T022, T024 | - | `src/services/trunks.py` | 🟢 | [X] |
| T026 | Implementar parser/importador CSV transacional, dry-run e relatório sanitizado | T012, T025 | - | `src/services/trunk_import.py` | 🟢 | [X] |
| T027 | Implementar router administrativo fino para condomínios, troncos, filtros e importação | T013, T025, T026 | - | `src/api/routers/trunks.py` | 🟢 | [X] |
| T054 | Implementar `LegacyDirectoryProvider` somente leitura com parsing seguro, cache por mtime e detecção de colisão | T053, T021 | - | `src/services/legacy_directory.py` | 🟢 | [X] |
| T028 | Implementar callback interno XML seguro, lookup por profile/username, fallback legado explícito e resposta fail-closed | T014, T025, T054 | - | `src/api/freeswitch_directory.py` | 🟢 | [X] |
| T029 | Implementar normalizador e máquina de estado de registro com persistência tenant-safe | T015, T025 | - | `src/telephony/trunk_state.py` | 🟢 | [X] |
| T030 | Implementar tracking de UUIDs ativos por tronco em Redis e consulta `active_calls`/`in_use` | T016, T029 | - | `src/telephony/trunk_state.py` | 🟢 | [X] |
| T031 | Implementar reconciliação de registros/canais no boot e após reconexão ESL | T017, T030 | - | `src/telephony/trunk_state.py` | 🟡 | [X] |
| [//] T032 | Implementar helpers Prometheus agregados de lookup, estado, reconciliação e chamadas | T020, T021 | [//] | `src/utils/telemetry.py` | 🟢 | [X] |
| [//] T033 | Implementar settings validados de chaves Fernet, Basic interno, URL e timeout XML Curl | T006, T009, T014 | [//] | `src/config.py` | 🟢 | [X] |
| T052 | Implementar renderer atômico do `xml_curl.conf.xml` real a partir do `.env`, com arquivo `.example`, modo 0600 e regra gitignore | T018, T021, T033 | - | `scripts/render_freeswitch_secrets.py` | 🟢 | [X] |
| T034 | Registrar routers e dependências no app sem iniciar listeners duplicados | T027, T028, T031, T033 | - | `src/main.py` | 🟢 | [X] |

## Fase 4, Integração

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T035 | Carregar `mod_xml_curl` antes do Sofia em `modules.conf.xml` e configurar binding `directory` privado, timeout 2 s e limite 64 KiB | T004, T018, T028, T033, T052 | - | `freeswitch/conf/autoload_configs/modules.conf.xml` | 🟢 | [X] |
| T036 | Habilitar autenticação segura de registros nos profiles `internal` e `internal-7060`, mantendo blind auth falso e 5062 inalterado | T018, T035 | - | `freeswitch/conf/sip_profiles/internal.xml` | 🟢 | [X] |
| T037 | Alterar somente a origem dos metadados no dialplan, preservando número, destino e bridge upstream | T019, T028, T036 | - | `freeswitch/conf/dialplan/default.xml` | 🟢 | [X] |
| T038 | Assinar eventos Sofia CUSTOM, integrar `TrunkStateService` e disparar reconciliação sem competir no socket ESL | T015, T017, T029, T030, T031 | - | `src/telephony/esl_client.py` | 🟢 | [X] |
| [//] T039 | Bloquear `/internal/` no proxy público e exigir presença do `mod_xml_curl` no gate do FreeSWITCH sem tocar recursos terceiros | T018, T035 | [//] | `docker-compose.app.yml` | 🟢 | [X] |
| T040 | Executar testes de migration no PostgreSQL isolado e provar que schemas de tenant não mudaram | T023 | - | `src/database/test_trunk_migrations.py` | 🟢 | [X] |
| T041 | Executar suíte unitária da feature e corrigir regressões até ficar verde | T024, T025, T026, T027, T028, T032, T034, T037, T038, T039, T040, T052, T054 | - | `src/`, `tests/` | 🟢 | [X] |
| T042 | Executar spike isolado do payload XML Curl e dos eventos Sofia, atualizando adaptadores somente com evidência real | T004, T035, T036, T038, T041 | - | `_reversa_forward/012-trunk-registration/investigation.md` | 🟡 | [X] |
| T043 | Normalizar a configuração privada individual do tronco 1020, executar dry-run sem inferir prefixo e cadastrar inicialmente desabilitado | T005, T026, T040, T041 | - | `_reversa_forward/012-trunk-registration/onboarding.md` | 🟢 | [X] |
| T055 | Comparar todos os usuários de `extensions.xml` com o backend e comprovar um registro legado real no ambiente isolado | T042, T054 | - | `_reversa_forward/012-trunk-registration/onboarding.md` | 🟢 | [X] |
| T044 | Após checkpoint humano, habilitar um ATA piloto 7060 e comprovar auth, estados, expiração, reconciliação e rollback | T042, T043, T055 | - | `_reversa_forward/012-trunk-registration/onboarding.md` | 🟡 | [ ] |
| T045 | Após sucesso do piloto 7060, repetir o gate em um ATA 5060 sem alterar o profile 5062 | T044 | - | `_reversa_forward/012-trunk-registration/onboarding.md` | 🟡 | [ ] |
| T046 | Executar E2E com chamadas simultâneas, eventos duplicados e prefixos iguais entre tenants, preservando dígitos e isolamento | T045 | - | `_reversa_forward/012-trunk-registration/onboarding.md` | 🟡 | [ ] |

## Fase 5, Polimento

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T047 | Auditar logs, erros, métricas, access logs e XML temporário com canário, eliminando todo vazamento de credencial | T028, T032, T038, T042 | - | `_reversa_forward/012-trunk-registration/security-verdict.md` | 🟢 | [ ] |
| T048 | Obter veredito independente pós-Green sobre casos de borda, viés, isolamento, cifra, XML e eventos; aplicar correções bloqueantes | T041, T046, T047 | - | `_reversa_forward/012-trunk-registration/test-bias-verdict.md` | 🟢 | [ ] |
| T049 | Executar suite global com coleta `tests/` e `src/**/test_*.py`, cobertura ≥80% e Alembic head duas vezes no banco isolado | T048 | - | `_reversa_forward/012-trunk-registration/progress.jsonl` | 🟢 | [ ] |
| T050 | Gerar `legacy-impact.md` e `regression-watch.md` com evidências reais, riscos de auth, variáveis, 5062, segredo e rollback | T049 | - | `_reversa_forward/012-trunk-registration/regression-watch.md` | 🟢 | [ ] |
| T051 | Preparar a convergência `/reversa-sync` somente após todas as ações e checkpoints reais estarem fechados | T050 | - | `_reversa_forward/012-trunk-registration/legacy-impact.md` | 🟢 | [ ] |

## Notas de execução

- T004, T005, T042, T043, T044, T045 e T046 dependem de ambiente ou evidência real; nunca marcar por inferência.
- T044 é checkpoint humano bloqueante para qualquer ativação de ATA real.
- `zenith-postgres` operacional não pode ser parado, recriado ou usado como banco de teste.
- O profile `internal-5062` e os gateways upstream são regressões protegidas, não alvos desta feature.
- Código e testes escritos pelo mesmo agente permanecem 🟡 até o veredito independente de T048.

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-08-01 | Versão inicial gerada por `/reversa-to-do` | reversa |
