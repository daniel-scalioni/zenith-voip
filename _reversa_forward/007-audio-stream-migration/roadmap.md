# Roadmap: Migração de mod_audio_fork para mod_audio_stream

> Identificador: `007-audio-stream-migration`
> Data: `2026-07-08`
> Requirements: `_reversa_forward/007-audio-stream-migration/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

O FreeSWITCH captura áudio hoje via `mod_audio_fork`, bloqueado desde o GAP-11 (repositório de origem descontinuado). A abordagem é trocar por `mod_audio_stream` (`amigniter/mod_audio_stream`, MIT), já validado nesta sessão como buildável e carregável contra o FreeSWITCH 1.11 real do projeto. A troca é feita em três frentes: (1) `freeswitch/Dockerfile` compila o novo módulo e copia as libs de runtime que faltam na imagem base (`libevent-*`); (2) `freeswitch/conf/autoload_configs/modules.conf.xml` e `freeswitch/conf/dialplan/default.xml` trocam a invocação de `uuid_audio_fork` por `uuid_audio_stream`, mantendo a mesma URL de destino e mix-type `stereo`; (3) `src/audio/ingestor.py` é validado (não reescrito, dado que o formato de payload é a mesma convenção PCM intercalado) contra uma chamada real. Em paralelo, o processo de build deixa de depender do repositório SignalWire estar sempre disponível: os pacotes `.deb` necessários são vendorizados localmente (fora do git), como decidido em `/reversa-clarify`.

## 2. Princípios aplicados

`.reversa/principles.md` está vazio neste projeto — nenhum princípio formal registrado. A feature segue as convenções do `CLAUDE.md` (sem segredo hardcoded, sem `except Exception` genérico, comentários só para o "porquê").

| Princípio | Como a feature se relaciona | Status |
|-----------|------------------------------|--------|
| n/a — `principles.md` vazio | — | n/a |

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|----------------|---------------------------|-------------|
| D-01 | Usar `mod_audio_stream` (amigniter, MIT) como substituto direto de `mod_audio_fork` | Validado nesta sessão: build funciona, módulo carrega (`module_exists=true`), API (`uuid_audio_stream ... start <ws> <mix-type> <rate>`) quase idêntica à de `mod_audio_fork` | `drachtio/drachtio-freeswitch-modules` (repo não existe mais); `drachtio/docker-drachtio-freeswitch-mrf` (imagem arquivada, sem manutenção) | 🟢 |
| D-02 | Manter mix-type `stereo` e sampling rate `8k`, só trocando o comando de `uuid_audio_fork` para `uuid_audio_stream` no dialplan | Minimiza superfície de mudança; RF-02 do requirements exige compatibilidade com `_split_stereo_frame` existente | Migrar para 16k (mais qualidade, mas fora de escopo — decidido em `/reversa-clarify`) | 🟢 |
| D-03 | Copiar `libevent-2.1`, `libevent_core`, `libevent_pthreads`, `libevent_openssl`, `libevent_extra` (`.so.7*`) do stage `builder` para a imagem final, em vez de instalar via apt na imagem final | A imagem final (`safarov/freeswitch:1.10.12`) não tem gerenciador de pacotes (sem apt/apk) — validado nesta sessão; `libspeexdsp`/`libssl`/`libz` já existem na base, só `libevent` faltava | Trocar a imagem base final por uma com apt (rejeitado: mudaria toda a base já validada em `004-bootstrap-freeswitch`) | 🟢 |
| D-04 | Vendorizar localmente (fora do git) os `.deb` de `libfreeswitch1`/`libfreeswitch-dev` e dependências diretas, baixados uma única vez do repositório SignalWire com o token válido | Resolve RF-05 (não depender do repositório SignalWire estar sempre no ar) sem exigir criar/manter um registry Docker próprio | Publicar imagem própria em registry controlado (descartado nesta feature por exigir infraestrutura nova — ver `requirements.md#Esclarecimentos`) | 🟡 |
| D-05 | Não reescrever `src/audio/ingestor.py` preventivamente — validar com teste real de chamada antes de qualquer mudança de código | Investigação do código-fonte de `mod_audio_stream` (parâmetro `channels`, resampler por canal) indica mesma convenção de PCM intercalado usada por `mod_audio_fork`; mudar código sem confirmar geraria risco de regressão desnecessária | Reescrever `_split_stereo_frame` preventivamente (descartado — sem evidência de que é necessário) | 🟡 |

## 4. Premissas

