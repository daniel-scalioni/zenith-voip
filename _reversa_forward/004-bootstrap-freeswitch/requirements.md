# Requirements: Bootstrap FreeSWITCH (container saudável)

> Identificador: `004-bootstrap-freeswitch`
> Data: `2026-06-23`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

O container `freeswitch` do `docker-compose.app.yml` precisa subir e permanecer estável (sem crash/restart loop). Hoje a config em `freeswitch/conf/` está incompleta — falta a base mínima que qualquer instância FreeSWITCH precisa para inicializar — e o serviço provavelmente não sobe. Esta feature entrega só a estabilização do boot; nenhuma funcionalidade de gravação de chamada (gateway por ramal, `mod_xml_curl`, dialplan de gravação, WebSocket de áudio, ESL listener) faz parte deste ciclo.

## 2. Contexto a partir do legado

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `_reversa_sdd/infra/deployment/design.md` | FreeSWITCH roda em `network_mode: host`; imagem base `safarov/freeswitch:1.10.12` não inclui `mod_audio_fork`; `freeswitch/Dockerfile` compila o módulo via `drachtio-freeswitch-modules` sobre essa imagem, "ainda não validado contra build real" | 🟢 |
| `_reversa_sdd/infra/deployment/requirements.md` | Responsabilidades de infra incluem orquestração Docker e FS host | 🟢 |
| `_reversa_sdd/architecture.md#Dívidas Técnicas` | TD05: ESL password = "ClueCon" (default FreeSWITCH), sem hardening ainda | 🟡 |
| Leitura direta de `freeswitch/conf/` (não documentada em nenhuma spec até agora) | A pasta só contém `autoload_configs/modules.conf.xml`, `dialplan/default.xml` e `sip_profiles/internal.xml`. Faltam `vars.xml`, `freeswitch.xml` (raiz), `acl.conf.xml`, `autoload_configs/event_socket.conf.xml`. O `docker-compose.app.yml` monta `./freeswitch/conf:/etc/freeswitch`, substituindo por inteiro a config padrão da imagem base | 🟢 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| Operador de infraestrutura (MASTER) | Subir o ambiente de telefonia sem o container `freeswitch` falhar/reiniciar em loop | Roda `docker compose -f docker-compose.app.yml up -d freeswitch` no servidor real (`10.10.10.11`) e confirma que o container permanece de pé |

## 4. Regras de negócio novas ou alteradas

1. **RN-01:** O diretório `freeswitch/conf/` montado no container deve conter uma configuração raiz completa e autocontida (não pode depender de arquivos que só existiam na imagem base e foram ocultados pelo bind mount). 🟢
   - Tipo: nova
