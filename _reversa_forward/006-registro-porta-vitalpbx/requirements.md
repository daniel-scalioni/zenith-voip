# Requirements: Registro de Entrada na Mesma Porta do Cadastro VitalPBX

> Identificador: `006-registro-porta-vitalpbx`
> Data: `2026-07-08`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

Hoje, migrar um interfone/softphone da VitalPBX para o FreeSWITCH (B2BUA) exige reconfigurar tanto o endereço do servidor SIP quanto, em alguns casos, a porta — porque o profile `internal` do FreeSWITCH só escuta em 5060, enquanto a VitalPBX expõe ramais PJSIP na porta 7060. Esta feature faz o FreeSWITCH aceitar REGISTER de entrada na mesma porta que cada ramal já usa hoje no cadastro da VitalPBX (5060 para `sip`, 7060 para `pjsip`), para que a migração de um aparelho seja só a troca do endereço do servidor SIP, sem tocar em porta. Resolve também, para os ramais que já migraram, a causa raiz identificada nesta sessão: o domínio do REGISTER usado por softphones (ex: 3CX) é o próprio endereço do servidor, não `zenith.local`.

## 2. Contexto a partir do legado

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `_reversa_sdd/telephony/design.md#3. Perfis SIP do FreeSWITCH` | Profile `internal` roda só na porta 5060; VitalPBX expõe `pjsip` em 7060 e `sip` em 5060/5062 conforme a tecnologia do ramal (coluna `technology` do CSV) | 🟢 |
| `_reversa_sdd/telephony/design.md#1. Topologia SIP` | B2BUA: interfone registra no FreeSWITCH (`internal`), que re-registra upstream na VitalPBX (`upstream`, porta 5065) | 🟢 |
| `specs/export_extensions.csv` (via `scripts/import_extensions.py`) | CSV traz `technology` por ramal; dedup hoje prioriza `pjsip` (porta 7060) quando o ramal tem entradas SIP e PJSIP | 🟢 |
| `freeswitch/conf/sip_profiles/internal.xml` | Hoje só declara `sip-port=5060`; `force-register-domain=$${domain}` foi adicionado nesta sessão para resolver mismatch de domínio do REGISTER (softphones usam o `PBXAddr` como domínio) | 🟢 |
| `freeswitch/conf/vars.xml` + `vars-external-ip.xml` | IP/FQDN externo do FreeSWITCH já é dinâmico via sidecar `ip-watcher` (feature `005-dynamic-external-ip`); endereço de servidor não é fixo | 🟢 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| Operador de infraestrutura (Daniel) | Migrar um ramal da VitalPBX para o FreeSWITCH trocando só o endereço do servidor SIP no aparelho | Ramal 1001 usa PJSIP:7060 na VitalPBX; ao trocar o servidor no softphone para o FreeSWITCH mantendo a porta 7060, o registro funciona sem reconfigurar porta |
| Usuário final do interfone | Continuar fazendo/recebendo chamadas durante a migração | Nenhuma reconfiguração manual de porta no aparelho físico |

## 4. Regras de negócio novas ou alteradas

1. **RN-01:** O FreeSWITCH DEVE aceitar REGISTER de entrada nas portas 5060, 5062 e 7060, refletindo a mesma porta que o ramal usa hoje no cadastro da VitalPBX, através de profiles SIP separados por porta (baixo acoplamento com o profile `internal` existente). 🟢
   - Origem no legado: `_reversa_sdd/telephony/design.md#3. Perfis SIP do FreeSWITCH`
   - Tipo: nova
2. **RN-02:** O domínio usado na autenticação do REGISTER de entrada DEVE ser resolvido independentemente do IP/FQDN ou porta usados pelo aparelho para alcançar o servidor (mesmo princípio do `force-register-domain` aplicado nesta sessão). 🟢
   - Origem no legado: correção aplicada em `freeswitch/conf/sip_profiles/internal.xml` nesta sessão
   - Tipo: nova
