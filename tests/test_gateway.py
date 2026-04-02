import pytest
from fastapi.testclient import TestClient
from api_gateway.main import app
from common.models import AnalyzeRequest

client = TestClient(app)

def test_health_check():
    with TestClient(app) as client: # 加入 with
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

def test_analyze_request_validation():
    with TestClient(app) as client: # 加入 with
        # 測試無效 URL (SSRF 防護)
        payload = {
            "content": "test content",
            "url": "http://localhost/admin",
            "timestamp": "2023-10-27T10:00:00Z"
        }
        response = client.post("/analyze", json=payload)
        assert response.status_code == 422 

def test_analyze_request_valid():
    with TestClient(app) as client: # 加入 with
        payload = {
            "content": "Valid content",
            "url": "https://google.com",
            "timestamp": "2023-10-27T10:00:00Z"
        }
        response = client.post("/analyze", json=payload)
        # 這次它會真的去找 http_client，因為沒開 NLP 服務，會噴 503 或 502
        assert response.status_code in [502, 503]
