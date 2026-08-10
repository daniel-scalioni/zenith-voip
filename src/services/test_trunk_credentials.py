import pytest
from cryptography.fernet import Fernet


def _credentials():
    from src.services.trunk_credentials import (
        CredentialConfigurationError,
        CredentialTokenError,
        TrunkCredentialCipher,
    )

    return TrunkCredentialCipher, CredentialConfigurationError, CredentialTokenError


def test_cipher_encrypts_without_embedding_plaintext_and_decrypts():
    # Arrange
    TrunkCredentialCipher, _, _ = _credentials()
    secret = "canary-trunk-password"
    cipher = TrunkCredentialCipher([Fernet.generate_key().decode()])

    # Act
    token = cipher.encrypt(secret)
    restored = cipher.decrypt(token)

    # Assert
    assert secret not in token
    assert restored == secret


def test_cipher_rotates_old_token_to_primary_key():
    # Arrange
    TrunkCredentialCipher, _, _ = _credentials()
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    old_token = TrunkCredentialCipher([old_key]).encrypt("rotation-secret")

    # Act
    rotated = TrunkCredentialCipher([new_key, old_key]).rotate(old_token)

    # Assert
    assert TrunkCredentialCipher([new_key]).decrypt(rotated) == "rotation-secret"
    assert rotated != old_token


def test_cipher_rejects_missing_keys_without_leaking_secret():
    # Arrange
    TrunkCredentialCipher, ConfigurationError, _ = _credentials()

    # Act
    with pytest.raises(ConfigurationError) as error:
        TrunkCredentialCipher([])

    # Assert
    assert "password" not in str(error.value).lower()


def test_cipher_rejects_empty_plaintext_without_persisting():
    # Arrange
    TrunkCredentialCipher, _, TokenError = _credentials()
    cipher = TrunkCredentialCipher([Fernet.generate_key().decode()])

    # Act
    with pytest.raises(TokenError, match="credential_plaintext_invalid"):
        cipher.encrypt("")


def test_cipher_rejects_corrupted_token_on_rotate():
    # Arrange
    TrunkCredentialCipher, _, TokenError = _credentials()
    cipher = TrunkCredentialCipher([Fernet.generate_key().decode()])
    canary = "canary-corrupted-token"

    # Act
    with pytest.raises(TokenError) as error:
        cipher.rotate(canary)

    # Assert
    assert canary not in str(error.value)


def test_cipher_rejects_corrupted_token_with_sanitized_error():
    # Arrange
    TrunkCredentialCipher, _, TokenError = _credentials()
    cipher = TrunkCredentialCipher([Fernet.generate_key().decode()])
    canary = "canary-corrupted-token"

    # Act
    with pytest.raises(TokenError) as error:
        cipher.decrypt(canary)

    # Assert
    assert canary not in str(error.value)
