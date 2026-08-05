# Requirements: Registro de troncos ATA

> Identificador: `012-trunk-registration`
> Data: `2026-08-01`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

A feature permitirá cadastrar, importar e acompanhar troncos de adaptadores telefônicos analógicos (ATAs) pertencentes aos condomínios atendidos pelo Zenith. Cada ATA se registrará no FreeSWITCH com credenciais próprias do protocolo de iniciação de sessão (SIP), usando a porta 5060 ou 7060 pelo protocolo de datagramas de usuário (UDP). O Zenith identificará o tenant, a central telefônica privada (Private Branch Exchange, PBX), o condomínio e o tronco sem assumir manipulação de dígitos, definição de fila ou regras de roteamento já mantidas no ATA e no VitalPBX. O estado administrativo, o registro SIP e o uso em chamadas serão apresentados como dimensões independentes.

## 2. Contexto a partir do legado

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `_reversa_sdd/architecture.md#Papel do FreeSWITCH: B2BUA com Registration Forwarding` | O FreeSWITCH ocupa a posição intermediária entre os dispositivos SIP e o VitalPBX e já recebe registros na borda. | 🟢 |
| `_reversa_sdd/architecture.md#Princípios Arquiteturais` | Dados e operações devem permanecer isolados por tenant. | 🟢 |
| `_reversa_sdd/domain.md#Glossário` | Tenant é o cliente isolado e PBX é uma central vinculada a esse tenant. | 🟢 |
| `_reversa_sdd/domain.md#PBXs` | Todo PBX pertence a um tenant e a topologia de entrada admite as portas 5060 e 7060. | 🟢 |
| `_reversa_sdd/domain.md#SIP e Telefonia` | A interface de eventos e comandos Event Socket Library (ESL) já mantém informações efêmeras de registro SIP e é resiliente a reconexões. | 🟢 |
| `_reversa_sdd/domain.md#TODOs e FIXMEs` | Variáveis globais fixas de tenant e PBX impedem o multitenancy real na telefonia atual. | 🟢 |
| `_reversa_sdd/code-analysis.md#telephony — Integração FreeSWITCH` | O módulo de telefonia já consome eventos de registro, desregistro e ciclo de vida de chamadas. | 🟢 |
| `_reversa_sdd/inventory.md#Módulos Identificados` | A mudança atravessa os domínios `database`, `api`, `telephony` e `infra`. | 🟢 |

O escopo e as decisões funcionais abaixo foram aprovados pelo usuário em 2026-08-01 após a discussão específica da feature 012.

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| Administrador do tenant | Cadastrar ou importar os troncos ATA dos condomínios sob seus PBXs | Importa uma extração de troncos do VitalPBX, corrige eventuais rejeições e habilita os registros válidos. |
| Operador técnico | Acompanhar disponibilidade e utilização sem acessar credenciais | Consulta se cada tronco está habilitado, registrado e com chamadas ativas, além do último erro sanitizado. |
| Responsável pelo condomínio | Manter a telefonia existente sem duplicar roteamento no Zenith | O ATA registra no FreeSWITCH e continua usando prefixos, destinos e regras já definidos no ATA ou no VitalPBX. |

## 4. Regras de negócio novas ou alteradas

1. **RN-01:** A hierarquia funcional será `Tenant → PBX → Condomínio → Tronco ATA`. 🟢
   - Origem no legado: `_reversa_sdd/domain.md#Glossário` e `_reversa_sdd/domain.md#PBXs`
   - Tipo: nova
2. **RN-02:** Um tenant poderá possuir vários PBXs; um PBX poderá atender vários condomínios; cada tronco ATA pertencerá a exatamente um condomínio. 🟢
   - Origem no legado: `_reversa_sdd/domain.md#PBXs`
   - Tipo: nova
3. **RN-03:** O prefixo do tronco é metadado opcional. Quando informado, será único dentro do tenant e poderá repetir em tenants diferentes; ele nunca participa da autenticação ou do roteamento. 🟢
   - Tipo: nova
