# Interface HTTP/XML: Diretório dinâmico FreeSWITCH

> Endpoint interno: `POST /internal/freeswitch/directory`
> Consumidor exclusivo: `zenith-freeswitch` via `mod_xml_curl`
> Binding: somente `directory`

Como o binding é a única autoridade da seção, o endpoint resolve duas fontes em ordem segura:

1. troncos ATA ativos no banco;
2. usuários legados no `extensions.xml` privado, por provider somente leitura.

Se as duas fontes resolverem a mesma identidade no mesmo profile, a resposta falha fechado como ambígua.

## Transporte e autenticação

- URL operacional via loopback do host para `zenith-api-1`.
- HTTP Basic dedicado configurado por segredo privado, distinto de ESL/JWT. O arquivo real `xml_curl.conf.xml` é gerado atomicamente com modo 0600 e é gitignored; o repositório contém apenas `.example` sem valor.
- Timeout do cliente FreeSWITCH: 2 segundos.
- Resposta máxima: 64 KiB.
- Headers: `Content-Type: application/xml; charset=utf-8`, `Cache-Control: no-store`.
- O proxy público bloqueia `/internal/*` antes de encaminhar à API.

## Entrada

O `mod_xml_curl` envia form fields. O adaptador aceita o envelope oficial e extrai apenas uma allowlist necessária:

- `section` deve ser `directory`;
- `tag_name`, `key_name`, `key_value`;
- usuário/autenticação (`sip_auth_username`, confirmado no spike T042; `user` permanece como alias);
- profile (`sip_profile`, confirmado no spike T042; aliases `sip_profile_name`/`variable_sofia_profile_name` permanecem aceitos);
- domínio solicitado em `key_value` (ou `domain` quando presente); `key_value` nunca é fallback de username.

Quando campos canônicos e aliases coexistirem, `sip_profile` vence os aliases de profile e `sip_auth_username` vence `user`.

Campos desconhecidos são ignorados e nunca logados em bloco.

## Resposta encontrada

Documento XML mínimo com um único usuário, senha decifrada apenas durante a serialização e variáveis:

```xml
<document type="freeswitch/xml">
  <section name="directory">
    <domain name="zenith.local">
      <groups>
        <group name="default">
          <users>
            <user id="ata-1140">
              <params>
                <param name="password" value="REDACTED_AT_REST"/>
              </params>
              <variables>
                <variable name="user_context" value="default"/>
                <variable name="zenith_tenant_id" value="uuid"/>
                <variable name="zenith_pbx_id" value="uuid"/>
                <variable name="zenith_condominium_id" value="uuid"/>
                <variable name="zenith_trunk_id" value="uuid"/>
                <variable name="zenith_trunk_prefix" value="1140"/>
              </variables>
            </user>
          </users>
        </group>
      </groups>
    </domain>
  </section>
</document>
```

O valor real de `password` existe apenas na resposta em memória e não pode ser persistido, logado ou anexado a erro.

## Não encontrado/falha fechada

Retornar o documento FreeSWITCH `not found` quando:

- usuário/profile não existe;
- tronco ou condomínio está desabilitado;
- PBX/tenant não está ativo;
- identidade é ambígua;
- section não é `directory`.

## Compatibilidade de usuários legados

- O provider lê somente `extensions.xml`, rejeita DTD/entidades externas e nunca altera o arquivo.
- O arquivo pode ser um fragmento de include com vários `<user>` consecutivos; o provider usa raiz sintética apenas em memória para analisá-lo.
- O parsing é cacheado por caminho + `mtime`; mudança do arquivo invalida o cache.
- Usuário legado recebe seus params/variables equivalentes, sem `zenith_trunk_id` inventado.
- O response XML nunca é logado; erros citam apenas código e request-id.
- Binding não pode ser ativado até uma comparação provar que todos os IDs legados válidos são resolvidos.

Autenticação HTTP inválida retorna 401 sem XML de usuário. Chave de cifra indisponível/cifra inválida retorna 503 e registra somente `trunk_id` + código sanitizado.

## Idempotência e observabilidade

- Lookup é somente leitura e idempotente.
- Métricas permitidas: resultado (`found`, `not_found`, `error`), profile e latência.
- Proibido usar username, prefixo, tenant, IP, password ou resposta XML como label.
- Logs registram request-id, profile e resultado; nunca form body completo.
