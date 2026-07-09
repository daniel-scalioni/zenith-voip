# Legacy Impact: Migração de mod_audio_fork para mod_audio_stream

> Identificador: `007-audio-stream-migration`
> Data: `2026-07-09`
> Execução: quase completa (12/14 ações) — T009/T010 bloqueadas nesta sessão por ausência do serviço `zenith-api-1`/FastAPI no ambiente e de ramal registrado no momento do teste

## Tabela de impacto

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|------------------|------------|------|------------|----------------|
| `freeswitch/Dockerfile` | Build da imagem FreeSWITCH (`_reversa_sdd/architecture.md#Papel do FreeSWITCH`) | regra-alterada | HIGH | Troca completa do mecanismo de captura de áudio (mod_audio_fork → mod_audio_stream); build agora usa `.deb` vendorizados em vez de depender do repositório SignalWire |
| `freeswitch/.dockerignore` (novo) | Build da imagem FreeSWITCH | componente-novo | LOW | Necessário para excluir `conf/` (permissão negada em `conf/tls`) do build context |
| `freeswitch/vendor/debs/` (novo, gitignored) | Build da imagem FreeSWITCH | componente-novo | MEDIUM | 37 `.deb` vendorizados localmente — reduz dependência externa, mas introduz responsabilidade de atualização manual quando a versão do FreeSWITCH mudar |
| `freeswitch/conf/autoload_configs/modules.conf.xml` | Carregamento de módulos SIP | regra-alterada | HIGH | `mod_audio_stream` carregado no lugar do `mod_audio_fork` (que nunca chegou a carregar em produção) |
| `freeswitch/conf/dialplan/default.xml` (extensão `zenith_audio_fork`) | Contrato WebSocket de captura de áudio | contrato-alterado | HIGH | `uuid_audio_fork` → `uuid_audio_stream`; mesma URL de destino, mesmo mix-type, sample rate mantido em 8k |
| `docker-compose.app.yml` (serviço `freeswitch`) | Deploy do FreeSWITCH | regra-alterada | MEDIUM | Bloco `build:` restaurado (estava comentado desde `004-bootstrap-freeswitch`), removida a linha `image: safarov/freeswitch:1.10.12` |
| `src/audio/ingestor.py` | Ingestão de áudio | sem mudança | — | Nenhuma alteração de código feita; compatibilidade é premissa não validada (ver Modificadas) |
| `_reversa_sdd/gaps.md#GAP-11` | Documentação de gaps | regra-alterada | MEDIUM | De "confirmado bloqueado" para "✅ Resolvida" com ressalva de validação end-to-end pendente |
| `_reversa_sdd/telephony/design.md#GAP-AUDIO-01`, `_reversa_sdd/architecture.md` | Documentação de arquitetura | regra-alterada | LOW | Referências a `mod_audio_fork` atualizadas para `mod_audio_stream` |

## Diff conceitual por componente

**Captura de áudio do FreeSWITCH:** antes desta feature, o mecanismo de captura (`mod_audio_fork`) estava documentado mas nunca funcionou em produção — o container rodava a imagem vanilla, sem o módulo (GAP-11). Agora, `mod_audio_stream` está compilado, carregado e confirmado via `module_exists` no container real de produção, com todos os profiles de entrada (`internal`, `internal-7060`, `internal-5062`) permanecendo `RUNNING` durante a troca. O dialplan foi atualizado para acionar o novo módulo com a mesma URL de destino (`ws://zenith-api-1:8000/audio-stream`).

**Redução de dependência externa:** o processo de build deixou de depender do repositório de pacotes da SignalWire estar sempre disponível — os `.deb` necessários (`libfreeswitch1`, `libfreeswitch-dev` e dependências transitivas) foram baixados uma única vez e vendorizados em `freeswitch/vendor/debs/` (fora do git). O build de produção foi validado usando exclusivamente esses `.deb` locais, sem tocar o repositório SignalWire.

**Lacuna remanescente:** a compatibilidade do payload binário entregue por `mod_audio_stream` com `src/audio/ingestor.py::_split_stereo_frame` é uma premissa fundamentada em análise do código-fonte do módulo (mesma convenção de PCM intercalado por canal), mas **não foi validada com uma chamada real** nesta sessão, porque o ambiente de produção não tem o serviço `zenith-api-1`/FastAPI deployado. Este é o único ponto em aberto da feature.

## Preservadas

- 🟢 Topologia B2BUA com Registration Forwarding (`_reversa_sdd/telephony/design.md#1`) — inalterada.
- 🟢 Separação entre profiles de entrada (`internal`/`internal-7060`/`internal-5062`) e profile `upstream` — confirmado que a troca de módulo de áudio não afetou nenhum deles.
- 🟢 `import_extensions.py` e a geração de gateways upstream — sem nenhuma alteração.
- 🟢 R07 (`domain.md`) — porta SIP padrão 5060 — inalterada por esta feature.

## Modificadas

- 🟡 Referência de arquitetura "FreeSWITCH captura áudio via `mod_audio_fork`" (`_reversa_sdd/architecture.md`, `_reversa_sdd/telephony/design.md`) — atualizada para `mod_audio_stream`. Confidência 🟡 (não 🟢) porque o mecanismo está carregado e configurado, mas o comportamento observável ponta a ponta (chamada real → transcrição) ainda não foi verificado nesta sessão.
- 🟡 GAP-11 e GAP-AUDIO-01 — marcados resolvidos com ressalva explícita de validação pendente, não confidência plena.
