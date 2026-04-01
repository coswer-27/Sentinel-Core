import uvicorn
from fastapi import FastAPI
from detectors.bert_engine import BertDetector

app = FastAPI(title="Sentinel NLP Service")
detector = BertDetector()

@app.post("/analyze")
async def nlp_endpoint(body: dict):
    content = body.get("content", "")
    trust_score = detector.analyze(content)
    return {
        "trust_score": trust_score,
        "label": "Danger" if trust_score <= 55 else "Safe",
        "reason": f"AI 分析信任度為 {trust_score}%"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)