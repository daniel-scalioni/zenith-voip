---
name: brainstorming-multiagent
description: >
  Protocolo socrático, delegação e validação cruzada com múltiplas LLMs reais
  via OpenCode CLI e Claude CLI. Use para decisões técnicas não-óbvias,
  diagnóstico incerto, requisitos vagos ou para delegar código/testes a um
  modelo independente e reduzir viés do agente principal. Quem chama escolhe
  modelos, permissões e lentes, e julga as respostas e alterações.
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

- **Você escolhe os modelos**, a cada consulta, com base no que está de fato disponível no ambiente
  (rode `opencode models` e, quando usar Anthropic diretamente, `claude --version`/`claude
  --help`). Não assuma nomes, aliases ou opções de memória. Não existe uma lista fixa de modelos
  obrigatórios: escolha 2-4 modelos com lentes diferentes, apropriadas à pergunta.
- **Você escreve as perguntas**, uma por modelo, específicas ao que essa lente deveria avaliar (não a mesma pergunta genérica para todos).
- **Você julga cada resposta antes de aceitar.** Se um modelo devolver algo quebrado, fora de tópico, ou claramente ruim (aconteceu com Llama numa consulta real — ver exemplo abaixo), descarte e troque por outro modelo. Não insista no mesmo modelo por ele estar "na lista"; não invente uma resposta melhor no lugar dela.
- **Você faz o veredito final**, baseado em análise das divergências reais, não em votação nem em média.

## ⚠️ Execução SEMPRE sequencial (regra não-negociável)

As consultas/chamadas a modelos **nunca devem ser executadas em paralelo**. Rode uma por vez
(serialize): inicie um modelo, aguarde o retorno completo, julgue-o **então** passe para o
próximo. Isso vale para todos os modos (consulta e delegação) e para os múltiplos modelos/lentes.

Motivo: a execução paralela de várias LLMs simultaneamente consome excessivamente CPU/RAM/GPU do
hardware local e pode saturar a máquina. Ser mais lento um pouco, mas sustentável, é preferível.

Na prática:
- Não dispare todas as chamadas de uma vez num único bloco de comandos (`&&` encadeado, loop
  `&`, `xargs -P`, background jobs em paralelo).
- Rode a primeira chamada, espere o terminal/CLI devolver a resposta completa, verifique o
  resultado, e só então rode a próxima.
- Ao usar múltiplos agentes/tasks, espere um terminar antes de iniciar o seguinte.

## Protocolo (passo a passo validado em uso real)

1. **Confirme as CLIs e modelos disponíveis:** `opencode models`; para Anthropic direto, confirme
   `claude --version` e a sintaxe vigente em `claude --help`. Não assuma nomes ou flags de memória.
2. **Escolha 2-4 modelos com lentes distintas**, adequadas à pergunta em questão. Exemplos de lente (troque livremente, não é fixo):
   - Pragmatismo/velocidade — "qual o fix mais rápido e seguro?"
   - Qualidade/arquitetura — "essa é a escolha certa a longo prazo? há alternativa melhor?"
   - Profundidade técnica — "que risco técnico específico estou ignorando?"
3. **Escolha o modo de cada chamada:**
   - **Consulta:** modelo responde/revisa sem editar arquivos.
   - **Delegação:** um modelo recebe autorização explícita e escopo exato para editar. Use quando a
     independência de autoria for parte do objetivo, como testes anti-viés.
4. **Escreva um prompt autocontido por modelo.** Cada processo começa sem acesso à conversa —
   inclua contexto, artefatos que deve ler, pergunta/tarefa exata, limites e formato de saída.
   Para prompts longos, use arquivo temporário no scratchpad e passe seu conteúdo à CLI.
