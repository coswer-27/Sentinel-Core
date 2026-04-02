import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# transformers is mocked in conftest.py; setdefault ensures standalone execution works too.
sys.modules.setdefault("transformers", MagicMock())
sys.modules.setdefault("torch", MagicMock())

_service_nlp_path = str(Path(__file__).parent.parent / "service_nlp")
if _service_nlp_path not in sys.path:
    sys.path.insert(0, _service_nlp_path)

from fastapi.testclient import TestClient
from main import app as nlp_app  # noqa: E402


def make_detector(analyze_return: int = 85) -> MagicMock:
    mock = MagicMock()
    mock.analyze.return_value = analyze_return
    return mock


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestNlpHealth:
    def test_health_returns_ok_when_model_loaded(self):
        with patch("main.BertDetector", return_value=make_detector()):
            with TestClient(nlp_app) as client:
                response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["model"] == "loaded"


# ---------------------------------------------------------------------------
# /analyze endpoint
# ---------------------------------------------------------------------------

class TestNlpAnalyze:
    def test_safe_label_for_high_score(self):
        with patch("main.BertDetector", return_value=make_detector(85)):
            with TestClient(nlp_app) as client:
                response = client.post("/analyze", json={"content": "Great trusted content"})
        assert response.status_code == 200
        data = response.json()
        assert data["trust_score"] == 85
        assert data["label"] == "Safe"
        assert "85%" in data["reason"]

    def test_danger_label_for_low_score(self):
        with patch("main.BertDetector", return_value=make_detector(30)):
            with TestClient(nlp_app) as client:
                response = client.post("/analyze", json={"content": "Suspicious content"})
        assert response.status_code == 200
        data = response.json()
        assert data["trust_score"] == 30
        assert data["label"] == "Danger"

    def test_score_at_threshold_55_is_danger(self):
        # TRUST_THRESHOLD = 55; score <= 55 → Danger
        with patch("main.BertDetector", return_value=make_detector(55)):
            with TestClient(nlp_app) as client:
                response = client.post("/analyze", json={"content": "borderline content"})
        assert response.json()["label"] == "Danger"

    def test_score_at_56_is_safe(self):
        with patch("main.BertDetector", return_value=make_detector(56)):
            with TestClient(nlp_app) as client:
                response = client.post("/analyze", json={"content": "borderline safe"})
        assert response.json()["label"] == "Safe"

    def test_inference_error_returns_500(self):
        mock_detector = make_detector()
        mock_detector.analyze.side_effect = RuntimeError("推論失敗")
        with patch("main.BertDetector", return_value=mock_detector):
            with TestClient(nlp_app) as client:
                response = client.post("/analyze", json={"content": "some content"})
        assert response.status_code == 500

    def test_missing_content_returns_422(self):
        with patch("main.BertDetector", return_value=make_detector()):
            with TestClient(nlp_app) as client:
                response = client.post("/analyze", json={})
        assert response.status_code == 422

    def test_response_contains_all_required_fields(self):
        with patch("main.BertDetector", return_value=make_detector(70)):
            with TestClient(nlp_app) as client:
                response = client.post("/analyze", json={"content": "test content"})
        data = response.json()
        assert "trust_score" in data
        assert "label" in data
        assert "reason" in data
