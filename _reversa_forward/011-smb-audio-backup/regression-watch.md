# Regression Watch: SMB Audio Backup

> Feature: `011-smb-audio-backup`
> Criado em: `2026-07-28`

## Watch principal

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|-------------------------|------------------------------|--------------------|-------------------|
| W001 | `_reversa_sdd/domain.md`, R38 | Áudio local permanece em tmpfs; persistência adicional ocorre somente no SMB configurado | redação | Gravação local migra para disco/nuvem ou SMB entra na cadeia crítica |
| W002 | `_reversa_sdd/domain.md`, R39 | `tx.mp3` e `rx.mp3` continuam monos; estéreo é derivado com left=tx/right=rx | presença | Monos removidos, canais invertidos ou mixados |
| W003 | `_reversa_sdd/domain.md`, R40 | Falha ffmpeg preserva `.raw` e permanece observável/retryable | presença | `.raw` removido após falha ou chamada some da fila |
| W004 | `_reversa_sdd/domain.md`, R37 | Cleanup mantém ciclo de 15 min e ignora lease SMB válido | presença | Cleanup remove chamada em transferência |
| W005 | `_reversa_sdd/architecture.md`, processamento assíncrono | SMB offline não impede captura ou conversão local | presença | Handler de gravação aguarda rede SMB |
| W006 | `_reversa_forward/011-smb-audio-backup/interfaces/smb.md`, Publicação | `.tmp` recebe checksum antes do rename e final recebe checksum posterior | presença | Final remoto aparece parcial/corrompido |
| W007 | `_reversa_forward/011-smb-audio-backup/requirements.md`, RF-06 | Chunks usam offsets crescentes; somente o primeiro trunca | presença | Chunk posterior sobrescreve o início ou limite é ignorado |
| W008 | `_reversa_forward/011-smb-audio-backup/requirements.md`, RF-10 | Credenciais ficam em `.env` e nunca em código/spec/log | ausência | Senha, username ou conexão integral aparece em artefato versionado/log |
| W009 | `_reversa_sdd/workers/design.md`, isolamento ARQ | Uploader, cleanup e SMB consomem filas exclusivas; produtor publica em `zenith:audio-upload` | presença | `arq:queue` reaparece ou resultado ARQ contém `function not found` |
| W010 | `_reversa_sdd/adrs/011-baseline-publica-e-provisionamento-tenant.md`, Decisão | Banco operacional permanece intacto; teste, rehearsal e candidato usam recursos próprios `zenith-*` sem porta publicada | ausência | Comando para/recria/reconfigura `zenith-postgres`, usa seu volume em testes ou publica porta de banco novo |
| W011 | `_reversa_sdd/adrs/011-baseline-publica-e-provisionamento-tenant.md`, Guard de validade | Squash só prossegue enquanto nenhum ambiente conhecido possuir revisão Alembic aplicada | presença | Migration aplicada é reescrita ou novo histórico é ignorado |

## Observações

- Vigiar fila acima de 100, cinco falhas consecutivas e conversão pendente.
- Vigiar uso do tmpfs de 512 MB durante indisponibilidade prolongada do SMB.
- ACL READ-ONLY dos auditores precisa de prova operacional periódica.
- O timeout global por chamada permanece em 30 s; lease UTC em 120 s com renovação a cada 30 s.
- Vigiar separadamente `zenith:audio-upload`, `zenith:audio-cleanup` e `zenith:smb-sync`; nenhuma
  delas pode ser substituída pela fila default.

## Histórico de re-extrações

Nenhuma re-extração executada após esta feature.

## Arquivadas

Nenhum item arquivado.
- Provisionamento concorrente do mesmo `schema_name` deve continuar falhando de modo seguro e sem resíduo.
- Falha durante a compensação transacional não pode ocultar o erro operacional original.
- `alembic downgrade` da baseline não é o rollback de produção; o rollback suportado continua sendo reapontar os serviços ao PostgreSQL anterior preservado.
