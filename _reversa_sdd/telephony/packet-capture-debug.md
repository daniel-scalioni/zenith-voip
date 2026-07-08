---
spec:
  component: packet-capture-debug-upstream-1001
  layer: telephony
  status: active
  version: 1.0.0
  language: text
  patterns: [b2bua-debugging, sip-comparison]
  inputs:
    - name: problematic_register
      type: pcap
      from: Mikrotik packet sniffer (FreeSwitch → VitalPBX)
    - name: working_register
      type: pcap
      from: Mikrotik packet sniffer (Softphone → VitalPBX)
  outputs:
    - name: sip_diff_report
      type: markdown
      to: Analysis of this document
  dependencies:
    - component: upstream-registration-fix
      layer: telephony
  updated_at: 2026-07-03
---

# Packet Capture Debug — Upstream-1001 Registration

## 🎯 Objetivo

Comparar REGISTER (FreeSwitch vs Softphone) para identificar SIP headers, SDP, ou outros campos que causam a rejeição do VitalPBX.

## 📊 Estado Atual (2026-07-03 após upstream-registration-fix)

**FreeSwitch**:
- ✅ Porta corrigida para 7060 (PJSIP)
- ✅ Profile carregado corretamente
- ❌ Status: DOWN, FAIL_WAIT — VitalPBX não aceita REGISTER

**Softphone (3CX)**:
- ✅ Registra com sucesso no mesmo VitalPBX (ambos SIP 5060 e PJSIP 7060)

## 📍 Endereços para Captura

| Origem | IP | Porta |
|--------|-----|-------|
| **FreeSwitch** | 10.10.10.11 | 5065 (upstream profile) |
| **Softphone** | {IP local} | variável (efêmera) |
| **VitalPBX** | 177.71.153.68 | 7060 (PJSIP) |

## 🔍 Procedimento de Captura no Mikrotik

1. **Abrir sniffer** no Mikrotik (IP gateway entre cliente e internet):
   ```
   /tool packet-sniffer
   set filter-interface=<WAN_INTERFACE>
   set filter-protocol=udp
   set filter-port=7060
   set file-name=register-debug.pcap
   start
   ```

2. **Capturar dois cenários:**
   - **Cenário 1**: FreeSwitch tenta registrar (deixar rodando por 30s)
   - **Cenário 2**: Softphone registra com sucesso (deixar rodando por 5s)

3. **Salvar PCAP** e fazer download

## 🔎 Análise Esperada

### Campos a comparar (SIP REGISTER):

| Campo | FreeSwitch | Softphone | Impacto |
|-------|------------|-----------|---------|
| **REGISTER Request-URI** | sip:sip.maisalerta.tecnorise.com:7060 | idem | Deve ser idêntico |
| **User-Agent** | FreeSWITCH-mod_sofia/VERSION | 3CX Phone/VERSION | Talvez rejeitado? |
| **From** | <sip:1001@sip.maisalerta.tecnorise.com:7060> | Deve ser igual | |
| **To** | <sip:1001@sip.maisalerta.tecnorise.com:7060> | Deve ser igual | |
| **Contact** | <sip:gw+upstream-1001@200.170.149.139:5065;transport=udp;gw=upstream-1001> | Deve ser igual | IP público (correto) |
| **Call-ID** | UUID gerado pelo FS | UUID único | Deve variar por REGISTER |
| **Via** | Via: SIP/2.0/UDP 200.170.149.139:5065 | Via: SIP/2.0/UDP {softphone_ip}:port | Topo da rota |
| **CSeq** | Número sequencial | Deve incrementar | |
| **Authorization** (se 407) | Digest auth fields | Deve ser similar | Autenticação |

### Cenários de resposta:

- **200 OK**: REGISTER aceito ✅
- **401 Unauthorized**: Senha errada / realm mismatch 🔴
- **403 Forbidden**: Extensão bloqueada/inativa no VitalPBX 🔴
- **407 Proxy Authentication**: Proxy exigindo auth (raro) 🔴
- **SIP Timeout**: Firewall bloqueando resposta 🔴
- **ICMP Port Unreachable**: Porta 7060 não aberta 🔴

## 🛠️ Ferramenta de Análise

```bash
# Usar Wireshark ou tshark para extrair SIP messages
tshark -r register-debug.pcap -Y sip.method==REGISTER -V
```

## 📝 Checklist

- [ ] Capturar REGISTER (FreeSwitch)
- [ ] Capturar REGISTER (Softphone bem-sucedido)
- [ ] Comparar User-Agent, From, To, Contact, Via
- [ ] Identificar campo diferente
- [ ] Ajustar config FreeSwitch se necessário
- [ ] Retornar a esta spec com resultado