| Premissa | Origem (`requirements.md` seção) | Risco se errada |
|----------|-----------------------------------|------------------|
| O payload binário de `mod_audio_stream` em modo `stereo` é PCM16 intercalado por canal, igual ao que `mod_audio_fork` já entregava | `requirements.md#9 Esclarecimentos` (resolução autônoma) | Se o formato for diferente (ex: dois frames separados por canal), `_split_stereo_frame` vai processar dados errados silenciosamente — mitigado por T-de-validação dedicada no `actions.md` com teste real antes de fechar a feature |

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-------------------|--------|
| Build da imagem FreeSWITCH | `freeswitch/Dockerfile` | regra-alterada | Troca o estágio de compilação de `mod_audio_fork` (repo morto) para `mod_audio_stream` (repo ativo), com libs de runtime copiadas explicitamente |
| Carregamento de módulos | `freeswitch/conf/autoload_configs/modules.conf.xml` | regra-alterada | `mod_audio_stream` entra na lista de load; remove a tentativa comentada de `mod_audio_fork` |
| Dialplan de captura | `freeswitch/conf/dialplan/default.xml` (extensão `zenith_audio_fork`) | contrato-alterado | `uuid_audio_fork ... stereo 8000 ...` vira `uuid_audio_stream ... stereo 8k ...`, mesma URL destino |
| Ingestão de áudio | `src/audio/ingestor.py::AudioIngestor` | sem mudança de código prevista (validação apenas) | Mantém `_split_stereo_frame`; validado com chamada real antes de fechar RF-04 |
| Gaps de arquitetura | `_reversa_sdd/architecture.md#TD` (via GAP-11/GAP-AUDIO-01) | regra-alterada | GAP-11 e GAP-AUDIO-01 passam de bloqueados para resolvidos |

## 6. Delta no modelo de dados

- Resumo das mudanças: nenhuma mudança em schema de banco de dados. O payload de áudio trafegado via WebSocket não é persistido em formato diferente — `src/services/calls.py`/upload de gravação não mudam.
- Detalhe completo em: `_reversa_forward/007-audio-stream-migration/data-delta.md`

## 7. Delta de contratos externos

| Contrato | Tipo | Arquivo de detalhe |
|----------|------|--------------------|
| WebSocket de streaming de áudio (`ws://zenith-api-1:8000/audio-stream`) | WebSocket (interno FreeSWITCH → FastAPI) | `_reversa_forward/007-audio-stream-migration/interfaces/audio-stream-websocket.md` |

## 8. Plano de migração

1. Vendorizar localmente os `.deb` necessários (`libfreeswitch1`, `libfreeswitch-dev`, dependências diretas) baixados com o token SignalWire válido, guardados fora do git.
2. Atualizar `freeswitch/Dockerfile`: builder compila `mod_audio_stream` a partir dos `.deb` vendorizados (ou do repositório, com fallback documentado); stage final copia `mod_audio_stream.so` + libs `libevent-*`.
3. Atualizar `freeswitch/conf/autoload_configs/modules.conf.xml` para carregar `mod_audio_stream`.
4. Atualizar `freeswitch/conf/dialplan/default.xml`: trocar `uuid_audio_fork` por `uuid_audio_stream` na extensão `zenith_audio_fork` (mesma URL, `stereo`, `8k`).
5. Rebuildar a imagem em produção (10.10.10.11) e reiniciar apenas o container `freeswitch` (fora de horário de uso, ou com aviso prévio — mesma cautela de `006-registro-porta-vitalpbx`).
6. Validar com uma chamada real: ramal registrado, chamada ativa, confirmar que `src/audio/ingestor.py` recebe e processa os chunks corretamente (RF-04).
7. Atualizar `_reversa_sdd/gaps.md#GAP-11` e `_reversa_sdd/telephony/design.md#GAP-AUDIO-01` para ✅ Resolvida.

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|-----------------|-----------|
| Payload de `mod_audio_stream` não ser byte-compatível com `_split_stereo_frame` (premissa D-05) | alto | baixo | Teste real de chamada antes de fechar a feature; se incompatível, ajustar `ingestor.py` num commit dedicado, sem afetar o resto da migração |
| Rebuild da imagem em produção derrubar chamadas ativas | médio | baixo | Rebuildar fora de horário de uso ou com aviso prévio ao usuário, mesmo padrão já usado nas features `005`/`006` |
| `.deb` vendorizados ficarem desatualizados quando o FreeSWITCH for atualizado de versão no futuro | baixo | médio | Documentar em `onboarding.md` o processo de atualização manual dos `.deb` vendorizados |
| Licença da edição community de `mod_audio_stream` mudar termos no futuro | baixo | baixo | MIT é permissiva e a versão vendorizada/commitada (se aplicável) preserva os termos vigentes no momento da adoção |

## 10. Critério de pronto

- [X] Todas as ações do `actions.md` marcadas `[X]` — exceto T009/T010, marcadas `bloqueado` (ver abaixo)
- [X] `regression-watch.md` gerado
- [X] `mod_audio_stream` carrega com sucesso na imagem de produção (`module_exists` = true) — confirmado em 2026-07-09 após recriar o container `freeswitch`
- [ ] Chamada real de teste confirma payload compatível com `_split_stereo_frame` (RF-04) — **não executado nesta sessão**: sem serviço `zenith-api-1`/FastAPI deployado no ambiente e sem ramal registrado no momento. Pendência registrada em `regression-watch.md#W004` e `gaps.md#GAP-11`
- [X] `GAP-11` e `GAP-AUDIO-01` marcados como resolvidos em `_reversa_sdd/` (com a ressalva acima sobre validação end-to-end pendente)
- [X] Processo de rebuild documentado sem dependência obrigatória do repositório SignalWire estar disponível — `.deb` vendorizados em `freeswitch/vendor/debs/`, build de produção testado e funcional usando apenas os `.deb` locais
- [ ] Re-extração reversa executada e sem regressão vermelha (recomendado, não obrigatório) — pendente, decisão do usuário

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-07-08 | Versão inicial gerada por `/reversa-plan` | reversa |
