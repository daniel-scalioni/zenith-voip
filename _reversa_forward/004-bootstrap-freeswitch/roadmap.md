# Roadmap: Bootstrap FreeSWITCH (container saudável)

> Identificador: `004-bootstrap-freeswitch`
> Data: `2026-06-23`
> Requirements: `_reversa_forward/004-bootstrap-freeswitch/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

O container `freeswitch` (`docker-compose.app.yml`) monta `./freeswitch/conf` por inteiro sobre `/etc/freeswitch`, substituindo toda a config da imagem `safarov/freeswitch:1.10.12`. Hoje só existem 3 arquivos do projeto ali (`autoload_configs/modules.conf.xml`, `dialplan/default.xml`, `sip_profiles/internal.xml`), sem a base raiz (`freeswitch.xml`, `vars.xml`) que qualquer instância FreeSWITCH precisa para inicializar. A abordagem é completar essa base mínima seguindo o layout vanilla padrão do FreeSWITCH 1.10.x, sem tocar em nenhuma extensão/gateway/módulo de gravação — apenas o suficiente para o processo `freeswitchd` carregar e ficar estável. Validação final acontece no servidor real (`10.10.10.11`), e qualquer divergência de layout descoberta lá volta primeiro para esta spec antes de qualquer ajuste de código (`requirements.md#10`).

## 2. Princípios aplicados

`.reversa/principles.md` não existe neste projeto ainda — nenhum princípio formal a verificar. n/a.

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|----------------|--------------------------|-------------|
| D-01 | Criar `freeswitch.xml` raiz com includes padrão (`vars.xml`, `sip_profiles/*.xml`, `dialplan/*.xml`, `autoload_configs/*.xml`, `directory/*.xml`), seguindo o layout vanilla do FreeSWITCH 1.10.x | É o ponto de entrada que falta — sem ele o `freeswitchd` não tem onde começar a carregar a config | Copiar a config original de dentro da imagem `safarov/freeswitch:1.10.12` antes de escrever a nova (descartado: exige rodar a imagem só para extrair arquivos, mais lento que partir do layout padrão documentado e corrigir após validação real) | 🟡 |
| D-02 | `vars.xml` define `domain` como valor lógico fixo (não um domínio SIP real), `local_ip=auto` (detecção automática, adequado a `network_mode: host`), `external_rtp_ip`/`external_sip_ip` apontando para `$${local_ip}` neste ciclo | Não há domínio SIP real do tenant ainda (isso só entra no ciclo de gateway por ramal); interfones discam por extensão, não por domínio. `local_ip=auto` é o padrão recomendado do FreeSWITCH para `network_mode: host` | Hardcode de IP do host (descartado: o servidor real pode ter o IP mudado entre deploys) | 🟡 |
| D-03 | `event_socket.conf.xml` e `acl.conf.xml` entram neste ciclo (não no de ESL/gravação), mesmo não sendo estritamente bloqueantes para o boot | Evita reabrir `modules.conf.xml`/ACL num ciclo futuro só para isso; reduz risco de módulo ausente aparecer no log já neste ciclo | Deixar para o ciclo do ESL listener (descartado: criaria um segundo ponto de retorno à mesma pasta de config por algo de baixo custo agora) | 🟡 |
| D-04 | `directory/default.xml` fica como esqueleto/placeholder, sem usuários reais | Diretório real de usuários (interfones) só existe a partir do ciclo de gateway por ramal (`mod_xml_curl` + modelo `SIPExtension`, fora de escopo aqui) | n/a | 🟢 |
| D-05 | Criar `autoload_configs/sofia.conf.xml` (descoberto durante `/reversa-coding`, ausente do levantamento original) — é o arquivo que `mod_sofia` lê para carregar `sip_profiles/*.xml` via `<X-PRE-PROCESS cmd="include" data="../sip_profiles/*.xml"/>`; sem ele, `internal.xml` (já existente) nunca seria lido | Sem este arquivo, o container poderia até subir "estável" no sentido de não reiniciar, mas sem nenhum profile SIP ativo — não atende ao espírito de RF-06 (boot funcional do FreeSWITCH, não só do processo) | n/a | 🟢 |
| D-06 | Build customizado (`freeswitch/Dockerfile`, compila `mod_audio_fork` via repositório APT da SignalWire) falhou na validação real em `10.10.10.11`: `401 Unauthorized` ao autenticar com o token em `freeswitch/signalwire_token.txt` — GAP-11 confirmado como bloqueado de fato, não só "não validado". Como gravação está fora de escopo deste ciclo, a decisão é usar a imagem vanilla `safarov/freeswitch:1.10.12` diretamente (sem build customizado) só para este ciclo, e remover `mod_audio_fork` de `modules.conf.xml` (módulo não estaria presente nessa imagem) | Token inválido/expirado é algo que só o usuário pode resolver (conta SignalWire); não há ação de código que contorne isso. Bloquear todo o ciclo de boot básico por uma dependência de uma funcionalidade fora de escopo não se justifica | Tentar outras variações de autenticação contra o repositório SignalWire (descartado: não é decisão técnica, é credencial de conta de terceiros, fora do meu alcance) | 🟢 |

