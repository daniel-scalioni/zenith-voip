# Plano corretivo — Qualidade da transcrição literal pt-BR

> Feature: `013-transcricao-persistida`
> Data: `2026-08-24`
> Estado: diagnóstico concluído; implementação não iniciada
> Spec anterior ao código: `_reversa_sdd/addenda/013-transcricao-persistida-qualidade.md`

## 1. Resultado do diagnóstico

### 1.1 Chamada correlacionada

| Campo | Valor |
|---|---|
| Call ID | `bad4cee5-2087-4e7b-81bf-7cbf706d299b` |
| Rota observada | `1001 → 1140100 → fila 30001` |
| Início | `2026-08-24 09:27:45 -03:00` |
| Fim no banco | `2026-08-24 09:28:07 -03:00` |
| Duração do WAV remoto | 19,86 s |
| Processamento STT | 636,44 s para os dois canais |
| Modelo atual | Whisper multilíngue `base`, `pt`, CPU, 1 thread |

O RTF observado foi aproximadamente `16,0` quando calculado sobre 39,72 s de áudio mono total
(19,86 s × 2 canais). Em tempo percebido por chamada, o worker levou cerca de 32 vezes a duração
da ligação.

### 1.2 Integridade e atividade acústica

O backup SMB contém WAV PCM16 estéreo 16 kHz válido, 16 bits, 512 kb/s e sem clipping. O contrato
da feature 014 define canal esquerdo como `tx` e direito como `rx`; a separação preservou exatamente
esses canais.

| Métrica | `tx` | `rx` |
|---|---:|---:|
| RMS global | -35,58 dBFS | -28,57 dBFS |
| Pico | -11,51 dBFS | -2,07 dBFS |
| Silêncio inicial detectado a -40 dB | 9,84 s | 2,50 s |
| Padrão visual | duas regiões principais de fala | múltiplas regiões de fala ao longo da chamada |

Não há evidência de arquivo vazio, taxa errada, clipping ou canais idênticos. A captura pode ter
ruído/codec de telefonia e merece um baseline de SNR, mas não explica sozinha texto começando em
silêncio nem a repetição idêntica em regiões acústicas diferentes.

### 1.3 Falhas observadas na saída

- O `tx` gerou texto em `0–13 s`, apesar de os primeiros ~9,8 s estarem abaixo do limiar de
  silêncio usado no diagnóstico.
- O `rx` repetiu a mesma sentença em nove segmentos consecutivos de 2 s, embora o espectro mostre
  blocos de fala e pausas diferentes.
- Confidence chegou a `0,95` em texto incompatível com a atividade acústica. O adapter calcula
  média de probabilidade de tokens, que não é confidence calibrada da transcrição nem prova de fala.
- O comando usa `-sns` (supressão de tokens não-fala), mas não usa o VAD disponível no binário.
- O modelo `base` tem 74 milhões de parâmetros. É um baseline pequeno; o próprio model card do
  Whisper reconhece variação por idioma e possibilidade de texto não pronunciado.

### 1.4 Papel dos canais

`tx → atendente` e `rx → cliente` não está comprovado para todos os sentidos de chamada. A spec
`_reversa_sdd/audio/design.md` registrou essa associação como pendente de validação real; depois,
a feature 013 a tratou como confirmação. A distribuição de fala desta chamada sugere possível
inversão, mas a correção não deve trocar duas constantes sem provar a perna FreeSWITCH capturada.

### 1.5 Limitação da análise atual

Este runtime não oferece reprodução auditiva direta ao agente. A avaliação foi feita por formato,
níveis, detecção de silêncio, waveform, espectrograma, logs e saída persistida. WER/CER literal só
pode ser calculado depois de uma pessoa autorizada anotar exatamente o que foi pronunciado. O WAV
não foi enviado a serviço externo.

## 2. Hipóteses priorizadas

