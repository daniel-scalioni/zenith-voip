# Detecção de Anomalias, Design

**Interface:** `analyze(call_id, text, speaker) → dict {score, severity}`
**Algoritmo:** 27 keywords PT-BR + regex stress patterns → fury_score + stress_score → severity (warning >= 3, danger >= 5)
**Validação de entrada:** `text` deve ser `str`; caso contrário levanta `TypeError` — `src/ai/anomaly_detector.py:25-26` 🟢
**Origem:** `src/ai/anomaly_detector.py:6-34` 🟢
