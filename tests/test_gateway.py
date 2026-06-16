import json
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
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


# ---------------------------------------------------------------------------
# Stats endpoint
# ---------------------------------------------------------------------------

def test_get_stats_success(gateway_client):
    # Mock aiosqlite.connect 以模擬資料庫回傳
    mock_row = {"total": 10, "avg_score": 85.5}
    
    with patch("aiosqlite.connect") as mock_connect:
        mock_db = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_db
        
        mock_cursor = AsyncMock()
        # 修正：db.execute 是一個協程，它直接回傳 cursor
        mock_db.execute.return_value = mock_cursor
        
        # cursor 是一個非同步上下文管理器
        mock_cursor.__aenter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = mock_row
        
        response = gateway_client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 10
        assert data["avg_score"] == 85.5


def test_get_stats_empty_db(gateway_client):
    # 模擬資料庫為空的情況
    mock_row = {"total": 0, "avg_score": None}
    
    with patch("aiosqlite.connect") as mock_connect:
        mock_db = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_db
        
        mock_cursor = AsyncMock()
        # 修正：db.execute 是一個協程，它直接回傳 cursor
        mock_db.execute.return_value = mock_cursor
        
        # cursor 是一個非同步上下文管理器
        mock_cursor.__aenter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = mock_row
        
        response = gateway_client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["avg_score"] == 0


def test_get_stats_db_error(gateway_client):
    # 模擬資料庫連線失敗
    with patch("aiosqlite.connect", side_effect=Exception("DB Error")):
        response = gateway_client.get("/stats")
        assert response.status_code == 500
        assert response.json()["detail"] == "無法讀取統計數據"


# ---------------------------------------------------------------------------
# Recent scans endpoint
# ---------------------------------------------------------------------------

def test_get_recent_success(gateway_client):
    rows = [
        {"content": "您的帳戶異常請點連結驗證", "url": "https://x.test",
         "trust_score": 8, "label": "Danger", "reason": "釣魚",
         "created_at": "2026-06-17 03:00:00"},
        {"content": "明天三點開會", "url": None,
         "trust_score": 95, "label": "Safe", "reason": "安全",
         "created_at": "2026-06-17 02:00:00"},
    ]
    with patch("aiosqlite.connect") as mock_connect:
        mock_db = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_db
        mock_cursor = AsyncMock()
        mock_db.execute.return_value = mock_cursor
        mock_cursor.__aenter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = rows

        response = gateway_client.get("/recent?limit=6")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["items"][0]["label"] == "Danger"
        assert data["items"][0]["trust_score"] == 8


def test_get_recent_truncates_content(gateway_client):
    long_content = "詐" * 200
    rows = [{"content": long_content, "url": None, "trust_score": 5,
             "label": "Danger", "reason": "x", "created_at": "2026-06-17 03:00:00"}]
    with patch("aiosqlite.connect") as mock_connect:
        mock_db = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_db
        mock_cursor = AsyncMock()
        mock_db.execute.return_value = mock_cursor
        mock_cursor.__aenter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = rows

        response = gateway_client.get("/recent")
        assert response.status_code == 200
        assert len(response.json()["items"][0]["content"]) == 80


def test_get_recent_empty(gateway_client):
    with patch("aiosqlite.connect") as mock_connect:
        mock_db = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_db
        mock_cursor = AsyncMock()
        mock_db.execute.return_value = mock_cursor
        mock_cursor.__aenter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        response = gateway_client.get("/recent")
        assert response.status_code == 200
        assert response.json() == {"items": []}


def test_get_recent_db_error(gateway_client):
    with patch("aiosqlite.connect", side_effect=Exception("DB Error")):
        response = gateway_client.get("/recent")
        assert response.status_code == 500
        assert response.json()["detail"] == "無法讀取近期掃描"


# ---------------------------------------------------------------------------
# Link scan forwarding + logging
# ---------------------------------------------------------------------------

