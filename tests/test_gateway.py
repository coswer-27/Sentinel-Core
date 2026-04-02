import pytest
from fastapi.testclient import TestClient
from api_gateway.main import app
from common.models import AnalyzeRequest

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_analyze_request_validation():
    # 測試無效 URL (SSRF 防護)
    payload = {
        "content": "test content",
        "url": "http://localhost/admin",
        "timestamp": "2023-10-27T10:00:00Z"
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 422 # Pydantic 驗證失敗

    # 測試無效時間戳記
    payload = {
        "content": "test content",
        "url": "https://example.com",
        "timestamp": "invalid-time\n[LOG INJECTION]"
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 422

def test_analyze_request_valid():
    # 這裡假設 NLP 服務未啟動，所以會得到 503 或 502
    payload = {
        "content": "Valid content",
        "url": "https://google.com",
        "timestamp": "2023-10-27T10:00:00Z"
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code in [502, 503]
