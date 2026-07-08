# Onboarding: Registro de Entrada na Mesma Porta do Cadastro VitalPBX

> Identificador: `006-registro-porta-vitalpbx`
> Data: `2026-07-08`

## Passo a passo para testar pela primeira vez

1. **Pré-requisito:** profile `internal` (5060) já deve estar com `force-register-domain` aplicado (feito nesta sessão em `freeswitch/conf/sip_profiles/internal.xml`).

2. **Copiar os novos profiles para o host de produção** (após implementados pelo `/reversa-coding`):
   ```bash
   scp freeswitch/conf/sip_profiles/internal-7060.xml administrator@10.10.10.11:~/zenith-voip/freeswitch/conf/sip_profiles/
   scp freeswitch/conf/sip_profiles/internal-5062.xml administrator@10.10.10.11:~/zenith-voip/freeswitch/conf/sip_profiles/
   ```

3. **Recarregar XML e iniciar os novos profiles sem tocar no `internal`:**
   ```bash
   ssh administrator@10.10.10.11 "docker exec freeswitch fs_cli -x 'reloadxml'"
   ssh administrator@10.10.10.11 "docker exec freeswitch fs_cli -x 'sofia profile internal-7060 start'"
   ssh administrator@10.10.10.11 "docker exec freeswitch fs_cli -x 'sofia profile internal-5062 start'"
   ```

4. **Confirmar que o profile `internal` (5060) não foi afetado:**
   ```bash
   ssh administrator@10.10.10.11 "docker exec freeswitch fs_cli -x 'sofia status profile internal reg'"
   ```
   O ramal 1001 (se já estiver registrado em 5060) deve continuar `REGED`.

5. **Testar o ramal 1001 na porta 7060** (mesma credencial usada em 5060, caso de teste confirmado em `/reversa-clarify`):
   - No softphone (perfil de teste, ex: `ScaliFreeSwitch` no `specs/3CXVoipPhone.ini`), trocar `PBXAddr` para `10.10.10.11:7060` (ou o FQDN/IP dinâmico equivalente).
   - Tentar registrar.
   - Verificar:
     ```bash
     ssh administrator@10.10.10.11 "docker exec freeswitch fs_cli -x 'sofia status profile internal-7060 reg'"
     ```
   - Esperado: ramal 1001 aparece como `REGED`.

6. **Confirmar que o gateway upstream não mudou de porta (RF-06):**
   ```bash
   ssh administrator@10.10.10.11 "docker exec freeswitch fs_cli -x 'sofia status gateway upstream::upstream-1001'"
   ```
   Deve continuar apontando para `sip.maisalerta.tecnorise.com:7060`.

7. **Repetir o teste para a porta 5062** com um ramal cadastrado nessa porta na VitalPBX, se disponível.

## Critério de sucesso do onboarding

- Ramal 1001 registra em 5060 (já funcionava) e em 7060 (novo), com a mesma senha, apenas trocando a porta no aparelho.
- Nenhuma interrupção observada no profile `internal` durante o teste.

## Resultado real do teste (2026-07-08)

- **Passo 5 confirmado:** ramal 1001, ao trocar `PBXAddr` do 3CX (perfil `ScaliFreeSwitch`) para `10.10.10.11:7060` (mesma credencial), registrou com sucesso. `sofia status profile internal-7060 reg` mostrou `Status: Registered(UDP-NAT)`, `Contact` do dispositivo `192.168.50.99`, `Agent: 3CXPhone 6.0.26523.0`.
- **Passo 4/observação sobre `internal`:** o profile `internal` (5060) permaneceu `RUNNING` durante toda a operação, sem interrupção. O ramal 1001 deixou de aparecer registrado em 5060 após a troca porque é **o mesmo aparelho** migrando de porta (não dois registros simultâneos) — comportamento esperado, não é regressão.
- **Passo 6 confirmado:** `sofia status gateway upstream::upstream-1001` mostrou `State: REGED`, `Proxy: sip:sip.maisalerta.tecnorise.com:7060` — nenhuma mudança de código foi necessária, o `import_extensions.py` já gerava essa porta corretamente via `PORT_BY_TECH`.
- **Ponto de atenção observado durante o teste:** a primeira tentativa de captura de tráfego não pegou nenhum pacote na porta 7060; só na segunda tentativa (com o usuário forçando o REGISTER exatamente durante a janela de captura) os pacotes apareceram. Ou seja, o softphone não fica reenviando REGISTER continuamente — é preciso forçar (reiniciar o profile/app) para observar em tempo real.
- **Passo 7 (porta 5062):** não executado nesta sessão — nenhum ramal cadastrado em 5062 disponível para teste real no momento.