4. **RN-04:** O ATA iniciará o registro no FreeSWITCH por usuário e senha; o FreeSWITCH não iniciará registro no ATA. 🟢
   - Origem no legado: `_reversa_sdd/architecture.md#Papel do FreeSWITCH: B2BUA com Registration Forwarding`
   - Tipo: alterada
5. **RN-05:** Cada tronco usará UDP em uma das entradas aprovadas: SIP na porta 5060 ou a entrada 7060 usada pelos dispositivos classificados como PJSIP no VitalPBX. No FreeSWITCH, ambas são profiles Sofia, isto é, conjuntos independentes de parâmetros de escuta e autenticação SIP. 🟢
   - Origem no legado: `_reversa_sdd/domain.md#PBXs`
   - Tipo: nova
6. **RN-06:** O Zenith não alterará dígitos, não escolherá fila de destino e não duplicará regras de roteamento do ATA ou do VitalPBX. 🟢
   - Tipo: nova
7. **RN-07:** `enabled`, `registration_status` e `active_calls` representarão dimensões independentes; `in_use` será derivado de `active_calls > 0`. 🟢
   - Tipo: nova
8. **RN-08:** `registration_status` aceitará `registered`, `unregistered` ou `unknown`; reinício, perda de conexão ESL ou ausência de evidência atual não poderá produzir um falso `registered`. 🟢
   - Origem no legado: `_reversa_sdd/domain.md#SIP e Telefonia`
   - Tipo: nova
9. **RN-09:** Credenciais de tronco nunca aparecerão em logs, métricas, mensagens de erro, respostas de consulta ou artefatos do Reversa. 🟢
   - Origem no legado: `_reversa_sdd/architecture.md#Princípios Arquiteturais`
   - Tipo: nova
