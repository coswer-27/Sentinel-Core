import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

_root = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def link_main():
    """延遲載入，避免覆寫 sys.modules['main']（service_nlp 測試需使用同名模組）。"""
    spec = importlib.util.spec_from_file_location(
        "sentinel_link_scanner_main",
        _root / "service_link_scanner" / "main.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_analyze_links_returns_results(link_main):
    with patch.object(link_main, "URLDetector") as mock_url:
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

        with TestClient(link_main.app) as client:
            response = client.post(
                "/analyze/links",
                json={"urls": ["https://a.test/", "https://b.test/"]},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 2
        assert data["results"][0]["label"] == "Malicious"
        assert data["results"][1]["label"] == "Suspicious"


def test_analyze_links_handles_exception(link_main):
    with patch.object(link_main, "URLDetector") as mock_url:
        mock_inst = MagicMock()
        mock_url.return_value = mock_inst
        mock_inst.analyze_batch = AsyncMock(side_effect=RuntimeError("network"))

        with TestClient(link_main.app) as client:
            response = client.post(
                "/analyze/links",
                json={"urls": ["https://broken.test/"]},
            )

        assert response.status_code == 200
        r = response.json()["results"][0]
        assert r["label"] == "Suspicious"
        assert "無法分析" in r["reason"]
