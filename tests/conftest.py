import sys
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# 註：torch / transformers 現已為真實安裝（GPU 版），不再以 MagicMock 取代。
# NLP 服務測試一律 patch main.BertDetector，故不會載入真實模型權重。

# Expose service_nlp's internal modules (detectors.bert_engine, etc.)
_service_nlp_path = str(Path(__file__).parent.parent / "service_nlp")
if _service_nlp_path not in sys.path:
    sys.path.insert(0, _service_nlp_path)

from fastapi.testclient import TestClient
from api_gateway.main import app as gateway_app


def build_nlp_mock_response(trust_score: int = 85, label: str = "Safe") -> MagicMock:
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    category = "safe" if label == "Safe" else "phishing"
    mock.json.return_value = {
        "trust_score": trust_score,
        "label": label,
        "reason": f"AI 分析信任度為 {trust_score}%",
        "category": category,
        "category_desc": "未偵測到明顯詐騙特徵" if label == "Safe" else "假冒官方/平台要求驗證帳號（釣魚）",
        "confidence": 0.99,
        "scam_probability": 0.0 if label == "Safe" else 1.0,
    }
    return mock


@pytest.fixture
def gateway_client():
    with TestClient(gateway_app) as c:
        yield c


@pytest.fixture
def gateway_with_mock_nlp(gateway_client):
    """Gateway client with NLP backend mocked to return a successful Safe response."""
    gateway_client.app.state.http_client.post = AsyncMock(
        return_value=build_nlp_mock_response()
    )
    return gateway_client


@pytest.fixture(autouse=True)
def mock_db_operations():
    """全域 Mock 資料庫操作，避免測試污染真實資料庫。"""
    with patch("api_gateway.database.log_scan", new_callable=AsyncMock) as mock_log, \
         patch("api_gateway.database.init_db", new_callable=AsyncMock) as mock_init:
        yield mock_log, mock_init
