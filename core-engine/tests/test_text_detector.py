from unittest.mock import patch, MagicMock

from detectors.text_detector import TextDetector


def test_analyze_danger():
    with patch("detectors.text_detector.pipeline") as mock_pipeline:
        mock_classifier = MagicMock()
        mock_classifier.return_value = [{"label": "1 star", "score": 0.9}]
        mock_pipeline.return_value = mock_classifier

        detector = TextDetector()
        result = detector.analyze("你的帳號即將被封鎖，請立即轉帳")

        assert result["is_danger"] is True
        assert result["trust_score"] == 20


def test_analyze_safe():
    with patch("detectors.text_detector.pipeline") as mock_pipeline:
        mock_classifier = MagicMock()
        mock_classifier.return_value = [{"label": "5 stars", "score": 0.95}]
        mock_pipeline.return_value = mock_classifier

        detector = TextDetector()
        result = detector.analyze("今天天氣很好")

        assert result["is_danger"] is False
        assert result["trust_score"] == 95
