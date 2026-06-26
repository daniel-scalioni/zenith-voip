# ADR-006: B2BUA com Registration Forwarding como padrão de integração SIP

**Data:** 2026-06-26
**Status:** Aceito
**Contexto:** zenith-voip — integração entre interfones/softphones e PBX de produção do cliente

---

## Contexto

O PBX de produção do cliente ("GPhone", fork do VitalPBX 3) não possui acesso administrativo disponível para o projeto. Interfones e softphones hoje registram diretamente no VitalPBX. Sistemas satélite externos dependem de ver esses ramais como registrados no VitalPBX — não podem ser redirecionados para um servidor diferente sem que o VitalPBX "enxergue" o ramal como presente.

O objetivo do Zenith é interceptar o áudio das chamadas sem alterar a visibilidade dos ramais para o VitalPBX e seus sistemas satélite.

---

## Decisão

FreeSWITCH atua como **B2BUA (Back-to-Back User Agent)** com **Registration Forwarding**:

1. Interfones/softphones são reconfigurados para registrar no FreeSWITCH (em vez do VitalPBX diretamente)
2. Para cada ramal, FreeSWITCH mantém um gateway upstream que registra *como aquele ramal* no VitalPBX, usando as mesmas credenciais SIP
3. O VitalPBX enxerga cada ramal como registrado normalmente — via FreeSWITCH como intermediário transparente
4. FreeSWITCH captura o áudio dos dois lados da chamada via `mod_audio_fork`

---

## Alternativas consideradas

| Alternativa | Por que descartada |
|-------------|-------------------|
| Proxy SIP transparente (sem B2BUA) | Não permite captura de mídia — áudio flui direto entre endpoints |
| Manter registro direto no VitalPBX + espelhamento de porta (SPAN) | Requer acesso à infraestrutura de rede do cliente; fora do escopo |
| Reconfigurar sistemas satélite para aceitar FreeSWITCH como PBX | Requer acesso admin ao VitalPBX e a cada sistema satélite — inviável |

---

## Consequências

**Positivas:**
- VitalPBX e sistemas satélite funcionam sem alteração
- FreeSWITCH tem controle total de sinalização e mídia para todos os ramais intermediados
- Escalável: provisionamento dinâmico via `mod_xml_curl` elimina configuração por ramal

**Negativas / Riscos:**
- Cada ramal requer suas credenciais SIP armazenadas no banco Zenith (risco de segurança → mitigação: cifração em repouso, acesso restrito ao endpoint interno)
- Reconfiguração dos interfones/softphones para apontar ao FreeSWITCH requer acesso aos dispositivos
- Para 1000 ramais iniciais: importação em lote necessária (ver GAP-PROV-02)

---

## Referências

- `_reversa_sdd/telephony/design.md` — topologia completa e fluxo de provisionamento
- `_reversa_forward/002-escala-eventos/requirements.md` — requisitos de escala e multi-tenancy
- `_reversa_sdd/adrs/001-multitenancy-schema-per-tenant.md` — isolamento de dados por tenant
