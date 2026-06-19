# Reversa

> Framework de Engenharia Reversa instalado neste projeto.

## Como usar

Digite `reversa` ou use `/reversa` para ativar o Reversa e iniciar ou retomar a análise do projeto.

## Comportamento ao ativar

Quando o usuário digitar `reversa` sozinho em uma mensagem ou usar `/reversa`:

1. Ative o skill `reversa` disponível em `.agents/skills/reversa/SKILL.md`
2. Leia o SKILL.md na íntegra e siga exatamente as instruções do Reversa

## Comandos Úteis do Projeto

- **Setup inicial:** `bash bootstrap.sh`
- **Subir infraestrutura:** `docker compose up -d`
- **Executar testes:** `pytest tests/ -v`
- **Testes específicos:** `pytest tests/test_bunker_sticky.py -v`

## Regra não-negociável

Nunca apague, modifique ou sobrescreva arquivos pré-existentes do projeto legado.
O Reversa escreve **apenas** em `.reversa/` e `_reversa_sdd/`.


# zenith-voip — Pasta de criação de slides (Mira)

Esta pasta é uma instalação do **Mira**: agentes e templates para criar apresentações HTML animadas com D3.js. Trate user pelo nome e interaja em pt-br.

## Regras para o agente

1. **Fontes vinculadas**: o conteúdo das apresentações vem das fontes listadas em `mira.config.json` (`sources[]`). Leia das fontes, mas NUNCA crie, edite ou apague arquivos dentro delas. Todo output vai para `decks/`.
2. **Pipeline**: para criar slides, siga a ordem: `/mira-extract` → `/mira-planner` → `/mira-copywriter` → `/mira-builder` + `/mira-animator` → `/mira-validator`.
3. **Regra zero de animação**: toda animação ENTRA com coreografia e DEPOIS continua em loop interno perpétuo. Animação estática é proibida.
4. **Tema**: o tema padrão deste projeto é `mira-dark`. Use SEMPRE as CSS variables do tema (`var(--mira-primary)` etc.) — nunca cores hardcoded. Temas em `mira-templates/themes/`.
5. **Idioma**: siga `_shared/idioma.md` — todo texto visível em português brasileiro com acentuação 100% correta.
6. **Templates**: blueprints de slides em `mira-templates/slides/`, decks completos em `mira-templates/decks/`, cards atômicos em `mira-builder/templates/` (dentro das skills).

## Estrutura

```
mira.config.json     fontes vinculadas, tema padrão, decks criados
decks/               apresentações geradas (uma pasta por deck)
mira-templates/      themes, slides e decks de referência
.mira/               estado da instalação (não editar manualmente)
```


# zenith-voip — Pasta de criação de slides (Mira)

Esta pasta é uma instalação do **Mira**: agentes e templates para criar apresentações HTML animadas com D3.js. Trate user pelo nome e interaja em pt-br.

## Regras para o agente

1. **Fontes vinculadas**: o conteúdo das apresentações vem das fontes listadas em `mira.config.json` (`sources[]`). Leia das fontes, mas NUNCA crie, edite ou apague arquivos dentro delas. Todo output vai para `decks/`.
2. **Pipeline**: para criar slides, siga a ordem: `/mira-extract` → `/mira-planner` → `/mira-copywriter` → `/mira-builder` + `/mira-animator` → `/mira-validator`.
3. **Regra zero de animação**: toda animação ENTRA com coreografia e DEPOIS continua em loop interno perpétuo. Animação estática é proibida.
4. **Tema**: o tema padrão deste projeto é `mira-dark`. Use SEMPRE as CSS variables do tema (`var(--mira-primary)` etc.) — nunca cores hardcoded. Temas em `mira-templates/themes/`.
5. **Idioma**: siga `_shared/idioma.md` — todo texto visível em português brasileiro com acentuação 100% correta.
6. **Templates**: blueprints de slides em `mira-templates/slides/`, decks completos em `mira-templates/decks/`, cards atômicos em `mira-builder/templates/` (dentro das skills).

## Estrutura

```
mira.config.json     fontes vinculadas, tema padrão, decks criados
decks/               apresentações geradas (uma pasta por deck)
mira-templates/      themes, slides e decks de referência
.mira/               estado da instalação (não editar manualmente)
```
