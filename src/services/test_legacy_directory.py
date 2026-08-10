import os

import pytest


def _provider(path):
    from src.services.legacy_directory import LegacyDirectoryError, LegacyDirectoryProvider

    return LegacyDirectoryProvider(path), LegacyDirectoryError


def test_legacy_provider_returns_equivalent_user_and_refreshes_on_mtime(tmp_path):
    # Arrange
    path = tmp_path / "extensions.xml"
    path.write_text('<user id="1001"><params><param name="password" value="first"/></params></user>', encoding="utf-8")
    provider, _ = _provider(path)

    # Act
    first = provider.lookup("1001")
    path.write_text('<user id="1001"><params><param name="password" value="second"/></params></user>', encoding="utf-8")
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    second = provider.lookup("1001")

    # Assert
    assert first.password == "first"
    assert second.password == "second"


def test_legacy_provider_rejects_dtd_and_external_entities(tmp_path):
    # Arrange
    path = tmp_path / "extensions.xml"
    path.write_text('<!DOCTYPE x [<!ENTITY leak SYSTEM "file:///etc/passwd">]><user id="1001">&leak;</user>', encoding="utf-8")
    provider, LegacyDirectoryError = _provider(path)

    # Act
    with pytest.raises(LegacyDirectoryError):
        provider.lookup("1001")

    # Assert
    assert "passwd" not in repr(provider)


def test_legacy_provider_treats_missing_file_as_empty_directory(tmp_path):
    # Arrange
    provider, _ = _provider(tmp_path / "missing.xml")

    # Act
    result = provider.lookup("1001")

    # Assert
    assert result is None


def test_legacy_provider_reports_membership_without_exposing_password(tmp_path):
    # Arrange
    path = tmp_path / "extensions.xml"
    path.write_text('<user id="1001"><params><param name="password" value="canary-secret"/></params></user>', encoding="utf-8")
    provider, _ = _provider(path)

    # Act
    result = provider.contains("internal", "1001")

    # Assert
    assert result is True
    assert "canary-secret" not in repr(provider)


def test_legacy_provider_rejects_duplicate_root_user_ids(tmp_path):
    # Arrange
    path = tmp_path / "extensions.xml"
    path.write_text(
        '<user id="1001"><params><param name="password" value="first"/></params></user>\n'
        '<user id="1001"><params><param name="password" value="duplicate"/></params></user>',
        encoding="utf-8",
    )
    provider, LegacyDirectoryError = _provider(path)

    # Act
    with pytest.raises(LegacyDirectoryError, match="legacy_directory_ambiguous_user"):
        provider.lookup("1001")


def test_legacy_provider_rejects_malformed_xml_even_after_wrapping(tmp_path):
    # Arrange
    path = tmp_path / "extensions.xml"
    path.write_text("not xml <at all", encoding="utf-8")
    provider, LegacyDirectoryError = _provider(path)

    # Act
    with pytest.raises(LegacyDirectoryError, match="legacy_directory_invalid"):
        provider.lookup("1001")


def test_legacy_provider_contains_rejects_profile_outside_allowlist(tmp_path):
    # Arrange
    path = tmp_path / "extensions.xml"
    path.write_text('<user id="1001"><params><param name="password" value="first"/></params></user>', encoding="utf-8")
    provider, _ = _provider(path)

    # Act
    result = provider.contains("external-pstn", "1001")

    # Assert
    assert result is False


def test_legacy_provider_accepts_freeswitch_include_with_multiple_root_users(tmp_path):
    # Arrange
    path = tmp_path / "extensions.xml"
    path.write_text(
        '<user id="1001"><params><param name="password" value="first"/></params></user>\n'
        '<user id="1002"><params><param name="password" value="second"/></params></user>',
        encoding="utf-8",
    )
    provider, _ = _provider(path)

    # Act
    first = provider.lookup("1001")
    second = provider.lookup("1002")

    # Assert
    assert first is not None
    assert second is not None
    assert first.password == "first"
    assert second.password == "second"
