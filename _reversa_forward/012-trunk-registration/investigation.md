# Investigation: Registro de troncos ATA

> Feature: `012-trunk-registration`
> Data: `2026-08-01`

## Estado atual confirmado

- `PBX` existe no schema `public`, vinculado a `Tenant`; não existe entidade de condomínio ou tronco ATA.
- `freeswitch/conf/directory/default.xml` é placeholder e inclui um `extensions.xml` privado gerado por script.
- `internal.xml` (5060) e `internal-7060.xml` usam Sofia/UDP, `force-register-domain`, mas mantêm `auth-calls=false`.
- `esl_client.py` assina eventos `SOFIA_REGISTER`/`SOFIA_UNREGISTER`, mantém apenas mappings SIP/IP com TTL e não persiste estado de tronco.
- `dialplan/default.xml` lê tenant/PBX de variáveis globais em `vars.xml`, dívida explicitada em `_reversa_sdd/domain.md#TODOs e FIXMEs`.
- `scripts/import_extensions.py` demonstra o formato anterior de importação, mas gera XML com senha em disco e trata ramais/gateways, não a hierarquia aprovada da feature 012.

## Pesquisa oficial

1. FreeSWITCH XML Curl: https://developer.signalwire.com/freeswitch/integration/xml-curl/
   - O binding `directory` atende autenticação SIP a partir de backend HTTP.
   - O binding substitui integralmente o diretório estático para aquela seção.
   - Há suporte a credenciais HTTP, timeout e limite de resposta.
   - O binding é exclusivo para a seção: arquivos estáticos não funcionam como fallback.
2. Carregamento de módulos: https://developer.signalwire.com/freeswitch/configuration/module-loading/
   - Providers XML devem carregar antes dos módulos consumidores; o plano usa `pre_load_modules.conf.xml`.
3. Profiles Sofia: https://developer.signalwire.com/freeswitch/users-and-endpoints/sip-profiles/
   - `auth-calls`, `accept-blind-reg` e `force-register-domain` possuem efeitos distintos; blind auth permanece desabilitado.
4. Catálogo de eventos: https://developer.signalwire.com/freeswitch/programming/events-catalog/
   - Os eventos documentados são `CUSTOM sofia::register`, `sofia::unregister` e `sofia::expire`, com profile, usuário, contato e IP.
5. MultiFernet: https://cryptography.io/en/latest/fernet/
   - A primeira chave cifra novos valores e as demais permitem decifrar/rotacionar valores existentes.

## Alternativas avaliadas

| Alternativa | Vantagens | Falhas para este caso | Veredito |
|-------------|-----------|-----------------------|----------|
| XML estático gerado do CSV | Simples e conhecido no projeto | Senha em disco, drift, reload manual e ausência de tenant-scoping transacional | descartada |
| PostgreSQL acessado diretamente pelo FreeSWITCH | Menos salto HTTP | Acopla schema/credenciais do banco ao switch e contorna serviços/Repository | descartada |
| `mod_xml_curl` somente para ATAs | Banco segue fonte de verdade | Binding exclusivo omitiria usuários existentes | descartada |
| `mod_xml_curl` com provider legado | Preserva `extensions.xml` e adiciona ATAs do banco | Backend passa a ser caminho de auth de todos os usuários | escolhida com rollout por profile |
| Contador inteiro em PostgreSQL | Consulta simples | Eventos duplicados/fora de ordem geram drift ou negativo | descartada |
| Set Redis de UUIDs por tronco | Idempotência natural e `SCARD` derivado | Requer reconciliação após perda do Redis | escolhida |
| Domain por tenant | Permite username repetido | Exige reconfigurar realm/domínio em todos os ATAs e remover `force-register-domain` | adiada |
| Username único por profile | Compatível com ATAs/realm atuais | Importação pode apontar colisões que exigem decisão operacional | escolhida para v1 |

## Spikes bloqueantes antes do rollout

1. Executar `module_exists mod_xml_curl` na imagem candidata; se falso, incorporar o módulo ao build antes de qualquer alteração de profile.
2. Capturar payload real de lookup XML Curl com credencial fictícia e confirmar os nomes de campos que identificam profile, usuário e domínio.
3. Capturar uma amostra privada da extração exclusiva de troncos do VitalPBX e mapear para o CSV canônico sem gravar senha nos artefatos.
4. Confirmar em rehearsal que `CUSTOM sofia::expire` ocorre quando o ATA deixa expirar o registro.
5. Confirmar que variáveis do directory aparecem como `variable_zenith_*` nos eventos de canal antes de remover as globais.
6. Comparar todos os IDs do `extensions.xml` privado com as respostas do provider legado e provar ausência de colisões antes de ativar o binding.

## Evidência T004 — imagem candidata

Verificação somente leitura em `10.10.10.11`, container `zenith-freeswitch`, em 2026-08-03:

- container: `zenith-freeswitch`, imagem `zenith-voip-freeswitch`, estado healthy;
- FreeSWITCH: `1.10.12-release-10222002881-a88d069d6f`;
- `/usr/lib/freeswitch/mod/mod_xml_curl.so`: presente, 26.984 bytes;
- `module_exists mod_xml_curl`: `false`, confirmando que o módulo existe na imagem mas ainda não está carregado;
- nenhum arquivo, profile, módulo ou container foi alterado durante a inspeção.

