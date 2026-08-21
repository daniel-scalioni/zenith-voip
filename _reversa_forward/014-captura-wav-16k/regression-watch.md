# Vigilância de regressão — feature 014-captura-wav-16k

## Watch principal

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|---|---|---|---|---|
| W001 | `_reversa_sdd/domain.md`, R38 | `zenith_recordings_tmpfs` permanece em 2 GiB, em RAM, com admissão preservando ao menos 20% projetados. | presença | Volume volta a 512 MiB, deixa de ser tmpfs ou aceita gravação abaixo da margem. |
| W002 | `_reversa_sdd/domain.md`, R39 | Cada canal final é WAV PCM16 mono 16 kHz; o estéreo SMB também é WAV 16 kHz. | redação | Retorno de MP3/8 kHz, codec lossy ou WAV apenas rotulado como 16 kHz. |
| W003 | `_reversa_sdd/domain.md`, R41 | Layout permanece `RECORDINGS_PATH/<tenant>/<call>/<canal>.wav`, com nomes `.tmp` privados durante escrita. | presença | Consumidor depende de `.mp3`, lê arquivo parcial ou perde o isolamento tenant/chamada. |

## Histórico de re-extrações

### Re-extração 2026-08-17 15:25

| ID | Veredito | Observação |
|----|----------|------------|
| W001 | 🟢 verde | Compose mantém tmpfs de 2 GiB e o SDD registra admissão/histerese 20/30%. |
| W002 | 🟢 verde | Captura, monos convertidos e estéreo SMB permanecem PCM16/WAV 16 kHz. |
| W003 | 🟢 verde | Temporários são privados, raws são promovidos e consumidores operam em paths tenant/call até os WAV finais. |

Nenhuma re-extração registrada.

## Arquivadas

Nenhuma vigilância arquivada.

## Observações

- R36 na extração ainda diz aproximadamente 1 hora, enquanto o baseline operacional anterior à
  feature já era `AUDIO_RETENTION_DAYS=0.0833` (aproximadamente 2 horas). A 014 não alterou esse
  valor; uma futura re-extração deve reconciliar a redação sem tratá-la como regressão da feature.
- As regras novas de lease, confirmação de consumidores e capacidade ainda não possuíam regra
  verde equivalente no legado; devem ser confirmadas numa futura re-extração antes de ganharem
  watch com peso de regressão.
- O contrato novo exige exclusão entre leases de owners distintos em qualquer estágio e ausência
  de entrada SMB para chamada ativa, par incompleto ou MP3 legado; ainda é observação sem peso por
  não derivar de regra verde do legado.