def test_analyze_links_forwards_results(gateway_client):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "results": [
            {"url": "https://evil.test", "final_url": "https://evil.test",
             "trust_score": 0, "label": "Malicious", "reason": "GSB", "hop_count": 0},
            {"url": "https://ok.test", "final_url": "https://ok.test",
             "trust_score": 90, "label": "Safe", "reason": "ok", "hop_count": 0},
        ]
    }
    gateway_client.app.state.http_client.post = AsyncMock(return_value=mock_resp)
    response = gateway_client.post(
        "/analyze/links", json={"urls": ["https://evil.test", "https://ok.test"]}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 2
    assert data["results"][0]["label"] == "Malicious"
    assert data["results"][0]["hop_count"] == 0


def test_analyze_links_upstream_offline_returns_503(gateway_client):
    gateway_client.app.state.http_client.post = AsyncMock(
        side_effect=httpx.ConnectError("connection refused")
    )
    response = gateway_client.post("/analyze/links", json={"urls": ["https://x.test"]})
    assert response.status_code == 503


# ---------------------------------------------------------------------------
# Behavior analysis + fusion endpoint
# ---------------------------------------------------------------------------

def _url_scan_resp(label="Safe", trust=90):
    m = MagicMock()
    m.raise_for_status = MagicMock()
    m.json.return_value = {"results": [{
        "url": "https://x.test", "final_url": "https://x.test",
        "trust_score": trust, "label": label, "reason": "r", "hop_count": 0,
    }]}
    return m


def test_analyze_behavior_external_password_form_is_danger(gateway_client):
    async def router(url, json=None, **kw):
        if url == gateway_main.URL_SERVICE_URL:
            return _url_scan_resp()
        if url == gateway_main.EXPLAIN_URL:
            m = MagicMock(); m.raise_for_status = MagicMock()
            m.json.return_value = {"explanation": "此頁要求於外部網域輸入密碼，疑似釣魚。", "source": "fallback"}
            return m
        raise AssertionError(f"unexpected url {url}")

    gateway_client.app.state.http_client.post = AsyncMock(side_effect=router)
    r = gateway_client.post("/analyze/behavior", json={
        "url": "https://x.test", "features": {"external_password_form": True},
    })
    assert r.status_code == 200
    data = r.json()
    assert data["behavior_score"] == 60
    assert data["label"] == "Danger"
    assert data["explanation"]


def test_analyze_behavior_low_risk_does_not_call_explain(gateway_client):
    calls = []

    async def router(url, json=None, **kw):
        calls.append(url)
        if url == gateway_main.URL_SERVICE_URL:
            return _url_scan_resp()
        raise AssertionError(f"unexpected url {url}")

    gateway_client.app.state.http_client.post = AsyncMock(side_effect=router)
    r = gateway_client.post("/analyze/behavior", json={
        "url": "https://x.test", "features": {"form_action_external": True},
    })
    assert r.status_code == 200
    assert r.json()["label"] != "Danger"
    assert gateway_main.EXPLAIN_URL not in calls


def test_analyze_behavior_tolerates_url_scan_failure(gateway_client):
    async def router(url, json=None, **kw):
        if url == gateway_main.URL_SERVICE_URL:
            raise httpx.ConnectError("link service down")
        if url == gateway_main.EXPLAIN_URL:
            m = MagicMock(); m.raise_for_status = MagicMock()
            m.json.return_value = {"explanation": "x", "source": "fallback"}
            return m
        raise AssertionError(f"unexpected url {url}")

    gateway_client.app.state.http_client.post = AsyncMock(side_effect=router)
    r = gateway_client.post("/analyze/behavior", json={
        "url": "https://x.test", "features": {"external_password_form": True},
    })
    assert r.status_code == 200
    data = r.json()
    assert data["label"] == "Danger"   # 行為極高，URL 掃描失敗仍升級
    assert data["url"] is None


def test_analyze_behavior_private_url_rejected(gateway_client):
    r = gateway_client.post("/analyze/behavior", json={
        "url": "http://192.168.1.1/", "features": {"external_password_form": True},
    })
    assert r.status_code == 422


def test_analyze_behavior_script_heavy_legit_site_not_danger(gateway_client):
    """回歸：Google 等腳本/iframe 繁多的正常網站不應被判 Danger。"""
    async def router(url, json=None, **kw):
        if url == gateway_main.URL_SERVICE_URL:
            return _url_scan_resp()
        raise AssertionError(f"unexpected url {url}")

    gateway_client.app.state.http_client.post = AsyncMock(side_effect=router)
    r = gateway_client.post("/analyze/behavior", json={
        "url": "https://www.google.com/search",
        "features": {
            "obfuscated_script": True, "dynamic_script_inject": 80,
            "cross_origin_iframe_count": 10, "password_field_count": 1,
        },
    })
    assert r.status_code == 200
    data = r.json()
    assert data["behavior_score"] == 0
    assert data["label"] != "Danger"
