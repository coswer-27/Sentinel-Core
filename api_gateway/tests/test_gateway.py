from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import main


# --- /analyze (proxy to NLP service) ---

def test_analyze_proxies_to_nlp():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"trust_score": 20, "label": "Danger", "reason": "AI 分析"}
    mock_resp.raise_for_status = MagicMock()

    with patch.object(main.app.state, "http_client", create=True):
        with TestClient(main.app) as client:
            client.app.state.http_client.post = AsyncMock(return_value=mock_resp)
            response = client.post("/analyze", json={"content": "你的帳號即將被封鎖"})

    assert response.status_code == 200
    assert response.json()["label"] == "Danger"


def test_analyze_accepts_extra_fields_from_browser_ext():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"trust_score": 90, "label": "Safe", "reason": "正常"}
    mock_resp.raise_for_status = MagicMock()

    with TestClient(main.app) as client:
        client.app.state.http_client.post = AsyncMock(return_value=mock_resp)
        response = client.post(
            "/analyze",
            json={
                "content": "hello",
                "request_id": "ui-test-123",
                "payload_type": "text",
                "url": "https://example.com",
            },
        )

    assert response.status_code == 200


def test_analyze_nlp_timeout_returns_504():
    with TestClient(main.app) as client:
        client.app.state.http_client.post = AsyncMock(
            side_effect=httpx.TimeoutException("timeout")
        )
        response = client.post("/analyze", json={"content": "test"})

    assert response.status_code == 504


def test_analyze_nlp_offline_returns_503():
    with TestClient(main.app) as client:
        client.app.state.http_client.post = AsyncMock(
            side_effect=httpx.ConnectError("refused")
        )
        response = client.post("/analyze", json={"content": "test"})

    assert response.status_code == 503


# --- /analyze/links (proxy to URL scanner service) ---

def test_analyze_links_proxies_to_url_service():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "results": [
            {"url": "https://evil.test/", "final_url": "https://evil.test/", "trust_score": 0, "label": "Malicious", "reason": "惡意網站"}
        ]
    }
    mock_resp.raise_for_status = MagicMock()

    with TestClient(main.app) as client:
        client.app.state.http_client.post = AsyncMock(return_value=mock_resp)
        response = client.post("/analyze/links", json={"urls": ["https://evil.test/"]})

    assert response.status_code == 200
    assert response.json()["results"][0]["label"] == "Malicious"


def test_analyze_links_url_service_timeout_returns_504():
    with TestClient(main.app) as client:
        client.app.state.http_client.post = AsyncMock(
            side_effect=httpx.TimeoutException("timeout")
        )
        response = client.post("/analyze/links", json={"urls": ["https://a.test/"]})

    assert response.status_code == 504


def test_analyze_links_url_service_offline_returns_503():
    with TestClient(main.app) as client:
        client.app.state.http_client.post = AsyncMock(
            side_effect=httpx.ConnectError("refused")
        )
        response = client.post("/analyze/links", json={"urls": ["https://a.test/"]})

    assert response.status_code == 503


def test_analyze_links_rejects_empty_urls():
    with TestClient(main.app) as client:
        response = client.post("/analyze/links", json={"urls": []})

    assert response.status_code == 422


def test_analyze_links_rejects_blank_url_string():
    with TestClient(main.app) as client:
        response = client.post("/analyze/links", json={"urls": ["   "]})

    assert response.status_code == 422
