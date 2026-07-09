# Requirements: Migração de mod_audio_fork para mod_audio_stream

> Identificador: `007-audio-stream-migration`
> Data: `2026-07-08`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

O FreeSWITCH captura áudio das chamadas via `mod_audio_fork` (`_reversa_sdd/architecture.md#Papel do FreeSWITCH`), mas o módulo está bloqueado desde o GAP-11: o repositório `drachtio/drachtio-freeswitch-modules`, de onde o módulo era compilado, não existe mais no GitHub. Esta feature substitui `mod_audio_fork` por `mod_audio_stream` (projeto `amigniter/mod_audio_stream`, MIT, ativo), validado nesta sessão como funcional (build e carregamento confirmados contra FreeSWITCH 1.11 real). Resolve GAP-11 e reduz a dependência de autenticação externa do processo de build, ao vendorizar os artefatos necessários em vez de depender indefinidamente do repositório de pacotes da SignalWire.

## 2. Contexto a partir do legado

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `_reversa_sdd/architecture.md#Papel do FreeSWITCH` | "FreeSWITCH captura o áudio para transcrição/IA via `mod_audio_fork`" — TD01 lista `_detect_channel()` hardcoded em `src/audio/ingestor.py:70-71` | 🟢 |
| `_reversa_sdd/telephony/design.md#GAP-AUDIO-01` | `mod_audio_fork` requer build customizado bloqueado pelo token SignalWire inválido (GAP-11) | 🔴 (confidência da lacuna original; a causa raiz mudou nesta sessão — ver abaixo) |
| `freeswitch/conf/dialplan/default.xml:34-43` | Extensão `zenith_audio_fork` invoca `uuid_audio_fork ${uuid} start ws://zenith-api-1:8000/audio-stream stereo 8000 {"call_id":"${uuid}"}` | 🟢 |
| `src/audio/ingestor.py` | `AudioIngestor.handle_forked_stream()` recebe WebSocket, espera PCM16 estéreo intercalado (`_split_stereo_frame`), publica eventos `audio_chunk` via Redis Streams | 🟢 |
| `_reversa_sdd/gaps.md#GAP-11` | Confirmado bloqueado (2026-06-24): token SignalWire rejeitado (401) contra o repositório de pacotes do FreeSWITCH | 🟢 (causa raiz específica do token já resolvida nesta sessão — ver Esclarecimentos) |
| Validação ao vivo nesta sessão (2026-07-08) | `mod_audio_stream` compilado com sucesso contra `libfreeswitch-dev` 1.11.1 (token SignalWire `pat_...` correto) + libs `libevent-2.1`/`core`/`pthreads`/`openssl`/`extra` copiadas do stage builder; `module_exists mod_audio_stream` retornou `true` num FreeSWITCH real rodando a conf do projeto | 🟢 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| Operador de infraestrutura (Daniel) | Ter a captura de áudio funcionando sem depender de um repositório de terceiros que pode sumir | Rebuild da imagem FreeSWITCH em uma máquina nova não falha por causa de autenticação externa |
| Zenith AI Audio Hub (sistema) | Continuar recebendo o mesmo formato de áudio (PCM16 estéreo, tx/rx) que já processa hoje | `src/audio/ingestor.py` recebe o stream sem precisar reescrever toda a lógica de de-interleaving |

## 4. Regras de negócio novas ou alteradas

1. **RN-01:** A captura de áudio de chamadas DEVE ocorrer via `mod_audio_stream` em vez de `mod_audio_fork`. 🟢
   - Origem no legado: `_reversa_sdd/architecture.md#Papel do FreeSWITCH` (regra alterada — mecanismo de captura muda, comportamento observável para o resto do sistema permanece o mesmo)
   - Tipo: alterada
2. **RN-02:** O processo de build da imagem FreeSWITCH NÃO pode depender indefinidamente de autenticação contra um serviço de terceiros (SignalWire) para poder ser reproduzido no futuro. 🟢
   - Origem: requisito explícito do usuário nesta sessão, motivado pela descoberta de que a URL de cadastro do token está morta e o repositório `drachtio-freeswitch-modules` foi descontinuado
   - Tipo: nova
