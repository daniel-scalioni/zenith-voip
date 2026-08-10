# Veredito de segurança — vazamento de credencial (T047)

> Gate: T047, auditoria de logs, erros, métricas, access logs e XML temporário
> Data do canário: 2026-08-07 14:58:43 UTC (`last_registered_at`/`last_unregistered_at` do tronco `55f84cde-38e8-446d-8113-831c8fba2959`)
> Data da auditoria/documento: 2026-08-08
> Ambiente: operacional `10.10.10.11` (`zenith-api-1`, `zenith-api-2`, `zenith-freeswitch`, `zenith-bunkerweb`, `zenith-loki`)

## Método

Reaproveitado o padrão de canário já validado em `onboarding.md §3.7` e usado nos gates T044/T046: nenhuma credencial real foi manuseada nesta auditoria.

1. Tronco descartável criado via `POST /trunks` real (não SQL direto) no tenant sintético já existente `Teste E2E T046 (sintetico, nao-cliente)` — `auth_username=canario-t047`, senha = string única gerada nesta sessão (`CANARIO-T047-<hex aleatório>`), `sip_profile=internal-7060`, `enabled=true`. JWT `tenant_admin` gerado dentro do próprio container `zenith-api-1`, sem expor `JWT_SECRET`.
2. Fluxo completo disparado com `spike/trunk_sip_register.py` contra `10.10.10.11:7060` (copiado temporariamente para o servidor e removido logo em seguida): senha errada → `403`; senha correta → `200`; `Expires: 0` → `200`. Isso exercitou, na ordem: FreeSWITCH (`internal-7060`), o callback `mod_xml_curl`/`freeswitch_directory`, os eventos ESL `sofia::register`/`sofia::unregister` consumidos por `trunk_state.py`/`esl_client.py`, e as métricas de telemetria.
3. Busca pela string do canário, somente leitura, nas superfícies dependentes de T028/T032/T038/T042:
   - `docker logs zenith-api-1` — **0 ocorrências**
   - `docker logs zenith-api-2` — **0 ocorrências**
   - `docker logs zenith-freeswitch` — **0 ocorrências** (resultado vazio por ausência de canal: o container tem apenas uma linha de startup em 2 semanas, o console do FreeSWITCH não é retido nesse stdout hoje — ver correção abaixo)
   - `docker logs zenith-bunkerweb` — **0 ocorrências**
   - `/var/log/freeswitch/freeswitch.xml.fsxml` (bind mount) — **0 ocorrências**
   - `/metrics` (Prometheus) de `zenith-api-1` e `zenith-api-2` — **0 ocorrências**
   - Nenhum XML temporário/debug novo encontrado em `freeswitch/conf` nem na raiz dos bind mounts após o teste (checagem inicial, ver correção abaixo)
   - `zenith-loki` — consultado via API (`/loki/api/v1/query_range` e `/loki/api/v1/labels`); **sem dados ingeridos** (nenhum label/série), ou seja, não é hoje um canal ativo de log desta stack — não representa risco de vazamento porque não recebe nada, mas também não serve como auditoria retida
   - `zenith-api-1` confirmado sem arquivo de log em disco (só `docker logs`/stdout); achado aplicável às demais imagens da mesma base

## Correção pós-revisão independente (advisor), duas rodadas

**Rodada 1 — corte de tempo vazio.** A primeira passada verificou XML temporário só no host (`find` em `/home/administrator/zenith-voip/freeswitch/conf` e na raiz), com corte de tempo `-newermt '2026-08-08 00:00:00'` — **posterior** ao canário real (14:58:43 de 07/08), um zero vazio por construção, e sem olhar dentro do próprio container `zenith-freeswitch`. Refeito com `find` dentro do container (não do bind mount), corte de tempo correto (`2026-08-07 14:58:00`–`15:05:00`), em toda a árvore (`/` é um único mount overlay, sem `/tmp` separado escapando do `-xdev`) e dedicado a `/tmp`: nenhum XML novo encontrado nessa checagem estática.

**Rodada 2 — o próprio diretório `/var/log/freeswitch` mostrava mtime alterado às 14:58:43.402 (2 ms do `last_registered_at` do canário), com o arquivo `freeswitch.xml.fsxml` em si intocado desde 06/08.** Isso só é possível se algo foi criado e removido/renomeado ali durante a checagem estática já ter passado. Investigado com uma captura de alta frequência (loop apertado, ~440 amostras/s, rodando dentro do próprio container para não ter atraso de rede) durante um REGISTER real do canário: capturado o nome `<uuid>.tmp.xml.fsxml` coexistindo com `freeswitch.xml.fsxml` em uma única amostra, confirmando o padrão escrever-em-temp-depois-renomear/descartar. Tentativas de capturar o **conteúdo** desse temporário (27 REGISTERs adicionais, incluindo uma segunda identidade de canário nunca vista antes, `canario-t047b`, para descartar cache de lookup) não reproduziram o arquivo — evidência de que ele não é disparado deterministicamente pelo REGISTER/lookup do diretório, e sim por algo mais raro/independente (plausivelmente tráfego real de produção concorrente no mesmo host, que tem centenas de ramais e 939 gateways upstream reais).

