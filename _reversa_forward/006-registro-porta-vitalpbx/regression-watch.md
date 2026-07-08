# Regression Watch: Registro de Entrada na Mesma Porta do Cadastro VitalPBX

> Identificador: `006-registro-porta-vitalpbx`

## Itens de observação

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|--------------------------|-------------------------------|------------------------|---------------------|
| W001 | `_reversa_sdd/domain.md#R07` | 5060 continua sendo a porta de entrada padrão/original — ramais que permanecerem apontando para 5060 (sem migrar o aparelho) continuam registrando normalmente | presença | Um ramal que não trocou de porta no aparelho passa a falhar ou exigir mudança de configuração em 5060 após esta feature (nota: um ramal que migra intencionalmente o aparelho de 5060→7060/5062 deixa de aparecer em `internal`/5060 por design, isso não é violação) |
| W002 | `freeswitch/conf/sip_profiles/internal.xml`, `internal-7060.xml`, `internal-5062.xml` | Os três profiles compartilham a mesma lógica de `force-register-domain` e variáveis de IP dinâmico — qualquer correção futura de domínio/IP precisa ser replicada nos três | redação | Um dos três profiles diverge (ex: alguém corrige só o `internal.xml` e esquece os outros dois) |
| W003 | `_reversa_sdd/telephony/design.md#Porta de destino no VitalPBX` | Gateway upstream por ramal continua espelhando a porta de entrada (ex: ramal registrado via 7060 mantém gateway upstream em `:7060`) | presença | Gateway upstream de um ramal migrado aponta para porta diferente da tecnologia (`technology`) declarada no CSV |
| W004 | `_reversa_forward/006-registro-porta-vitalpbx/roadmap.md#9` | Profile `internal` (5060) permanece `RUNNING`/sem interrupção de registros ativos durante e após a criação dos profiles `internal-7060` e `internal-5062` | presença | `sofia status profile internal reg` mostra queda de registros ativos correlacionada com o deploy desta feature |
| W005 | Teste real de 2026-07-08 (`onboarding.md#Resultado real do teste`) | O REGISTER de um softphone só é reenviado quando forçado (restart do profile/app) — não há retry contínuo visível em captura de tráfego passiva de curta duração | confiança | Diagnósticos futuros que assumam retry automático dentro de poucos segundos vão falhar em capturar tráfego real sem forçar o REGISTER manualmente |

## Observações (confidência 🟡/🔴, sem peso de regressão)

- 🟡 A porta 5062 foi incluída no escopo por decisão de `/reversa-clarify`, mas não há ramal real confirmado cadastrado nessa porta para validação end-to-end (T008-T010 cobrem apenas a porta 7060 com o ramal 1001). `internal-5062` está `RUNNING` em produção, mas sem registro real testado.

## Histórico de re-extrações

### Re-extração 2026-07-08 22:31

| ID | Veredito | Observação |
|----|----------|------------|
| W001 | 🟢 verde | `domain.md#R07` atualizado nesta re-extração para refletir 7060/5062 como portas de entrada válidas, preservando 5060 como padrão |
| W002 | 🟢 verde | `telephony/design.md#3` documenta explicitamente que os três profiles compartilham `force-register-domain` e devem ser atualizados juntos |
| W003 | 🟢 verde | Confirmado ao vivo nesta sessão: `upstream-1001` aponta para `sip.maisalerta.tecnorise.com:7060`, consistente com a tecnologia `pjsip` do ramal |
| W004 | 🟢 verde | `internal` (5060) permaneceu `RUNNING` durante todo o deploy, confirmado via `sofia status` |
| W005 | 🟢 verde | Comportamento documentado em `onboarding.md#Resultado real do teste`, evidência direta do teste ao vivo |

## Arquivadas

_Vazio._
