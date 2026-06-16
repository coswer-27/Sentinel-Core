import importlib.util
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

_service_nlp_path = str(Path(__file__).parent.parent / "service_nlp")
if _service_nlp_path not in sys.path:
    sys.path.insert(0, _service_nlp_path)

from fastapi.testclient import TestClient

# 以獨立模組名載入 service_nlp/main.py，避免與 api_gateway/main.py 的 "main" 名稱衝突
_nlp_main_path = Path(__file__).parent.parent / "service_nlp" / "main.py"
_spec = importlib.util.spec_from_file_location("nlp_main", _nlp_main_path)
nlp_main = importlib.util.module_from_spec(_spec)
sys.modules["nlp_main"] = nlp_main
_spec.loader.exec_module(nlp_main)
nlp_app = nlp_main.app


def make_detector(category: str = "safe", trust_score: int = 99, confidence: float = 0.99) -> MagicMock:
    """模擬新版 BertDetector：analyze() 回傳 dict（category/confidence/trust_score/...）。"""
    descs = {
        "safe": "未偵測到明顯詐騙特徵",
        "phishing": "假冒官方/平台要求驗證帳號（釣魚）",
        "investment_scam": "假投資、飆股、虛擬幣詐騙",
    }
    mock = MagicMock()
    mock.analyze.return_value = {
        "category": category,
        "category_desc": descs.get(category, category),
        "confidence": confidence,
        "trust_score": trust_score,
        "scam_probability": 0.0 if category == "safe" else 1.0,
    }
    return mock


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestNlpHealth:
    def test_health_returns_ok_when_model_loaded(self):
        with patch.object(nlp_main, "BertDetector", return_value=make_detector()):
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
    def test_safe_category_returns_safe_label(self):
        with patch.object(nlp_main, "BertDetector", return_value=make_detector("safe", 98)):
            with TestClient(nlp_app) as client:
                response = client.post("/analyze", json={"content": "明天三點開會記得帶筆電"})
        assert response.status_code == 200
        data = response.json()
        assert data["trust_score"] == 98
        assert data["label"] == "Safe"
        assert data["category"] == "safe"

    def test_scam_category_returns_danger_label(self):
        with patch.object(nlp_main, "BertDetector", return_value=make_detector("phishing", 2)):
            with TestClient(nlp_app) as client:
                response = client.post("/analyze", json={"content": "您的帳號異常請點連結驗證"})
        assert response.status_code == 200
        data = response.json()
        assert data["trust_score"] == 2
        assert data["label"] == "Danger"
        assert data["category"] == "phishing"

    def test_response_includes_category_metadata(self):
        with patch.object(nlp_main, "BertDetector", return_value=make_detector("investment_scam", 1, 0.97)):
            with TestClient(nlp_app) as client:
                response = client.post("/analyze", json={"content": "老師帶你飆股穩賺不賠"})
        data = response.json()
        assert data["category"] == "investment_scam"
        assert data["category_desc"]
        assert data["confidence"] == 0.97
        assert "scam_probability" in data

    def test_inference_error_returns_500(self):
        mock_detector = make_detector()
        mock_detector.analyze.side_effect = RuntimeError("推論失敗")
        with patch.object(nlp_main, "BertDetector", return_value=mock_detector):
            with TestClient(nlp_app) as client:
                response = client.post("/analyze", json={"content": "some content"})
        assert response.status_code == 500

    def test_missing_content_returns_422(self):
        with patch.object(nlp_main, "BertDetector", return_value=make_detector()):
            with TestClient(nlp_app) as client:
                response = client.post("/analyze", json={})
        assert response.status_code == 422

    def test_response_contains_all_required_fields(self):
        with patch.object(nlp_main, "BertDetector", return_value=make_detector("phishing", 5)):
            with TestClient(nlp_app) as client:
                response = client.post("/analyze", json={"content": "test content"})
        data = response.json()
        for key in ("trust_score", "label", "reason", "category", "confidence"):
            assert key in data
