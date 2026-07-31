import pytest
from unittest.mock import AsyncMock, patch

from src.extraction.regex_layer import RegexExtractor
from src.extraction.llm_layer import LocalLLMExtractor


# --- RegexExtractor ---


@pytest.mark.asyncio
async def test_regex_extract_returns_empty_on_empty_text():
    # Arrange
    extractor = RegexExtractor()

    # Act
    result = await extractor.extract("")

    # Assert
    assert result == {}


@pytest.mark.asyncio
async def test_regex_extract_returns_empty_on_no_match():
    # Arrange
    extractor = RegexExtractor()

    # Act
    result = await extractor.extract("just some plain text")

    # Assert
    assert result == {}


@pytest.mark.asyncio
async def test_regex_extract_cpf():
    # Arrange
    extractor = RegexExtractor()
    text = "meu cpf é 123.456.789-00"

    # Act
    result = await extractor.extract(text)

    # Assert
    assert "cpf" in result
    assert result["cpf"][0]["value"] == "123.456.789-00"
    assert result["cpf"][0]["sensitive"] is False


@pytest.mark.asyncio
async def test_regex_extract_phone():
    # Arrange
    extractor = RegexExtractor()
    text = "ligue para (11) 99876-5432"

    # Act
    result = await extractor.extract(text)

    # Assert
    assert "phone" in result
    assert "99876" in result["phone"][0]["value"]


@pytest.mark.asyncio
async def test_regex_extract_credit_card_is_sensitive():
    # Arrange
    extractor = RegexExtractor()
    text = "cartão 4111-1111-1111-1111"

    # Act
    result = await extractor.extract(text)

    # Assert
    assert "credit_card" in result
    assert result["credit_card"][0]["sensitive"] is True


@pytest.mark.asyncio
async def test_regex_extract_multiple_entities():
    # Arrange
    extractor = RegexExtractor()
    text = "cpf 123.456.789-00 e plada ABC-1234"

    # Act
    result = await extractor.extract(text)

    # Assert
    assert "cpf" in result or "plate" in result


@pytest.mark.asyncio
async def test_regex_has_suspicion_true_for_cpf():
    # Arrange
    extractor = RegexExtractor()

    # Act
    result = await extractor.has_suspicion("meu cpf é 123.456.789-00")

    # Assert
    assert result is True


@pytest.mark.asyncio
async def test_regex_has_suspicion_false_for_clean_text():
    # Arrange
    extractor = RegexExtractor()

    # Act
    result = await extractor.has_suspicion("nada sensível aqui")

    # Assert
    assert result is False


@pytest.mark.asyncio
async def test_regex_extract_rg():
    # Arrange
    extractor = RegexExtractor()
    text = "rg 12.345.678-9"

    # Act
    result = await extractor.extract(text)

    # Assert
    assert "rg" in result


@pytest.mark.asyncio
async def test_regex_extract_plate():
    # Arrange
    extractor = RegexExtractor()
    text = "placa ABC1D23"

    # Act
    result = await extractor.extract(text)

    # Assert
    assert "plate" in result


@pytest.mark.asyncio
async def test_regex_extract_cep():
    # Arrange
    extractor = RegexExtractor()
    text = "cep 01310-100"

    # Act
    result = await extractor.extract(text)

    # Assert
    assert "cep" in result


# --- LocalLLMExtractor ---


@pytest.mark.asyncio
async def test_llm_sanitize_returns_structured_response():
    # Arrange
    extractor = LocalLLMExtractor()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "response": '{"entity_type": "cpf", "value": "123.456.789-00", "corrected": true, "confidence": 0.95}'
    }
    extractor.client = AsyncMock()
    extractor.client.post = AsyncMock(return_value=mock_response)

    # Act
    result = await extractor.sanitize("123.456.789-00", "cpf", "context")

    # Assert
    assert isinstance(result, str)
    assert "cpf" in result
    extractor.client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_llm_sanitize_returns_error_on_network_failure():
    # Arrange
    extractor = LocalLLMExtractor()
    extractor.client = AsyncMock()
    extractor.client.post = AsyncMock(side_effect=Exception("connection refused"))

    # Act
    result = await extractor.sanitize("bad", "cpf")

    # Assert
    assert isinstance(result, dict)
    assert result["corrected"] is False
    assert result["confidence"] == 0.0
    assert "error" in result


@pytest.mark.asyncio
async def test_llm_sanitize_returns_error_on_http_error():
    # Arrange
    extractor = LocalLLMExtractor()
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = Exception("503 Server Error")
    extractor.client = AsyncMock()
    extractor.client.post = AsyncMock(return_value=mock_response)

    # Act
    result = await extractor.sanitize("data", "phone")

    # Assert
    assert isinstance(result, dict)
    assert result["corrected"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_llm_sanitize_returns_error_on_malformed_json_response():
    # Arrange
    extractor = LocalLLMExtractor()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"response": "not json at all"}
    extractor.client = AsyncMock()
    extractor.client.post = AsyncMock(return_value=mock_response)

    # Act
    result = await extractor.sanitize("data", "cpf")

    # Assert
    assert isinstance(result, str)
    assert result == "not json at all"


@pytest.mark.asyncio
async def test_llm_sanitize_returns_error_on_missing_response_key():
    # Arrange
    extractor = LocalLLMExtractor()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {}
    extractor.client = AsyncMock()
    extractor.client.post = AsyncMock(return_value=mock_response)

    # Act
    result = await extractor.sanitize("data", "cpf")

    # Assert
    assert isinstance(result, str)
    assert result == "{}"
