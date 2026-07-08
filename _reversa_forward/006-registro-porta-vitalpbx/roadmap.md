# Roadmap: Registro de Entrada na Mesma Porta do Cadastro VitalPBX

> Identificador: `006-registro-porta-vitalpbx`
> Data: `2026-07-08`
> Requirements: `_reversa_forward/006-registro-porta-vitalpbx/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

Hoje só existe o profile `internal` (porta 5060) para REGISTER de entrada. A abordagem escolhida (RN-01, esclarecimento de baixo acoplamento) é criar **um profile SIP novo por porta adicional** — `internal-7060` e `internal-5062` — em vez de multiplexar portas dentro do `internal` existente. Cada novo profile herda a mesma correção de domínio já validada nesta sessão (`force-register-domain=$${domain}`) e usa as mesmas variáveis dinâmicas de IP (`$${local_ip}`, `$${external_sip_ip}`) do profile `internal`. O diretório de usuários (`directory/extensions.xml`) já é compartilhado por todos os profiles via include global do FreeSWITCH, então nenhuma duplicação de credencial é necessária — o mesmo usuário 1001 autentica em qualquer porta. O gateway upstream por ramal já é gerado com a porta correta (`PORT_BY_TECH` em `import_extensions.py`), então RF-06 (upstream espelha a porta de entrada) já está coberto pela lógica existente e não precisa de mudança de código, apenas confirmação via teste.

## 2. Princípios aplicados

`.reversa/principles.md` está vazio neste projeto — nenhum princípio formal registrado ainda. A feature segue as convenções do `CLAUDE.md` (baixo acoplamento, sem SQL solto, sem segredo hardcoded) por serem regras de projeto, não princípios formais do Reversa.

| Princípio | Como a feature se relaciona | Status |
|-----------|------------------------------|--------|
| n/a — `principles.md` vazio | — | n/a |

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|----------------|---------------------------|-------------|
| D-01 | Criar profiles SIP novos e separados (`internal-7060`, `internal-5062`) em vez de múltiplas portas no profile `internal` | Esclarecimento do usuário: prioriza baixa acoplamento/alta coesão; profiles separados isolam blast radius — um `rescan`/restart de um não afeta o outro, mesmo padrão já usado entre `internal` e `upstream` | Multiplexar `sip-port` no mesmo profile `internal` (mais simples, mas acopla o ciclo de vida das portas) | 🟢 |
| D-02 | Replicar `force-register-domain=$${domain}` em cada novo profile | Mesma causa raiz identificada nesta sessão para o profile `internal` se aplica a qualquer porta nova — sem isso, softphones usariam o próprio endereço/porta como domínio do REGISTER e falhariam do mesmo jeito | Resolver domínio só no `internal` e deixar os novos profiles sem essa correção (reproduziria o bug) | 🟢 |
| D-03 | Diretório de usuários (`directory/extensions.xml`) permanece único e compartilhado entre todos os profiles internos | É assim que o FreeSWITCH já resolve usuários hoje (include global, não por profile); nenhuma duplicação de credencial necessária para o ramal 1001 registrar em 5060 ou 7060 | Duplicar entradas de usuário por profile (rejeitado: duplicação de senha, risco de dessincronia) | 🟢 |
| D-04 | Nenhuma mudança em `import_extensions.py` ou no gateway upstream — `PORT_BY_TECH` já gera a porta correta por tecnologia | RF-06 já é atendido pelo comportamento existente do script (`_reversa_sdd/telephony/design.md#Porta de destino no VitalPBX`); a feature é só sobre o lado de entrada | Reescrever a lógica de dedup/gateway (descartado, sem necessidade identificada) | 🟢 |
| D-05 | Cada novo profile aponta `sip-ip`/`rtp-ip` para as mesmas variáveis dinâmicas (`$${local_ip}`, `$${external_sip_ip}`) já usadas no `internal` | Mantém RF-05/RN-03: nenhuma porta nova pode depender de IP fixo, dado o ambiente de teste com IP externo variável (feature `005-dynamic-external-ip`) | Hardcodar IP/FQDN no novo profile (violaria RN-03 e quebraria em troca de ISP) | 🟢 |

## 4. Premissas

Nenhuma — todos os pontos de `[DÚVIDA]` do `requirements.md` foram resolvidos em `/reversa-clarify` antes deste plano.

