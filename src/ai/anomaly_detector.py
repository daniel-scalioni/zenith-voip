import re
from src.api.websockets import agent_assist_ws


class AnomalyDetector:
    FURY_KEYWORDS = [
        "gritar", "berrar", "calar", "calado", "quieto", "escuta aqui",
        "vc sabe", "voce sabe", "presta atencao", "presta atenção",
        "vou processar", "reclamação", "reclamar", "advogado",
        "chefe", "gerente", "quero falar", "supervisor",
        "policia", "polícia", "chamar a policia", "boletim de ocorrencia",
        "ameaça", "ameacar", "processo", "justiça", "justica",
    ]

    STRESS_PATTERNS = [
        re.compile(r"[A-ZÀ-Ú]{3,}"),  # ALL CAPS segments
        re.compile(r"!{2,}"),          # multiple exclamation marks
        re.compile(r"\b(\w+)\s+\1\b", re.IGNORECASE),  # repeated words
    ]

    def __init__(self):
        self.anomaly_threshold = 3

    async def analyze(self, call_id: str, text: str, speaker: str) -> dict:
        fury_score = self._score_fury(text)
        stress_score = self._score_stress(text)
        total_score = fury_score + stress_score

        if total_score >= self.anomaly_threshold:
            await agent_assist_ws.handle_alert(
                call_id,
                "fury_detected",
                f"Possível anomalia detectada no speaker {speaker} (score: {total_score})",
                severity="danger" if total_score >= 5 else "warning",
            )

        return {
            "fury_score": fury_score,
            "stress_score": stress_score,
            "total_score": total_score,
            "anomaly_detected": total_score >= self.anomaly_threshold,
        }

    def _score_fury(self, text: str) -> int:
        text_lower = text.lower()
        score = 0
        for keyword in self.FURY_KEYWORDS:
            if keyword in text_lower:
                score += 1
        return score

    def _score_stress(self, text: str) -> int:
        score = 0
        for pattern in self.STRESS_PATTERNS:
            matches = pattern.findall(text)
            score += len(matches)
        return score


anomaly_detector = AnomalyDetector()
