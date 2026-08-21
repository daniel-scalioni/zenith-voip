---
spec:
  component: trunk-admin
  layer: api
  status: active
  version: 1.2.0
  language: python
  patterns: [repository, dependency-injection]
  inputs: [{name: admin_request, type: HTTP, from: tenant-admin}, {name: directory_lookup, type: HTTPForm, from: freeswitch}]
  outputs: [{name: trunk_view, type: JSON, to: tenant-admin}, {name: directory_xml, type: XML, to: freeswitch}]
  dependencies: [{component: trunk-registry, layer: database}, {component: auth, layer: api}, {component: trunk-registration, layer: telephony}]
  events_produced: []
  updated_at: 2026-08-18
---

# Administração e Diretório de Troncos

## Visão Geral

Esta unit administra condomínios e troncos ATA dentro do tenant autenticado e atende o lookup
privado de usuários do FreeSWITCH. Separa o contrato humano JWT do contrato máquina-a-máquina
Basic Auth. 🟢

## Responsabilidades

- Expor cadastro, consulta, alteração e importação de condomínios/troncos sem vazar segredo. 🟢
- Resolver identidades de diretório entre banco e XML legado com exclusividade e falha fechada. 🟢
- Derivar todo escopo administrativo do JWT, nunca do payload importado. 🟢

## Regras de Negócio

- Somente `tenant_admin` acessa operações administrativas; recurso de outro tenant é 404. 🟢
- Criação/importação inicia tronco desabilitado; não existe DELETE físico neste contrato. 🟢
- Username exibido é mascarado; senha e cifra nunca aparecem em response, log ou erro. 🟢
- CSV aceita até 5 MiB/10.000 linhas; JSON operacional exige mapa explícito para condomínio. 🟢
- Lookup presente simultaneamente no banco e legado retorna not-found, sem escolher fonte. 🟢
- Alterações parciais usam PATCH, derivam o tenant exclusivamente do JWT e rejeitam nulos/vazios
  para campos não anuláveis. Mudança de condomínio é revalidada contra tenant e PBX. 🟢
- Toda view de tronco consulta a cardinalidade Redis atual; `in_use` é derivado do resultado. 🟢
- Falha Redis depois de uma mutação não muda o resultado persistido em erro: a leitura de uso
  degrada para zero com log da exceção original. 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|---|---|---|---|
| RF-01 | Administrar condomínios e troncos dentro do tenant do JWT | Must | CRUD parcial não alcança recursos de outro tenant 🟢 |
| RF-02 | Importar CSV e JSON operacional com dry-run sem persistência/cifra | Must | dry-run mantém banco inalterado e não chama cipher 🟢 |
| RF-03 | Rejeitar lote JSON inteiro se qualquer item falhar no pré-voo | Must | nenhuma linha é persistida após erro de uma entrada 🟢 |
| RF-04 | Servir diretório XML Curl por profile+auth_username | Must | identidade habilitada recebe XML escapado e variáveis autenticadas 🟢 |
| RF-05 | Preservar usuário legado quando não houver identidade no banco | Must | params/variables do XML privado são reproduzidos sem alteração 🟢 |
| RF-06 | Sanitizar todas as saídas sensíveis | Must | senha-canário não aparece em JSON/XML de erro/log 🟢 |
| RF-07 | Alterar condomínio e tronco por PATCH tenant-scoped | Must | services recebem o tenant do JWT e recurso estrangeiro retorna 404 🟢 |
| RF-08 | Expor `active_calls` real em POST, PATCH e GET de troncos | Must | API consulta `TrunkStateService.active_calls` por ID e deriva `in_use` 🟢 |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|---|---|---|---|
| Segurança | JWT tenant-scoped no admin e Basic dedicado no callback | `src/api/routers/trunks.py`; `src/api/freeswitch_directory.py` | 🟢 |
| Segurança | Resposta XML limitada a 64 KiB e sem cache | `src/api/freeswitch_directory.py` | 🟢 |
| Disponibilidade | Timeout XML Curl de 2 s e not-found em ambiguidade/falha | `freeswitch/conf/autoload_configs/xml_curl.conf.xml.example` | 🟢 |
| Privacidade | Configuração real do binding é 0600 e gitignored | `scripts/render_freeswitch_secrets.py` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado um tenant_admin e um PBX do mesmo tenant
Quando ele cria um tronco com identidade válida
Então o tronco é persistido desabilitado e a resposta omite senha e cifra

Dado um recurso pertencente a outro tenant
Quando o administrador tenta consultá-lo ou alterá-lo
Então a API responde 404 sem revelar sua existência

Dado que a mesma identidade existe no banco e no XML legado
Quando o FreeSWITCH solicita o diretório
Então o callback falha fechado com resposta not-found e sem credenciais

Dado um lote JSON com uma linha inválida
Quando a importação real é solicitada
Então nenhuma linha do lote é persistida
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|---|---|---|
| Diretório autenticado | Must | Registro SIP depende deste caminho crítico 🟢 |
| Isolamento e segredo | Must | Falha expõe outro tenant ou credencial 🟢 |
| Importação em lote | Should | Há cadastro individual como alternativa 🟢 |
| DELETE físico | Won't | Ausente deliberadamente na versão atual 🟢 |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---|---|---|
| `src/api/freeswitch_directory.py` | `DirectoryLookupService`, `freeswitch_directory` | 🟢 |
| `src/api/routers/trunks.py` | endpoints administrativos e importação | 🟢 |
| `src/services/trunk_import.py` | parsers/importadores CSV e JSON | 🟢 |
| `src/services/legacy_directory.py` | `LegacyDirectoryProvider` | 🟢 |
