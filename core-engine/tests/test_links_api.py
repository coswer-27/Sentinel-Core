from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

import main


def test_analyze_links_returns_results():
    with patch("main.TextDetector") as mock_td, patch("main.URLDetector") as mock_url:
        mock_td.return_value = MagicMock()
        mock_inst = MagicMock()
        mock_url.return_value = mock_inst
        mock_inst.analyze_batch = AsyncMock(
            return_value=[
                {
                    "final_url": "https://evil.example/",
                    "trust_score": 0,
                    "label": "Malicious",
                    "reason": "Google Safe Browsing 標記為惡意網站",
                },
                {
                    "final_url": "https://xn--test.example/",
                    "trust_score": 40,
                    "label": "Suspicious",
                    "reason": "Punycode",
                },
            ]
        )

        with TestClient(main.app) as client:
            response = client.post(
                "/analyze/links",
                json={"urls": ["https://a.test/", "https://b.test/"]},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 2
        assert data["results"][0]["label"] == "Malicious"
        assert data["results"][1]["label"] == "Suspicious"


def test_analyze_links_handles_exception():
    with patch("main.TextDetector") as mock_td, patch("main.URLDetector") as mock_url:
        mock_td.return_value = MagicMock()
        mock_inst = MagicMock()
        mock_url.return_value = mock_inst
        mock_inst.analyze_batch = AsyncMock(side_effect=RuntimeError("network"))

        with TestClient(main.app) as client:
            response = client.post(
                "/analyze/links",
                json={"urls": ["https://broken.test/"]},
            )

        assert response.status_code == 200
        r = response.json()["results"][0]
        assert r["label"] == "Suspicious"
        assert "無法分析" in r["reason"]
