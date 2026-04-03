import json
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
import api_gateway.main as gateway_main
from api_gateway.main import app, _rate_limit_exceeded_handler
from api_gateway.rules_engine import engine  # 注意前面的那個「.」

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def test_health_check():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Request validation — 422
# ---------------------------------------------------------------------------

def test_analyze_ssrf_localhost_blocked():
    with TestClient(app) as client:
        payload = {
            "content": "test content",
            "url": "http://localhost/admin",
            "timestamp": "2023-10-27T10:00:00Z",
        }
        response = client.post("/analyze", json=payload)
        assert response.status_code == 422


def test_analyze_log_injection_in_timestamp_blocked():
    with TestClient(app) as client:
        payload = {
            "content": "test content",
            "url": "https://example.com",
            "timestamp": "invalid-time\n[LOG INJECTION]",
        }
        response = client.post("/analyze", json=payload)
        assert response.status_code == 422


def test_analyze_content_empty_returns_422():
    with TestClient(app) as client:
        assert client.post("/analyze", json={"content": ""}).status_code == 422


def test_analyze_content_whitespace_only_returns_422():
    with TestClient(app) as client:
        assert client.post("/analyze", json={"content": "   "}).status_code == 422


def test_analyze_content_too_long_returns_422():
    with TestClient(app) as client:
        assert client.post("/analyze", json={"content": "a" * 5001}).status_code == 422


def test_analyze_missing_content_returns_422():
    with TestClient(app) as client:
        assert client.post("/analyze", json={"url": "https://example.com"}).status_code == 422


def test_analyze_rule_engine_intercepts_line_scam(gateway_client):
    payload = {"content": "趕快加我 LINE 領取飆股資訊！"}
    response = gateway_client.post("/analyze", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "[快速攔截]" in data["reason"]
    assert data["trust_score"] == 15


@pytest.mark.parametrize("private_url", [
    "http://127.0.0.1/admin",
    "http://127.0.0.2/",
    "http://192.168.1.1/internal",
    "http://192.168.255.255/",
    "http://10.0.0.1/secret",
    "http://10.255.255.255/",
    "http://172.16.0.1/private",
    "http://172.20.0.1/private",
    "http://172.31.0.1/private",
])
def test_analyze_ssrf_all_private_ranges_blocked(gateway_client, private_url):
    response = gateway_client.post("/analyze", json={"content": "test", "url": private_url})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Upstream error handling
# ---------------------------------------------------------------------------

def test_analyze_no_nlp_service_returns_503_or_502(gateway_client):
    # 使用 AsyncMock 強迫 http_client 拋出連線錯誤
    gateway_client.app.state.http_client.post = AsyncMock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    
    payload = {
        "content": "Valid content",
        "url": "https://google.com",
        "timestamp": "2023-10-27T10:00:00Z",
    }
    response = gateway_client.post("/analyze", json=payload)
    
    # 確保當連線失敗時，Gateway 會回傳我們定義好的錯誤碼
    assert response.status_code in [502, 503]


def test_analyze_timeout_returns_504(gateway_client):
    gateway_client.app.state.http_client.post = AsyncMock(
        side_effect=httpx.TimeoutException("timed out")
    )
    response = gateway_client.post("/analyze", json={"content": "test"})
    assert response.status_code == 504


def test_analyze_connect_error_returns_503(gateway_client):
    gateway_client.app.state.http_client.post = AsyncMock(
        side_effect=httpx.ConnectError("connection refused")
    )
    response = gateway_client.post("/analyze", json={"content": "test"})
    assert response.status_code == 503


def test_analyze_upstream_http_error_returns_502(gateway_client):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 Internal Server Error",
        request=MagicMock(),
        response=MagicMock(status_code=500),
    )
    gateway_client.app.state.http_client.post = AsyncMock(return_value=mock_resp)
    response = gateway_client.post("/analyze", json={"content": "test"})
    assert response.status_code == 502


# ---------------------------------------------------------------------------
# Success (mocked NLP)
# ---------------------------------------------------------------------------

def test_analyze_success_returns_nlp_payload(gateway_with_mock_nlp):
    response = gateway_with_mock_nlp.post(
        "/analyze",
        json={"content": "This is a trustworthy article."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["trust_score"] == 85
    assert data["label"] == "Safe"
    assert "85%" in data["reason"]


def test_analyze_content_at_max_length_accepted(gateway_with_mock_nlp):
    response = gateway_with_mock_nlp.post("/analyze", json={"content": "a" * 5000})
    assert response.status_code == 200


def test_analyze_without_optional_fields(gateway_with_mock_nlp):
    response = gateway_with_mock_nlp.post("/analyze", json={"content": "hello"})
    assert response.status_code == 200


def test_analyze_with_valid_public_url(gateway_with_mock_nlp):
    response = gateway_with_mock_nlp.post("/analyze", json={
        "content": "test content",
        "url": "https://example.com",
        "timestamp": "2024-01-01T00:00:00Z",
    })
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Rate limit handler
# ---------------------------------------------------------------------------

def test_rate_limit_handler_returns_429_with_detail():
    from slowapi.errors import RateLimitExceeded

    mock_request = MagicMock()
    mock_request.client = "127.0.0.1"
    mock_exc = MagicMock(spec=RateLimitExceeded)
    mock_exc.detail = "10/minute"

    response = _rate_limit_exceeded_handler(mock_request, mock_exc)

    assert response.status_code == 429
    body = json.loads(response.body)
    assert "detail" in body
    assert "10/minute" in body["detail"]
