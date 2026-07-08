# Deploy, Design

**Stack:** 15 containers Docker (incluindo `arq-uploader`, novo), BunkerWeb proxy, FreeSWITCH host network
**HA:** 2 instâncias FastAPI com sticky session via X-Call-ID
**GPU:** Reservada para Ollama via docker-compose device mapping
**Deploy:** deploy.sh com backup + health check + rollback; `scripts/setup-recording-mvp.sh` para provisionar a infra do MVP de gravação (build do FreeSWITCH custom, migrations, workers)
**Storage de gravação:** disco local (`./data/recordings` no host, bind mount em `fastapi-1`/`fastapi-2`/`arq-uploader`/`arq-cleanup`) — decisão de produto em 2026-06-22, substitui S3 (nunca chegou a ser provisionado: `S3_ENDPOINT` vazio nos `.env.*.example`, sem MinIO no compose)
**Origem:** `docker-compose.app.yml`, `deploy.sh`, `scripts/setup-recording-mvp.sh` 🟢

## Risco em resolução (2026-06-22, atualizado 2026-06-24)

🔴 A imagem `safarov/freeswitch:1.10.12` referenciada no compose é uma build vanilla do FreeSWITCH — **não inclui `mod_audio_fork`** (confirmado via inspeção direta da imagem, módulo ausente). `freeswitch/Dockerfile` foi criado para compilar o módulo (fonte: `drachtio-freeswitch-modules`, contra `freeswitch-dev` do repositório APT da SignalWire) e empacotá-lo sobre a imagem original — requer um token de conta SignalWire (`freeswitch/signalwire_token.txt`, ver `freeswitch/signalwire_token.txt.example`), passado como build secret. **Validado contra build real em 2026-06-24** (servidor `10.10.10.11`): build falha com `401 Unauthorized` — o token atual é rejeitado pelo repositório APT da SignalWire. Renovação do token é responsabilidade do usuário (conta SignalWire); ver GAP-11.

## Boot básico do FreeSWITCH (ciclo `004-bootstrap-freeswitch`, 2026-06-24)

🟢 `freeswitch/conf/` recebeu a config raiz completa que faltava (`vars.xml`, `freeswitch.xml`, `acl.conf.xml`, `autoload_configs/event_socket.conf.xml`, `autoload_configs/sofia.conf.xml`, `directory/default.xml`) e a correção de `mod_esl` → `mod_event_socket` em `modules.conf.xml` (módulo inexistente carregado por engano). Enquanto o token SignalWire não for renovado (risco acima), o serviço `freeswitch` usa `image: safarov/freeswitch:1.10.12` direto (sem o `build:` customizado) e sem `mod_audio_fork` carregado — decisão registrada em `_reversa_forward/004-bootstrap-freeswitch/roadmap.md#D-06`, fora do escopo deste ciclo (sem gravação).

Validado com boot real: container subiu via `docker compose -f docker-compose.infra.yml -f docker-compose.app.yml up -d freeswitch` em `10.10.10.11` (deploy isolado em `/home/administrator/zenith-voip`, primeira implantação desse projeto nesse servidor — ver GAP-16) e permaneceu estável por 90s de observação (`RestartCount=0`, sem erro fatal nos logs). Detalhe completo em `_reversa_forward/004-bootstrap-freeswitch/`.

GAP-17 resolvido em 2026-06-26: `internal.xml` corrigido (TLS desativado, porta 5060 apenas).

**Atualização 2026-07-08 (feature `006-registro-porta-vitalpbx`):** `internal.xml` deixou de ser o único profile de entrada. Dois profiles novos foram adicionados — `sip_profiles/internal-7060.xml` (porta 7060) e `sip_profiles/internal-5062.xml` (porta 5062) — para que um ramal migre da VitalPBX trocando só o endereço do servidor no aparelho, sem reconfigurar porta. Os três profiles de entrada compartilham `force-register-domain=$${domain}` (correção aplicada primeiro em `internal.xml`, feature `006-registro-porta-vitalpbx`, para resolver mismatch de domínio em softphones como o 3CX) e as mesmas variáveis dinâmicas de IP (`$${local_ip}`, `$${external_sip_ip}`) já usadas pelo sidecar `ip-watcher` (feature `005-dynamic-external-ip`). Validado em produção com o ramal 1001 (registro real via 3CXPhone na porta 7060).

## B2BUA Registration Forwarding — provisão de ramais (2026-06-26)

🟢 Estratégia definida e implementada para o MVP (ADR-006):

- **Profile `upstream`** (`sip_profiles/upstream.xml`, porta 5065): perfil SIP separado do `internal` exclusivo para gateways upstream ao VitalPBX (`sip.maisalerta.tecnorise.com`). Separação evita que um `sofia profile upstream rescan` derrube REGISTERs ativos dos interfones no `internal`.
- **`vars.xml`**: variável `pbx_host=sip.maisalerta.tecnorise.com` adicionada; gateways upstream referenciam via `$${pbx_host}`.
- **Importação em lote**: `scripts/import_extensions.py` lê `specs/export_extensions.csv` (exportado do VitalPBX) e gera:
  - `freeswitch/conf/directory/extensions.xml` — usuários para autenticação local dos interfones
  - `freeswitch/conf/sip_profiles/upstream/*.xml` — um gateway por ramal para registro upstream no VitalPBX
- **Segurança**: arquivos gerados com senhas em texto (`extensions.xml`, `upstream/*.xml`, `specs/export_extensions.csv`) são gitignored; apenas estrutura sem credenciais está no repositório.
- **Futuro**: substituir arquivos estáticos por `mod_xml_curl` → FastAPI → PostgreSQL (`SIPExtension`) quando o ciclo de provisionamento dinâmico for implementado (GAP-PROV-01).

## Status do deploy B2BUA (2026-06-29)

🔴 **GAP-UPSTREAM-01 — Gateways upstream em FAIL_WAIT**

Deploy executado com sucesso (git clone no servidor + 939 arquivos de gateway copiados via scp).
FreeSWITCH subiu, profiles `internal` e `upstream` carregados. Porém todos os 939 gateways
estão em `FAIL_WAIT` — o VitalPBX (`sip.maisalerta.tecnorise.com`) está rejeitando os registros.

**Causas prováveis (a verificar em ordem):**

1. **IP não liberado no VitalPBX** ← mais provável
   O IP `10.10.10.11` nunca registrou SIP no VitalPBX antes. O VitalPBX (FreePBX-based) usa
   firewall e fail2ban que bloqueiam IPs desconhecidos. O administrador do VitalPBX precisa
   adicionar `10.10.10.11` à lista de IPs permitidos para registro SIP.

2. **Divergência de senha**
   As senhas vieram do campo `device_password` do CSV exportado do VitalPBX. Se os ramais usam
   senhas diferentes para registro externo (SIP trunk vs. registro de dispositivo), podem divergir.
   Teste: tentar registrar manualmente um ramal com a senha do CSV em um softphone apontando para
   `sip.maisalerta.tecnorise.com` direto (sem FreeSWITCH no meio) — se falhar, o problema é de senha.

**Ação necessária**: acionar administrador do VitalPBX para liberar `10.10.10.11`.
Plano de deploy completo: `_reversa_sdd/infra/deployment/deploy-phase1-b2bua.md`
