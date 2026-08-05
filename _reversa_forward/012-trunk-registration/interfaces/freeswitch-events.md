# Interface ESL: Estado de registro e uso de troncos

> Produtor: FreeSWITCH/mod_sofia
> Consumidor: `src/telephony/esl_client.py` → `src/telephony/trunk_state.py`

## Assinaturas

O listener preserva eventos de canal existentes e acrescenta:

```text
events json CHANNEL_CREATE CHANNEL_ANSWER CHANNEL_HANGUP SOFIA_REGISTER SOFIA_UNREGISTER CUSTOM sofia::register sofia::unregister sofia::expire
```

A sintaxe final da assinatura será confirmada no spike ESL e coberta por teste de framing; se o FreeSWITCH exigir comandos separados para `CUSTOM`, o cliente enviará duas assinaturas sem compartilhar leitura com o canal de comandos.

## Registro

Campos normalizados:

| Campo | Fontes aceitas |
|-------|----------------|
| `event_type` | subclass `sofia::register`, `sofia::unregister`, `sofia::expire`; aliases legados durante transição |
| `profile` | `profile-name`, `Profile-Name`, `variable_sofia_profile_name` |
| `auth_username` | `from-user` no register; `user`/`username` no expire (confirmados no spike T042); `sip_auth_username`, `Caller-Caller-ID-Number` como aliases |
| `occurred_at` | timestamp do evento; fallback para UTC de recebimento |
| `expires` | `expires`, quando presente |

Resolução usa `(profile, auth_username)`, nunca apenas prefixo ou IP.

Transições:

- register → `registered`, atualiza `last_registered_at` e limpa erro operacional aplicável;
- unregister/expire → `unregistered`, atualiza `last_unregistered_at`;
- desconexão ESL → troncos anteriormente `registered` passam a `unknown` até reconciliar.

## Chamadas ativas

Eventos de canal devem carregar `variable_zenith_trunk_id` proveniente do diretório autenticado.

- `CHANNEL_CREATE`/`CHANNEL_ANSWER`: `SADD zenith:trunk:active_calls:{id} <uuid>`;
- `CHANNEL_HANGUP`: `SREM ... <uuid>`;
- consulta: `SCARD`; `in_use = SCARD > 0`.

Duplicidade é no-op. Hangup desconhecido não reduz abaixo de zero. Eventos sem `trunk_id` continuam no fluxo legado e não alteram estado de tronco.

## Reconciliação

No boot/reconnect do listener único (`INSTANCE_ID==1`):

1. marcar como `unknown` os troncos que estavam `registered`;
2. consultar registros ativos por profile via conexão ESL de comandos;
3. resolver somente identidades não ambíguas e atualizar `registered`;
4. limpar sets de canal inexistentes após comparar UUIDs observáveis;
5. registrar métricas agregadas e códigos sanitizados para falhas parciais.

Falha de uma linha não aborta toda a reconciliação; a identidade afetada permanece `unknown` e o erro original é logado sem credenciais.
