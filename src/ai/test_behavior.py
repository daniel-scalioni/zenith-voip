from unittest.mock import AsyncMock, patch

import pytest

from src.ai.anomaly_detector import AnomalyDetector


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "expected_score", "expected_alert", "expected_severity"),
    [
        ("advogado chefe", 2, False, None),
        ("advogado chefe gerente", 3, True, "warning"),
        ("advogado chefe gerente supervisor", 4, True, "warning"),
        ("advogado chefe gerente supervisor processo", 5, True, "danger"),
    ],
)
async def test_anomaly_total_score_boundaries(
    text,
    expected_score,
    expected_alert,
    expected_severity,
):
    # Arrange
    detector = AnomalyDetector()

    # Act
    with patch(
        "src.ai.anomaly_detector.agent_assist_ws.handle_alert",
        new_callable=AsyncMock,
    ) as alert:
        result = await detector.analyze("call-boundary", text, "customer")

    # Assert
    assert result["total_score"] == expected_score
    assert result["anomaly_detected"] is expected_alert
    if expected_alert:
        assert alert.await_args.kwargs["severity"] == expected_severity
    else:
        alert.assert_not_awaited()


@pytest.mark.asyncio
async def test_anomaly_empty_text_returns_empty_state_without_alert():
    # Arrange
    detector = AnomalyDetector()

    # Act
    with patch(
        "src.ai.anomaly_detector.agent_assist_ws.handle_alert",
        new_callable=AsyncMock,
    ) as alert:
        result = await detector.analyze("call-empty", "", "customer")

    # Assert
    assert result == {
        "fury_score": 0,
        "stress_score": 0,
        "total_score": 0,
        "anomaly_detected": False,
    }
    alert.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_text", [None, 42, [], {}])
async def test_anomaly_rejects_none_and_non_text_values(invalid_text):
    # Arrange
    detector = AnomalyDetector()

    # Act / Assert
    with pytest.raises(TypeError, match="text|str|string"):
        await detector.analyze("call-invalid", invalid_text, "customer")


def _consensus_graph_class():
    try:
        from src.ai.consensus_graph import ConsensusGraph
    except ModuleNotFoundError as exc:
        pytest.fail(f"dependência pinada ausente: {exc}", pytrace=False)
    return ConsensusGraph


@pytest.mark.asyncio
async def test_consensus_real_empty_flow_rejects_at_maximum_iteration():
    # Arrange
    graph = _consensus_graph_class()()

    # Act
    with patch(
        "src.ai.consensus_graph.event_bus.publish",
        new_callable=AsyncMock,
    ) as publish:
        result = await graph.run("call-empty-consensus", "", "neutral", 0.0)

    # Assert
    assert result["entities"] == {}
    assert result["final_decision"] == "rejected"
    assert result["iteration"] == 3
    publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_consensus_real_regex_flow_approves_sentiment_boundary():
    # Arrange
    graph = _consensus_graph_class()()

    # Act
    with patch(
        "src.ai.consensus_graph.event_bus.publish",
        new_callable=AsyncMock,
    ) as publish:
        result = await graph.run(
            "call-cpf",
            "Documento informado: 123.456.789-00",
            "negative",
            -0.3,
        )

    # Assert
    assert "cpf" in result["entities"]
    assert result["final_decision"] == "approved"
    assert result["iteration"] == 1
    publish.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_transcript", [None, 42, [], {}])
async def test_consensus_rejects_none_and_non_text_transcripts(invalid_transcript):
    # Arrange
    graph = _consensus_graph_class()()

    # Act / Assert
    with patch(
        "src.ai.consensus_graph.event_bus.publish",
        new_callable=AsyncMock,
    ) as publish:
        with pytest.raises(TypeError, match="transcript|str|string"):
            await graph.run("call-invalid", invalid_transcript, "neutral", 0.0)
    publish.assert_not_awaited()
