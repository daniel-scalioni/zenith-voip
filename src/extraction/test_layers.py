import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from src.extraction.regex_layer import RegexExtractor
from src.extraction.llm_layer import LocalLLMExtractor


# --- RegexExtractor ---


@pytest.mark.asyncio
async def test_regex_extract_returns_empty_dict_for_empty_text():
    # Arrange
    extractor = RegexExtractor()

    # Act
    result = await extractor.extract("")

    # Assert
    assert result == {}


@pytest.mark.asyncio
async def test_regex_extract_raises_type_error_for_non_string_text():
    # Arrange
    extractor = RegexExtractor()

    # Act / Assert
    with pytest.raises(TypeError):
        await extractor.extract(None)


@pytest.mark.asyncio
async def test_regex_extract_returns_empty_dict_when_no_pattern_matches():
    # Arrange
    extractor = RegexExtractor()

    # Act
    result = await extractor.extract("just some plain text")

    # Assert
    assert result == {}


@pytest.mark.asyncio
async def test_regex_extract_cpf_matches_and_is_not_sensitive():
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
async def test_regex_extract_phone_matches():
    # Arrange
    extractor = RegexExtractor()
    text = "ligue para (11) 99876-5432"

    # Act
    result = await extractor.extract(text)

    # Assert
    assert "phone" in result
    assert "99876" in result["phone"][0]["value"]


@pytest.mark.asyncio
async def test_regex_extract_rg_matches():
    # Arrange
    extractor = RegexExtractor()
    text = "rg 12.345.678-9"

    # Act
    result = await extractor.extract(text)

    # Assert
    assert "rg" in result
    assert result["rg"][0]["value"] == "12.345.678-9"


@pytest.mark.asyncio
async def test_regex_extract_plate_matches():
    # Arrange
    extractor = RegexExtractor()
    text = "placa ABC1D23"

    # Act
    result = await extractor.extract(text)

    # Assert
    assert "plate" in result
    assert result["plate"][0]["value"] == "ABC1D23"


@pytest.mark.asyncio
async def test_regex_extract_cep_matches():
    # Arrange
    extractor = RegexExtractor()
    text = "cep 01310-100"

    # Act
    result = await extractor.extract(text)

    # Assert
    assert "cep" in result
    assert result["cep"][0]["value"] == "01310-100"


@pytest.mark.asyncio
async def test_regex_extract_credit_card_matches_and_is_sensitive():
    # Arrange
    extractor = RegexExtractor()
    text = "cartão 4111-1111-1111-1111"

    # Act
    result = await extractor.extract(text)

    # Assert
    assert "credit_card" in result
    assert result["credit_card"][0]["sensitive"] is True


@pytest.mark.asyncio
async def test_regex_extract_multiple_entities_in_same_text():
    # Arrange
    extractor = RegexExtractor()
    text = "cpf 123.456.789-00 e placa ABC1D23"

    # Act
    result = await extractor.extract(text)

    # Assert
    assert "cpf" in result
    assert "plate" in result


@pytest.mark.asyncio
async def test_regex_has_suspicion_true_for_cpf():
    # Arrange
    extractor = RegexExtractor()

    # Act
    result = await extractor.has_suspicion("meu cpf é 123.456.789-00")

    # Assert
    assert result is True


@pytest.mark.asyncio
async def test_regex_has_suspicion_true_for_rg():
    # Arrange
    extractor = RegexExtractor()

    # Act
    result = await extractor.has_suspicion("meu rg é 12.345.678-9")

    # Assert
    assert result is True


@pytest.mark.asyncio
async def test_regex_has_suspicion_true_for_plate():
    # Arrange
    extractor = RegexExtractor()

    # Act
    result = await extractor.has_suspicion("a placa é ABC1D23")

    # Assert
    assert result is True


@pytest.mark.asyncio
async def test_regex_has_suspicion_true_for_credit_card():
    # Arrange: design.md declara que cartão também deve disparar suspeita
    # (design.md linha 28: "CPF, RG, placa ou cartão encontrados")
    extractor = RegexExtractor()

    # Act
    result = await extractor.has_suspicion("cartão 4111-1111-1111-1111")

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
async def test_regex_has_suspicion_false_for_empty_text():
    # Arrange
    extractor = RegexExtractor()

    # Act
    result = await extractor.has_suspicion("")

    # Assert
    assert result is False


@pytest.mark.asyncio
async def test_regex_has_suspicion_raises_type_error_for_non_string_text():
    # Arrange
    extractor = RegexExtractor()

    # Act / Assert
    with pytest.raises(TypeError):
        await extractor.has_suspicion(None)


# --- LocalLLMExtractor ---


@pytest_asyncio.fixture
async def llm_extractor():
    # Fecha o AsyncClient real criado no __init__, mesmo quando o teste
    # substitui extractor.client por um mock (o real fica órfão senão).
    extractor = LocalLLMExtractor()
    real_client = extractor.client

    yield extractor

    await real_client.aclose()


