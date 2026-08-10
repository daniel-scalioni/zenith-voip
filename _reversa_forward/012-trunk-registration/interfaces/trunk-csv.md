# Interface de arquivo: Importação de troncos VitalPBX

> Formato canônico UTF-8, delimitado por vírgula, cabeçalho obrigatório.

## Colunas

| Coluna | Obrigatória | Regra |
|--------|-------------|-------|
| `condominium_external_id` | não | chave estável; recomendada |
| `condominium_name` | sim | 1–128 caracteres |
| `prefix` | não | quando presente, 1–32 dígitos e único no tenant; nunca inferir de `auth_username` |
| `auth_username` | sim | 1–128 caracteres; único no profile |
| `password` | sim para novo | não vazia; nunca incluída em erro/relatório |
| `technology` | sim | `sip` ou `pjsip` |
| `enabled` | não | default `false`; valores `true/false/1/0` |

Mapeamento de tecnologia:

- `sip` → `internal` / UDP / 5060;
- `pjsip` → `internal-7060` / UDP / 7060.

`tenant_id` e `pbx_id` não são aceitos no arquivo: tenant vem do JWT e PBX do parâmetro autenticado da requisição.

## Exemplo exclusivamente fictício

```csv
condominium_external_id,condominium_name,prefix,auth_username,password,technology,enabled
demo-01,Condominio Exemplo,1140,ata-demo-1140,fixture-not-a-secret,pjsip,false
```

## Validação e idempotência

- máximo 5 MiB e 10.000 linhas;
- BOM UTF-8 é tolerado; encoding inválido é rejeitado;
- espaços externos são removidos; valores internos são preservados;
- linha vazia é ignorada;
- headers desconhecidos geram aviso, não são persistidos;
- mesma identidade `(sip_profile,auth_username)` atualiza o tronco quando o prefixo estiver ausente; prefixo não nulo continua único por tenant;
- `dry_run` executa parsing, normalização, constraints e relatório sem persistência;
- erro estrutural de arquivo aborta tudo; erros de linha são enumerados sem ecoar conteúdo sensível.

## Adaptação da exportação real

Quando a instalação do VitalPBX não oferecer exportação de troncos, o cadastro individual usa o mesmo contrato normalizado a partir de configuração privada. Aliases nativos só serão adicionados depois de confirmados por evidência e cobertos por fixture sanitizada. Arquivos reais permanecem fora do Git.
