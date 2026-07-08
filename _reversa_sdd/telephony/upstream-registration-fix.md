---
spec:
  component: upstream-registration-fix
  layer: telephony
  status: active
  version: 1.0.0
  language: text
  patterns: [b2bua-registration-forwarding]
  inputs:
    - name: ramal_extensao
      type: string
      from: VitalPBX CSV (specs/export_extensions.csv)
    - name: technology
      type: enum (sip|pjsip)
      from: VitalPBX CSV technology column
  outputs:
    - name: gateway_file
      type: xml
      to: freeswitch/conf/sip_profiles/upstream/upstream-{ext}.xml
    - name: register_status
      type: bool
      to: FreeSWITCH Sofia Profile
  dependencies:
    - component: import-extensions-script
      layer: scripts
    - component: sofia-upstream-profile
      layer: telephony
  updated_at: 2026-07-03
---

# Upstream Registration Fix — Ramal 1001

## 🎯 Objetivo

Garantir que ramais importados do VitalPBX via `import_extensions.py` registrem corretamente no VitalPBX upstream, com a porta correta conforme o `technology` (PJSIP:7060 ou SIP:5060).

## 🔴 Problema Diagnosticado (2026-07-03)

### Camada 1: Configuração do arquivo ✅ RESOLVIDO

**Sintoma**: Ramal 1001 não registra no VitalPBX. Status: `DOWN`, Estado: `FAIL_WAIT`.

**Causa Raiz**: 
- Arquivo `upstream-1001.xml` **no container** estava com porta **5060** (SIP clássico)
- Arquivo **local** em `/app/zenith-voip/freeswitch/conf/...` tinha porta **7060** (PJSIP)
- Arquivo no container nunca foi sincronizado após atualização local

**Solução**: 
- ✅ Copiar arquivo correto para container
- ✅ Reiniciar profile upstream (`sofia profile upstream stop/start`)
- ✅ Verificar que porta mudou para 7060 (confirmado)

### Camada 2: Conectividade de rede 🔴 PROBLEMA NOVO

**Diagnóstico (2026-07-03 16:30)**:
```
docker exec freeswitch ping 177.71.153.68
→ 100% packet loss
docker exec freeswitch traceroute 177.71.153.68
→ Trava no hop 2 (gateway 10.10.10.1 / Mikrotik)
```

**Conclusão**: FreeSWITCH **consegue enviar REGISTER** para 177.71.153.68:7060, mas **não recebe resposta** porque o Mikrotik (gateway) não roteia a resposta de volta.

**Impacto**: Mesmo com config correta, VitalPBX não consegue responder → REGISTER nunca completa → Estado fica FAIL_WAIT indefinidamente.

**Solução**: Firewall do Mikrotik tinha uma regra específica que não encaminhava pacotes de resposta do GPhone/VitalPBX de volta para o FreeSWITCH. Usuário corrigiu a regra no Mikrotik.

### Verificação Final (2026-07-08) ✅ CONFIRMADO

Packet capture no host FreeSWITCH (via container `nicolaka/netshoot` com `tcpdump`, `net=host`) confirmou o fluxo completo de registro:

```
Frame 7:  REGISTER (1001) → 200 OK
Frame 9:  REGISTER (1001, novo Call-ID, sem auth) → 401 Unauthorized (challenge)
Frame 11: REGISTER (1001, com Authorization digest) → 200 OK
```

**Status final do gateway**:
```
State   	REGED
Status  	UP (ping)
Uptime  	35s+
```

**Ramal 1001 está registrado com sucesso no VitalPBX via FreeSWITCH (B2BUA).**

## 🎓 Lições Aprendidas

1. **Múltiplas camadas de falha simultâneas**: config desatualizada (porta errada) + firewall bloqueando resposta. Corrigir uma sem a outra não resolve — diagnóstico precisou isolar cada camada.
2. **Packet capture foi decisivo**: sem ver o REGISTER real saindo e a resposta 401/200 chegando, não daria para confirmar que o problema era de rede e não de credencial/config SIP.
3. **Ferramenta de captura no host Docker**: `tcpdump` não estava disponível sem sudo interativo; solução foi rodar container `nicolaka/netshoot` com `--net=host --cap-add=NET_ADMIN --cap-add=NET_RAW` e volume montado para persistir o `.pcap`.
4. **Processo de deploy precisa de verificação**: arquivos gerados localmente por `import_extensions.py` devem ser sempre copiados para o servidor E para dentro do container — nenhuma automação existe hoje para isso (risco de nova regressão).