@pytest.mark.asyncio
async def test_llm_sanitize_returns_structured_dict_on_happy_path(llm_extractor):
    # Arrange
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "response": '{"entity_type": "cpf", "value": "123.456.789-00", "corrected": true, "confidence": 0.95}'
    }
    llm_extractor.client = AsyncMock()
    llm_extractor.client.post = AsyncMock(return_value=mock_response)

    # Act
    result = await llm_extractor.sanitize("123.456.789-00", "cpf", "context")

    # Assert
    assert isinstance(result, dict)
    assert result["entity_type"] == "cpf"
    assert result["value"] == "123.456.789-00"
    assert result["corrected"] is True
    assert result["confidence"] == 0.95
    llm_extractor.client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_llm_sanitize_returns_fallback_dict_on_network_failure(llm_extractor):
    # Arrange
    llm_extractor.client = AsyncMock()
    llm_extractor.client.post = AsyncMock(side_effect=Exception("connection refused"))

    # Act
    result = await llm_extractor.sanitize("bad", "cpf")

    # Assert
    assert isinstance(result, dict)
    assert result["entity_type"] == "cpf"
    assert result["value"] == "bad"
    assert result["corrected"] is False
    assert result["confidence"] == 0.0
    assert "error" in result


@pytest.mark.asyncio
async def test_llm_sanitize_returns_fallback_dict_on_http_error(llm_extractor):
    # Arrange
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = Exception("503 Server Error")
    llm_extractor.client = AsyncMock()
    llm_extractor.client.post = AsyncMock(return_value=mock_response)

    # Act
    result = await llm_extractor.sanitize("data", "phone")

    # Assert
    assert isinstance(result, dict)
    assert result["entity_type"] == "phone"
    assert result["value"] == "data"
    assert result["corrected"] is False
    assert result["confidence"] == 0.0
    assert "error" in result


@pytest.mark.asyncio
async def test_llm_sanitize_returns_fallback_dict_on_malformed_inner_json(llm_extractor):
    # Arrange
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"response": "not json at all"}
    llm_extractor.client = AsyncMock()
    llm_extractor.client.post = AsyncMock(return_value=mock_response)

    # Act
    result = await llm_extractor.sanitize("data", "cpf")

    # Assert
    assert isinstance(result, dict)
    assert result["entity_type"] == "cpf"
    assert result["value"] == "data"
    assert result["corrected"] is False
    assert result["confidence"] == 0.0
    assert "error" in result


@pytest.mark.asyncio
async def test_llm_sanitize_returns_fallback_dict_on_missing_response_key(llm_extractor):
    # Arrange
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {}
    llm_extractor.client = AsyncMock()
    llm_extractor.client.post = AsyncMock(return_value=mock_response)

    # Act
    result = await llm_extractor.sanitize("data", "cpf")

    # Assert
    assert isinstance(result, dict)
    assert result["entity_type"] == "cpf"
    assert result["value"] == "data"
    assert result["corrected"] is False
    assert result["confidence"] == 0.0
    assert "error" in result


@pytest.mark.asyncio
async def test_llm_sanitize_rejects_empty_raw_value_without_calling_client(llm_extractor):
    # Arrange
    llm_extractor.client = AsyncMock()
    llm_extractor.client.post = AsyncMock()

    # Act
    result = await llm_extractor.sanitize("", "cpf")

    # Assert
    assert isinstance(result, dict)
    assert result["entity_type"] == "cpf"
    assert result["value"] == ""
    assert result["corrected"] is False
    assert result["confidence"] == 0.0
    assert "error" in result
    llm_extractor.client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_llm_sanitize_rejects_none_raw_value_without_calling_client(llm_extractor):
    # Arrange
    llm_extractor.client = AsyncMock()
    llm_extractor.client.post = AsyncMock()

    # Act
    result = await llm_extractor.sanitize(None, "cpf")

    # Assert
    assert isinstance(result, dict)
    assert result["entity_type"] == "cpf"
    assert result["value"] is None
    assert result["corrected"] is False
    assert result["confidence"] == 0.0
    assert "error" in result
    llm_extractor.client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_llm_sanitize_rejects_invalid_entity_type_without_calling_client(llm_extractor):
    # Arrange
    llm_extractor.client = AsyncMock()
    llm_extractor.client.post = AsyncMock()

    # Act
    result = await llm_extractor.sanitize("123", "totally_unknown_entity")

    # Assert
    assert isinstance(result, dict)
    assert result["entity_type"] == "totally_unknown_entity"
    assert result["value"] == "123"
    assert result["corrected"] is False
    assert result["confidence"] == 0.0
    assert "error" in result
    llm_extractor.client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_llm_sanitize_sends_sensitive_credit_card_value_to_http_boundary(llm_extractor):
    # Arrange: prova a marcação real do RegexExtractor antes de acionar a LLM
    regex_extractor = RegexExtractor()
    text = "cartão 4111-1111-1111-1111"
    regex_result = await regex_extractor.extract(text)
    assert regex_result["credit_card"][0]["sensitive"] is True
    sensitive_value = regex_result["credit_card"][0]["value"]

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "response": '{"entity_type": "credit_card", "value": "****", "corrected": true, "confidence": 0.8}'
    }
    llm_extractor.client = AsyncMock()
    llm_extractor.client.post = AsyncMock(return_value=mock_response)

    # Act
    result = await llm_extractor.sanitize(sensitive_value, "credit_card", text)

    # Assert: só o limite HTTP e o resultado público são verificados
    llm_extractor.client.post.assert_awaited_once()
    called_url = llm_extractor.client.post.await_args.args[0]
    assert called_url == f"{llm_extractor.base_url}/api/generate"
    assert isinstance(result, dict)
    assert result["entity_type"] == "credit_card"
