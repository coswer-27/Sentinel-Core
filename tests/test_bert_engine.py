"""
BertDetector 整合測試（使用真實 fine-tuned 模型）。

若模型尚未訓練（detectors/model 不存在），整個模組會被 skip，
不影響其他測試。完整驗證請另跑：
    python service_nlp/train/smoke_test_engine.py
"""
import sys
from pathlib import Path

import pytest

_service_nlp_path = str(Path(__file__).parent.parent / "service_nlp")
if _service_nlp_path not in sys.path:
    sys.path.insert(0, _service_nlp_path)

from detectors.bert_engine import BertDetector, MODEL_DIR, CATEGORY_LABELS  # noqa: E402

pytestmark = pytest.mark.skipif(
    not (MODEL_DIR / "config.json").exists(),
    reason="fine-tuned 模型尚未訓練；請先執行 service_nlp/train/fine_tune.py",
)


@pytest.fixture(scope="module")
def detector():
    return BertDetector()


class TestBertDetectorInit:
    def test_missing_model_raises_runtime_error(self, tmp_path, monkeypatch):
        import detectors.bert_engine as engine
        monkeypatch.setattr(engine, "MODEL_DIR", tmp_path / "nonexistent")
        with pytest.raises(RuntimeError, match="找不到 fine-tuned 模型"):
            engine.BertDetector()


class TestBertDetectorAnalyze:
    def test_empty_text_returns_safe_neutral(self, detector):
        r = detector.analyze("")
        assert r["category"] == "safe"
        assert r["trust_score"] == 50

    def test_whitespace_returns_safe_neutral(self, detector):
        assert detector.analyze("   \t\n ")["category"] == "safe"

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("您的網路銀行帳號偵測到異常登入，請點擊連結驗證身分", "phishing"),
            ("老師帶你買飆股穩賺不賠，加LINE進群免費領取明牌", "investment_scam"),
            ("親愛的我是駐外軍官，因戰地無法領薪需要你幫忙代收包裹", "romance_scam"),
            ("您的包裹因地址不全無法配送，請點連結更新收件資訊", "parcel_scam"),
            ("我是地檢署檢察官，您涉及洗錢案請將存款轉入安全帳戶", "gov_impersonation"),
            ("明天下午三點開會，地點在三樓會議室，記得帶筆電", "safe"),
        ],
    )
    def test_six_categories(self, detector, text, expected):
        assert detector.analyze(text)["category"] == expected

    def test_scam_has_low_trust_score(self, detector):
        r = detector.analyze("您的帳戶異常請立即點擊連結驗證否則凍結")
        assert r["trust_score"] < 50
        assert r["scam_probability"] > 0.5

    def test_safe_has_high_trust_score(self, detector):
        r = detector.analyze("今天天氣很好，下午一起去公園散步吧")
        assert r["trust_score"] > 50

    def test_return_shape(self, detector):
        r = detector.analyze("測試內容")
        for key in ("category", "category_desc", "confidence", "trust_score", "scam_probability"):
            assert key in r
        assert r["category"] in CATEGORY_LABELS
        assert 0.0 <= r["confidence"] <= 1.0
        assert 0 <= r["trust_score"] <= 100