5. **Rode de verdade via uma CLI confirmada — SEMPRE em sequência**, um modelo por vez: execute a
   primeira chamada, aguarde o retorno completo, julgue e só então execute a próxima. Nunca lance
   os vários modelos em paralelo num mesmo bloco de comandos (ver seção "Execução SEMPRE sequencial").
   - OpenCode:
     ```bash
     opencode run --model <provider/model> "$(cat prompt.txt)"
     ```
   - Claude Code, consulta read-only:
     ```bash
     claude --print --model <alias-ou-modelo> --tools "Read,Grep,Glob" \
       --permission-mode dontAsk "$(cat prompt.txt)"
     ```
   - Claude Code, delegação com escrita limitada ao workspace:
     ```bash
     claude --print --model <alias-ou-modelo> --tools "Read,Grep,Glob,Edit,Write,Bash" \
       --permission-mode acceptEdits "$(cat prompt.txt)"
     ```
   Confirme as flags contra o `--help` instalado. Defina diretório de trabalho no projeto e nunca
   forneça segredos no prompt.
6. **Em delegação, serialize escritores.** Somente um modelo pode editar determinado conjunto de
   arquivos por vez. Depois da escrita, capture o diff e entregue esse diff — não a resposta
   desejada — a outro modelo em modo read-only para revisão independente.
7. **Preserve autoria e anti-viés.** O orquestrador não deve reescrever silenciosamente os testes
   delegados. Ele valida contrato, qualidade e execução; se houver falha substantiva, devolve ao
   autor externo ou solicita uma correção independente, registrando a rodada.
   Timeout inicial de ~150s costuma bastar. Modelos que exploram o repositório (leem arquivos antes de responder) podem precisar de 250-300s — se der timeout no meio de uma exploração legítima, rode de novo com mais tempo antes de descartar o modelo.
8. **Julgue a resposta ou diff.** Resultado quebrado, genérico, fora de tópico ou fora do escopo →
   descarte/reverta somente as alterações daquele agente e troque de modelo; registre a troca.
9. **Analise convergência E divergência.** Onde os modelos concordam é sinal de robustez. Onde
   divergem, investigue o motivo e decida por evidência, não por votação.
10. **Reporte ao usuário em linguagem natural, curto:** modelos/CLIs usados, autoria dos arquivos,
    divergências, correções solicitadas e veredito. Não invente confiança numérica.

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
| Executar múltiplos modelos/consultas em paralelo (bloco único de comandos, `&&` encadeado, `xargs -P`, background) | Satura CPU/RAM/GPU do hardware local; serialize — um modelo por vez, aguarde e julgue antes do próximo |
| Permitir dois modelos editarem os mesmos arquivos em paralelo | Mistura autoria, cria conflitos e invalida a revisão independente |
| O orquestrador “melhorar” silenciosamente testes delegados | Reintroduz o viés que a delegação deveria reduzir |
| Usar `--permission-mode bypassPermissions` por conveniência | Amplia autoridade sem necessidade; prefira ferramentas e permissões mínimas |

## Protocolo Socrático (pedidos vagos)

Antes de implementar algo vago ("crie um X", feature nova sem detalhe, mudança de escopo ambíguo): pare e faça no mínimo 3 perguntas — propósito, usuários/contexto, escopo (must-have vs. nice-to-have) — e espere a resposta antes de prosseguir. Para bancos de perguntas específicos por domínio (e-commerce, auth, real-time, CMS) e o algoritmo de priorização (P0 bloqueante / P1 alto impacto / P2 opcional), ver `dynamic-questioning.md`.

## Troubleshooting

| Problema | Solução |
|---|---|
| `opencode: command not found` | Confirme instalação: `which opencode && opencode --version` |
| `claude: command not found` | Confirme instalação: `which claude && claude --version` |
| Claude não autenticado/modelo indisponível | Use outro alias confirmado ou volte ao OpenCode; registre a troca |
| Timeout | Não é necessariamente modelo ruim — se estava explorando o repo, rode de novo com mais tempo (250-300s) |
| Modelo pede créditos/erro de billing | Troque por outro da lista de `opencode models` sem esse requisito |
| Resposta quebrada/sem relação com a pergunta | Descarte o modelo para essa consulta, troque, siga em frente — não é bloqueante |
