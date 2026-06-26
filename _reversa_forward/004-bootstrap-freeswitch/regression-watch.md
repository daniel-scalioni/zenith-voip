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

<!-- Preenchido pelo agente reverso (/reversa) na próxima execução completa. -->

## Arquivadas

<!-- Itens descontinuados por mudança de escopo ou superados por nova arquitetura entram aqui, sem perder o ID. -->
