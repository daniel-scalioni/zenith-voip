# Veredito independente sobre testes

> Feature: `011-smb-audio-backup`
> Data: `2026-07-28`
> Revisores externos: DeepSeek V4 Flash e Gemini 2.5 Flash via OpenCode

## Pergunta

> Há casos de borda não cobertos? Os testes estão viesados para esta implementação específica?

## Achados aceitos e corrigidos

| Achado | Correção | Evidência |
|--------|----------|-----------|
| Cancelar o timeout podia deixar ffmpeg órfão | `generate_stereo` encerra e aguarda o subprocesso, removendo temporário | teste Red de cancelamento |
| Checksum somente após rename podia expor final corrompido | SHA256 do `.tmp` é validado antes do rename; divergência remove temporário | teste Red de corrupção pré-rename + E2E real |
| Falha na renovação do lease não era observável | erro é logado por classe e o loop tenta renovar novamente | teste Red de falha/continuidade |
| Faltavam caminhos negativos na integração SMB | fake SMB cobre offsets/publicação/checksum e storage real confirmou cliente e strategy | testes locais + dois E2E reais |

## Achados reclassificados

- `stereo_path.unlink()` concorrente com cleanup: o lease válido cobre toda a chamada e o timeout
  máximo é menor que sua validade; `missing_ok` seria apenas defesa adicional.
- Race no pool Redis do uploader: preexistente e fora do delta SMB.
- Cleanup excluir arquivos não-áudio: comportamento legado da pasta exclusiva de gravações; mudar
  a política exigiria requisito próprio.
- `call_id` curto: chamadas reais usam UUID; o fallback de colisão especificado permanece
  `call_id[6:10]`.
- Pipeline totalmente mockado: reclassificado porque `SMBBackupStrategy` foi exercitado contra o
  storage real, incluindo offsets, checksum temporário/final, rename e cleanup.

## Cobertura e viés

- `src/workers/smb_sync.py`: 85% antes das correções adicionais.
- Testes priorizam contratos observáveis: nome, canais, offsets, integridade, idempotência,
  timeout, lock, lease, retry/circuit breaker e cleanup.
- Mocks ficam nas portas externas: subprocesso ffmpeg, SMB, banco e relógio.
- Dois E2E reais compensam o risco de um fake SMB reproduzir a implementação em vez do protocolo.

## Veredito

Após as correções, não permanece caso de borda bloqueante conhecido. A suíte ainda depende do E2E
operacional para ACL READ-ONLY e execução dentro da rede Docker; esses pontos não são simulados como
confirmados.
## Rodada independente T053 — isolamento de filas ARQ

Data: 2026-07-30.

| Participante | Papel | Resultado |
|-------------|-------|-----------|
| Claude Sonnet via Claude CLI | autor inicial | escreveu os testes, mas a CLI travou antes do relatório final |
| DeepSeek V4 Flash via OpenCode | revisor read-only | pediu cobertura de contaminação em todas as direções e AAA real |
| North Mini Code via OpenCode | autor de correção | descartado: violou o escopo e tentou implementar o Green |
| DeepSeek V4 Flash via OpenCode | autor de correção | removeu redundâncias, completou isolamento e corrigiu AAA após devolutiva |
| Orquestrador Codex | validação, sem autoria dos testes | confirmou escopo, ausência de Green e execução Red |

Veredito: os testes T053 são aceitos como independentes da implementação. Eles cobrem os três
nomes de fila, ausência da fila default, isolamento das funções entre workers e a fila efetiva do
produtor por `default_queue_name` ou `_queue_name`. Execução focada: 27 passaram e 5 falharam
pelos motivos esperados do Red. A integração Redis/containers continua reservada para T055.

## Revisão T081 — banco e migrations

Data: 2026-07-31.

| Participante | Papel | Resultado |
|-------------|-------|-----------|
| Claude Sonnet via Claude CLI | autor/revisor tentado | timeouts sem escrita ou parecer |
| DeepSeek V4 Flash via OpenCode | autor tentado | timeout sem escrita |
| Mimo V2.5 via OpenCode | autor T066–T068 | 44 testes coletados; 41 Red e 3 passed |
| Laguna S 2.1 via OpenCode | revisor somente leitura | **REPROVADO**, correções bloqueantes devolvidas ao autor |

### Bloqueadores

1. `migrations_contract`, `provision_contract` e `isolation_contract` são módulos/APIs inventados
   pelos testes e não correspondem aos alvos Green T082–T085.
2. Três testes de teardown exercitam somente callbacks/listas, sem provar limpeza real no banco de
   teste.
3. Um teste consulta `public` sem executar upgrade antes, permitindo passe vacuamente verdadeiro.
4. O conjunto exato de tabelas em `public` e o formato `dict`/chaves do provisionador não são
   contratos especificados.
5. Testes tautológicos/circulares inflam cobertura sem provar comportamento.

### Bordas ausentes

- UUID inválido, duplicado ou conflitante; schema inválido e rollback parcial.
- DSN `None`/vazia, IPv6, encoding, driver/alias/case/query inesperados.
- Unicidade concorrente e teardown sob falha, cancelamento ou conexão ativa.

### Decisão do orquestrador

T066–T068 e T081 permanecem abertos. Os testes devem ser reescritos contra Alembic real,
`scripts/provision_tenant.py` e fixtures/helpers planejados de `tests/conftest.py`, sempre no
`zenith-postgres-test`. A sugestão do revisor de implementar o Green primeiro foi rejeitada porque
violaria Red → Green. O autor externo recebeu as correções começando por T066.

## Autoria T069–T070

- T069: Claude Sonnet escreveu cinco testes de `AudioIngestor`; todos passam contra o comportamento
  atual. O teste usa `receive()`, cobre controle/binário, desconexão e isolamento. T086 tende a N/A
  após T113.
- T070: Claude Sonnet escreveu três testes unitários com `httpx.MockTransport` e três integrações
  opt-in por `BUNKERWEB_URL`. Execução default: 3 passed, 3 skipped, sem rede. HTTP 404/502 e
  `ConnectError` não são tratados como sucesso.
- Ressalva não bloqueante: o marker `integration` ainda não está registrado e gera warning.