3. **RN-03:** O formato de payload de áudio entregue a `src/audio/ingestor.py` (PCM16, estéreo, canais tx/rx separáveis) DEVE permanecer compatível, para não exigir reescrita da lógica de de-interleaving e publicação de eventos já existente. 🟢
   - Origem no legado: `src/audio/ingestor.py::_split_stereo_frame`
   - Tipo: nova (restrição de compatibilidade)
4. **RN-04:** GAP-11 e GAP-AUDIO-01 DEVEM ser fechados em `_reversa_sdd/gaps.md` e `_reversa_sdd/telephony/design.md` como parte desta feature. 🟢
   - Tipo: nova

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| RF-01 | `freeswitch/Dockerfile` deve compilar `mod_audio_stream` a partir do repositório `amigniter/mod_audio_stream`, copiando o `.so` e as dependências de runtime necessárias (`libevent-2.1`, `libevent_core`, `libevent_pthreads`, `libevent_openssl`, `libevent_extra`) para a imagem final | Must | Build da imagem passa sem erro; `fs_cli -x "module_exists mod_audio_stream"` retorna `true` num container rodando a imagem | 🟢 |
| RF-02 | `freeswitch/conf/autoload_configs/modules.conf.xml` deve carregar `mod_audio_stream` (e não mais tentar carregar `mod_audio_fork`) | Must | `sofia`/`fs_cli` não reporta erro de carregamento de módulo no boot | 🟢 |
| RF-03 | `freeswitch/conf/dialplan/default.xml` deve trocar `uuid_audio_fork ... start ws://... stereo 8000 ...` por `uuid_audio_stream ... start ws://... stereo 8k ...` (ou `16k`, a decidir), mantendo a URL de destino (`ws://zenith-api-1:8000/audio-stream`) e o metadata `call_id` | Must | Chamada real de teste gera stream recebido por `src/audio/ingestor.py` sem erro | 🟢 |
| RF-04 | `src/audio/ingestor.py` deve ser revisado para confirmar (ou ajustar) a compatibilidade do payload recebido de `mod_audio_stream` com `_split_stereo_frame` — `mod_audio_stream` no modo `stereo` envia dois canais (caller/callee); confirmar se o payload chega como um único frame intercalado (igual ao `mod_audio_fork`) ou em formato diferente (ex: mensagens JSON + binário separados) | Must | Teste real ponta-a-ponta com uma chamada mostra eventos `audio_chunk` publicados corretamente com tx/rx distintos | 🔴 |
| RF-05 | O processo de build não deve depender de o repositório de pacotes da SignalWire continuar disponível no futuro — vendorizar os headers do FreeSWITCH necessários (`libfreeswitch-dev`) OU publicar uma imagem própria já buildada em um registry controlado pelo time (Docker Hub próprio ou registry privado) | Must | Documentado um destes dois caminhos como decisão, com rota de rebuild que não depende do token SignalWire | 🔴 |
| RF-06 | `_reversa_sdd/gaps.md#GAP-11` e `_reversa_sdd/telephony/design.md#GAP-AUDIO-01` devem ser atualizados para refletir a resolução | Must | Ambos os arquivos mostram status ✅ Resolvida com a evidência desta feature | 🟢 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| Disponibilidade | A troca de módulo não pode interromper registros ativos no profile `internal` nem nos profiles `internal-7060`/`internal-5062` (feature `006`) | Mesmo cuidado já aplicado em `005-dynamic-external-ip` e `006-registro-porta-vitalpbx` | 🟢 |
| Segurança | Nenhuma credencial (token SignalWire, senha ESL) deve vazar em logs de build ou runtime | Política do projeto (`CLAUDE.md#Credenciais e Segurança`) | 🟢 |
| Portabilidade/Supply-chain | O processo de rebuild da imagem não deve falhar de forma bloqueante se um serviço de terceiros (SignalWire) descontinuar seu fluxo de autenticação, repetindo o incidente do GAP-11 | Motivação explícita do usuário nesta sessão | 🟢 |
| Licenciamento | `mod_audio_stream` (edição community, MIT) deve ser usado dentro dos termos da licença; a "edição comercial" (bidirecional, limite de 10 canais) não é necessária para o caso de uso atual (streaming unidirecional para transcrição) | Verificado no `README.md` e `LICENSE` do repositório nesta sessão | 🟢 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Build da imagem FreeSWITCH sem mod_audio_fork
  Dado o Dockerfile atualizado para usar mod_audio_stream
  Quando o build é executado com o token SignalWire válido
  Então a imagem é gerada com sucesso
  E mod_audio_stream.so está presente em /usr/lib/freeswitch/mod/

