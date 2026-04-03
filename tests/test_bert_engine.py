import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# transformers is mocked in conftest.py before this file is collected,
# but setdefault here ensures isolation if this file is run standalone.
sys.modules.setdefault("transformers", MagicMock())

sys.path.insert(0, str(Path(__file__).parent.parent / "service_nlp"))

from detectors.bert_engine import BertDetector  # noqa: E402


@pytest.fixture
def detector():
    with patch("detectors.bert_engine.pipeline") as mock_pipeline:
        mock_classifier = MagicMock()
        mock_pipeline.return_value = mock_classifier
        d = BertDetector()
        d._mock_classifier = mock_classifier
        yield d


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestBertDetectorInit:
    def test_init_calls_pipeline_with_correct_args(self):
        with patch("detectors.bert_engine.pipeline") as mock_pipeline:
            mock_pipeline.return_value = MagicMock()
            BertDetector()
            mock_pipeline.assert_called_once_with(
                "sentiment-analysis",
                model="nlptown/bert-base-multilingual-uncased-sentiment",
            )

    def test_init_raises_runtime_error_on_load_failure(self):
        with patch("detectors.bert_engine.pipeline", side_effect=OSError("model not found")):
            with pytest.raises(RuntimeError, match="BERT 模型載入失敗"):
                BertDetector()


# ---------------------------------------------------------------------------
# analyse()
# ---------------------------------------------------------------------------

class TestBertDetectorAnalyze:
    def test_empty_text_returns_neutral_50(self, detector):
        assert detector.analyze("") == 50

    def test_whitespace_only_returns_neutral_50(self, detector):
        assert detector.analyze("   \t\n  ") == 50

    def test_all_weight_on_five_stars_returns_100(self, detector):
        detector._mock_classifier.return_value = [
            {"label": "5 stars", "score": 1.0},
            {"label": "4 stars", "score": 0.0},
            {"label": "3 stars", "score": 0.0},
            {"label": "2 stars", "score": 0.0},
            {"label": "1 star",  "score": 0.0},
        ]
        assert detector.analyze("perfect content") == 100

    def test_all_weight_on_one_star_returns_0(self, detector):
        detector._mock_classifier.return_value = [
            {"label": "1 star",  "score": 1.0},
            {"label": "2 stars", "score": 0.0},
            {"label": "3 stars", "score": 0.0},
            {"label": "4 stars", "score": 0.0},
            {"label": "5 stars", "score": 0.0},
        ]
        assert detector.analyze("terrible scam") == 0

    def test_three_stars_returns_50(self, detector):
        detector._mock_classifier.return_value = [
            {"label": "3 stars", "score": 1.0},
            {"label": "1 star",  "score": 0.0},
            {"label": "2 stars", "score": 0.0},
            {"label": "4 stars", "score": 0.0},
            {"label": "5 stars", "score": 0.0},
        ]
        assert detector.analyze("neutral content") == 50

    def test_mixed_probabilities_weighted_average(self, detector):
        # 0.8*100 + 0.1*75 + 0.05*50 + 0.03*25 + 0.02*0 = 90.75 → rounds to 91
        detector._mock_classifier.return_value = [
            {"label": "5 stars", "score": 0.80},
            {"label": "4 stars", "score": 0.10},
            {"label": "3 stars", "score": 0.05},
            {"label": "2 stars", "score": 0.03},
            {"label": "1 star",  "score": 0.02},
        ]
        assert detector.analyze("mostly good article") == 91

    def test_result_is_integer(self, detector):
        detector._mock_classifier.return_value = [
            {"label": "5 stars", "score": 0.5},
            {"label": "1 star",  "score": 0.5},
            {"label": "2 stars", "score": 0.0},
            {"label": "3 stars", "score": 0.0},
            {"label": "4 stars", "score": 0.0},
        ]
        result = detector.analyze("mixed content")
        assert isinstance(result, int)

    def test_inference_failure_raises_runtime_error(self, detector):
        detector._mock_classifier.side_effect = Exception("BERT exploded")
        with pytest.raises(RuntimeError, match="BERT 推論失敗"):
            detector.analyze("some text")
