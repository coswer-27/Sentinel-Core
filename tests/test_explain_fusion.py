"""B2: gateway 高風險融合 / LLM 解釋觸發邏輯測試。"""
from unittest.mock import AsyncMock, MagicMock

import api_gateway.main as gateway_main


def _resp(json_data):
    m = MagicMock()
    m.raise_for_status = MagicMock()
    m.json.return_value = json_data
    return m


class TestShouldExplain:
    def test_danger_triggers(self):
        assert gateway_main.should_explain("Danger") is True

    def test_safe_does_not_trigger(self):
        assert gateway_main.should_explain("Safe") is False

    def test_none_does_not_trigger(self):
        assert gateway_main.should_explain(None) is False


class TestGatewayFusion:
    def test_danger_attaches_explanation(self, gateway_client):
        async def router(url, json=None, **kw):
            if url == gateway_main.NLP_URL:
                return _resp({
                    "trust_score": 3, "label": "Danger",
                    "reason": "偵測為釣魚", "category": "phishing",
                    "confidence": 0.99, "scam_probability": 1.0,
                })
            if url == gateway_main.EXPLAIN_URL:
                return _resp({"explanation": "這是假冒銀行的釣魚頁面，請勿輸入個資。", "source": "fallback"})
            raise AssertionError(f"unexpected url {url}")

        gateway_client.app.state.http_client.post = AsyncMock(side_effect=router)
        r = gateway_client.post("/analyze", json={"content": "您的帳戶異常請點連結驗證"})
        assert r.status_code == 200
        data = r.json()
        assert data["label"] == "Danger"
        assert data["explanation"] == "這是假冒銀行的釣魚頁面，請勿輸入個資。"
        assert data["explanation_source"] == "fallback"

    def test_safe_does_not_call_explain(self, gateway_client):
        calls = []

        async def router(url, json=None, **kw):
            calls.append(url)
            if url == gateway_main.NLP_URL:
                return _resp({
                    "trust_score": 96, "label": "Safe",
                    "reason": "未偵測到明顯詐騙特徵", "category": "safe",
                    "confidence": 0.98, "scam_probability": 0.02,
                })
            raise AssertionError(f"unexpected url {url}")

        gateway_client.app.state.http_client.post = AsyncMock(side_effect=router)
        r = gateway_client.post("/analyze", json={"content": "明天三點開會記得帶筆電"})
        assert r.status_code == 200
        assert "explanation" not in r.json()
        assert gateway_main.EXPLAIN_URL not in calls

    def test_explain_failure_is_non_fatal(self, gateway_client):
        async def router(url, json=None, **kw):
            if url == gateway_main.NLP_URL:
                return _resp({
                    "trust_score": 5, "label": "Danger",
                    "reason": "偵測為投資詐騙", "category": "investment_scam",
                    "confidence": 0.97, "scam_probability": 0.95,
                })
            raise ConnectionError("explain service down")

        gateway_client.app.state.http_client.post = AsyncMock(side_effect=router)
        r = gateway_client.post("/analyze", json={"content": "老師帶你飆股穩賺不賠"})
        # 解釋服務掛掉不應影響主要分析結果
        assert r.status_code == 200
        assert r.json()["label"] == "Danger"
