# Actions: Registro de Entrada na Mesma Porta do Cadastro VitalPBX

> Identificador: `006-registro-porta-vitalpbx`
> Data: `2026-07-08`
> Roadmap: `_reversa_forward/006-registro-porta-vitalpbx/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 13 |
| Paralelizáveis (`[//]`) | 4 |
| Maior cadeia de dependência | 6 (T001 → T004 → T006 → T008 → T011 → T013) |

## Fase 1, Preparação

<!-- Setup, scaffolding, configuração inicial dos novos profiles SIP. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T001 | Criar `freeswitch/conf/sip_profiles/internal-7060.xml` baseado em `internal.xml`: `sip-port=7060`, `<domains>` e alias próprios, `force-register-domain=$${domain}`, `sip-ip`/`rtp-ip`/`ext-sip-ip`/`ext-rtp-ip` usando as mesmas variáveis dinâmicas do `internal` | - | `[//]` | `freeswitch/conf/sip_profiles/internal-7060.xml` | 🟢 | `[X]` |
| T002 | Criar `freeswitch/conf/sip_profiles/internal-5062.xml` no mesmo padrão de T001, com `sip-port=5062` | - | `[//]` | `freeswitch/conf/sip_profiles/internal-5062.xml` | 🟢 | `[X]` |
| T003 | Adicionar comentário XML idêntico em `internal.xml`, `internal-7060.xml` e `internal-5062.xml` documentando que os três profiles compartilham a mesma lógica de domínio/IP dinâmico e devem ser atualizados em conjunto (mitigação do risco de dessincronia do `roadmap.md#9`) | T001, T002 | - | `freeswitch/conf/sip_profiles/internal.xml`, `freeswitch/conf/sip_profiles/internal-7060.xml`, `freeswitch/conf/sip_profiles/internal-5062.xml` | 🟢 | `[X]` |

## Fase 3, Núcleo

<!-- Aplicação dos novos profiles no host de produção. Sem fase de testes automatizados: infraestrutura SIP não tem suíte de TDD no projeto. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T004 | Copiar `internal-7060.xml` para `administrator@10.10.10.11:~/zenith-voip/freeswitch/conf/sip_profiles/` via `scp` e rodar `fs_cli -x 'reloadxml'` (conforme `onboarding.md`) | T001 | - | `freeswitch/conf/sip_profiles/internal-7060.xml` | 🟢 | `[X]` |
| T005 | Copiar `internal-5062.xml` para o host de produção e rodar `reloadxml`, mesmo processo de T004 | T002 | - | `freeswitch/conf/sip_profiles/internal-5062.xml` | 🟢 | `[X]` |
| T006 | Iniciar o profile `internal-7060` via `fs_cli -x 'sofia profile internal-7060 start'` e confirmar `RUNNING` em `sofia status` | T004 | - | `freeswitch/conf/sip_profiles/internal-7060.xml` | 🟢 | `[X]` |
| T007 | Iniciar o profile `internal-5062` via `fs_cli -x 'sofia profile internal-5062 start'` e confirmar `RUNNING` em `sofia status` | T005 | - | `freeswitch/conf/sip_profiles/internal-5062.xml` | 🟢 | `[X]` |

## Fase 4, Integração

<!-- Validação end-to-end com o ramal real de teste (1001) e com o profile internal existente. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T008 | Testar registro do ramal 1001 na porta 7060 (mesma credencial usada em 5060, trocando só `PBXAddr` no softphone de teste) e confirmar `REGED` via `sofia status profile internal-7060 reg` | T006 | - | `-` | 🟢 | `[X]` |
| T009 | Confirmar que o profile `internal` (5060) permanece `REGED` para o ramal 1001 durante e após o teste de T008, sem regressão (RF-02) | T006 | `[//]` | `-` | 🟢 | `[X]` |
| T010 | Confirmar que o gateway upstream do ramal 1001 continua apontando para `sip.maisalerta.tecnorise.com:7060` após o teste de T008, via `sofia status gateway upstream::upstream-1001` (RF-06) | T008 | - | `-` | 🟢 | `[X]` |

## Fase 5, Polimento

<!-- Documentação do resultado real e watch de regressão. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T011 | Atualizar `onboarding.md` marcando os passos confirmados com o resultado real do teste (T008, T009, T010) | T008, T009, T010 | `[//]` | `_reversa_forward/006-registro-porta-vitalpbx/onboarding.md` | 🟢 | `[X]` |
| T012 | Gerar `regression-watch.md` listando os pontos de regressão: (1) profile `internal` (5060) permanece ativo após criação dos novos profiles; (2) os três profiles (`internal`, `internal-7060`, `internal-5062`) permanecem sincronizados na lógica de domínio/IP; (3) gateway upstream por ramal continua espelhando a porta de entrada | - | `[//]` | `_reversa_forward/006-registro-porta-vitalpbx/regression-watch.md` | 🟢 | `[X]` |
| T013 | Marcar o critério de pronto em `roadmap.md#10` conforme os resultados reais de T008–T012 | T011, T012 | - | `_reversa_forward/006-registro-porta-vitalpbx/roadmap.md` | 🟢 | `[X]` |

## Notas de execução

<!-- Reservado para /reversa-coding registrar avisos ou observações que surgiram durante a execução. -->

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-07-08 | Versão inicial gerada por `/reversa-to-do` | reversa |
