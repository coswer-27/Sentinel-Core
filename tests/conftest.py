import sys
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Mock heavy ML dependencies before any test file imports NLP service code
sys.modules.setdefault("transformers", MagicMock())
sys.modules.setdefault("torch", MagicMock())

# Expose service_nlp's internal modules (detectors.bert_engine, etc.)
_service_nlp_path = str(Path(__file__).parent.parent / "service_nlp")
if _service_nlp_path not in sys.path:
    sys.path.insert(0, _service_nlp_path)

from fastapi.testclient import TestClient
from api_gateway.main import app as gateway_app


def build_nlp_mock_response(trust_score: int = 85, label: str = "Safe") -> MagicMock:
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {
        "trust_score": trust_score,
        "label": label,
        "reason": f"AI 分析信任度為 {trust_score}%",
    }
    return mock


@pytest.fixture
def gateway_client():
    with TestClient(gateway_app) as c:
        yield c


@pytest.fixture
def gateway_with_mock_nlp(gateway_client):
    """Gateway client with NLP backend mocked to return a successful Safe response."""
    gateway_client.app.state.http_client.post = AsyncMock(
        return_value=build_nlp_mock_response()
    )
    return gateway_client