| Prioridade | Hipótese | Evidência | Como confirmar/refutar |
|---|---|---|---|
| P0 | Ausência de VAD permite decodificação sobre silêncio/ruído e favorece alucinação. | Texto começa durante ~9,8 s de silêncio; `--vad` não está no comando. | Reprocessar corpus com Silero VAD e medir inserções em não-fala. |
| P0 | `base` é insuficiente para pt-BR telefônico deste domínio. | Repetição no `rx` apesar de fala presente; modelo tem 74 M parâmetros. | Benchmark cego `base`/`small`/`medium` ou equivalente quantizado contra ground truth. |
| P0 | Confidence atual mascara falhas. | Segmentos espúrios receberam 0,90–0,95. | Separar probabilidade de token, `no_speech`, VAD e métricas de decodificação; calibrar no corpus. |
| P0 | Papel de falante foi inferido do índice do canal. | Pendência histórica ainda existe; não há prova de entrada e saída. | Chamadas controladas com frases-identidade e inspeção de UUID/perna/direção. |
| P1 | Áudio telefônico precisa de condicionamento moderado. | `tx` tem nível global baixo e ambos os canais têm banda/ruído de telefonia. | A/B sem filtro vs. high-pass/normalização limitada; aceitar só se WER melhorar sem distorção. |
| P2 | Prompt de vocabulário pode ajudar nomes e números. | Domínio possui ramais, filas e nomes próprios. | Testar depois do modelo/VAD; rejeitar se elevar inserções. |

## 3. Estratégia recomendada

Não escolher um modelo maior por intuição. Executar uma competição offline com o mesmo corpus e
selecionar o candidato mais barato que passe os gates do adendo.

| Candidato | Papel no teste | Expectativa | Restrição |
|---|---|---|---|
| `whisper.cpp base` atual, sem VAD | Controle negativo | Reproduzir baseline | Não elegível se repetir o incidente. |
| `whisper.cpp base` + Silero VAD | Correção mínima | Reduzir alucinação em silêncio | Pode continuar errando palavras. |
| `whisper.cpp small` quantizado + VAD | **Primeiro candidato recomendado** | Melhor equilíbrio CPU/qualidade | Medir RAM e backlog; limite atual de 768 MiB provavelmente precisará mudar. |
| `whisper.cpp medium` quantizado + VAD | Escalonamento de qualidade | Usar se `small` não atingir WER | Custo CPU/RAM maior; só em canário isolado. |
| `faster-whisper small/medium`, CPU `int8` + VAD | Alternativa de engine | Pode melhorar throughput CPU | Nova imagem/dependências; comparar antes de migrar adapter. |

`audio-transcript-long` não é um candidato de runtime. Essa skill orquestra transcrição auxiliar
de arquivos longos; o benchmark pode reutilizar conceitos de chunking/faster-whisper, mas a
produção continuará em um worker versionado e testável do Zenith.

## 4. Plano Red → Green → Refactor

### Fase 0 — Corpus e baseline reproduzível

1. Preservar em storage privado o WAV estéreo e os canais da chamada incidente; registrar apenas
   hash, duração e call ID pseudonimizado no Git.
2. Produzir ground truth literal humana por canal, incluindo hesitações, repetições e palavras
   incompreensíveis marcadas por convenção explícita.
3. Coletar até atingir pelo menos 20 chamadas **e** 60 minutos, cobrindo entrada/saída, fila, URA,
   ruído, silêncio, sobreposição, números, nomes próprios e diferentes aparelhos.
4. Criar avaliador determinístico de WER/CER, inserção/deleção/substituição, texto em não-fala,
   RTF, RSS e CPU. O conteúdo real permanece fora do repositório.
5. Rodar o worker atual e congelar o baseline antes de qualquer ajuste.

**Gate:** nenhuma escolha de modelo antes do ground truth e do baseline.

### Fase 1 — Testes Red de silêncio e metadados de qualidade

Arquivos-alvo: `src/services/test_stt_whisper.py`, `src/workers/test_transcript_batch.py` e testes
de configuração correspondentes.

1. Testar que áudio sem fala produz zero segmentos, mesmo se o decoder devolver tokens com alta
   probabilidade.
2. Testar regiões de silêncio antes/depois da fala e timestamps após VAD/padding.
3. Testar propagação de `no_speech`, probabilidades e parâmetros do decoder para
   `extra_metadata`, sem tratá-los isoladamente como verdade.
4. Testar que falha/ausência do modelo VAD não publica texto silenciosamente e mantém retry seguro.
5. Testar cancelamento, timeout e cleanup dos sidecars/modelos temporários.
6. Manter o subprocesso como port externo mockado; não mockar normalização, rejeição ou regras de
   domínio.

**Green mínimo:** adapter configurável habilita VAD, preserva sinais do decoder e não persiste
segmento fora de região falada.

### Fase 2 — Benchmark de modelo e engine

