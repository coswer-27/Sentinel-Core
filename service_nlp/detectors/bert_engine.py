import logging
from transformers import pipeline

logger = logging.getLogger(__name__)


class BertDetector:
    def __init__(self):
        logger.info("[NLP] 載入 BERT 模型中...")
        try:
            self.classifier = pipeline(
                "sentiment-analysis",
                model="nlptown/bert-base-multilingual-uncased-sentiment",
            )
        except Exception as e:
            raise RuntimeError(f"BERT 模型載入失敗: {e}") from e
        self.weights = {
            "1 star": 0,
            "2 stars": 25,
            "3 stars": 50,
            "4 stars": 75,
            "5 stars": 100,
        }

    def analyze(self, text: str) -> int:
        if not text or not text.strip():
            return 50

        try:
            results = self.classifier(text, top_k=5)
        except Exception as e:
            raise RuntimeError(f"BERT 推論失敗: {e}") from e

        prob_dict = {res["label"]: res["score"] for res in results}
        score = sum(
            prob_dict.get(label, 0.0) * weight
            for label, weight in self.weights.items()
        )
        return int(round(score))