Conclusão: não é necessário reconstruir a imagem para obter o módulo; a implementação deve carregá-lo pelo pre-load e validar `module_exists=true` apenas no ambiente isolado antes do rollout.

## Evidência T005 — amostra privada do VitalPBX

Foi inspecionado somente o schema e contagens agregadas de `specs/export_extensions.csv`; nenhuma linha, identidade ou senha foi impressa:

- 988 registros: 651 `pjsip`, 320 `sip`, 17 `virtual`;
- 971 registros têm `device_user` não vazio;
- 988 registros têm `device_password` não vazio;
- as 17 ausências de usuário coincidem em quantidade com os registros virtuais, que ficam fora do escopo ATA.

Mapeamento confirmado para o contrato canônico:

| CSV VitalPBX | CSV canônico | Regra |
|--------------|---------------|-------|
| `device_user` | `auth_username` | direto após trim |
| `device_password` | `password` | somente em memória; nunca no relatório |
| `technology=sip` | `technology=sip` | profile `internal` / 5060 |
| `technology=pjsip` | `technology=pjsip` | profile `internal-7060` / 7060 |
| `technology=virtual` | n/a | ignorar |

Campos não confirmados na amostra:

- condomínio e sua chave externa não existem no export;
- `extension` não será tratado como prefixo de condomínio sem evidência da rota/ATA;
- `enabled` permanece `false` por default.

Conclusão: credenciais e tecnologia já estão disponíveis no export atual. Condomínio e prefixo deverão ser associados por fonte complementar privada antes do dry-run real de T043; isso não altera o parser canônico nem autoriza inferir `extension=prefix`.

## Evidência T042 — XML Curl e eventos Sofia isolados

Rehearsal executado em 2026-08-03 exclusivamente na rede Docker `zenith-feature-012-spike-net`, usando `zenith-freeswitch-spike-012`, `zenith-freeswitch-baseline-012` e `zenith-xml-stub-012`. O container operacional `zenith-freeswitch` não foi alterado.

Resultados sanitizados:

- `module_exists mod_xml_curl=true`; binding `directory` carregado antes do Sofia;
- a imagem FreeSWITCH 1.10.12 transmite o valor de `method` literalmente: `post` produziu HTTP 501; `POST` realizou o lookup com sucesso;
- o form real de autenticação trouxe `section=directory`, `sip_profile=internal`, `sip_auth_username=<fixture>` e `key_value=zenith.local`;
- o registro SIP fictício recebeu 401 Digest e depois 200, sem persistir ou imprimir senha;
- `CUSTOM sofia::register` trouxe `profile-name` e `from-user`, além de `zenith_trunk_id` proveniente do XML;
- `CUSTOM sofia::expire` foi observado após o TTL efetivo do profile e trouxe `profile-name` com identidade em `user`/`username`, sem `from-user`;
- a configuração privada permaneceu modo 0600 e `xml_curl debug_off`; os logs anexados contêm apenas nomes de campos e valores não sensíveis.

Adaptações guiadas pela evidência:

- renderer e exemplo usam `method=POST`;
- callback aceita `sip_profile` como campo canônico e `sip_auth_username` antes de aliases;
- `key_value` é somente domínio, nunca fallback de username;
- normalizador de eventos aceita `user`/`username` no caminho `sofia::expire`.

Validação: 26 testes focados verdes. Revisão independente final concluiu que envelope HTTP, precedência de aliases e expiração estão cobertos sem bloqueio restante no escopo T042. O parser de reconciliação e os profiles 7060/5060 com ATA real continuam para T044/T045.

## Arquivos previstos

- `_reversa_sdd/database/trunk-registry/design.md`
- `_reversa_sdd/api/trunk-admin/design.md`
- `_reversa_sdd/telephony/trunk-registration/design.md`
- `alembic/versions/002_ata_trunks.py`
- `src/database/models.py`
- `src/services/trunks.py`
- `src/services/legacy_directory.py`
- `src/api/routers/trunks.py`
- `src/api/freeswitch_directory.py`
- `src/telephony/trunk_state.py`
- `src/telephony/esl_client.py`
- `src/config.py`
- `src/main.py`
- `src/utils/telemetry.py`
- `freeswitch/conf/autoload_configs/pre_load_modules.conf.xml`
- `freeswitch/conf/autoload_configs/xml_curl.conf.xml`
- `freeswitch/conf/autoload_configs/xml_curl.conf.xml.example`
- `scripts/render_freeswitch_secrets.py`
- `freeswitch/conf/sip_profiles/internal.xml`
- `freeswitch/conf/sip_profiles/internal-7060.xml`
- `freeswitch/conf/dialplan/default.xml`
- `.env.example`
- testes colocados ao lado dos componentes alterados, conforme TDD do projeto

## Fora de escopo confirmado

- Troncos de operadora/PSTN.
- Transporte TCP/TLS/WSS.
- Manipulação de dígitos, seleção de fila ou novo motor de roteamento.
- Exclusão física de tronco.
- Migração do profile 5062.
- Alteração dos gateways upstream por ramal, salvo o uso dos metadados autenticados no fluxo já existente.
- Migração dos usuários existentes de `extensions.xml` para o banco; nesta feature eles são atendidos por adaptador somente leitura.
