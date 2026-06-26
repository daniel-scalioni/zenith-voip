# Investigação: Bootstrap FreeSWITCH

> Identificador: `004-bootstrap-freeswitch`
> Data: `2026-06-23`

## Pesquisa de fundo

A imagem `safarov/freeswitch:1.10.12` (Docker Hub) empacota um build vanilla do FreeSWITCH 1.10.x. O padrão de config desse projeto (linha "default" do próprio FreeSWITCH, distribuída no repositório oficial `signalwire/freeswitch` em `conf/vanilla/`) usa a seguinte árvore mínima para o processo iniciar:

```
freeswitch.xml              # raiz, <X-PRE-PROCESS cmd="include" data="..."/> para os demais
vars.xml                    # variáveis globais ($${...})
autoload_configs/*.xml      # um arquivo por módulo/subsistema (event_socket, acl, modules, etc.)
sip_profiles/*.xml          # perfis SIP (sofia)
dialplan/*.xml              # contextos de roteamento de chamada
directory/*.xml             # diretório de usuários/extensões
```

Este projeto já tem `dialplan/default.xml`, `sip_profiles/internal.xml` e `autoload_configs/modules.conf.xml` — faltam exatamente as peças "raiz" (`freeswitch.xml`, `vars.xml`) e dois autoload_configs adicionais (`acl.conf.xml`, `event_socket.conf.xml`) mais um `directory/` mínimo.

## Alternativas avaliadas

| Alternativa | Descrição | Por que não foi escolhida |
|-------------|-----------|----------------------------|
| Extrair a config original de dentro da imagem (`docker run --rm safarov/freeswitch:1.10.12 cat /etc/freeswitch/...`) antes de escrever a nova | Copiaria exatamente o que a imagem espera, zero adivinhação | Mais lento (precisa rodar a imagem antes de qualquer código), e a imagem pode ter exemplos/config de demonstração que não fazem sentido para este projeto (ex: perfis de exemplo, sons de demo). Layout vanilla documentado é suficiente e mais limpo; a validação real no servidor cobre o risco residual |
| Trocar a imagem base por uma distribuição que já venha com config completa adaptada (ex: imagens "ready to use" de terceiros) | Evitaria escrever a config do zero | Já existe uma decisão de produto anterior usando `safarov/freeswitch:1.10.12` como base para o build customizado de `mod_audio_fork` (`_reversa_sdd/infra/deployment/design.md`); trocar a imagem base reabriria essa decisão sem necessidade — fora de escopo deste ciclo |
| Não usar bind mount completo de `/etc/freeswitch`, montar só os arquivos específicos do projeto sobre a config padrão da imagem | Preservaria a config padrão da imagem como base | Decisão de infraestrutura mais ampla (mudaria `docker-compose.app.yml` de forma que afeta outros ciclos também, ex: build do `mod_audio_fork`); mais simples e local resolver completando o bind mount existente |

## Padrões aplicáveis

- Layout de config FreeSWITCH vanilla 1.10.x (fonte: distribuição oficial do projeto FreeSWITCH, padrão amplamente documentado na comunidade).
- Convenção já em uso neste projeto: `network_mode: host` para o container `freeswitch`, mantido sem alteração.