10. **RN-10:** Somente administradores do tenant poderão criar, importar, alterar, habilitar ou desabilitar troncos pertencentes ao próprio tenant. 🟢
    - Origem no legado: `_reversa_sdd/domain.md#API e Segurança`
    - Tipo: nova

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| RF-01 | Manter o cadastro de condomínios sob um PBX do tenant. | Must | Um administrador cria, consulta e atualiza um condomínio sem conseguir associá-lo a PBX de outro tenant. | 🟢 |
| RF-02 | Manter troncos ATA com condomínio, usuário, segredo, perfil de entrada, estado administrativo e prefixo opcional. | Must | Um tronco sem prefixo é persistido e identificado por profile/usuário; o segredo nunca retorna em leitura. | 🟢 |
| RF-03 | Cadastrar troncos individualmente a partir da configuração privada disponível e manter importação CSV quando a origem oferecer exportação. | Must | Cadastro e dry-run aceitam prefixo ausente, iniciam desabilitados e nunca revelam segredos; CSV continua suportado sem ser pré-condição operacional. | 🟢 |
| RF-04 | Impedir prefixos repetidos dentro do mesmo tenant quando preenchidos. | Must | Dois troncos com o mesmo prefixo não nulo no tenant são rejeitados; vários troncos sem prefixo são aceitos e a identidade SIP permanece globalmente única por profile/usuário. | 🟢 |
| RF-05 | Disponibilizar os troncos habilitados para registro iniciado pelo ATA no profile 5060 ou 7060 correspondente. | Must | Credenciais corretas no profile configurado registram o ATA; credenciais erradas, tronco desabilitado ou profile divergente são recusados. | 🟢 |
| RF-06 | Resolver cada registro para tenant, PBX, condomínio e tronco sem depender de variáveis globais fixas. | Must | Dois tenants com o mesmo prefixo são identificados corretamente pelas credenciais e pelo contexto de registro, sem cruzamento de dados. | 🟢 |
| RF-07 | Atualizar o estado de registro a partir do estado real do FreeSWITCH. | Must | Registro e desregistro alteram `registration_status` e seus timestamps; perda de evidência atual resulta em `unknown` ou `unregistered`, nunca em falso positivo. | 🟢 |
| RF-08 | Contabilizar chamadas ativas por tronco. | Must | Início e término de chamadas ajustam `active_calls` sem valor negativo; `in_use` corresponde exatamente a `active_calls > 0`. | 🟢 |
| RF-09 | Expor consulta tenant-scoped dos estados administrativo, de registro e de uso. | Must | O administrador consulta apenas troncos do próprio tenant e vê `enabled`, `registration_status`, `active_calls`, `in_use`, timestamps e último erro sanitizado. | 🟢 |
| RF-10 | Preservar o número recebido e o destino já determinado pelo ATA ou VitalPBX. | Must | Uma chamada atravessa o FreeSWITCH sem regra adicional de remoção, adição ou substituição de dígitos e sem seleção de fila pelo Zenith. | 🟢 |
| RF-11 | Reconciliar o estado operacional após inicialização ou reconexão do consumidor ESL. | Must | Após reconexão, o estado persistido converge com os registros e chamadas observáveis no FreeSWITCH sem exigir novo registro do ATA. | 🟡 |
| RF-12 | Registrar o último erro operacional de forma sanitizada. | Should | Falhas de autenticação, profile ou transporte são distinguíveis para operação sem expor usuário completo, senha ou material de autenticação. | 🟢 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| Segurança | Segredos devem ser armazenados protegidos, aceitos apenas em entrada administrativa e omitidos de toda saída e telemetria. | RN-09 e princípio de isolamento em `_reversa_sdd/architecture.md#Princípios Arquiteturais`. | 🟢 |
| Isolamento | Toda leitura, escrita, importação e resolução operacional deve estar vinculada ao tenant correto. | `_reversa_sdd/architecture.md#Princípios Arquiteturais`. | 🟢 |
| Consistência | Importações repetidas do mesmo CSV devem ser idempotentes e não duplicar condomínio ou tronco. | Necessário para reextrações periódicas do VitalPBX. | 🟢 |
| Concorrência | Eventos duplicados, atrasados ou fora de ordem não podem produzir contador negativo nem estado de registro incoerente. | O módulo já opera sobre eventos ESL e reconexões, conforme `_reversa_sdd/code-analysis.md#telephony — Integração FreeSWITCH`. | 🟡 |
| Disponibilidade | Falha no acompanhamento de estado não pode derrubar o plano de mídia ou impedir chamadas já estabelecidas. | O FreeSWITCH permanece no caminho crítico da chamada, conforme `_reversa_sdd/architecture.md#Fluxo Principal de uma Chamada`. | 🟢 |
| Desempenho | Uma atualização individual de registro ou chamada deve ficar visível para consulta em até 5 segundos em condições normais. | Janela operacional suficiente para acompanhamento sem impor processamento síncrono à chamada. | 🟡 |
| Observabilidade | Devem existir métricas de troncos por estado e logs estruturados de transição, sem labels de alta cardinalidade nem credenciais. | Padrões de observabilidade existentes em `_reversa_sdd/inventory.md#Módulos Identificados`. | 🟢 |
| Compatibilidade | A feature deve preservar os profiles e fluxos de chamada existentes nas portas 5060 e 7060. | `_reversa_sdd/domain.md#PBXs`. | 🟢 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Importar troncos ATA de dois condomínios
  Dado um administrador autenticado e um CSV válido extraído do VitalPBX
  Quando ele importa condomínios e troncos vinculados ao seu PBX
  Então cada tronco fica associado ao tenant, PBX e condomínio corretos
  E nenhuma credencial aparece no resultado da importação

Cenário: Registrar ATA habilitado
  Dado um tronco habilitado com credenciais válidas e profile 5060
  Quando o ATA envia o registro ao FreeSWITCH
  Então o registro é aceito
  E o tronco passa para registered em até 5 segundos