3. **RN-03:** O endereço (IP/FQDN) do servidor SIP anunciado ou usado para conexão DEVE permanecer flexível e dinâmico — nenhuma porta nova pode depender de IP fixo, dado o ambiente de teste com IP externo variável. 🟢
   - Origem no legado: `_reversa_forward/005-dynamic-external-ip/requirements.md`
   - Tipo: nova
4. **RN-04:** A porta de escuta de entrada por ramal DEVE ser derivada da coluna `technology` do CSV de exportação da VitalPBX, sem exigir digitação manual por ramal. 🟡
   - Origem no legado: `_reversa_sdd/telephony/design.md#Porta de destino no VitalPBX`
   - Tipo: nova

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| RF-01 | Um profile SIP novo e separado (ex: `internal-pjsip`) deve escutar na porta 7060, com seu próprio `<domains>` e `force-register-domain` | Must | `sofia status` lista o novo profile ativo com `sip-port=7060`; REGISTER de um ramal PJSIP nessa porta é aceito | 🟢 |
| RF-01b | A porta 5062 deve ser coberta por profile análogo (novo ou o mesmo de 7060, conforme desenho técnico do `/reversa-plan`) | Must | Ramal cadastrado em 5062 na VitalPBX registra com sucesso ao apontar para o FreeSWITCH na mesma porta | 🟢 |
| RF-02 | Ramais com `technology=sip` continuam registrando em 5060 sem alteração de comportamento | Must | Ramal 1001 (sip) continua registrando normalmente em 5060 após a mudança | 🟢 |
| RF-03 | O REGISTER de entrada não deve falhar por mismatch de domínio, independentemente da porta usada | Must | Teste manual de registro via porta 7060 resulta em `REGED`, sem erro de autenticação por domínio | 🟢 |
| RF-04 | `import_extensions.py` deve continuar gerando corretamente os artefatos de diretório/gateway por ramal, sem regressão na lógica de dedup SIP/PJSIP existente | Must | Rodar `import_extensions.py` sobre o CSV atual gera saída idêntica à anterior para ramais não afetados | 🟢 |
| RF-05 | A mudança não deve exigir IP ou FQDN fixo no cadastro do novo profile/porta | Should | Configuração da nova porta usa as mesmas variáveis dinâmicas (`$${local_ip}`, `$${external_sip_ip}`) já usadas pelo profile `internal` | 🟢 |
| RF-06 | Quando o REGISTER de entrada chega pela porta 7060, o gateway upstream correspondente na VitalPBX deve continuar usando a porta 7060, sem mudança de lógica | Must | Ramal 1001, registrado via 7060, mantém gateway upstream apontando para `sip.maisalerta.tecnorise.com:7060` | 🟢 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| Disponibilidade | A adição da porta 7060 não pode derrubar registros já ativos na porta 5060 | Mesma preocupação já registrada em `005-dynamic-external-ip` para não afetar o profile `internal` | 🟢 |
| Segurança | Nenhuma credencial SIP deve ser exposta em log ou em configuração versionada ao expor a nova porta | Política do projeto (`CLAUDE.md#Credenciais e Segurança`) | 🟢 |
| Compatibilidade | A solução deve funcionar com a imagem `safarov/freeswitch:1.10.12` já em uso, sem exigir build customizado | Consistente com RF-06 de `005-dynamic-external-ip` | 🟡 |
| Observabilidade | Deve ser possível diferenciar, em log/objeto de status, se um ramal registrou via 5060 ou 7060 | Facilita diagnóstico de migração ramal a ramal | 🟡 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Ramal PJSIP migra trocando só o servidor
  Dado que o ramal 1001 está cadastrado na VitalPBX como tecnologia "pjsip" na porta 7060
  Quando o softphone troca apenas o endereço do servidor SIP para o FreeSWITCH, mantendo a porta 7060
  Então o FreeSWITCH aceita o REGISTER na porta 7060
  E o ramal aparece como REGED em "sofia status profile internal reg"

