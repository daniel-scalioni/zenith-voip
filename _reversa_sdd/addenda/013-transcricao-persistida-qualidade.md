---
spec:
  component: transcript-batch-quality-addendum
  layer: workers
  status: draft
  version: 1.0.0
  language: python
  patterns: [strategy, repository, event-driven]
  inputs:
    - {name: recording_pair, type: "WAV PCM16 mono 16 kHz", from: audio-uploader}
    - {name: literal_ground_truth, type: "pt-BR transcript", from: validation-corpus}
  outputs:
    - {name: quality_gated_transcript, type: "list[Transcript]", to: postgres-smb}
  dependencies:
    - {component: transcript-batch, layer: workers}
    - {component: whisper-cpp-stt, layer: services}
    - {component: audio-ingestion, layer: audio}
  events_produced: []
  updated_at: 2026-08-24
---

# Adendo corretivo 013 — Qualidade da transcrição literal

## Origem

- Feature: `013-transcricao-persistida`
- Incidente observado: chamada `1001 → 1140100 → fila 30001`, iniciada em
  `2026-08-24 09:27:45 -03:00`
- Call ID de diagnóstico: `bad4cee5-2087-4e7b-81bf-7cbf706d299b`
- Plano detalhado: `_reversa_forward/013-transcricao-persistida/quality-improvement-plan.md`

## Vigência

**Draft, ainda não vigente.** Este adendo especifica a correção necessária, mas não declara que
a qualidade foi entregue. Só muda para `status: active` depois que todos os critérios de aceite
deste documento forem comprovados em corpus pt-BR anotado e em canário de produção.

## Problema confirmado

O pipeline entrega arquivos e persistência corretamente, mas não garante fidelidade textual. Na
chamada de diagnóstico:

- o WAV remoto é PCM16 estéreo 16 kHz válido, tem 19,86 s e não apresenta clipping;
- o canal `tx` contém aproximadamente 9,8 s de silêncio inicial, mas recebeu um segmento textual
  começando em 0 s e terminando em 13 s;
- o canal `rx` contém vários blocos acústicos de fala, porém o modelo repetiu a mesma sentença em
  nove segmentos consecutivos de 2 s;
- segmentos claramente incompatíveis com o áudio receberam confidence de até `0,95`, logo a média
  de probabilidade dos tokens não pode ser tratada como medida calibrada de fidelidade;
- o worker usa `ggml-base.bin`, idioma `pt`, uma thread e `-sns`, mas não habilita VAD;
- a associação `tx → atendente` / `rx → cliente` foi promovida a regra confirmada sem encerrar a
  pendência registrada em `_reversa_sdd/audio/design.md`. O incidente sugere possível inversão,
  mas não basta para decidir o mapeamento correto em todos os sentidos de chamada.

## Delta de requisitos

| ID | Requisito | Prioridade | Critério de aceite |
|---|---|---|---|
| QR-01 | Produzir transcrição **literal em pt-BR**, sem tradução, resumo, paráfrase ou correção semântica. | Must | Corpus anotado compara palavras pronunciadas com a saída; o task do STT permanece `transcribe` e o idioma é `pt`. |
| QR-02 | Não persistir texto sem evidência acústica de fala. VAD deve delimitar regiões faladas antes da decodificação ou rejeitar segmentos fora delas. | Must | Em silêncio e pausas anotadas não há segmentos; taxa de inserção em não-fala ≤ 1 segmento espúrio por 10 minutos. |
| QR-03 | Não usar confidence média de token como garantia isolada de qualidade. Persistir em `extra_metadata` sinais de não-fala/decodificação e uma flag de rejeição quando aplicável. | Must | Segmento rejeitado por não-fala não chega ao texto final mesmo que a probabilidade média de tokens seja alta. |
| QR-04 | Selecionar modelo, quantização, engine, threads e parâmetros por benchmark reproduzível no domínio de chamadas VoIP pt-BR. | Must | Matriz registra WER, CER, inserções, deleções, substituições, RTF, CPU e pico de RAM para cada candidato. |
| QR-05 | Confirmar a semântica dos canais por chamada controlada e pela perna FreeSWITCH onde `uuid_audio_stream` foi anexado; não assumir que o índice estéreo identifica papel de negócio. | Must | Frases-identidade distintas em cada ponta comprovam canal físico e papel em chamada de entrada e de saída. |
| QR-06 | Derivar `speaker` de metadados de direção/perna depois de QR-05, ou publicar papel neutro quando a direção não puder ser provada. | Must | Nenhum segmento recebe `atendente`/`cliente` apenas por `tx`/`rx` sem evidência do sentido da chamada. |
| QR-07 | Manter processamento local, sem GPU e sem envio de áudio sensível a STT externo. | Must | Imagem e execução não dependem de API externa; modelos são armazenados localmente com checksum. |
| QR-08 | Isolar recursos do STT dos containers de telefonia e banco. Aumento de CPU/RAM só ocorre depois do benchmark e preserva margem operacional do host. | Must | Limites Docker explícitos com prefixo `zenith-`; canário não aumenta jitter/perda de áudio do FreeSWITCH. |

## Gates quantitativos iniciais

O corpus de aceite deve conter pelo menos 20 chamadas ou 60 minutos, o que for atingido por último,
com ambos os canais anotados literalmente e amostras de silêncio, fila, URA, ruído, sobreposição,
números, nomes próprios e fala curta.

| Métrica | Gate inicial |
|---|---:|
| WER global | ≤ 20% |
| WER P90 por chamada | ≤ 35% |
| Inserção durante não-fala | ≤ 1 segmento / 10 min |
| Repetição alucinada idêntica em 3 ou mais regiões consecutivas | 0 |
| Papel de falante em chamadas controladas | 100% |
| Tradução, resumo ou paráfrase intencional | 0 |

Os limites devem ser revistos com o usuário depois do primeiro baseline; não podem ser afrouxados
apenas para aprovar o modelo atual.

## Restrições e dados sensíveis

- O WAV real e sua transcrição literal não entram no Git.
- O corpus vive em storage privado, com manifesto de hashes e IDs pseudonimizados no artefato de
  benchmark.
- Specs e logs não devem conter credenciais SMB, dados pessoais ou conteúdo integral de chamadas.
- A gravação e o backup continuam independentes: falha de STT não pode bloquear telefonia nem SMB.

## Impactos sob vigilância

- Aumentar o modelo sem VAD pode continuar alucinando e apenas elevar CPU/RAM.
- Aplicar filtro textual de frases repetidas é mitigação frágil; o gate deve atuar sobre fala,
  decodificação e evidência acústica.
- Prompt de vocabulário pode ajudar nomes do domínio, mas também induzir inserções; só entra se
  melhorar o corpus sem violar QR-02.
- `audio-transcript-long` não integra este fluxo: é uma skill auxiliar para arquivos longos, não o
  worker de produção da feature 013.

## Evidência usada

- `_reversa_forward/013-transcricao-persistida/quality-improvement-plan.md`
- `_reversa_forward/013-transcricao-persistida/interfaces/transcript-md.md`
- `_reversa_forward/014-captura-wav-16k/interfaces/recording-audio-files.md`
- `src/services/stt_whisper.py`
- `src/workers/transcript_batch.py`
- `_reversa_sdd/audio/design.md`
