# Detecção de Anomalias, Design

**Interface:** `analyze(call_id, text, speaker) → dict {score, severity}`
**Algoritmo:** 13 keywords PT-BR + regex stress patterns → fury_score + stress_score → severity (warning >= 3, danger >= 5)
**Origem:** `src/ai/anomaly_detector.py:6-34` 🟢
