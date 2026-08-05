# Regression Watch: Registro de troncos ATA

> Feature: `012-trunk-registration`
> Execução parcial: 47 de 55 ações concluídas após T055

## Watch principal

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|-------------------------|-----------------------------|--------------------|-------------------|
| W001 | `_reversa_sdd/domain.md#SIP e Telefonia`, R54 | FreeSWITCH só fica healthy quando `mod_audio_stream` e `mod_xml_curl` estão carregados. | redação | Healthcheck aceita container sem um dos dois módulos. |

## Observações

- O binding exige `method=POST` em maiúsculas na imagem FreeSWITCH 1.10.12; `post` causa HTTP 501.
- O envelope XML Curl observado usa `sip_profile`, `sip_auth_username` e `key_value` como domínio.
- `sofia::expire` foi observado com `profile-name` e identidade em `user`/`username`.
- Usuários de `extensions.xml`, profile 5062 e gateways upstream continuam protegidos; equivalência real aguarda T055.
- O tronco 1020 é identidade SIP, não prefixo: o Zenith deve preservar o destino `100` sem adicionar ou remover dígitos.
- A configuração individual de Parque Portugal foi importada com `prefix=null` e `enabled=false`; a ativação real continua bloqueada por T044.
- A equivalência do diretório legado foi comprovada para 939 usuários, sem ausências ou divergências; um registro legado real em 7060 e sua remoção retornaram SIP 200.

## Histórico de re-extrações

Nenhuma.

## Arquivadas

Nenhuma.
