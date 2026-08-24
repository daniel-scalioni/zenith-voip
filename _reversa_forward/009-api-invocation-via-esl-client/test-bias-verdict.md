# Veredito independente dos testes — adendo de roteamento

- Data: 2026-08-24
- Revisor: Gemini CLI 0.55.1, modelo `gemini-3.7-flash`
- Modo: `plan` (somente leitura)
- Arquivos revisados:
  - `_reversa_sdd/addenda/009-api-invocation-via-esl-client-routing.md`
  - `freeswitch/conf/dialplan/default.xml`
  - `tests/test_trunk_dialplan.py`

## Pergunta obrigatória

> Há casos de borda não cobertos? Os testes estão viesados para esta implementação específica?

## Primeiro parecer

**Aprovado com ressalvas.** O revisor identificou:

1. simulação incorreta da semântica PCRE com `re.fullmatch`;
2. ausência de asserção do bridge upstream exato e da preservação de `${destination_number}`;
3. ausência de testes negativos para impedir rotas técnicas no upstream.

## Correções aplicadas aos testes

1. o simulador passou a usar `re.search`, compatível com o casamento parcial do FreeSWITCH;
2. o padrão upstream passou a exigir explicitamente as âncoras `^` e `$`;
3. a URI exata `sofia/gateway/upstream-${sip_from_user}/${destination_number}` passou a ser
   verificada;
4. `*9196`, `*88` e `play:filler` passaram a ser testados como rejeitados pela rota numérica.

## Revalidação

**APROVADO.** O revisor confirmou que as três ressalvas foram corrigidas e que os testes não estão
viesados para a implementação. Foram registradas apenas observações fora do contrato atual:

- origem sem `sip_from_user` não resolve um gateway upstream;
- destino alfanumérico não casa a rota telefônica numérica.

Esses casos são informativos porque o contrato deste adendo pressupõe endpoint autenticado e
destino telefônico puramente numérico.
