from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from support_assistant.main import create_app
from support_assistant.schemas.confidence import (
    ConfidenceAssessment,
    ConfidenceDecision,
    EvaluatedGroundedDraft,
)


@pytest.fixture
def mock_draft_service() -> MagicMock:
    service = MagicMock()
    assessment = ConfidenceAssessment(
        decision=ConfidenceDecision.ACCEPT,
        confidence_score=0.85,
        supporting_evidence_ids=["faq-100"],
        weak_evidence_indicators=[],
        reason="Draft accepted with high confidence.",
        metadata={"top_reranker_score": 0.9},
    )
    service.process_query = AsyncMock(
        return_value=EvaluatedGroundedDraft(
            decision=ConfidenceDecision.ACCEPT,
            confidence=0.85,
            answer="Here is your answer.",
            reason="Draft accepted with high confidence.",
            citations=[],
            confidence_assessment=assessment,
            grounded_draft=None,
        )
    )
    return service


def test_post_draft_endpoint(mock_draft_service: MagicMock) -> None:
    app = create_app()
    app.state.draft_service = mock_draft_service
    client = TestClient(app)

    response = client.post("/draft", json={"query": "How do I cancel my subscription?"})
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "accept"
    assert data["confidence"] == 0.85
    assert data["answer"] == "Here is your answer."


def test_post_drafts_plural_endpoint(mock_draft_service: MagicMock) -> None:
    app = create_app()
    app.state.draft_service = mock_draft_service
    client = TestClient(app)

    response = client.post("/drafts", json={"query": "How do I cancel my subscription?"})
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "accept"
    assert data["confidence"] == 0.85