2. **RN-02:** Esta etapa não introduz nenhuma extensão, gateway, profile externo ou módulo de gravação — apenas o necessário para o processo `freeswitchd` inicializar e ficar de pé. Esses recursos chegam em ciclos `/reversa-forward` futuros, cada um com sua própria spec. 🟢
   - Tipo: nova

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| RF-01 | Criar `freeswitch/conf/vars.xml` com as variáveis hoje referenciadas sem definição em `sip_profiles/internal.xml` (`domain`, `local_ip`, `external_rtp_ip`, `external_sip_ip`, `global_codec_prefs`) | Must | `internal.xml` resolve `$${domain}` e demais variáveis sem ficar vazio | 🟢 |
| RF-02 | Criar `freeswitch/conf/freeswitch.xml` (config raiz) incluindo `vars.xml`, `sip_profiles/*.xml`, `dialplan/*.xml`, `autoload_configs/*.xml` e `directory/*.xml` | Must | Processo `freeswitchd` carrega sem erro de XML ausente/raiz não encontrada | 🟢 |
| RF-03 | Criar `freeswitch/conf/autoload_configs/event_socket.conf.xml` (porta 8021, password = `FREESWITCH_ESL_PASSWORD`, ACL liberando a rede usada pelos demais containers) | Should | Módulo carrega sem erro; não é pré-requisito para o boot estável em si, mas evita módulo ausente no log | 🟡 |
| RF-04 | Criar `freeswitch/conf/autoload_configs/acl.conf.xml` (ACL — Access Control List, lista de controle de acesso por rede) com a lista `rfc1918` já referenciada em `internal.xml` (`apply-nat-acl`) | Must | `internal.xml` não falha por ACL inexistente | 🟢 |
| RF-05 | Criar `freeswitch/conf/directory/default.xml` mínimo (placeholder, sem usuários reais) para satisfazer o include de `freeswitch.xml` | Should | Boot não falha por diretório de usuários ausente | 🟡 |
| RF-06 | Validar o boot do container `freeswitch` no servidor real (`10.10.10.11`, via SSH) após as mudanças | Must | `docker compose ps freeswitch` não mostra `Restarting`; logs não mostram erro fatal de inicialização | 🟢 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| Compatibilidade | A configuração deve ser compatível com o layout esperado pela imagem `safarov/freeswitch:1.10.12`, já que o bind mount substitui `/etc/freeswitch` por inteiro | `_reversa_sdd/infra/deployment/design.md` (risco de build já registrado para `mod_audio_fork`; o mesmo tipo de risco de layout se aplica aqui) | 🟡 |
| Segurança | A senha do Event Socket Layer não deve ficar hardcoded em texto além do já existente `FREESWITCH_ESL_PASSWORD` (`ClueCon` é valor de desenvolvimento, troca fica fora de escopo deste ciclo) | `_reversa_sdd/architecture.md#Dívidas Técnicas` (TD05) | 🟡 |
| Escopo | Nenhuma alteração deste ciclo deve introduzir lógica de gravação de chamada, gateway, ou ESL listener Python | Decisão explícita do usuário para este ciclo | 🟢 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Container FreeSWITCH sobe estável
  Dado que freeswitch/conf/ contém a configuração completa (vars.xml, freeswitch.xml, acl.conf.xml, event_socket.conf.xml, directory/default.xml, sip_profiles/internal.xml, dialplan/default.xml)
  Quando o operador executa "docker compose -f docker-compose.app.yml up -d freeswitch" no servidor real
  Então o container permanece em execução (sem reinício) e os logs não mostram erro fatal de boot

Cenário: Configuração ausente ainda causa falha (estado anterior, caso negativo de referência)
  Dado que freeswitch/conf/ não contém vars.xml nem freeswitch.xml (estado anterior a esta feature)
  Quando o operador tenta subir o container
  Então o processo falha ou reinicia em loop por configuração raiz/variáveis ausentes
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|----------------|
| RF-01, RF-02, RF-04, RF-06 | Must | Sem eles o container não sobe de forma estável — é o próprio objetivo do ciclo |
| RF-03, RF-05 | Should | Não bloqueiam o boot básico, mas evitam módulos/diretório ausentes que vão ser necessários nos próximos ciclos (ESL, gravação) |
| RNF de segurança (ESL password) | Won't (neste ciclo) | Hardening de credenciais fica para quando o ESL listener Python for ligado, fora deste escopo |

## 9. Esclarecimentos

### Sessão 2026-06-23

- **Q:** Como tratar o risco de o layout de `vars.xml`/`freeswitch.xml` não corresponder exatamente ao que a imagem `safarov/freeswitch:1.10.12` espera?
- **R:** Basear-se no layout padrão (vanilla) do FreeSWITCH 1.10.x, validar no boot real em `10.10.10.11`, e corrigir a spec antes do código se algo divergir — não é uma decisão nova, formaliza a política de "spec reflete o resultado real" já definida no ciclo.

## 10. Lacunas

- 🟡 Layout de `freeswitch.xml`/`vars.xml` segue o padrão vanilla do FreeSWITCH 1.10.x; confirmação definitiva só vem da validação real no servidor (`10.10.10.11`) — ver RF-06. Risco operacional, não bloqueante.

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-06-23 | Versão inicial gerada por `/reversa-requirements` | reversa |