Cenário: Módulo carrega no boot
  Dado o container FreeSWITCH com a nova imagem
  Quando o FreeSWITCH inicia
  Então "fs_cli -x módulo_exists mod_audio_stream" retorna true
  E nenhum profile de entrada (internal, internal-7060, internal-5062) fica indisponível

Cenário: Chamada real gera stream de áudio
  Dado um ramal registrado (ex: 1001) em chamada ativa
  Quando o dialplan aciona uuid_audio_stream
  Então src/audio/ingestor.py recebe o WebSocket e processa os chunks de áudio
  E eventos audio_chunk são publicados no Redis Streams com tx/rx distintos

Cenário: Rebuild futuro sem o token SignalWire
  Dado que o token/repositório SignalWire deixou de existir
  Quando alguém tenta reconstruir a imagem FreeSWITCH a partir do zero
  Então o processo documentado (headers vendorizados ou imagem própria publicada) permite o rebuild sem essa dependência
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|----------------|
| RF-01 — build de mod_audio_stream | Must | Sem isso não há substituição nenhuma |
| RF-02 — carregar módulo correto | Must | Módulo compilado sem carregar não resolve nada |
| RF-03 — dialplan atualizado | Must | Sem isso a captura nunca é acionada numa chamada real |
| RF-04 — compatibilidade do payload | Must | Sem isso o pipeline de transcrição quebra silenciosamente |
| RF-06 — fechar gaps na spec | Must | Exigência do CLAUDE.md (specs refletem estado real) |
| RF-05 — reduzir dependência externa | Must (mas com desenho a decidir em `/reversa-plan`) | Requisito explícito do usuário, mas a forma exata (vendorizar vs. imagem própria) precisa de decisão técnica |

## 9. Esclarecimentos

### Sessão 2026-07-08 (resolução autônoma, autorizada explicitamente pelo usuário)

- **Q:** Formato exato do payload de `mod_audio_stream` em modo `stereo` — compatível com `_split_stereo_frame`?
  **R:** Investigação do código-fonte (`audio_streamer_glue.cpp`, parâmetro `channels` + resampler por canal) mostra que o módulo segue a convenção padrão de PCM intercalado por canal (mesma convenção usada por `mod_audio_fork`), não mensagens separadas por canal. Alta probabilidade de compatibilidade direta com `_split_stereo_frame`, mas fica como item de validação obrigatória em `/reversa-coding` (teste real com chamada ativa) antes de considerar RF-04 fechado — por isso mantém confidência 🟡 em vez de 🟢.

- **Q:** Estratégia de redução de dependência externa (RF-05)?
  **R:** Vendorizar os pacotes `.deb` necessários (`libfreeswitch1`, `libfreeswitch-dev` e dependências diretas) baixados uma única vez do repositório SignalWire, guardados fora do git (mesmo padrão já usado para `freeswitch/signalwire_token.txt`, artefato local/gitignored, não versionado por serem binários grandes), permitindo `dpkg -i` local no build sem depender do repositório estar no ar. Publicar imagem própria em registry foi descartado por ora — exigiria decidir/criar infraestrutura de registry nova, fora do escopo desta feature; fica registrado como alternativa futura se o volume de rebuilds justificar.

- **Q:** Sampling rate — 8k ou 16k?
  **R:** Manter **8k**, igual ao valor `8000` já usado hoje no dialplan para `mod_audio_fork`. Minimiza superfície de mudança e é consistente com o que o pipeline STT (Deepgram/Whisper) já está calibrado para processar (áudio de telefonia). Migração para 16k fica registrada como melhoria futura, fora de escopo.

## 10. Lacunas

- 🟢 Formato de payload: PCM intercalado por canal (mesma convenção de `mod_audio_fork`), a confirmar com teste real em `/reversa-coding`.
- 🟢 Redução de dependência externa: vendorizar `.deb` do FreeSWITCH localmente (fora do git), sem publicar registry próprio nesta feature.
- 🟢 Sampling rate: 8k, sem mudança em relação ao comportamento atual.

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-07-08 | Versão inicial gerada por `/reversa-requirements` | reversa |
