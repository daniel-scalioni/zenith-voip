# Regression Watch: Registro de troncos ATA

> Feature: `012-trunk-registration`
> Execução parcial: 47 de 55 ações concluídas após T055

## Watch principal

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|-------------------------|-----------------------------|--------------------|-------------------|
| W001 | `_reversa_sdd/domain.md#SIP e Telefonia`, R54 | FreeSWITCH só fica healthy quando `mod_audio_stream` e `mod_xml_curl` estão carregados. | redação | Healthcheck aceita container sem um dos dois módulos. |
| W002 | `docker-compose.infra.yml`, serviço `postgres` | O banco que a API usa é quem detém o alias de rede `postgres` em `zenith-voip_ai-hub-net`. Hoje é o `zenith-postgres-candidate`; o compose ainda declara `zenith-postgres`, que está fora de qualquer rede. | presença | Um `docker compose up` sem `--no-deps` reconecta o `zenith-postgres`, a API passa a apontar para um banco sem `condominiums`/`ata_trunks` e o registro de troncos falha fechado sem erro aparente. |
| W003 | `freeswitch/conf/sip_profiles/internal.xml` | O profile `internal` (5060) tem `auth-calls=true` **em disco** mas ainda não aplicado em memória; o container tem `restart: unless-stopped`. | presença | Qualquer restart do container ou do host aplica autenticação no 5060 sem gate deliberado. A população legada continua atendida pelo binding (verificado: registro 200/200), mas a mudança passa a valer sem decisão humana. |
| W004 | `src/services/trunks.py::upsert_imported` | Reimportar um tronco existente não deve deixar o estado operacional inconsistente. | redação | `registration_status` volta para `unknown` enquanto `last_registered_at`/`last_unregistered_at` seguem preenchidos — observado no tronco 1780 em 2026-08-06. Um tronco registrado que for reimportado passa a reportar estado desconhecido sem que nada tenha mudado na telefonia. |

## Observações

- O binding exige `method=POST` em maiúsculas na imagem FreeSWITCH 1.10.12; `post` causa HTTP 501.
- O envelope XML Curl observado usa `sip_profile`, `sip_auth_username` e `key_value` como domínio.
- `sofia::expire` foi observado com `profile-name` e identidade em `user`/`username`.
- Usuários de `extensions.xml`, profile 5062 e gateways upstream continuam protegidos; equivalência real aguarda T055.
- O tronco 1020 é identidade SIP, não prefixo: o Zenith deve preservar o destino `100` sem adicionar ou remover dígitos.
- A configuração individual de Parque Portugal foi importada com `prefix=null` e `enabled=false`; a ativação real continua bloqueada por T044.
- A equivalência do diretório legado foi comprovada para 939 usuários, sem ausências ou divergências; um registro legado real em 7060 e sua remoção retornaram SIP 200.
- O binding XML Curl é declarado por seção (`bindings="directory"`), nunca por profile: uma vez ativo, vale para 5060, 7060 e 5062 simultaneamente. O que isola o 5062 hoje é `auth-calls=false`, não o alcance do binding.
- Com o binding global ativo, um usuário legado registrou no profile `internal` (5060) com 200/200, confirmando que o provider somente-leitura atende a população existente.

## Histórico de re-extrações

Nenhuma.

## Arquivadas

Nenhuma.
