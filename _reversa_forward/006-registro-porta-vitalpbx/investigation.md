# Investigation: Registro de Entrada na Mesma Porta do Cadastro VitalPBX

> Identificador: `006-registro-porta-vitalpbx`
> Data: `2026-07-08`

## 1. Pesquisa de fundo

O FreeSWITCH suporta múltiplos profiles `sofia` simultâneos, cada um com seu próprio `sip-port`, `<domains>` e conjunto de parâmetros — este é exatamente o padrão já usado no projeto para separar `internal` (5060, entrada) de `upstream` (5065, saída). Não há limitação técnica conhecida para ter 3+ profiles de entrada ativos ao mesmo tempo no mesmo host, desde que cada um escute em porta distinta (`network_mode: host` já garante bind direto na interface do host, sem conflito de mapeamento Docker).

## 2. Causa raiz relacionada (contexto desta sessão)

Durante o debug do ramal 1001 nesta mesma sessão, identificou-se que softphones (ex: 3CX) usam o próprio endereço do servidor SIP (`PBXAddr`) como domínio do REGISTER, não um campo de domínio separado. Como o `internal.xml` só reconhecia `$${domain}` (`zenith.local`) como domínio válido, o REGISTER falhava com aparência de erro de autenticação. A correção aplicada — `force-register-domain=$${domain}` — resolve isso ao forçar a resolução do domínio real independentemente do que o dispositivo enviar. Essa mesma lógica precisa ser replicada em qualquer profile novo, ou o mesmo bug se repete em cada porta adicional.

## 3. Alternativas avaliadas

| Alternativa | Descrição | Por que foi descartada |
|-------------|-----------|--------------------------|
| Múltiplas portas no mesmo profile `internal` | FreeSWITCH permite declarar `sip-port` como lista/múltiplos binds em alguns cenários, ou usar `sofia profile ... siptrace` compartilhado | Descartada por decisão explícita do usuário em `/reversa-clarify`: prioriza baixo acoplamento — um profile único acopla o ciclo de vida (restart/rescan) de todas as portas |
| Proxy/dispatcher de porta na frente do FreeSWITCH (ex: iptables DNAT redirecionando 7060→5060) | Redirecionar no nível de rede em vez de configurar o FreeSWITCH | Descartada: não resolveria o mismatch de domínio (RF-03) nem daria visibilidade por profile em `sofia status`; esconderia a porta real do SIP stack |
| Duplicar `directory/extensions.xml` por profile | Um arquivo de usuários por porta | Descartada: diretório já é global no FreeSWITCH (include compartilhado), duplicar introduziria risco de dessincronia de senha sem benefício |

## 4. Padrões aplicáveis

- **Separação por profile como isolamento de blast radius**: já validado no próprio projeto pela separação `internal`/`upstream` (`_reversa_sdd/telephony/design.md#3. Perfis SIP do FreeSWITCH`).
- **Configuração via variáveis dinâmicas (`$${...}`)**: já validado pela feature `005-dynamic-external-ip`, que resolve IP externo em runtime sem exigir hardcode.
