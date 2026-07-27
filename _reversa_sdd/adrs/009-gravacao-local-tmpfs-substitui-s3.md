# ADR-009: Gravação em tmpfs local com MP3 por canal, em substituição ao S3

**Data:** 2026-07-10 (retroativo — registrado na re-extração de 2026-07-27)
**Status:** Aceito
**Contexto:** zenith-voip — módulo `workers`, `infra`
**Commits de origem:** `4a724e4`, `e724c59` — *feat: grava chamadas em MP3, volume tmpfs, retenção de 1h*

---

## Contexto

O desenho original previa que toda gravação fosse para um bucket S3 por tenant
(`{prefix}-{tenant_id}`), com retenção de 90 dias e cleanup diário em lotes de 1000 objetos.
Esse caminho **nunca chegou a rodar em produção**: dependia de credenciais S3 que não existiam
no ambiente, e todo o código de upload e cleanup tinha um curto-circuito
`if not S3_ENDPOINT: return skipped` — ou seja, na prática nada era gravado e nada era
limpo.

Ao mesmo tempo, a Fase 1 do MVP exigia gravação real para **auditoria imediata** da chamada:
o operador precisa poder ouvir a ligação que acabou de acontecer, não recuperar áudio de
três meses atrás.

Somam-se dois pontos: as gravações contêm dados sensíveis de clientes (o mesmo motivo que
levou o LLM a ser local, ADR-003), e persistir esse áudio em disco ou em nuvem de terceiros
amplia bastante a superfície de exposição para um requisito que é de curtíssimo prazo.

## Decisão

1. **Remover o S3 por completo** — `boto3` fora do `requirements.txt`, variáveis `S3_*` fora
   do `config.py` e do compose.
2. Gravar em **filesystem local** sob `RECORDINGS_PATH` (`/data/recordings`), no layout
   `<tenant_id>/<call_id>/<channel>.mp3`.
3. Montar esse caminho como **tmpfs de 512 MB** (volume `zenith_recordings_tmpfs`) — o áudio
   vive em **RAM**, nunca toca o disco do host.
4. Converter cada canal para **MP3 mono 8 kHz** via `ffmpeg` (`s16le` → `libmp3lame`),
   mantendo `tx` e `rx` **separados** (não misturados, não estéreo).
5. Retenção de **~1 hora** (`AUDIO_RETENTION_DAYS=0.0417`), com cleanup **a cada 15 minutos**.

## Justificativa

- **Retenção curta + tmpfs** dão descarte por construção: mesmo que o cleanup falhe, um
  restart do container zera as gravações, e nada persiste em mídia durável.
- **MP3 por canal** é o formato que serve auditoria humana: o `tx` isolado permite avaliar o
  atendente sem o ruído do outro lado, e vice-versa. Áudio misturado inviabilizaria isso.
- **Cleanup a cada 15 min** é consequência direta da retenção: um cron diário às 03:00
  deixaria arquivos vivos por até 24 h antes da primeira avaliação — o TTL de 1 h não seria
  respeitado de verdade.

## Consequências

**Positivas**
- Pipeline de gravação funciona sem nenhuma credencial ou dependência de nuvem.
- Dado sensível não sai da máquina e não sobrevive a restart — coerente com ADR-003.
- Conversão para MP3 reduz o volume em ordem de grandeza frente ao PCM bruto.
- Falha de conversão preserva o `.raw` (`uploaded_raw_only`): degrada, não perde.

**Negativas**
- 🔴 **512 MB é um teto rígido e sem backpressure.** Com chamadas simultâneas suficientes o
  tmpfs enche, e a escrita falha por chamada (retorna `failed`) sem nenhum alarme agregado.
- 🔴 **Gravação some no restart do container.** Aceitável para auditoria imediata, inaceitável
  para qualquer requisito de retenção legal ou de compliance.
- 🔴 Consome RAM do host, que é compartilhado com outros stacks.
- As métricas Prometheus de S3 (módulo `observability`) passaram a medir um subsistema que
  não existe mais.
- `ffmpeg` virou dependência de runtime da imagem do worker.

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Manter S3 e obter credenciais | Não resolvia o requisito de curto prazo e mantinha áudio sensível em terceiro |
| Volume de disco comum em vez de tmpfs | Áudio sensível persistiria em mídia durável; descarte deixaria de ser automático |
| Estéreo num único arquivo | Impede avaliar cada lado isoladamente, que é o uso pretendido |

## Reversão

Se surgir requisito de retenção longa (compliance, disputa contratual), este ADR deve ser
revisto por inteiro: a volta a um armazenamento objeto exige reintroduzir cifragem em repouso,
política de retenção por tenant e trilha de acesso — nada disso existe hoje.

## Relacionados

- [ADR-003](003-dados-sensiveis-llm-local.md) — mesma lógica de não deixar dado sensível sair
- [ADR-007](007-validacao-e2e-chamada-real.md) — validação E2E que exercitou este caminho
- `_reversa_sdd/workers/legacy-mapping.md`, `_reversa_sdd/infra/legacy-mapping.md`