| Premissa | Origem (`requirements.md` seção) | Risco se errada |
|----------|-----------------------------------|------------------|
| n/a | — | — |

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-------------------|--------|
| Profile SIP `internal-7060` | `_reversa_sdd/telephony/design.md#3. Perfis SIP do FreeSWITCH` | componente-novo | Novo profile FreeSWITCH escutando em 7060, espelha o `internal` (auth, domínio, IP dinâmico) |
| Profile SIP `internal-5062` | `_reversa_sdd/telephony/design.md#3. Perfis SIP do FreeSWITCH` | componente-novo | Novo profile FreeSWITCH escutando em 5062, mesmo padrão do `internal-7060` |
| Profile `internal` (5060) | `freeswitch/conf/sip_profiles/internal.xml` | regra-alterada (já feita nesta sessão) | `force-register-domain` já adicionado; nenhuma mudança adicional necessária nesta feature |
| `import_extensions.py` / gateway upstream | `_reversa_sdd/telephony/design.md#Porta de destino no VitalPBX` | sem mudança | `PORT_BY_TECH` já gera a porta upstream correta; RF-06 validado por teste, não por código novo |

## 6. Delta no modelo de dados

- Resumo das mudanças: nenhuma mudança em schema de banco de dados ou modelo de domínio da aplicação. O "dado" que muda é configuração de infraestrutura (arquivos XML de profile SIP do FreeSWITCH), não dado de negócio.
- Detalhe completo em: `_reversa_forward/006-registro-porta-vitalpbx/data-delta.md`

## 7. Delta de contratos externos

Não há contrato HTTP/fila/gRPC/GraphQL afetado — a mudança é inteiramente no protocolo SIP de entrada (REGISTER), já coberto pelos critérios de aceitação do `requirements.md#7`. Pasta `interfaces/` omitida.

## 8. Plano de migração

1. Criar `freeswitch/conf/sip_profiles/internal-7060.xml` como cópia adaptada de `internal.xml` (porta 7060, alias de domínio próprio, `force-register-domain`, ACL e includes de gateway equivalentes).
2. Criar `freeswitch/conf/sip_profiles/internal-5062.xml` seguindo o mesmo padrão para a porta 5062.
3. Validar com `sofia profile internal-7060 start` e `sofia profile internal-5062 start` sem impacto no profile `internal` já ativo (RF-02 — sem regressão em 5060).
4. Testar registro do ramal 1001 na porta 7060 (mesma credencial usada hoje em 5060) — caso de teste real definido em `/reversa-clarify`.
5. Confirmar que o gateway upstream do ramal 1001 permanece direcionado a `sip.maisalerta.tecnorise.com:7060` durante o teste (RF-06), sem necessidade de alterar `import_extensions.py`.
6. Documentar em `onboarding.md` o passo a passo para o operador migrar um ramal trocando apenas o endereço do servidor no aparelho.

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|-----------------|-----------|
| Três profiles de entrada (5060, 5062, 7060) competindo por ACL/porta no host com `network_mode: host` | médio | baixo | Cada profile usa porta distinta; sem overlap de bind, já confirmado pelo padrão `internal`/`upstream` existente |
| Duplicação de configuração entre `internal.xml`, `internal-7060.xml` e `internal-5062.xml` gerar dessincronia futura (ex: corrigir bug só em um) | médio | médio | Documentar explicitamente em comentário XML que os três profiles compartilham a mesma lógica de domínio/IP e devem ser atualizados em conjunto; considerar extração para include comum em iteração futura (fora de escopo aqui) |
| Teste no ramal 1001 causar interrupção temporária do ramal em uso (softphone real do usuário) | médio | médio | Testar fora de horário de uso ou avisar o usuário antes de cada tentativa de registro |

## 10. Critério de pronto

- [X] Todas as ações do `actions.md` marcadas `[X]`
- [ ] `cross-check.md` (se executado) sem CRITICAL nem HIGH — não executado, `/reversa-audit` é opcional e não foi solicitado
- [X] `regression-watch.md` gerado
- [X] Ramal 1001 registra com sucesso em 7060 usando a mesma credencial já usada em 5060, sem erro de domínio — validado ao vivo em 2026-07-08 (o mesmo aparelho migra de porta, não fica registrado nas duas simultaneamente, comportamento esperado)
- [X] Profile `internal` (5060) não sofre nenhuma interrupção durante a criação e ativação dos novos profiles `internal-7060`/`internal-5062` — confirmado `RUNNING` durante todo o teste
- [ ] Re-extração reversa executada e sem regressão vermelha (recomendado, não obrigatório) — pendente, decisão do usuário

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-07-08 | Versão inicial gerada por `/reversa-plan` | reversa |