## 4. Premissas

Nenhuma — todos os `[DÚVIDA]` do `requirements.md` foram resolvidos em `/reversa-clarify` (ver `requirements.md#9`). n/a.

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-----------------|--------|
| FreeSWITCH (container) | `_reversa_sdd/c4-context.md#73` ("FreeSWITCH — Central telefônica, gera eventos ESL e envia áudio") | componente-alterado | Config local (`freeswitch/conf/`) passa de incompleta para bootável; nenhuma mudança de responsabilidade externa do componente nesta etapa |
| `infra/deployment` | `_reversa_sdd/infra/deployment/design.md` | regra-alterada | Risco "ainda não validado contra build real" (GAP-11, `mod_audio_fork`) permanece para ciclo futuro; este ciclo resolve um risco anterior e mais básico (boot da config raiz), que bloqueava até testar o GAP-11 |

## 6. Delta no modelo de dados

- Nenhuma mudança de modelo de dados nesta etapa — escopo é só configuração de infraestrutura do FreeSWITCH.
- Detalhe completo em: `_reversa_forward/004-bootstrap-freeswitch/data-delta.md` (n/a, gerado por completude do template).

## 7. Delta de contratos externos

Nenhum contrato HTTP/fila/gRPC afetado nesta etapa — sem mudança de API, sem `interfaces/`.

## 8. Plano de migração

1. Criar os arquivos de config novos (`vars.xml`, `freeswitch.xml`, `acl.conf.xml`, `autoload_configs/event_socket.conf.xml`, `directory/default.xml`) sem remover nada do que já existe.
2. Ajustar `sip_profiles/internal.xml` (domínio real) e `autoload_configs/modules.conf.xml` (`mod_event_socket`, sem `mod_xml_curl` ainda — fora de escopo deste ciclo).
3. Subir o container `freeswitch` isoladamente no servidor real (`10.10.10.11`, via SSH) e observar logs/estabilidade.
4. Se o boot falhar por divergência de layout, atualizar esta spec (`roadmap.md`/`data-delta.md` conforme o caso) com o ajuste descoberto antes de tocar no código de novo.

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Layout vanilla assumido (D-01) não corresponde ao que `safarov/freeswitch:1.10.12` espera | Médio (boot falha, precisa de iteração) | Médio | Validação real no servidor antes de fechar o ciclo; spec atualizada primeiro se divergir (`requirements.md#10`) |
| `network_mode: host` do container já é uma dívida técnica conhecida (`_reversa_sdd/telephony/design.md`, "sem isolamento de rede Docker") | Baixo para este ciclo (não é alterado aqui) | n/a | Fora de escopo — só registrar que continua valendo |
| `sip_profiles/internal.xml` declara `tls-cert-dir`/`tls-certificate`/`tls-private-key` apontando para `/etc/freeswitch/tls/`, mas essa pasta não existe; também declara dois `<param name="sip-port">` (5060 e 5061), o que é atípico (o segundo provavelmente deveria ser um `tls-sip-port` separado) | Médio (pode gerar erro/warning no profile `internal`, possivelmente impedindo bind na porta 5060) | Médio | Descoberto durante a investigação deste ciclo, mas fora do escopo das ações já aprovadas (T001-T012). Deixar a validação real (T008/T009) confirmar se é fatal; se for, abrir ação nova no `actions.md` (spec primeiro) antes de editar `internal.xml` |

## 10. Critério de pronto

- [ ] Todas as ações do `actions.md` marcadas `[X]`
- [ ] Container `freeswitch` sobe e permanece estável no servidor real (`10.10.10.11`), sem crash/restart loop
- [ ] `regression-watch.md` gerado
- [ ] Re-extração reversa: n/a para este ciclo (sem mudança de código de aplicação, só infra)

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-06-23 | Versão inicial gerada por `/reversa-plan` | reversa |
