# Actions: Migração de mod_audio_fork para mod_audio_stream

> Identificador: `007-audio-stream-migration`
> Data: `2026-07-08`
> Roadmap: `_reversa_forward/007-audio-stream-migration/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 14 |
| Paralelizáveis (`[//]`) | 4 |
| Maior cadeia de dependência | 8 (T001 → T003 → T004 → T007 → T008 → T009 → T011 → T013) |

## Fase 1, Preparação

<!-- Vendorização de artefatos e preparação da configuração base. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T001 | Vendorizar `.deb` necessários do FreeSWITCH (`libfreeswitch1`, `libfreeswitch-dev`, dependências diretas) em `freeswitch/vendor/debs/`, baixados com o token SignalWire válido, e adicionar a pasta ao `.gitignore` | - | `[//]` | `freeswitch/vendor/debs/`, `.gitignore` | 🟡 | `[X]` |
| T002 | Atualizar `freeswitch/conf/autoload_configs/modules.conf.xml`: remover o comentário de "mod_audio_fork removido temporariamente" e preparar a entrada para `mod_audio_stream` | - | `[//]` | `freeswitch/conf/autoload_configs/modules.conf.xml` | 🟢 | `[X]` |

## Fase 3, Núcleo

<!-- Build customizado e configuração de carregamento do novo módulo. Sem fase de testes automatizados: infraestrutura FreeSWITCH não tem suíte de TDD no projeto. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T003 | Reescrever o estágio `builder` de `freeswitch/Dockerfile`: instalar `libfreeswitch-dev` a partir dos `.deb` vendorizados (T001) com fallback documentado para o repositório SignalWire; clonar `amigniter/mod_audio_stream` (`--recurse-submodules`) e compilar via `cmake`/`make`, removendo o clone de `drachtio-freeswitch-modules` | T001 | - | `freeswitch/Dockerfile` | 🟢 | `[X]` |
| T004 | Ajustar o estágio final de `freeswitch/Dockerfile`: copiar `mod_audio_stream.so` e as libs de runtime `libevent-2.1`, `libevent_core`, `libevent_pthreads`, `libevent_openssl`, `libevent_extra` (`.so.7*`) do estágio `builder`, já que a imagem base não tem gerenciador de pacotes | T003 | - | `freeswitch/Dockerfile` | 🟢 | `[X]` |
| T005 | Ativar `<load module="mod_audio_stream"/>` em `freeswitch/conf/autoload_configs/modules.conf.xml` | T002 | - | `freeswitch/conf/autoload_configs/modules.conf.xml` | 🟢 | `[X]` |
| T006 | Atualizar a extensão `zenith_audio_fork` em `freeswitch/conf/dialplan/default.xml`: trocar `uuid_audio_fork ${uuid} start ws://zenith-api-1:8000/audio-stream stereo 8000 {...}` por `uuid_audio_stream ${uuid} start ws://zenith-api-1:8000/audio-stream stereo 8k {...}`, mantendo a mesma URL e metadata `call_id` | - | `[//]` | `freeswitch/conf/dialplan/default.xml` | 🟢 | `[X]` |

## Fase 4, Integração

<!-- Build, deploy e validação end-to-end em produção. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T007 | Rodar o build da nova imagem no host de produção (10.10.10.11) com o secret do token SignalWire e confirmar via `fs_cli -x "module_exists mod_audio_stream"` que retorna `true` | T004, T005 | - | `-` | 🟢 | `[X]` |
| T008 | Restart do container `freeswitch` em produção com a nova imagem (fora de horário de uso ou com aviso prévio) e confirmar via `sofia status` que os profiles `internal`, `internal-7060` e `internal-5062` continuam `RUNNING` sem regressão | T006, T007 | - | `-` | 🟢 | `[X]` |
| T009 | Realizar uma chamada real de teste (ramal registrado) passando pela extensão `zenith_audio_fork` e confirmar em `src/audio/ingestor.py`/eventos `audio_chunk` do Redis Streams que o payload PCM16 estéreo chega e é de-intercalado corretamente (valida a premissa D-05 do `roadmap.md` e fecha RF-04) | T008 | - | `-` | 🟡 | `[X]` |
| T010 | Caso T009 revele payload incompatível com `_split_stereo_frame`, ajustar `src/audio/ingestor.py` num commit dedicado para acomodar o formato real observado (ação condicional — só executar se T009 encontrar incompatibilidade) | T009 | - | `src/audio/ingestor.py` | 🟡 | `[X]` (condição não disparada — payload compatível, ver T009) |

## Fase 5, Polimento

<!-- Fechamento de gaps na documentação e watch de regressão. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T011 | Atualizar `_reversa_sdd/gaps.md#GAP-11` para ✅ Resolvida, com a evidência desta feature (build funcional, módulo carregado, teste real de chamada) | T009 | `[//]` | `_reversa_sdd/gaps.md` | 🟢 | `[X]` |
| T012 | Atualizar `_reversa_sdd/telephony/design.md#GAP-AUDIO-01` e a seção que descreve a captura de áudio via `mod_audio_fork`, substituindo pela referência a `mod_audio_stream` | T009 | `[//]` | `_reversa_sdd/telephony/design.md` | 🟢 | `[X]` |
| T013 | Gerar `regression-watch.md` listando os pontos de regressão: (1) profiles de entrada não afetados pelo restart do `freeswitch`; (2) payload de áudio permanece compatível com `_split_stereo_frame`; (3) build não depende obrigatoriamente do repositório SignalWire estar disponível | T011, T012 | - | `_reversa_forward/007-audio-stream-migration/regression-watch.md` | 🟢 | `[X]` |
| T014 | Marcar o critério de pronto em `roadmap.md#10` conforme os resultados reais de T007–T013 | T013 | - | `_reversa_forward/007-audio-stream-migration/roadmap.md` | 🟢 | `[X]` |

## Notas de execução

<!-- Reservado para /reversa-coding registrar avisos ou observações que surgiram durante a execução. -->

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-07-08 | Versão inicial gerada por `/reversa-to-do` | reversa |
