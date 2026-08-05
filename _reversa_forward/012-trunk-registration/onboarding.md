# Onboarding: Registro de troncos ATA

> Procedimento de primeira validação. Use somente recursos `zenith-*` e dados fictícios até o checkpoint de produção.

## 1. Pré-requisitos

1. Estar no branch `feature/012-trunk-registration`.
2. Manter `.env` privado e definir chaves fictícias de teste para `TRUNK_CREDENTIAL_KEYS` e autenticação XML Curl.
3. Confirmar que nenhum segredo aparece em `git diff`.
4. Usar exclusivamente PostgreSQL, Redis e FreeSWITCH de teste com prefixo `zenith-`; nunca tocar recursos externos ao projeto.

## 2. Gates antes do banco

1. Rodar a suíte Red documentada em `progress.jsonl` e comprovar as falhas esperadas.
2. Subir o banco isolado de quality já existente.
3. Aplicar `alembic upgrade head` duas vezes.
4. Confirmar as tabelas públicas e ausência de mudanças nos schemas de tenant.

## 3. Teste da API com dados fictícios

1. Criar um tenant/PBX de teste ou reutilizar somente fixture isolada.
2. Criar dois condomínios pelo contrato `interfaces/trunks-api.md`.
3. Executar dry-run do CSV fictício e conferir totais.
4. Importar o arquivo e repetir a importação; a segunda execução não pode duplicar registros.
5. Tentar prefixo repetido no mesmo tenant e depois em tenant diferente.
6. Consultar troncos e confirmar ausência dos campos `encrypted_password`, senha e chaves.
7. Buscar o canário de senha em logs, métricas e respostas; a busca deve retornar zero ocorrências.

## 4. Spike do FreeSWITCH

1. Na imagem candidata, executar `module_exists mod_xml_curl` sem alterar o container operacional.
2. Gerar `xml_curl.conf.xml` privado por script e confirmar modo 0600, gitignore e ausência do segredo no diff.
3. Montar uma fixture privada de `extensions.xml` e comparar todos os usuários por lookup.
4. Ativar o binding apenas no FreeSWITCH isolado.
5. Consultar o endpoint com Basic inválido e confirmar 401 sem detalhe sensível.
6. Fazer lookup válido de tronco e usuário legado, validando XML bem formado, `Cache-Control: no-store` e timeout.
7. Confirmar que lookup ausente/desabilitado/ambíguo retorna `not found` e falha fechado.
8. Manter `xml_curl debug_off`; verificar que nenhum XML temporário com senha foi criado.

## 5. Registro e eventos

1. Configurar um ATA/softphone de teste no profile 7060 com UDP.
2. Registrar com senha errada e confirmar recusa/sanitização.
3. Registrar com senha correta e confirmar `registered`, timestamp e IDs de contexto.
4. Desregistrar e deixar um registro expirar para validar ambos os caminhos.
5. Repetir no profile 5060 somente após o gate 7060.
6. Reiniciar apenas o FreeSWITCH de teste e validar reconciliação.
7. Registrar um usuário legado do `extensions.xml` no mesmo profile e comprovar comportamento equivalente ao anterior.

## 6. Chamadas

1. Fazer duas chamadas simultâneas pelo tronco de teste.
2. Confirmar `active_calls=2`, `in_use=true` e `registration_status=registered`.
3. Encerrar em ordem inversa e reenviar evento duplicado no teste; o contador deve convergir a zero.
4. Confirmar que os dígitos não foram modificados e que nenhuma fila foi selecionada pelo Zenith.
5. Confirmar nos eventos os IDs corretos de tenant, PBX, condomínio e tronco.

## 7. CSV real e rollout

1. Armazenar a extração real fora do repositório em diretório privado.
2. Executar dry-run e registrar apenas hash, contagens e códigos de rejeição.
3. Resolver colisões de identidade de autenticação antes de habilitar qualquer tronco.
4. Importar inicialmente com `enabled=false`.
5. Fazer checkpoint humano antes de ativar um ATA real.
6. Ativar 7060, validar registro/chamada e só então ativar 5060.

### Estado T043 em 2026-08-03

