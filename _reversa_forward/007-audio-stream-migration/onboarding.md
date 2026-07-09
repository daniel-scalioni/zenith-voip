# Onboarding: Migração de mod_audio_fork para mod_audio_stream

> Identificador: `007-audio-stream-migration`
> Data: `2026-07-08`

## Passo a passo para testar pela primeira vez

1. **Vendorizar os `.deb` do FreeSWITCH** (evita depender do repositório SignalWire no futuro):
   ```bash
   # No host de produção, com o token válido em freeswitch/signalwire_token.txt:
   mkdir -p ~/zenith-voip/freeswitch/vendor/debs
   # baixar libfreeswitch1, libfreeswitch-dev e dependências diretas via apt-get download
   # guardar em freeswitch/vendor/debs/ (fora do git — adicionar ao .gitignore)
   ```

2. **Build da nova imagem** (local ou no host):
   ```bash
   cd freeswitch
   DOCKER_BUILDKIT=1 docker build --secret id=signalwire_token,src=./signalwire_token.txt -t zenith-freeswitch:audiostream .
   ```

3. **Atualizar `docker-compose.app.yml`** para apontar para a nova imagem (ou manter o build customizado, restaurando o bloco `build:` comentado desde `004-bootstrap-freeswitch`).

4. **Restart do container `freeswitch`** em produção (10.10.10.11), fora de horário de uso ou com aviso prévio:
   ```bash
   ssh administrator@10.10.10.11 "cd ~/zenith-voip && docker compose -f docker-compose.infra.yml -f docker-compose.app.yml up -d freeswitch"
   ```

5. **Confirmar módulo carregado:**
   ```bash
   ssh administrator@10.10.10.11 "docker exec freeswitch fs_cli -x 'module_exists mod_audio_stream'"
   ```
   Esperado: `true`.

6. **Confirmar que os profiles de entrada continuam ativos** (sem regressão das features `005`/`006`):
   ```bash
   ssh administrator@10.10.10.11 "docker exec freeswitch fs_cli -x 'sofia status'"
   ```

7. **Teste real com uma chamada ativa** (ramal 1001 ou outro registrado):
   - Originar/receber uma chamada que passe pela extensão `zenith_audio_fork` do dialplan.
   - Verificar nos logs de `src/audio/ingestor.py` (ou no Redis Streams, evento `audio_chunk`) se os chunks de tx/rx chegam corretamente.
   - Se o payload vier incompatível com `_split_stereo_frame`, ajustar `src/audio/ingestor.py` num commit dedicado (não deve ser necessário, segundo a investigação, mas é o ponto de maior incerteza da feature).

## Critério de sucesso do onboarding

- `mod_audio_stream` carrega na imagem de produção.
- Uma chamada real gera eventos `audio_chunk` com tx/rx corretamente separados, iguais ao comportamento documentado quando `mod_audio_fork` era o mecanismo (mesmo que nunca tenha rodado em produção, dado o GAP-11).
- Nenhum profile de entrada (`internal`, `internal-7060`, `internal-5062`) fica indisponível durante o processo.
