# Data Delta: Piper TTS como Processo Local

> Identificador: `008-piper-tts-standalone`
> Data: `2026-07-09`

## 1. Resumo

Nenhuma alteração em banco de dados de aplicação. O único artefato novo é o modelo de voz Piper (`.onnx` + `.onnx.json`), tratado como artefato de infraestrutura vendorizado, não como dado de negócio.

## 2. Estruturas afetadas

| Estrutura | Antes | Depois |
|-----------|-------|--------|
| `requirements.txt` | `piper-tts==1.2.0` (depende de `piper-phonemize`, indisponível) | `piper-tts==1.4.2` (PyPI, sem dependências nativas problemáticas) |
| `audio/voices/` (novo, gitignored) | Não existe | Modelo de voz `pt_BR-<voz>-medium.onnx` + `.onnx.json` |
| `docker-compose.app.yml` (serviço `piper-tts`) | `image: rhasspy/piper-tts:2023.11.14` (inexistente) | Serviço removido |
| `src/config.py::PIPER_TTS_URL` | `http://piper-tts:5000` | Removido/deprecated |

## 3. Migração necessária

Nenhuma migração de banco de dados. Passo operacional único: baixar o modelo de voz uma vez por ambiente (`python3 -m piper.download_voices`).
