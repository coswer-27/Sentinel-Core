import logging
from pathlib import Path

import torch
import torch.nn.functional as F
from transformers import AutoModelForSequenceClassification, AutoTokenizer

logger = logging.getLogger(__name__)

# fine-tuned 模型存放位置（由 service_nlp/train/fine_tune.py 產生）
MODEL_DIR = Path(__file__).resolve().parent / "model"

# 類別 → 人類可讀說明（供 reason 與前端使用）
CATEGORY_LABELS = {
    "phishing": "假冒官方/平台要求驗證帳號（釣魚）",
    "investment_scam": "假投資、飆股、虛擬幣詐騙",
    "romance_scam": "感情詐騙話術",
    "parcel_scam": "假包裹/物流通知詐騙",
    "gov_impersonation": "假冒政府機關（假檢警）",
    "safe": "未偵測到明顯詐騙特徵",
}

MAX_LEN = 128


class BertDetector:
    """
    fine-tuned 6 類中文詐騙分類器。
    analyze() 回傳 dict：category / confidence / trust_score / scam_probability。
    trust_score = P(safe) * 100（越高越可信；scam 類別會偏低）。
    """

    def __init__(self):
        if not (MODEL_DIR / "config.json").exists():
            raise RuntimeError(
                f"找不到 fine-tuned 模型於 {MODEL_DIR}，"
                "請先執行 `python service_nlp/train/fine_tune.py` 進行訓練。"
            )
        logger.info("[NLP] 載入 fine-tuned 詐騙分類模型中: %s", MODEL_DIR)
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
            self.model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
            self.model.eval()
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model.to(self.device)
            self.id2label = self.model.config.id2label
            self.label2id = self.model.config.label2id
        except Exception as e:
            raise RuntimeError(f"詐騙分類模型載入失敗: {e}") from e

    def analyze(self, text: str) -> dict:
        if not text or not text.strip():
            return {
                "category": "safe",
                "category_desc": CATEGORY_LABELS["safe"],
                "confidence": 1.0,
                "trust_score": 50,
                "scam_probability": 0.0,
            }

        try:
            enc = self.tokenizer(
                text, truncation=True, max_length=MAX_LEN, return_tensors="pt"
            ).to(self.device)
            with torch.no_grad():
                logits = self.model(**enc).logits
            probs = F.softmax(logits, dim=-1)[0]
        except Exception as e:
            raise RuntimeError(f"詐騙分類推論失敗: {e}") from e

        top_id = int(torch.argmax(probs).item())
        category = self.id2label[top_id]
        confidence = float(probs[top_id].item())

        safe_id = self.label2id.get("safe")
        p_safe = float(probs[safe_id].item()) if safe_id is not None else 0.0
        scam_probability = 1.0 - p_safe
        trust_score = int(round(p_safe * 100))

        return {
            "category": category,
            "category_desc": CATEGORY_LABELS.get(category, category),
            "confidence": round(confidence, 4),
            "trust_score": trust_score,
            "scam_probability": round(scam_probability, 4),
        }
