# Legacy Impact: Bootstrap FreeSWITCH (container saudável)

> Identificador: `004-bootstrap-freeswitch`
> Data: `2026-06-24`

## Arquivos afetados

| Arquivo afetado | Componente (`_reversa_sdd/architecture.md`) | Tipo | Severidade | Justificativa |
|------------------|----------------------------------------------|------|------------|----------------|
| `freeswitch/conf/vars.xml` (novo) | FreeSWITCH | componente-novo | LOW | Variáveis globais que faltavam para qualquer config resolver `$${...}` |
| `freeswitch/conf/freeswitch.xml` (novo) | FreeSWITCH | componente-novo | HIGH | Ponto de entrada raiz ausente — sem ele o processo não carrega nenhuma config |
| `freeswitch/conf/autoload_configs/acl.conf.xml` (novo) | FreeSWITCH | componente-novo | LOW | ACL `rfc1918` já referenciada por `internal.xml`, mas inexistente |
| `freeswitch/conf/autoload_configs/event_socket.conf.xml` (novo) | FreeSWITCH / ESL | componente-novo | MEDIUM | Sem isso, a porta ESL 8021 nunca abre (pré-requisito de ciclo futuro, não bloqueante para boot básico) |
| `freeswitch/conf/autoload_configs/sofia.conf.xml` (novo) | FreeSWITCH | componente-novo | HIGH | Descoberto durante a execução (D-05) — sem ele, `sip_profiles/internal.xml` (já existente) nunca seria carregado por `mod_sofia` |
| `freeswitch/conf/directory/default.xml` (novo) | FreeSWITCH | componente-novo | LOW | Placeholder mínimo, sem usuários reais |
| `freeswitch/conf/sip_profiles/internal.xml` | FreeSWITCH | regra-alterada (efetiva via T001, sem edição direta do arquivo) | LOW | `$${domain}` passa a resolver para `zenith.local` |
| `freeswitch/conf/autoload_configs/modules.conf.xml` | FreeSWITCH | regra-alterada | MEDIUM | `mod_esl` (módulo inexistente) trocado por `mod_event_socket`; `mod_audio_fork` removido temporariamente (ver `docker-compose.app.yml` abaixo) |
| `docker-compose.app.yml` | infra/deployment | regra-alterada | HIGH | Serviço `freeswitch` trocado de `build:` customizado para `image: safarov/freeswitch:1.10.12` (vanilla), temporariamente, por token SignalWire inválido (D-06) |
| `_reversa_sdd/gaps.md` | (documentação) | regra-alterada | n/a | GAP-11 atualizado para "confirmado bloqueado"; GAP-16 e GAP-17 novos |
| `_reversa_sdd/infra/deployment/design.md` | infra/deployment | regra-alterada | n/a | Documenta boot básico validado e risco do token SignalWire confirmado |

## Diff conceitual por componente

**FreeSWITCH (container).** Antes desta feature, a config em `freeswitch/conf/` era um subconjunto incompleto (3 arquivos) que dependia implicitamente da config padrão da imagem base — mas o bind mount `./freeswitch/conf:/etc/freeswitch` no compose substitui essa config por inteiro, então o container provavelmente nunca chegou a inicializar de fato. Agora a árvore de config é autocontida e bootável (vanilla layout do FreeSWITCH 1.10.x), validada com um boot real e estável.

**infra/deployment.** O risco "ainda não validado" de GAP-11 (`mod_audio_fork` ausente da imagem vanilla, build customizado pendente) deixou de ser uma incerteza e passou a ser um fato confirmado: o token SignalWire atual está inválido. Como decisão de produto para este ciclo, o serviço `freeswitch` roda hoje sem o módulo de gravação — não há regressão de funcionalidade de gravação porque ela nunca esteve funcional (GAP-11 já apontava isso desde 2026-06-22).

## Preservadas

- Todas as regras 🟢 de `_reversa_sdd/domain.md` permanecem intactas — esta feature não tocou em nenhuma regra de domínio (multitenancy, STT fallback, consenso, etc.), só em configuração de infraestrutura de telefonia.
- `dialplan/default.xml` não foi alterado nesta feature (a correção da colisão `bypass_to_pbx`/`zenith_audio_fork` e a lógica de gateway por ramal continuam pendentes para ciclos futuros, conforme já registrado em conversa anterior, fora do escopo de `004-bootstrap-freeswitch`).

## Modificadas

- **GAP-11** (`_reversa_sdd/gaps.md`): de "em resolução, pendente validação" para "confirmado bloqueado" — mudança de confiança 🟡 → 🔴 sustentada por evidência real (build executado, 401 Unauthorized).
- **`infra/deployment/design.md`**: a seção de risco do `mod_audio_fork` passou de inferência (sem Docker disponível para testar) para fato confirmado com data e ambiente de teste.
