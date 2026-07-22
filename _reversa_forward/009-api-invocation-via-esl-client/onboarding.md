# Onboarding: Invocação de comandos de API do FreeSWITCH via ESL client

> Identificador: `009-api-invocation-via-esl-client`
> Data: `2026-07-14`

Passo a passo para um humano validar esta feature pela primeira vez, após o `/reversa-coding` ter
aplicado as mudanças.

## Pré-requisitos

- Acesso SSH ao servidor (`administrator@10.10.10.11`, chave configurada — ver
  `.claude/deploy-access.local.md`).
- Um ramal Zenith registrado e funcional (ex.: 1001) e um destino externo válido para discar
  (ex.: fila 30001 no VitalPBX).

## Passos

1. Confirmar que o código novo está no servidor:
   ```bash
   ssh administrator@10.10.10.11 "docker exec freeswitch grep -c uuid_audio_stream /etc/freeswitch/dialplan/default.xml"
   ```
   Esperado: `0` (a action foi removida do dialplan).

2. Confirmar que `fastapi-1` está rodando o código novo do `ESLClient` (reiniciar se necessário):
   ```bash
   ssh administrator@10.10.10.11 "cd ~/zenith-voip && docker compose restart fastapi-1"
   ```

3. Abrir uma captura ao vivo do console do FreeSWITCH (com pseudo-TTY, para evitar buffer preso):
   ```bash
   ssh -tt administrator@10.10.10.11 "cd ~/zenith-voip && docker compose exec freeswitch fs_cli"
   ```

4. Em paralelo, acompanhar os logs do `fastapi-1`:
   ```bash
   ssh administrator@10.10.10.11 "cd ~/zenith-voip && docker compose logs -f fastapi-1"
   ```

5. Originar a chamada de teste: discar do ramal 1001 para a fila 30001.

6. **Critério de sucesso:**
   - No `fs_cli`: a chamada aparece como `answered` e permanece `ACTIVE` (bridged), sem
     `[ERR] ... Invalid Application` nem hangup com causa `DESTINATION_OUT_OF_ORDER` logo após o
     `answer`.
   - No log do `fastapi-1`: uma requisição de WebSocket em `GET /audio-stream/<uuid>` aparece
     (não apenas os `GET /health` de rotina).
   - A chamada completa normalmente do ponto de vista do ramal que discou (sem "Call Ended"
     prematuro).

7. Se algo falhar, checar primeiro a resposta do `send_bgapi` nos logs do `fastapi-1` (deve
   aparecer como WARNING estruturado, conforme D-04 do `roadmap.md`) antes de investigar mais fundo.

## Rollback

Se o teste falhar de forma que bloqueie produção, reverter é: restaurar a versão anterior de
`freeswitch/conf/dialplan/default.xml` e `freeswitch/conf/vars.xml` via `scp` + `reloadxml`, e dar
`git revert` no commit de `src/telephony/esl_client.py`/`src/config.py`, seguido de restart do
`fastapi-1`. Nenhuma migração de banco para reverter (ver `data-delta.md`).
