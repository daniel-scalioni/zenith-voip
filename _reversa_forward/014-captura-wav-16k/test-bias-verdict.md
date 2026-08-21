# Veredito independente anti-viés — Feature 014

> Data: 2026-08-14
> Modo: consultas read-only sequenciais via Claude CLI, Gemini CLI e OpenCode CLI
> Pergunta: “Há casos de borda não cobertos? Os testes estão viesados para esta implementação específica?”

## Veredito final do orquestrador

**GO para gates e validação operacional**, após correções Red → Green motivadas pelos pareceres.

## Modelos e julgamento

### Claude Sonnet — concorrência e lifecycle

Veredito recebido: NO-GO. Achados aceitos e corrigidos:

1. Falha de escrita em um canal não pode impedir a publicação do canal saudável.
2. `stream_metadata` precisa ser removido em recusa de capacidade e hangup antes do WebSocket.
3. O fallback SMB precisa respeitar o mesmo lease de conversão do uploader.

O item sobre cortar chamadas acima de cinco minutos foi rejeitado: 300 s é a premissa de
dimensionamento fornecida pelo usuário; a regra aprovada preserva chamadas ativas e bloqueia
somente novas gravações.

### Gemini 3 Flash Preview — capacidade e operação

Veredito recebido: NO-GO. Foi aceita a essência do risco de expansão pós-captura, mas rejeitada a
recomendação de elevar o tmpfs a 4 GiB, pois contrariava a decisão 1A e assumia 30 mixagens SMB
concorrentes, enquanto o worker SMB é sequencial.

Correção incorporada: `RecordingCapacityGuard` soma dinamicamente o crescimento ainda não
materializado de `.raw` para `.wav`. O teste de backlog comprova que 30 chamadas partindo de vazio
são admitidas, mas raws antigos reduzem novas admissões antes de cruzar 20% livre.

### OpenCode DeepSeek / Nemotron — testes adversariais

A primeira consulta DeepSeek foi descartada sem veredito porque tentou ler internals fora do
workspace e encerrou após a permissão ser negada. O Nemotron substituiu-a e concluiu a revisão.

Achados aceitos:

1. Perda do lease de captura deve fechar o WebSocket **e finalizar explicitamente** o estado,
   liberando reserva/handles mesmo sem depender de evento posterior.
2. A idempotência deve ser provada com duas chamadas realmente concorrentes a `finalize_stream`.
3. A configuração futura de dois consumidores deve ter teste positivo, não somente ausência.

Achados rejeitados por evidência:

- Exatamente 20% livre é permitido por “ao menos 20%”; `free_percent < threshold` está correto.
- `.consumed-smb` só é escrito após par WAV completo e checksum remoto, portanto não confirma um
  canal ausente.
- O SMB operacional possui um container, cron Redis único e lock de ciclo; o cenário de dois
  ciclos de processos distintos não representa o deploy especificado.
- TTL de duas horas é maior que a janela de duas rodadas de 15 minutos.
- `os.link` opera entre dois nomes criados no mesmo diretório/tmpfs, não entre filesystems.
- Validação acústica real da taxa/canais pertence ao gate T038 com `ffprobe` e chamada real.

## Evidência pós-correção

- Escrita falha por canal; canal saudável é publicado e enfileirado.
- Recusa/hangup precoce não deixam metadata.
- `ensure_mono_pair` retorna pendente se o uploader detém `.conversion-processing`.
- Backlog raw→WAV participa da projeção de capacidade.
- Heartbeat perdido finaliza o estado e libera a reserva.
- Duas finalizações concorrentes produzem um único enqueue/resultado final.
- Dois consumidores (`smb`, `transcription`) são confirmados sem alteração de código.

Os testes permanecem parcialmente apoiados em ports simulados (ffmpeg/SMB/clock), como exige a
estratégia de testes do projeto. Por isso o GO local não substitui os gates reais T038–T040.
