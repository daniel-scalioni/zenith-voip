# Onboarding: Piper TTS como Processo Local

> Identificador: `008-piper-tts-standalone`
> Data: `2026-07-09`

## Passo a passo para testar pela primeira vez

1. **Instalar a dependência atualizada:**
   ```bash
   pip install -r requirements.txt  # agora com piper-tts==1.4.2
   ```

2. **Baixar o modelo de voz pt_BR:**
   ```bash
   mkdir -p audio/voices
   python3 -m piper.download_voices pt_BR-faber-medium --download-dir audio/voices
   ```

3. **Testar a síntese diretamente:**
   ```python
   import asyncio
   from src.services.tts_fallback import TTSWithFallback

   async def main():
       tts = TTSWithFallback()
       audio = await tts.synthesize("Aguarde um momento, por favor.")
       with open("/tmp/teste.wav", "wb") as f:
           f.write(audio)
       print(f"{len(audio)} bytes gerados")

   asyncio.run(main())
   ```
   Esperado: arquivo `/tmp/teste.wav` reproduzível, não vazio.

4. **Confirmar que o `docker-compose.app.yml` não referencia mais o serviço quebrado:**
   ```bash
   docker compose -f docker-compose.infra.yml -f docker-compose.app.yml config --services | grep piper
   ```
   Esperado: nenhuma saída (serviço `piper-tts` removido).

## Critério de sucesso do onboarding

- Síntese de voz retorna áudio válido sem depender de nenhum serviço HTTP externo.
- `docker compose up` não tenta mais puxar a imagem `rhasspy/piper-tts:2023.11.14`.
