# Data Delta: Registro de Entrada na Mesma Porta do Cadastro VitalPBX

> Identificador: `006-registro-porta-vitalpbx`
> Data: `2026-07-08`

## 1. Resumo

Não há alteração em modelo de dados de aplicação (banco de dados, entidades SQLAlchemy, schema multi-tenant). A mudança é inteiramente em configuração de infraestrutura SIP do FreeSWITCH — arquivos XML de profile, não linhas de banco de dados.

## 2. Estruturas de configuração afetadas (não são "dados" de aplicação, mas documentadas aqui por serem o equivalente conceitual)

| Estrutura | Antes | Depois |
|-----------|-------|--------|
| `freeswitch/conf/sip_profiles/internal.xml` | Único profile de entrada, porta 5060 | Inalterado nesta feature (já corrigido nesta sessão com `force-register-domain`) |
| `freeswitch/conf/sip_profiles/internal-7060.xml` | Não existe | Novo arquivo, profile de entrada na porta 7060 |
| `freeswitch/conf/sip_profiles/internal-5062.xml` | Não existe | Novo arquivo, profile de entrada na porta 5062 |
| `freeswitch/conf/directory/extensions.xml` | Um `<user>` por ramal, compartilhado por todos os profiles | Sem mudança — continua compartilhado, nenhum campo novo necessário |

## 3. Migração necessária

Nenhuma migração de banco de dados (`alembic`) é necessária. A "migração" aqui é operacional: copiar os novos arquivos de profile para o host de produção e iniciar os profiles via `fs_cli`, sem downtime do profile `internal` existente (RF-02).
