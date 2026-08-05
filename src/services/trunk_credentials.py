"""Cifra de credenciais SIP sem expor material sensível em erros."""

from cryptography.fernet import Fernet, InvalidToken, MultiFernet


class CredentialConfigurationError(ValueError):
    pass


class CredentialTokenError(ValueError):
    pass


class TrunkCredentialCipher:
    def __init__(self, keys: list[str] | tuple[str, ...]):
        try:
            normalized = [key.strip().encode() for key in keys if key and key.strip()]
            if not normalized:
                raise ValueError
            self._cipher = MultiFernet([Fernet(key) for key in normalized])
        except (TypeError, ValueError) as error:
            raise CredentialConfigurationError("credential_keys_invalid") from error

    def encrypt(self, plaintext: str) -> str:
        if not isinstance(plaintext, str) or not plaintext:
            raise CredentialTokenError("credential_plaintext_invalid")
        return self._cipher.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._cipher.decrypt(token.encode()).decode()
        except (AttributeError, InvalidToken, UnicodeDecodeError) as error:
            raise CredentialTokenError("credential_token_invalid") from error

    def rotate(self, token: str) -> str:
        try:
            return self._cipher.rotate(token.encode()).decode()
        except (AttributeError, InvalidToken) as error:
            raise CredentialTokenError("credential_token_invalid") from error
