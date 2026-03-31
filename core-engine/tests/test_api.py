from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

import main


def test_analyze_returns_danger():
    with patch("main.TextDetector") as mock_td:
        mock_instance = MagicMock()
        mock_td.return_value = mock_instance
        mock_instance.analyze.return_value = {
            "is_danger": True,
            "trust_score": 20,
            "reason": "AI 偵測到異常語意偏好 (1 star)。"
        }
        with TestClient(main.app) as client:
            response = client.post(
                "/analyze",
                json={
                    "request_id": "test-001",
                    "payload_type": "text",
                    "content": "test"
                }
            )
        assert response.status_code == 200
        data = response.json()
        assert data["label"] == "Danger"
        assert data["trust_score"] == 20
        assert data["request_id"] == "test-001"


def test_analyze_returns_safe():
    with patch("main.TextDetector") as mock_td:
        mock_instance = MagicMock()
        mock_td.return_value = mock_instance
        mock_instance.analyze.return_value = {
            "is_danger": False,
            "trust_score": 95,
            "reason": "語意分析正常"
        }
        with TestClient(main.app) as client:
            response = client.post(
                "/analyze",
                json={
                    "request_id": "test-002",
                    "payload_type": "text",
                    "content": "test"
                }
            )
        assert response.status_code == 200
        assert response.json()["label"] == "Safe"
