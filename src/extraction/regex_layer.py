import re
from typing import Any


class RegexExtractor:
    PATTERNS = {
        "cpf": re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"),
        "rg": re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}-?[0-9xX]\b"),
        "phone": re.compile(r"\b\(?\d{2}\)?\s?\d{4,5}-?\d{4}\b"),
        "plate": re.compile(r"\b[A-Za-z]{3}[-\s]?\d[A-Za-z0-9]\d{2}\b"),
        "cep": re.compile(r"\b\d{5}-?\d{3}\b"),
        "credit_card": re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
    }

    SENSITIVE_PATTERNS = ["credit_card"]

    async def extract(self, text: str) -> dict[str, list[dict[str, Any]]]:
        results: dict[str, list[dict[str, Any]]] = {}
        for label, pattern in self.PATTERNS.items():
            matches = []
            for match in pattern.finditer(text):
                matches.append({
                    "value": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                    "sensitive": label in self.SENSITIVE_PATTERNS,
                })
            if matches:
                results[label] = matches
        return results

    async def has_suspicion(self, text: str) -> bool:
        for label in ("cpf", "rg", "plate"):
            if self.PATTERNS[label].search(text):
                return True
        return False