Como o destino final desse temporário é sempre `freeswitch.xml.fsxml` (mesmo nome, mesmo diretório) e esse arquivo é uma serialização da **árvore de configuração estática mesclada** (mesmo teor visto na prévia lida: comentários de `ip-watcher`, "Tenant Akom" — texto de arquivos em disco, não resposta dinâmica do XML Curl), e o `mtime` do arquivo final nunca mudou em nenhuma das 3 + 27 tentativas de REGISTER do canário, o grep já feito nesse arquivo (**0 ocorrências**, 761 KB) cobre também a classe de conteúdo do temporário. O canário só existe no Postgres e chega ao `mod_sofia` como resposta HTTP por requisição — nunca entra nessa árvore de configuração estática. Mecanismo caracterizado, não é vazamento; não abre watch item porque foi resolvido, não deixado em aberto.

**Correção do dial errado.** A nota original atribuía a segurança a `sofia.conf.xml log-level="0"` — esse parâmetro é o nível de trace do stack SIP interno do Sofia, não o que controla se `mod_xml_curl` loga o corpo da resposta do diretório. O dado real, descoberto durante a investigação acima: `docker logs zenith-freeswitch` está **praticamente vazio há 2 semanas** (uma única linha de startup) e o único arquivo em `/var/log/freeswitch/` é o cache `.fsxml` — ou seja, o log de console do FreeSWITCH **não é retido em lugar nenhum hoje neste host**. Isso torna o "0 ocorrências em `docker logs zenith-freeswitch`" um resultado vazio por ausência de canal, não uma prova de que o console está limpo. **Observação operacional, não corrigida agora:** se alguém no futuro subir o loglevel do console ou redirecionar o stdout para um arquivo retido, a resposta XML do diretório (com a credencial) passa a ser potencialmente gravável nesse canal — mitigação é nunca fazer isso por tempo prolongado em produção; não abre watch item porque é comportamento padrão do FreeSWITCH, não um defeito desta feature, mas fica registrado aqui para quem depurar este host no futuro.

## Achado de investigação (não é vazamento)

`/var/log/bunkerweb/{access,error,modsec_audit}.log` e `/var/log/nginx/{access,error}.log` são **symlinks para `/proc/1/fd/1`/`/proc/1/fd/2`** dentro do container — tudo vai para stdout/stderr, já coberto por `docker logs zenith-bunkerweb`. Ler esses caminhos como arquivo comum (`tail`/`grep` direto) trava esperando EOF, porque um fd de pipe não termina; **não é volume de dado grande, é um fd especial**. Não afeta o veredito porque a superfície real (stdout/stderr) já foi coberta por outro comando.

## Limpeza

Os dois troncos canário (`canario-t047` e `canario-t047b`) desabilitados via `UPDATE` direto (mesma exceção documentada e registrada como W006 — `PATCH /trunks/{id}` ainda não existe no router); scripts de spike e diretórios de captura temporários no servidor removidos após o uso; nenhum resíduo do canário em disco.

## Fora de escopo, registrado para não ser confundido com achado deste gate

`tmp_pcap/zenith_call_test.pcap` (41 MB) e `.deploy-backups/feature-011-*` no checkout do servidor são resíduos da feature-011, anteriores a esta rodada — não tocados, não fazem parte do fluxo de credencial de tronco auditado aqui.

## Veredito

🟢 **Sem vazamento de credencial** nas superfícies de log, erro, métrica, access log e XML temporário dependentes de T028/T032/T038/T042, com evidência real de dois REGISTERs SIP completos (negado, aceito, removido) no ambiente operacional, incluindo a caracterização direta do mecanismo de arquivo temporário do FreeSWITCH (não é vazamento — árvore estática, nunca contém o canário). O veredito é específico ao canal de log retido hoje neste host (`docker logs`/stdout, arquivo `.fsxml`, métricas, Loki inativo); não cobre uma eventual sessão futura com o console do FreeSWITCH redirecionado para um arquivo retido ou em loglevel elevado (ver observação operacional acima). Gate fechado.
