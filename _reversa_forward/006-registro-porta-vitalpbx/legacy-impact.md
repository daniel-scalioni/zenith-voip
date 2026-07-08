# Legacy Impact: Registro de Entrada na Mesma Porta do Cadastro VitalPBX

> Identificador: `006-registro-porta-vitalpbx`
> Data: `2026-07-08`
> Execução: completa — Fases 1 a 5 (T001-T013) concluídas, validadas com teste real do ramal 1001 em produção (2026-07-08)

## Tabela de impacto

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|------------------|------------|------|------------|----------------|
| `freeswitch/conf/sip_profiles/internal-7060.xml` (novo) | Profile SIP de entrada (`_reversa_sdd/architecture.md:109`) | componente-novo | MEDIUM | Novo profile de entrada na porta 7060, espelhando `internal` (5060) |
| `freeswitch/conf/sip_profiles/internal-5062.xml` (novo) | Profile SIP de entrada (`_reversa_sdd/architecture.md:109`) | componente-novo | MEDIUM | Novo profile de entrada na porta 5062, mesmo padrão |
| `freeswitch/conf/sip_profiles/internal.xml` | Profile SIP de entrada (`_reversa_sdd/architecture.md:109`) | regra-alterada | LOW | Apenas comentário adicionado referenciando os profiles irmãos; nenhum parâmetro funcional mudou nesta feature (o `force-register-domain` já havia sido adicionado em sessão anterior) |
| `_reversa_sdd/domain.md#R07` ("Porta SIP padrão é 5060") | Regra de domínio | regra-alterada | MEDIUM | R07 deixa de ser a única porta de entrada válida — passa a existir registro de entrada também em 7060 e 5062, mantendo 5060 como a porta padrão/original |

## Diff conceitual por componente

**Profiles SIP de entrada:** antes desta feature, existia um único ponto de entrada de REGISTER (`internal`, porta 5060), documentado em `_reversa_sdd/architecture.md:109` e `_reversa_sdd/domain.md#R07`. Agora existem três profiles de entrada ativos simultaneamente (`internal`/5060, `internal-7060`/7060, `internal-5062`/5062), cada um com o mesmo diretório de usuários compartilhado (`freeswitch/conf/directory/extensions.xml`, sem alteração) e a mesma correção de domínio (`force-register-domain=$${domain}`). O profile `upstream` (5065, saída para VitalPBX) não foi tocado — a mudança é inteiramente no lado de entrada.

## Preservadas

- 🟢 R07 (parcialmente): 5060 continua sendo a porta padrão de entrada e nenhum ramal existente teve seu comportamento alterado nela.
- 🟢 R24 (mapeamento SIP→IP expira em 1 hora): não afetado, lógica de `esl_client.py` inalterada.
- 🟢 Separação `internal`/`upstream` (`_reversa_sdd/telephony/design.md#3`): preservada — os novos profiles seguem o mesmo padrão de isolamento entre entrada e saída.

## Modificadas

- 🟡 R07 ("Porta SIP padrão é 5060"): a interpretação estrita de "a" porta SIP passa a ser "uma das portas SIP de entrada" — 5060 continua padrão/original, mas 7060 e 5062 tornam-se portas de entrada válidas e equivalentes para ramais migrados da VitalPBX. Rebaixada de 🟢 para 🟡 porque o código-fonte (`models.py:48`) referenciado pela regra original ainda não foi (e não precisa ser) atualizado — a regra vale para a camada de aplicação, não para a topologia SIP do FreeSWITCH.
