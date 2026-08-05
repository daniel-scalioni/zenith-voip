---
spec:
  component: trunk-registration
  layer: telephony
  status: active
  version: 1.2.0
  language: python
  patterns: [observer, event-driven, module-singleton]
  inputs: [{name: directory_user, type: XML, from: trunk-admin}, {name: sofia_events, type: ESL, from: freeswitch}]
  outputs: [{name: registration_state, type: persisted-status, to: trunk-registry}, {name: active_call_state, type: redis-set, to: trunk-admin}]
  dependencies: [{component: trunk-registry, layer: database}, {component: redis-streams, layer: events}, {component: esl-client, layer: telephony}]
  events_produced: []
  updated_at: 2026-08-04
---

# Trunk Registration — Design

## Responsabilidade

Autenticar ATAs nos profiles Sofia 5060/7060, associar registros/canais à hierarquia correta e manter estados operacionais idempotentes sem assumir roteamento de dígitos ou filas.

## Profiles

- `internal` escuta SIP/UDP 5060.
- `internal-7060` escuta SIP/UDP 7060 para dispositivos classificados como PJSIP no VitalPBX.
- `internal-5062` permanece intocado.
- `accept-blind-reg` e `accept-blind-auth` permanecem falsos.
- O diretório é consultado por `mod_xml_curl` com timeout de 2 s e falha fechada.

## Carregamento/configuração

- `mod_xml_curl` carrega como primeiro item de `modules.conf.xml`, antes de `mod_sofia`.
- `pre_load_modules.conf.xml` não é usado: a imagem FreeSWITCH 1.10.12 sofreu segfault reproduzível nesse caminho; o carregamento normal ordenado foi validado no spike isolado T042.
- O binding é exclusivamente `directory`, limite 64 KiB.
- O parâmetro `method` do `mod_xml_curl` usa `POST` em maiúsculas; a imagem 1.10.12 transmite o valor literalmente e `post` causa HTTP 501 no backend.
- Gate de build/runtime exige `module_exists mod_xml_curl`.
- O arquivo real do binding é privado, gitignored e renderizado antes do boot.
- `xml_curl debug_off` é obrigatório fora de diagnóstico isolado.

## Variáveis autenticadas

Usuários ATA válidos recebem:

- `zenith_tenant_id`
- `zenith_pbx_id`
- `zenith_condominium_id`
- `zenith_trunk_id`
- `zenith_trunk_prefix` somente quando o metadado opcional estiver preenchido
- `user_context=default`

O dialplan usa essas variáveis no lugar dos valores globais. Usuários legados preservam suas variáveis atuais e não recebem `trunk_id` fictício.

## Compatibilidade do diretório legado

- `extensions.xml` é um fragmento de inclusão do FreeSWITCH e pode conter vários elementos `<user>` consecutivos, sem raiz XML única.
- O provider envolve o conteúdo somente em uma raiz sintética em memória; nunca reescreve o arquivo privado.
- Documento XML completo com uma raiz e fragmento com múltiplos usuários são aceitos.
- DTD e entidades permanecem proibidos antes de qualquer parsing.
- IDs vazios ou repetidos falham fechado; params, variables e senhas são preservados sem aparecer em logs ou evidências.

## Eventos

O listener único (`INSTANCE_ID==1`) preserva eventos existentes e assina `CUSTOM`:

- `sofia::register`
- `sofia::unregister`
- `sofia::expire`

Aliases legados são aceitos na transição. Resolução usa `(profile, auth_username)`, nunca prefixo ou IP.
No FreeSWITCH 1.10.12, `sofia::expire` entrega o profile em `profile-name` e a identidade em `user`/`username`; esses campos fazem parte do contrato normalizado.

Transições:

- register → `registered`, atualiza `last_registered_at`;
- unregister/expire → `unregistered`, atualiza `last_unregistered_at`;
- desconexão ESL → `unknown` até reconciliação.

Eventos duplicados são idempotentes. Erros mantêm o evento seguinte processável e registram stack trace sem credenciais.

## Chamadas ativas

- Chave Redis: `zenith:trunk:active_calls:{trunk_id}`.
- `CHANNEL_CREATE`/`CHANNEL_ANSWER`: `SADD` do UUID.
- `CHANNEL_HANGUP`: `SREM` do UUID.
- TTL de segurança: 24 h, renovado em evento.
- `active_calls=SCARD`; `in_use=active_calls>0`.
- Hangup desconhecido/duplicado nunca produz valor negativo.

## Reconciliação

No boot e após reconexão:

1. marcar registros persistidos como `unknown`;
2. consultar registros Sofia atuais por profile usando a conexão ESL de comandos;
3. normalizar linhas individualmente e resolver identidades não ambíguas;
4. atualizar `registered` e preservar `unknown` em falha parcial;
5. comparar canais observáveis e limpar UUIDs órfãos;
6. emitir métricas agregadas.

## Dialplan/roteamento

- Nenhuma regra adiciona, remove ou substitui dígitos.
- Nenhuma fila é selecionada pelo Zenith.
- A bridge upstream existente é preservada.
- Metadados autenticados acompanham a chamada e alimentam o ciclo de `Call`/áudio já existente.

## Segurança e observabilidade

- Logs nunca incluem senha, material digest, XML, contact completo ou body HTTP.
- Métricas usam apenas resultado/profile/estado; sem tenant, username, prefixo ou IP como label.
- Falha do tracking não derruba mídia nem chamada já estabelecida.

## Testes bloqueantes

- Parser/framing e assinatura CUSTOM.
- register/unregister/expire duplicados e fora de ordem.
- reconciliação total/parcial/ambígua.
- chamadas simultâneas e contador não negativo.
- profiles 5060/7060 autenticados, 5062 intacto.
- dialplan sem globais e sem manipulação de dígitos.
- registro real de usuário legado e ATA piloto antes do rollout.

## Rastreabilidade

- `_reversa_forward/012-trunk-registration/interfaces/freeswitch-events.md`.
- `_reversa_forward/012-trunk-registration/roadmap.md`: D-02, D-03, D-08, D-09, D-10, D-11, D-14.
- Requirements RF-05, RF-06, RF-07, RF-08, RF-10, RF-11.
