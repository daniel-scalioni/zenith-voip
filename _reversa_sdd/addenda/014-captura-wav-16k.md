# Adendo 014 — Captura de áudio em WAV 16 kHz na origem

- Identificador: `014-captura-wav-16k`
- Data: `2026-08-17`
- Cenário: `legado`

## Vigência

Vigente desde 2026-08-17.

Superado pela re-extração de 2026-08-17.

## Resumo da entrega

A captura de chamadas passou de MP3 mono 8 kHz para WAV PCM16 mono 16 kHz por canal, com escrita
incremental, publicação atômica e WAV estéreo no backup SMB. A entrega também acrescentou
coordenação por leases, confirmação de consumidores, cleanup seguro e controle de capacidade do
tmpfs sem interromper a telefonia. Foram concluídas 60 de 60 ações.

## Impacto por artefato da extração

| Artefato | Seção | Tipo de impacto | Delta |
|---|---|---|---|
| `_reversa_sdd/domain.md` | `Captura de áudio` — R42 | `regra-alterada` | A captura via ESL continua no `CHANNEL_ANSWER`, mas agora solicita explicitamente `stereo 16000`; ver `legacy-impact.md` da feature. |
| `_reversa_sdd/architecture.md` | `Fluxo Principal de uma Chamada` | `regra-alterada` | O `AudioIngestor` não acumula mais a chamada inteira em memória: grava cada canal incrementalmente como `.tmp.raw` e publica `.raw` por rename atômico. |
| `_reversa_sdd/architecture.md` | `Fluxo Principal de uma Chamada` | `componente-novo` | O fluxo deve incluir o recording lifecycle, com leases renováveis e exclusão entre estágios para owners distintos. |
| `_reversa_sdd/domain.md` | `Gravação e retenção` | `componente-novo` | A admissão de gravações agora reserva capacidade, preserva ao menos 20% projetados e usa histerese de recuperação em 30%, sem interromper o SIP. |
| `_reversa_sdd/domain.md` | `Gravação e retenção` — R39, R40 e R41 | `regra-alterada` | Os canais finais passam a WAV PCM16 mono 16 kHz; falha continua preservando `.raw`, e o layout mantém tenant/chamada com estados transitórios explícitos. |
| `_reversa_sdd/architecture.md` | `Fluxo Principal de uma Chamada` | `regra-alterada` | O backup SMB deriva `stereo.wav`, publica por temporário remoto com checksum e mantém chamadas ocupadas, incompletas ou legadas invisíveis ao log. |
| `_reversa_sdd/domain.md` | `Gravação e retenção` — R37 | `regra-alterada` | O cleanup continua a cada 15 minutos, mas diferencia finais consumidos, TTL de segurança e temporários órfãos confirmados em duas rodadas sob lock. |
| `_reversa_sdd/architecture.md` | `Fluxo Principal de uma Chamada` | `componente-novo` | Confirmações atômicas `.consumed-<consumer>` passam a controlar a exclusão antecipada dos artefatos finais. |
| `_reversa_sdd/architecture.md` | `Stack Tecnológica` | `delta-de-contrato-externo` | A configuração passa a expor consumidores exigidos, tempos de lease, parâmetros de cleanup e margens de capacidade. |
| `_reversa_sdd/architecture.md` | `Visão Geral` | `regra-nova` | A observabilidade passa a medir capacidade reservada, modo degradado, recusas, cleanup e falhas de lease. |
| `_reversa_sdd/domain.md` | `Gravação e retenção` — R38 | `delta-de-dados` | O `zenith_recordings_tmpfs` deve ser lido como tmpfs de 2 GiB, ainda em RAM, sujeito ao controle de admissão. |
| `_reversa_sdd/architecture.md` | `Dívidas Técnicas` — TD08 | `regra-nova` | A implementação agora possui testes de formato, atomicidade, concorrência, cleanup e capacidade, com gate final de 89,86% de cobertura. |

## Regras sob vigilância

- `W001` — `_reversa_forward/014-captura-wav-16k/regression-watch.md`
- `W002` — `_reversa_forward/014-captura-wav-16k/regression-watch.md`
- `W003` — `_reversa_forward/014-captura-wav-16k/regression-watch.md`

## Fontes

- `_reversa_forward/014-captura-wav-16k/legacy-impact.md`
- `_reversa_forward/014-captura-wav-16k/regression-watch.md`
- `_reversa_forward/014-captura-wav-16k/requirements.md`
- `_reversa_forward/014-captura-wav-16k/actions.md`
- `_reversa_forward/014-captura-wav-16k/progress.jsonl`
