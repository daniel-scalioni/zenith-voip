---
name: brainstorming-multiagent
description: >
  Protocolo socrático + validação cruzada com múltiplas LLMs reais via OpenCode
  CLI. Use para decisões técnicas não-óbvias (causa raiz incerta, escolha de
  arquitetura/módulo, trade-off relevante) antes de agir, ou para requisitos
  vagos antes de implementar. Quem chama a skill é quem escolhe os modelos,
  escreve as perguntas e julga as respostas — não há lista fixa de LLMs.
allowed-tools: Read, Bash, Grep, Write
---

# Brainstorming & Validação Multi-LLM

## Quando usar

| Situação | Ação |
|---|---|
| Pedido vago ("crie/construa X" sem detalhes) | Fazer 3 perguntas antes de implementar (ver seção Socrática) |
| Decisão técnica com mais de uma alternativa razoável | Consultar 2-3 LLMs reais com lentes diferentes antes de decidir |
| Diagnóstico de causa raiz que você não tem 100% de certeza | Pedir uma segunda opinião técnica real antes do fix |
| Confiança alta / ação trivial / já validado com evidência direta (log, teste rodado) | **Não precisa** — não use a skill para teatro de validação |

## Papel do orquestrador (quem chamou a skill)

**Você é responsável por gerenciar e moderar a conversa entre as LLMs — a skill não faz isso sozinha.** Isso significa, na prática:

- **Você escolhe os modelos**, a cada consulta, com base no que está de fato disponível no ambiente (rode `opencode models` antes de assumir um nome — nomes e sufixos como `:free` variam por ambiente e mudam com o tempo). Não existe uma lista fixa de "4 LLMs obrigatórias": escolha 2-4 modelos com lentes diferentes, apropriadas à pergunta.
- **Você escreve as perguntas**, uma por modelo, específicas ao que essa lente deveria avaliar (não a mesma pergunta genérica para todos).
- **Você julga cada resposta antes de aceitar.** Se um modelo devolver algo quebrado, fora de tópico, ou claramente ruim (aconteceu com Llama numa consulta real — ver exemplo abaixo), descarte e troque por outro modelo. Não insista no mesmo modelo por ele estar "na lista"; não invente uma resposta melhor no lugar dela.
- **Você faz o veredito final**, baseado em análise das divergências reais, não em votação nem em média.

## Protocolo (passo a passo validado em uso real)

1. **Confirme os modelos disponíveis:** `opencode models`. Não assuma nomes de memória.
2. **Escolha 2-4 modelos com lentes distintas**, adequadas à pergunta em questão. Exemplos de lente (troque livremente, não é fixo):
   - Pragmatismo/velocidade — "qual o fix mais rápido e seguro?"
   - Qualidade/arquitetura — "essa é a escolha certa a longo prazo? há alternativa melhor?"
   - Profundidade técnica — "que risco técnico específico estou ignorando?"
3. **Escreva um prompt autocontido por modelo.** Cada chamada `opencode run` é um processo novo, sem acesso à sua conversa — inclua todo o contexto necessário (o que já foi investigado, evidência já coletada, a pergunta exata). Para prompts longos/multilinha, escreva em um arquivo no scratchpad e rode com `"$(cat arquivo.txt)"` — evita problemas de quoting.
4. **Rode de verdade, via Bash:**
   ```bash
   opencode run --model <provider/model> "$(cat prompt.txt)"
   ```
   Timeout inicial de ~150s costuma bastar. Modelos que exploram o repositório (leem arquivos antes de responder) podem precisar de 250-300s — se der timeout no meio de uma exploração legítima, rode de novo com mais tempo antes de descartar o modelo.
5. **Julgue a resposta.** Resposta quebrada/genérica/fora de tópico → descarte e troque de modelo, registre a troca (não esconda que um modelo falhou).
6. **Analise convergência E divergência.** Onde os modelos concordam é sinal de robustez. Onde divergem, **investigue o motivo** — normalmente um viu algo que o outro não viu. Credite o ponto certo a quem estiver certo, com base em evidência, não em "3 contra 1".
7. **Reporte ao usuário em linguagem natural, curto**: uma tabela leve com as posições + o veredito com a razão técnica. Não invente métricas de confiança numérica (ex.: "99% de confiança") sem lastro real — isso é ruído, não informação.

## Exemplo real (consulta que originou este protocolo)

Diagnóstico: FreeSWITCH em produção sem `mod_audio_stream` carregado (imagem certa nunca promovida). Antes de fazer o rebuild, consultamos 3 modelos com lentes diferentes:

```bash
opencode models | grep free   # confirma o que está disponível antes de escolher

opencode run --model opencode/mimo-v2.5-free "$(cat q_mimo.txt)"        # lente: fix mais rápido/seguro
opencode run --model google/gemini-2.5-flash "$(cat q_gemini.txt)"     # lente: escolha certa a longo prazo
opencode run --model openrouter/meta-llama/llama-3.3-70b-instruct "$(cat q_llama.txt)"  # lente: risco técnico
```

O Llama devolveu uma resposta sem sentido (invocou uma skill errada, retornou um path de arquivo aleatório). Descartamos e trocamos por `opencode/deepseek-v4-flash-free` com a mesma pergunta — resposta excelente, levantou um risco real (incompatibilidade de ABI entre o `.so` compilado e o binário do FreeSWITCH) que os outros dois não tinham mencionado. O veredito final incorporou esse ponto como validação adicional obrigatória, em vez de ser descartado por "só 1 de 3 mencionou".

## Anti-patterns

| Não fazer | Por quê |
|---|---|
| Simular resposta de LLM ("acho que o Gemini diria...") | Não é validação, é invenção — invalida o veredito |
| Insistir num modelo que está falhando porque ele "é obrigatório" | Lista de modelos não é fixa; o orquestrador decide |
| Tratar divergência como empate/média | É onde está a informação real — investigue |
| Inventar score/confiança numérica sem lastro | Reporte incerteza real, não teatro de precisão |
| Fazer a mesma pergunta genérica para todos os modelos | Cada lente deve testar algo diferente |

## Protocolo Socrático (pedidos vagos)

Antes de implementar algo vago ("crie um X", feature nova sem detalhe, mudança de escopo ambíguo): pare e faça no mínimo 3 perguntas — propósito, usuários/contexto, escopo (must-have vs. nice-to-have) — e espere a resposta antes de prosseguir. Para bancos de perguntas específicos por domínio (e-commerce, auth, real-time, CMS) e o algoritmo de priorização (P0 bloqueante / P1 alto impacto / P2 opcional), ver `dynamic-questioning.md`.

## Troubleshooting

| Problema | Solução |
|---|---|
| `opencode: command not found` | Confirme instalação: `which opencode && opencode --version` |
| Timeout | Não é necessariamente modelo ruim — se estava explorando o repo, rode de novo com mais tempo (250-300s) |
| Modelo pede créditos/erro de billing | Troque por outro da lista de `opencode models` sem esse requisito |
| Resposta quebrada/sem relação com a pergunta | Descarte o modelo para essa consulta, troque, siga em frente — não é bloqueante |