Cenário: Ramal SIP continua funcionando em 5060
  Dado que o ramal X está cadastrado como tecnologia "sip" na porta 5060
  Quando o softphone registra no FreeSWITCH na porta 5060, como já funciona hoje
  Então o registro continua bem-sucedido, sem regressão

Cenário: Mismatch de domínio não bloqueia a nova porta
  Dado que um softphone usa o próprio endereço do servidor como domínio do REGISTER
  Quando ele registra na porta 7060
  Então o FreeSWITCH resolve o domínio corretamente e não rejeita por "usuário não encontrado"

Cenário: IP do servidor muda durante o teste
  Dado que o IP público do CPD muda devido a failover de ISP (feature 005-dynamic-external-ip)
  Quando um ramal tenta registrar na porta 7060 usando o novo IP/FQDN
  Então o registro funciona normalmente, sem exigir reconfiguração da porta no aparelho
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|----------------|
| RF-01 — escutar também em 7060 | Must | Sem isso, ramais PJSIP continuam exigindo reconfiguração de porta na migração |
| RF-03 — domínio não bloqueia a nova porta | Must | Sem isso, a nova porta reproduziria o mesmo bug já corrigido para 5060 |
| RF-02 — não regressão em 5060 | Must | Ramais já migrados (ex: 1001) não podem parar de funcionar |
| RF-04 — sem regressão no import_extensions.py | Must | Script já gera artefatos usados em produção |
| RF-05 — sem IP fixo | Should | Ambiente de teste já lida com IP dinâmico; nova porta deve seguir o mesmo padrão |

## 9. Esclarecimentos

### Sessão 2026-07-08

- **Q:** Como a nova porta 7060 deve ser implementada no FreeSWITCH — profile novo separado ou mesmo profile `internal` com múltiplas portas?
  **R:** Profile SIP novo e separado (baixo acoplamento, alta coesão), com seu próprio `<domains>` e `force-register-domain`, independente do profile `internal` (5060).

- **Q:** A porta 5062 também entra no escopo?
  **R:** Sim, também deve ser coberta.

- **Q:** Existe um ramal real cadastrado como `pjsip`/7060 disponível para teste?
  **R:** Sim, o ramal 1001 já está cadastrado como `sip` (5060) e `pjsip` (7060) na VitalPBX, com mesmo usuário e senha — deve ser possível migrar trocando só a porta.

- **Q:** O gateway upstream deve mudar de porta quando o registro de entrada muda de porta?
  **R:** Não muda a lógica — se o ramal registra pela 7060 no FreeSWITCH, o FreeSWITCH deve solicitar registro upstream à VitalPBX também pela 7060 (acoplamento porta-a-porta mantido, já é o comportamento do `import_extensions.py` via `technology`).

## 10. Lacunas

- 🟢 **Topologia da porta 7060:** profile SIP novo e separado (ex: `internal-pjsip`), com seu próprio `<domains>` e `force-register-domain`, priorizando baixo acoplamento com o profile `internal` (5060) existente.
- 🟢 **Porta 5062:** entra no escopo. A feature deve cobrir 5060, 7060 e 5062.
- 🟢 **Caso de teste real:** ramal 1001, já cadastrado na VitalPBX tanto como `sip` (5060) quanto `pjsip` (7060), mesmas credenciais — serve para validar a troca só de porta, sem trocar usuário/senha.
- 🟢 **Upstream por porta:** quando o registro de entrada chega pela porta 7060, o FreeSWITCH deve solicitar registro upstream à VitalPBX também pela porta 7060 (mesmo acoplamento porta-a-porta hoje já produzido por `import_extensions.py` via coluna `technology`).

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-07-08 | Versão inicial gerada por `/reversa-requirements` | reversa |
| 2026-07-08 | Esclarecimentos da sessão 2026-07-08 integrados: profile separado para 7060 (baixo acoplamento), 5062 incluso no escopo, ramal 1001 como caso de teste, upstream espelha a porta de entrada | reversa-clarify |
