# Onboarding: Bootstrap FreeSWITCH

> Identificador: `004-bootstrap-freeswitch`
> Data: `2026-06-23`

Passo a passo para um humano validar esta feature pela primeira vez, depois que o código (`/reversa-coding`) estiver implementado.

## Pré-requisitos

- Acesso SSH ao servidor `10.10.10.11` (usuário `administrator`).
- Repositório `zenith-voip` já clonado/sincronizado nesse servidor, com as mudanças desta feature aplicadas.

## Passos

1. Conectar via SSH no servidor:
   ```
   ssh administrator@10.10.10.11
   ```
2. Ir até o diretório do projeto e confirmar que `freeswitch/conf/` contém os arquivos novos: `vars.xml`, `freeswitch.xml`, `acl.conf.xml`, `autoload_configs/event_socket.conf.xml`, `directory/default.xml` (além dos 3 já existentes).
3. Subir só o serviço `freeswitch`:
   ```
   docker compose -f docker-compose.app.yml up -d freeswitch
   ```
4. Acompanhar os logs por pelo menos 1 minuto:
   ```
   docker compose -f docker-compose.app.yml logs -f freeswitch
   ```
   Esperado: nenhuma mensagem de erro fatal de boot, e o log eventualmente mostra o processo pronto (mensagem padrão de boot do FreeSWITCH).
5. Confirmar que o container não está em loop de reinício:
   ```
   docker compose -f docker-compose.app.yml ps freeswitch
   ```
   Esperado: status `Up`, sem `Restarting`.
6. Se o boot falhar: copiar o erro exato do log, voltar para `_reversa_forward/004-bootstrap-freeswitch/requirements.md`/`roadmap.md`, registrar o ajuste necessário na spec primeiro, e só então repetir `/reversa-coding` com o ajuste.

## Fora de escopo deste teste

- Registrar um interfone de teste no FreeSWITCH.
- Validar `mod_audio_fork`, ESL listener, gravação de chamada — isso pertence a ciclos futuros.
