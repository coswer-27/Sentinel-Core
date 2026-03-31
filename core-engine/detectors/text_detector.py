from transformers import pipeline


class TextDetector:
    def __init__(self):
        print("⏳ 正在載入 AI 模型，請稍候...")
        self._classifier = pipeline(
            "sentiment-analysis",
            model="nlptown/bert-base-multilingual-uncased-sentiment"
        )
        print("✅ AI 模型載入完成！")

    def analyze(self, content: str) -> dict:
        prediction = self._classifier(content)[0]
        label = prediction['label']
        confidence = prediction['score']
        is_danger = label in ["1 star", "2 stars"]
        trust_score = int(confidence * 100) if not is_danger else 20
        reason = (
            f"AI 偵測到異常語意偏好 ({label})。內容可能含有強迫性或詐騙誘導。"
            if is_danger else "語意分析正常"
        )
        return {
            "is_danger": is_danger,
            "trust_score": trust_score,
            "reason": reason
        }
