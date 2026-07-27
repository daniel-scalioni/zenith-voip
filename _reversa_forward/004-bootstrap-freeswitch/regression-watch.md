# Regression Watch: Bootstrap FreeSWITCH (container saudável)

> Identificador: `004-bootstrap-freeswitch`
> Data: `2026-06-24`

## Itens de verificação

| ID | Origem | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|--------|-----------------------------|----------------------|--------------------|
| W001 | `freeswitch/conf/freeswitch.xml`, `vars.xml` | Container `freeswitch` deve subir e permanecer estável (sem `Restarting`) com a config raiz vanilla criada nesta feature. | presença | `docker compose ps freeswitch` mostra `Restarting` ou container sai (`Exited`). |
| W002 | `freeswitch/conf/autoload_configs/sofia.conf.xml` | `mod_sofia` deve carregar `sip_profiles/internal.xml` via include — sem este arquivo, nenhum profile SIP fica ativo. | presença | `sofia status` (via ESL/fs_cli) não lista o profile `internal`. |
| W003 | `freeswitch/conf/autoload_configs/modules.conf.xml` | `mod_audio_fork` está deliberadamente ausente do load list (decisão D-06) — não é uma regressão até o ciclo de gravação renovar o token SignalWire e restaurar o build customizado. | ausência | Se uma re-extração futura tratar a ausência de `mod_audio_fork` como bug sem checar `roadmap.md#D-06`, está desinformada. |
| W004 | `docker-compose.app.yml` (serviço `freeswitch`) | `image: safarov/freeswitch:1.10.12` é temporário — o bloco `build:` customizado original está comentado, não removido, para restauração fácil quando o token SignalWire for renovado. | redação | Bloco `build:` removido/apagado em vez de restaurado, perdendo o registro de como reativar o build customizado. |
| W005 | `_reversa_sdd/gaps.md` (GAP-11) | Status deve refletir "confirmado bloqueado" (não mais "pendente validação") enquanto o token SignalWire não for renovado. | confiança | Re-extração futura rebaixando a confiança de volta a 🟡 sem nova evidência, ou mantendo "pendente" após o token já ter sido testado e confirmado inválido. |

## Histórico de re-extrações

### Re-extração 2026-07-27 (incremental, base 48da5b1 → 0658157)

| ID | Veredito | Observação |
|----|----------|------------|
| W001 | 🟢 verde | Container estável; ganhou healthcheck próprio (`module_exists mod_audio_stream`) e boot validado em produção |
| W002 | 🟢 verde | `sofia.conf.xml` segue incluindo os profiles; hoje são quatro (`internal`, `internal-5062`, `internal-7060`, `upstream`) |
| W003 | 🟡 amarelo | **Superado por design.** A ausência de `mod_audio_fork` deixou de ser espera por renovação de token: o módulo foi substituído por `mod_audio_stream` (ADR-010, feature `007-audio-stream-migration`). O cenário que o item pressupõe não existe mais — mantido no histórico justamente para impedir que a ausência seja diagnosticada como bug numa leitura futura |
| W004 | 🟡 amarelo | **Superado por design.** O `image:` temporário foi substituído pelo `build:` próprio (`freeswitch/Dockerfile`, `.deb` vendorizados), exatamente o desfecho que o item protegia. Objetivo cumprido; candidato a arquivamento |
| W005 | 🟢 verde | `gaps.md` GAP-11 está ✅ Resolvida com evidência de produção — a confiança subiu, nunca foi rebaixada |


<!-- Preenchido pelo agente reverso (/reversa) na próxima execução completa. -->

## Arquivadas

<!-- Itens descontinuados por mudança de escopo ou superados por nova arquitetura entram aqui, sem perder o ID. -->
