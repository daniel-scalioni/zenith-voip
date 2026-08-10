# Adendo — Registro de troncos ATA

> Feature: `012-trunk-registration`
> Data: `2026-08-10`
> Cenário: legado

## Vigência

Vigente desde 2026-08-10.

## Resumo da entrega

A feature permite cadastrar, importar e acompanhar troncos de ATAs (adaptadores telefônicos analógicos) dos condomínios atendidos pelo Zenith, na hierarquia `Tenant → PBX → Condomínio → Tronco ATA`. Cada ATA se registra no FreeSWITCH via SIP (portas 5060/7060, UDP) com credenciais próprias, cifradas em repouso; o Zenith identifica tenant/PBX/condomínio/tronco sem assumir manipulação de dígitos, fila ou roteamento — isso continua no ATA e no VitalPBX. Estado administrativo, registro SIP e uso em chamada são apresentados como dimensões independentes.

56 de 56 ações concluídas, incluindo os checkpoints que exigiam evidência real de ambiente (não inferência): T044 com ATA físico real registrado em 7060, T046 com prefixo idêntico entre dois tenants registrado simultaneamente via SIP real, T047 com auditoria de vazamento de credencial por canário real.

## Impacto por artefato da extração

| Artefato | Seção | Tipo de impacto | Delta |
|---|---|---|---|
| `_reversa_sdd/domain.md#PBXs` (R05, R07) | Glossário e hierarquia PBX | regra-nova | PBX passa a ter condomínios e troncos ATA subordinados; portas 5060/7060 permanecem, ver `legacy-impact.md` para o detalhamento por profile. |
| `_reversa_sdd/domain.md#SIP e Telefonia` (R24-R26, R54) | Registro/expiração SIP e healthcheck | regra-alterada | `mod_xml_curl` passa a ser autoridade de diretório dinâmico nos profiles-alvo (7060); healthcheck do FreeSWITCH passa a exigir também `mod_xml_curl` carregado, além de `mod_audio_stream`; TTL/linkage/reconexão ESL legados preservados sem alteração. |
| `_reversa_sdd/domain.md#Chamadas` (R46) | Persistência de chamada por `tenant_id` | preservada | Nenhuma mudança; chamada sem `tenant_id` continua sem persistência. |
| `_reversa_sdd/domain.md#API e Segurança` (R52-R56) | Isolamento de instância, prefixo Docker, binding de porta | preservada | Nenhuma mudança; recursos novos seguem prefixo `zenith-` e API em loopback. |
| `_reversa_sdd/architecture.md#Papel do FreeSWITCH: B2BUA com Registration Forwarding` | Registro na borda | delta-de-contrato-externo | O FreeSWITCH, que já recebia registros na borda, ganha um segundo caminho de diretório dinâmico (XML Curl) coexistindo com o `extensions.xml` estático, sem substituí-lo. |
| `_reversa_sdd/architecture.md#Dívidas Técnicas` | Multitenancy real na telefonia | regra-nova | Endereça parcialmente a dívida de variáveis globais fixas de tenant/PBX citada no legado: o novo registry resolve tenant/PBX/condomínio/tronco por identidade SIP, mas o gap mais amplo de multitenancy na telefonia segue fora do escopo desta feature. |
| `src/database/models.py`, `alembic/versions/002_ata_trunks.py` (componente novo) | schema público | componente-novo | Novas tabelas `condominiums`/`ata_trunks`, escopadas por tenant/PBX; ver `legacy-impact.md` para constraints. |
| `src/services/trunks.py`, `trunk_import.py`, `trunk_credentials.py`, `legacy_directory.py` (componente novo) | camada de serviço | componente-novo | Registry, importação CSV/JSON, cifra `MultiFernet` de senha SIP e provider somente-leitura de compatibilidade com `extensions.xml`. |
| `src/api/routers/trunks.py`, `src/api/freeswitch_directory.py` (componente novo) | API administrativa e callback interno | componente-novo | CRUD administrativo tenant-scoped (`PATCH` ainda ausente, ver W006) e callback XML Curl interno autenticado. |
| `src/telephony/trunk_state.py` (componente novo) | estado operacional | componente-novo | Normaliza eventos de registro/desregistro/expiração, persiste estado e reconcilia registros e chamadas ativas contra o FreeSWITCH. |

## Regras sob vigilância

`W001`–`W007`, apontador completo em `_reversa_forward/012-trunk-registration/regression-watch.md`.

## Fontes

- `_reversa_forward/012-trunk-registration/legacy-impact.md`
- `_reversa_forward/012-trunk-registration/regression-watch.md`
- `_reversa_forward/012-trunk-registration/requirements.md`
- `_reversa_forward/012-trunk-registration/progress.jsonl`