Cenário: Registrar dispositivo da origem PJSIP na entrada 7060
  Dado um tronco habilitado configurado para a entrada 7060
  Quando o ATA envia o registro UDP com credenciais válidas
  Então o profile Sofia 7060 aceita o registro
  E a origem continua identificada como pertencente ao tronco correto

Cenário: Recusar credencial inválida sem vazamento
  Dado um tronco cadastrado
  Quando um ATA tenta registrar com senha incorreta
  Então o registro é recusado
  E logs, métricas, respostas e último erro não contêm a senha nem material de autenticação

Cenário: Isolar prefixos iguais entre tenants
  Dado que dois tenants possuem troncos com o mesmo prefixo
  Quando ambos os ATAs se registram
  Então cada registro é resolvido para o tenant correto pelas suas credenciais e contexto
  E nenhum estado ou chamada cruza a fronteira de tenant

Cenário: Aceitar tronco sem prefixo e impedir duplicidade quando preenchido
  Dado um tronco cuja autenticação e roteamento não usam prefixo no Zenith
  Quando o administrador o cadastra sem prefixo
  Então a identidade é resolvida por profile e usuário
  E nenhum dígito é inferido a partir da credencial SIP

  Dado um tenant que já possui um tronco com determinado prefixo não nulo
  Quando o administrador tenta cadastrar outro tronco com o mesmo prefixo
  Então a operação é rejeitada com erro de conflito sem alterar o tronco existente

Cenário: Representar registro e uso simultaneamente
  Dado um tronco habilitado e registrado
  Quando duas chamadas simultâneas usam o tronco
  Então registration_status permanece registered
  E active_calls vale 2
  E in_use vale verdadeiro

Cenário: Encerrar chamadas sem contador negativo
  Dado um tronco com uma chamada ativa
  Quando eventos de término duplicados ou fora de ordem são recebidos
  Então active_calls converge para 0 e nunca fica negativo
  E registration_status não é substituído por um estado de uso

Cenário: Preservar roteamento externo
  Dado um ATA registrado cujos dígitos e destino já foram definidos no VitalPBX ou no PABX do condomínio
  Quando uma chamada atravessa o FreeSWITCH
  Então o Zenith não altera os dígitos
  E não seleciona fila de destino

Cenário: Reconciliar depois de reconexão ESL
  Dado que o consumidor ESL perdeu a conexão enquanto havia troncos registrados
  Quando a conexão é restabelecida
  Então o Zenith reconcilia os estados com o FreeSWITCH
  E não mantém registered sem evidência operacional atual
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|---------------|
| RF-01 a RF-10 | Must | Formam o contrato mínimo de cadastro, importação, registro, isolamento e acompanhamento operacional. |
| RF-11 | Must | Sem reconciliação, reinícios e falhas ESL deixariam estados operacionais falsos. |
| RF-12 | Should | Melhora o diagnóstico, desde que a sanitização seja garantida. |
| Segurança e isolamento | Must | Credenciais e fronteiras de tenant são bloqueantes. |
| Observabilidade agregada | Should | Necessária para operação, mas não deve ampliar o caminho crítico da chamada. |

## 9. Esclarecimentos

> Decisões aprovadas em 2026-08-01 e refinadas em 2026-08-04: ATA inicia o registro; escopo limitado a troncos ATA; hierarquia Tenant → PBX → Condomínio → Tronco ATA; entradas UDP 5060/7060; sem manipulação de dígitos ou filas; prefixo opcional e único por tenant somente quando preenchido; identidade por profile/usuário; estado administrativo, registro e uso independentes.

## 10. Lacunas

- Nenhuma lacuna funcional pendente. O formato exato do CSV, o mecanismo de proteção do segredo e a estratégia de reconciliação serão definidos no plano técnico sem alterar o contrato acima.

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-08-01 | Versão inicial gerada por `/reversa-requirements` a partir do contrato aprovado em sessão anterior | reversa |
| 2026-08-01 | Siglas e conceito de profile Sofia definidos após `/reversa-quality` | reversa |
