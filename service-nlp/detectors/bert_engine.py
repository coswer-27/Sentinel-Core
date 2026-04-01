from transformers import pipeline

class BertDetector:
    def __init__(self):
        print("⏳ [NLP] 載入 BERT 模型中...")
        self.classifier = pipeline("sentiment-analysis", model="nlptown/bert-base-multilingual-uncased-sentiment")
        self.weights = {"1 star": 0, "2 stars": 25, "3 stars": 50, "4 stars": 75, "5 stars": 100}

    def analyze(self, text):
        results = self.classifier(text, top_k=5)
        prob_dict = {res['label']: res['score'] for res in results}
        score = sum(prob_dict[label] * self.weights[label] for label in self.weights)
        return int(round(score))