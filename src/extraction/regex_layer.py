import re
from typing import Any


def _is_valid_cpf(raw_value: str) -> bool:
    """Valida o dígito verificador do CPF (módulo 11). Sem a lib python-brasilcpf
    (removida no GAP-18), o regex sozinho aceitava qualquer sequência de 11 dígitos."""
    digits = re.sub(r"\D", "", raw_value)
    if len(digits) != 11 or digits == digits[0] * 11:
        return False

    def check_digit(base: str) -> int:
        total = sum(int(d) * w for d, w in zip(base, range(len(base) + 1, 1, -1)))
        remainder = total % 11
        return 0 if remainder < 2 else 11 - remainder

    first = check_digit(digits[:9])
    second = check_digit(digits[:9] + str(first))
    return digits[9] == str(first) and digits[10] == str(second)


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
    VALIDATORS = {"cpf": _is_valid_cpf}

    async def extract(self, text: str) -> dict[str, list[dict[str, Any]]]:
        results: dict[str, list[dict[str, Any]]] = {}
        for label, pattern in self.PATTERNS.items():
            validator = self.VALIDATORS.get(label)
            matches = []
            for match in pattern.finditer(text):
                if validator and not validator(match.group()):
                    continue
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
        for label in ("cpf", "rg", "plate", "credit_card"):
            validator = self.VALIDATORS.get(label)
            for match in self.PATTERNS[label].finditer(text):
                if not validator or validator(match.group()):
                    return True
        return False
