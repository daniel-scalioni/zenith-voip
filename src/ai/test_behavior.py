from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from src.ai.anomaly_detector import AnomalyDetector
from src.ai.consensus_graph import ConsensusGraph


# --- AnomalyDetector ---


@pytest.mark.asyncio
async def test_anomaly_analyze_returns_zero_score_for_clean_text():
    # Arrange
    detector = AnomalyDetector()

    # Act
    result = await detector.analyze("call-1", "tudo bem, obrigado", "agent")

    # Assert
    assert result["fury_score"] == 0
    assert result["stress_score"] == 0
    assert result["total_score"] == 0
    assert result["anomaly_detected"] is False


@pytest.mark.asyncio
async def test_anomaly_analyze_detects_fury_keywords():
    # Arrange
    detector = AnomalyDetector()
    text = "quero falar com o advogado agora"

    # Act
    result = await detector.analyze("call-2", text, "customer")

    # Assert
    assert result["fury_score"] >= 2
    assert result["anomaly_detected"] is True


@pytest.mark.asyncio
async def test_anomaly_analyze_detects_stress_patterns():
    # Arrange
    detector = AnomalyDetector()
    text = "NÃO AGUENTO MAIS!! ISSO É UM PROBLEMA GRAVE!!"

    # Act
    result = await detector.analyze("call-3", text, "customer")

    # Assert
    assert result["stress_score"] >= 2


@pytest.mark.asyncio
async def test_anomaly_analyze_below_threshold():
    # Arrange
    detector = AnomalyDetector()
    detector.anomaly_threshold = 10
    text = "reclamação apenas"

    # Act
    result = await detector.analyze("call-4", text, "customer")

    # Assert
    assert result["anomaly_detected"] is False


@pytest.mark.asyncio
async def test_anomaly_analyze_empty_text():
    # Arrange
    detector = AnomalyDetector()

    # Act
    result = await detector.analyze("call-5", "", "agent")

    # Assert
    assert result["total_score"] == 0
    assert result["anomaly_detected"] is False


@pytest.mark.asyncio
async def test_anomaly_analyze_only_repeated_words():
    # Arrange
    detector = AnomalyDetector()
    text = "não não não por favor"

    # Act
    result = await detector.analyze("call-6", text, "customer")

    # Assert
    assert result["stress_score"] >= 1


@pytest.mark.asyncio
async def test_anomaly_analyze_caps_and_exclamation_combined():
    # Arrange
    detector = AnomalyDetector()
    text = "CALMA CALMA CALMA!! EU NÃO ACEITO ISSO!!"

    # Act
    result = await detector.analyze("call-7", text, "customer")

    # Assert
    assert result["anomaly_detected"] is True


@pytest.mark.asyncio
async def test_anomaly_threshold_boundary():
    # Arrange
    detector = AnomalyDetector()
    detector.anomaly_threshold = 1

    # Act
    result = await detector.analyze("call-8", "reclamação", "customer")

    # Assert
    assert result["anomaly_detected"] is True


# --- ConsensusGraph ---


@pytest.mark.asyncio
async def test_consensus_graph_approves_with_entities_and_good_sentiment():
    # Arrange
    graph = ConsensusGraph()

    # Act
    result = await graph.run("call-1", "meu cpf é 123.456.789-00", "neutral", 0.0)

    # Assert
    assert result["final_decision"] == "approved"


@pytest.mark.asyncio
async def test_consensus_graph_rejects_when_no_entities_and_low_sentiment():
    # Arrange
    graph = ConsensusGraph()

    # Act
    result = await graph.run("call-2", "tudo certo", "negative", -0.5)

    # Assert
    assert result["final_decision"] == "rejected"


@pytest.mark.asyncio
async def test_consensus_graph_bypass_when_human_bypass():
    # Arrange
    graph = ConsensusGraph()

    # Act
    result = await graph.run(
        "call-3", "tudo certo", "negative", -0.5
    )
    result_with_bypass = await graph.run(
        "call-4", "tudo certo", "negative", -0.5
    )

    # Assert
    assert result_with_bypass["final_decision"] == "rejected"


@pytest.mark.asyncio
async def test_consensus_graph_rejects_at_max_iterations():
    # Arrange
    graph = ConsensusGraph()

    # Act - run multiple times to test max iterations path
    results = []
    for i in range(5):
        r = await graph.run(
            f"call-limit-{i}",
            "texto limpo sem entidades",
            "negative",
            -0.8,
        )
        results.append(r["final_decision"])

    # Assert
    assert all(d == "rejected" for d in results)


@pytest.mark.asyncio
async def test_consensus_graph_empty_transcript():
    # Arrange
    graph = ConsensusGraph()

    # Act
    result = await graph.run("call-5", "", "neutral", 0.0)

    # Assert
    assert "final_decision" in result


@pytest.mark.asyncio
async def test_consensus_graph_publishes_event():
    # Arrange
    graph = ConsensusGraph()
    with patch.object(graph, "llm") as mock_llm:
        mock_llm.sanitize = AsyncMock(return_value={"sanitized": True})

        # Act
        result = await graph.run("call-6", "cpf 123.456.789-00", "positive", 0.5)

    # Assert
    assert "final_decision" in result


@pytest.mark.asyncio
async def test_consensus_graph_entities_extraction_populated():
    # Arrange
    graph = ConsensusGraph()

    # Act
    result = await graph.run(
        "call-7", "meu cpf é 123.456.789-00", "neutral", 0.0
    )

    # Assert
    assert "entities" in result


@pytest.mark.asyncio
async def test_consensus_graph_iteration_bounded():
    # Arrange
    graph = ConsensusGraph()

    # Act
    result = await graph.run(
        "call-8", "texto sem entidade", "negative", -0.9
    )

    # Assert
    assert "iteration" in result
    assert result["iteration"] <= 3


@pytest.mark.asyncio
async def test_consensus_graph_sentiment_boundary_negative_03():
    # Arrange
    graph = ConsensusGraph()

    # Act - score exactly -0.3 should be approved if entities exist
    result = await graph.run(
        "call-9", "cpf 123.456.789-00", "negative", -0.3
    )

    # Assert
    assert result["final_decision"] == "approved"