Tentativa interrompida antes do dry-run: a única fonte privada encontrada foi `specs/export_extensions.csv`, que contém credenciais/tecnologia mas não associa troncos a condomínio nem fornece um prefixo comprovado. Nenhuma linha ou credencial foi registrada. É necessário fornecer uma fonte complementar privada com a chave de junção e os campos de condomínio/prefixo; `extension=prefix` não será inferido.

### Resolução T043 em 2026-08-04

A configuração individual fornecida para `Parque Portugal` foi armazenada em arquivo privado gitignored, validada sem expor o segredo e normalizada com estas decisões:

- `auth_username=1020` e `sip_profile=internal-7060` formam a identidade SIP canônica;
- `prefix=null`: o número 1020 não é interpretado nem persistido como regra de roteamento;
- `enabled=false`: nenhuma tentativa de registro real foi disparada nesta etapa;
- o destino `100` permanece inalterado pelo Zenith; VitalPBX e ATA são responsáveis pelo roteamento.

O dry-run retornou uma linha válida e zero escritas. Em seguida, a migration `002_ata_trunks` foi aplicada no PostgreSQL de ensaio `zenith-postgres-rehearsal` e o cadastro desabilitado foi persistido com credencial cifrada. A chave de ensaio foi efêmera; portanto, esse registro comprova persistência segura, mas deve ser recifrado com a chave definitiva antes do teste SIP. A suíte focada encerrou com 76 testes aprovados e 1 integração local ignorada, já exercitada no ambiente PostgreSQL de ensaio.

### Estado parcial T055 em 2026-08-04

O arquivo privado real é um fragmento de include do FreeSWITCH com vários elementos `<user>` consecutivos, não um documento XML com raiz única. Após correção spec-first e TDD do provider, a comparação sanitizada integral obteve:

- 939 usuários na origem e 939 identidades únicas;
- zero usuários ausentes;
- zero divergências em ID, params ou variables;
- zero respostas acima do limite de 64 KiB.

O conjunto de identidades foi registrado somente por SHA-256 (`0de645b76b578d19284c71634bc56a3e68f9b304a8f3a7c70b4bec687a18692d`); nenhum ID ou segredo foi emitido. O revisor independente liberou a comparação. T055 permanece aberta porque o registro SIP legado real ainda não foi comprovado: o workspace não possui cliente Docker e o host de ensaio recusou a chave SSH desta sessão.

### Conclusão T055 em 2026-08-04

A indisponibilidade do SSH foi contornada pela conectividade SIP direta já autorizada para o ambiente isolado. Um usuário real do diretório legado foi selecionado somente em memória e registrado no FreeSWITCH existente em `10.10.10.11:7060` por desafio Digest. O servidor retornou `200` para o REGISTER e `200` para a remoção imediata do contato com `Expires: 0`. A evidência expôs apenas o hash SHA-256 da identidade (`9af15b336e6a9619928537df30b2e6a2376569fcf9d7e773eccede65606529a0`).

O cliente sanitizado foi desenvolvido em TDD; após o primeiro parecer independente, passou a cobrir `qop=auth`, challenge sem qop e rejeição explícita de `auth-int` quando não há `auth`. A execução real repetida após a correção permaneceu `200/200`. O parecer final independente liberou T055 com melhorias de teste conhecidas para T048.

## 8. Rollback

1. Desabilitar o binding XML Curl nos profiles afetados.
2. Restaurar os arquivos de profile anteriores e executar `reloadxml`/restart apenas do profile autorizado.
3. Confirmar que chamadas existentes não foram derrubadas e que 5062/upstream permanecem intactos.
4. Manter as tabelas aditivas; não executar downgrade no banco operacional.
5. Registrar evidências sanitizadas em `progress.jsonl` e `regression-watch.md`.

## 9. Quality gates

```text
pytest tests/ -v --cov --cov-fail-under=80
pytest src/ -v --cov=src --cov-fail-under=80
alembic upgrade head
```

Além dos comandos acima, obter veredito independente sobre casos de borda, viés dos testes, segredo e isolamento de tenant antes do aceite.