## 🔜 Follow-up Recomendado

- [ ] Automatizar sincronização `import_extensions.py` → servidor → container (hoje é manual via scp/docker cp)
- [ ] Documentar a regra de firewall corrigida no Mikrotik (fora do escopo deste repositório, mas relevante para runbook de operação)
- [ ] Validar demais ramais migrados têm a mesma condição de rede (não apenas 1001)

## ✅ Solução

### Passo 1: Sincronizar arquivo local com container

```bash
# No servidor (10.10.10.11), copiar arquivo correto
scp -i ~/.ssh/id_ed25519 \
  /app/zenith-voip/freeswitch/conf/sip_profiles/upstream/upstream-1001.xml \
  administrator@10.10.10.11:~/zenith-voip/freeswitch/conf/sip_profiles/upstream/

# Copiar para o container
docker exec freeswitch cp \
  ~/zenith-voip/freeswitch/conf/sip_profiles/upstream/upstream-1001.xml \
  /etc/freeswitch/sip_profiles/upstream/
```

**Conteúdo esperado**: `proxy` com porta **7060** (PJSIP).

### Passo 2: Recarregar profile upstream

```bash
docker exec freeswitch fs_cli -x "sofia profile upstream rescan"
```

**Efeito**: Relê todos os arquivos em `upstream/*.xml`, reconstrói gateways, sem reiniciar FreeSWITCH.

### Passo 3: Verificar status

```bash
docker exec freeswitch fs_cli -x "sofia status gateway upstream-1001"
```

**Esperado**:
- `Realm`: sip.maisalerta.tecnorise.com:7060
- `Proxy`: sip:sip.maisalerta.tecnorise.com:7060
- `Status`: UP (após 1-2 segundos)
- `State`: REGED (registered)

### Passo 4: Validar REGISTER recebido

Se status não mudar para UP dentro de 30s, fazer packet sniffer no Mikrotik para comparar REGISTER (FS) vs REGISTER bem-sucedido (softphone).

## 🔧 Workflow Correto (para futuras importações)

1. Rodar `import_extensions.py --enable {ext1,ext2}` **localmente**
2. **Copiar arquivos gerados** para servidor:
   ```bash
   scp -r freeswitch/conf/directory/extensions.xml \
     freeswitch/conf/sip_profiles/upstream/ \
     administrator@10.10.10.11:~/zenith-voip/freeswitch/conf/
   ```
3. **Copiar para dentro do container**:
   ```bash
   docker exec freeswitch bash -c \
     "cp -r ~/zenith-voip/freeswitch/conf/* /etc/freeswitch/conf/"
   ```
4. **Recarregar**:
   ```bash
   docker exec freeswitch fs_cli -x "sofia profile upstream rescan"
   docker exec freeswitch fs_cli -x "sofia profile internal rescan"
   ```
5. **Verificar**:
   ```bash
   docker exec freeswitch fs_cli -x "sofia status gateway upstream-1001"
   ```

## 🛡️ Garantias (por design)

- ✅ **CSV é a fonte de verdade**: `specs/export_extensions.csv` vem do VitalPBX
- ✅ **Dedup automático**: Se ramal tem SIP + PJSIP, prevalece PJSIP (porta correta por tecnologia)
- ✅ **Senhas nunca commitadas**: `upstream-*.xml` e `extensions.xml` estão em `.gitignore`
- ✅ **Multi-ramal**: script gera um arquivo por ramal, permite ativar seletivamente via `--enable`
- ✅ **Sem reinício**: `rescan` recarrega sem parar chamadas ativas

## 📋 Checklist de Implementação

- [ ] Copiar arquivo correto do local para servidor
- [ ] Recarregar profile upstream
- [ ] Verificar status do gateway (deve estar UP/REGED)
- [ ] Testar REGISTER via softphone (deve funcionar)
- [ ] Documentar resultado nesta spec
- [ ] Atualizar `CLAUDE.md` com workflow correto se desvio for encontrado
- [ ] Adicionar CI/CD check: verificar sincronização de arquivos antes de deploy
