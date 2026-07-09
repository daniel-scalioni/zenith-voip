# Investigation: Migração de mod_audio_fork para mod_audio_stream

> Identificador: `007-audio-stream-migration`
> Data: `2026-07-08`

## 1. Pesquisa de fundo

`mod_audio_fork` era distribuído junto com `drachtio/drachtio-freeswitch-modules`, um repositório GitHub que não existe mais na organização `drachtio` (confirmado via API do GitHub nesta sessão: apenas `drachtio-server`, `drachtio-sip`, `drachtio-fsmrf` etc. seguem ativos; nenhum `drachtio-freeswitch-modules`). O "Plano B" já previsto no `Dockerfile` antigo (`drachtio/docker-drachtio-freeswitch-mrf`) existe mas está **arquivado** (último push 2024-10-21).

## 2. Alternativas avaliadas

| Alternativa | Descrição | Por que foi descartada/aceita |
|-------------|-----------|-------------------------------|
| `drachtio/drachtio-freeswitch-modules` (original) | Repositório de módulos FreeSWITCH do time drachtio | Descartada — repositório não existe mais |
| `drachtio/docker-drachtio-freeswitch-mrf` | Imagem Docker pronta com módulos drachtio | Descartada — arquivada, sem manutenção, exigiria revalidar toda a `freeswitch/conf/` contra uma base desconhecida |
| Fork da comunidade `W1ck3dZA/mod_audio_fork` | Fork não-oficial do módulo original | Descartada — sem tração da comunidade (poucas estrelas), sem garantia de manutenção |
| **`amigniter/mod_audio_stream`** | Módulo de streaming de áudio via WebSocket, "inspirado no mod_audio_fork" | **Aceita** — 224 estrelas, commit recente (2026-01-28), MIT, dependências padrão Debian, testado nesta sessão com sucesso |

## 3. Validação técnica realizada nesta sessão

1. Token SignalWire correto (`pat_...`, Personal Access Token) identificado e validado contra o repositório de pacotes (200 OK).
2. Bug real corrigido no `Dockerfile`: pacote `freeswitch-dev` não existe, o correto é `libfreeswitch-dev` (commitado em `8bec67c`).
3. Build de `mod_audio_stream` via `cmake` funcionou de primeira contra `libfreeswitch-dev` 1.11.1.
4. Módulo não carregava na imagem final por falta de `libevent` (não existe na imagem base `safarov/freeswitch:1.10.12`, que não tem gerenciador de pacotes). Corrigido copiando os `.so.7*` do stage builder.
5. `fs_cli -x "module_exists mod_audio_stream"` retornou `true` contra uma instância real rodando a conf do projeto (após ajustar temporariamente o ACL do event socket para teste, já que o teste rodou em rede bridge isolada, não host).
6. Inspeção do código-fonte (`audio_streamer_glue.cpp`) mostra parâmetro `channels` e resampler por canal — mesma convenção de PCM intercalado que `mod_audio_fork` usava, sustentando a premissa de compatibilidade com `src/audio/ingestor.py::_split_stereo_frame`.

## 4. Padrões aplicáveis

- **Separação de stages de build (builder/final) com libs copiadas explicitamente**: já era o padrão do `Dockerfile` original para `mod_audio_fork`; mantido para `mod_audio_stream`.
- **Vendorização de artefatos para reduzir dependência de serviços externos**: novo padrão introduzido por esta feature, motivado pela lição aprendida com o GAP-11 original (URL de cadastro morta, repositório descontinuado).