1. Baixar modelos localmente com versão e SHA-256 fixos; nunca usar `latest` implícito.
2. Executar a matriz `base/small/medium`, VAD ligado, quantizações candidatas e threads
   `2/4/6`, uma chamada por vez.
3. Comparar `whisper.cpp` com `faster-whisper int8` somente se o primeiro candidato não atender
   simultaneamente qualidade e backlog.
4. Medir no host/VM real com `docker stats`, RSS peak, CPU, wall time e RTF; observar FreeSWITCH
   durante o teste.
5. Testar condicionamento conservador (`high-pass` e normalização limitada) como dimensão separada;
   não misturar seu efeito com a troca de modelo.
6. Selecionar o menor candidato que passe todos os gates quantitativos.

**Gate:** decisão registrada com tabela completa; nenhum rollout baseado em uma única chamada.

### Fase 3 — Semântica de canal e speaker

1. Fazer uma chamada de saída e uma de entrada controladas.
2. Cada participante pronuncia uma frase-identidade distinta, por exemplo “ponta ramal 1001” e
   “ponta atendente da fila”, sem usar conteúdo pessoal.
3. Correlacionar esquerdo/direito, `tx`/`rx`, UUID capturado, `Caller-Channel-Direction`,
   `agent_extension`, caller/callee e perna bridgeada.
4. Escrever testes Red para as duas direções e para metadado insuficiente.
5. Derivar `speaker` de direção/perna; se não houver prova, usar papel neutro em vez de atribuição
   falsa.

**Gate:** 100% de papéis corretos nas chamadas controladas.

### Fase 4 — Recursos e configuração

1. Acrescentar configurações explícitas para modelo STT, modelo VAD, thresholds, quantização,
   threads e parâmetros aprovados; validar limites em `src/config.py`.
2. Atualizar `Dockerfile.transcript` com artefatos pinados e checksums.
3. Dimensionar `zenith-arq-transcript` a partir do benchmark. Ponto inicial de experimento, não
   valor de produção: `small` com até 2 CPU/2 GiB; `medium` com até 4 CPU/4 GiB.
4. Antes de elevar limites, medir folga da VM de 16 GiB e dos demais containers. Se não houver
   margem segura, expandir a VM no hypervisor antes do rollout.
5. Manter concorrência 1 até comprovar que backlog e FreeSWITCH permanecem estáveis.

**Gate:** nenhuma mudança de memória/CPU sem evidência de pico e margem operacional.

### Fase 5 — Canário, gates e convergência

1. Executar novo pipeline em shadow/canário sem sobrescrever o transcript atual nas primeiras
   chamadas.
2. Comparar pelo menos 20 chamadas canário com ground truth ou revisão humana cega.
3. Passar `pytest -v tests src` e cobertura canônica ≥ 80%.
4. Rodar `alembic upgrade head`; nenhuma migration é esperada se sinais adicionais couberem em
   `extra_metadata`.
5. Obter parecer independente: “Há casos de borda não cobertos? Os testes estão viesados para esta
   implementação específica?”. Corrigir bloqueantes.
6. Promover o adendo de `draft` para `active` somente depois dos gates; então substituir o pipeline
   anterior e registrar rollback.

## 5. Critérios de parada e rollback

- Se VAD remover fala real, interromper o candidato e recalibrar threshold/padding; não compensar
  inserindo texto por heurística.
- Se `small` não passar WER, testar `medium`; se `medium` exceder margem/RTF, comparar
  `faster-whisper int8` ou expandir a VM antes de qualquer deploy.
- Se nenhum candidato local atingir o gate, registrar o resultado e negociar explicitamente novo
  hardware ou novo gate; não enviar áudio à nuvem por conveniência.
- Rollback restaura imagem/modelo/config anteriores sem afetar WAV, SMB ou lifecycle.

## 6. Próxima ação recomendada

Anotar literalmente a chamada incidente e realizar as duas chamadas controladas de identificação
de canal. Com esses três exemplos já é possível construir o primeiro teste Red, reproduzir o erro
e iniciar a matriz `base + VAD` versus `small + VAD` sem alterar a produção.

## 7. Fontes técnicas

- OpenAI Whisper model card: `https://github.com/openai/whisper/blob/main/model-card.md`
- OpenAI Whisper README/modelos: `https://github.com/openai/whisper`
- Ajuda do `whisper.cpp` v1.8.6 instalada no container, incluindo `--vad`, `--vad-model`,
  `--no-speech-thold`, `--entropy-thold` e `--logprob-thold`.
