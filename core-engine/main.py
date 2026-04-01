import time
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from transformers import pipeline

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

print("⏳ [System] 正在初始化 BERT 模型...")
start_time = time.time()

classifier = None
try:
    classifier = pipeline("sentiment-analysis", model="nlptown/bert-base-multilingual-uncased-sentiment")
    print(f"✅ [System] 模型載入成功！耗時: {time.time() - start_time:.2f} 秒")
except Exception as e:
    print(f"❌ [System] 模型載入失敗: {e}")


class SecurityRequest(BaseModel):
    content: str = Field(..., max_length=5000)


@app.post("/analyze")
@limiter.limit("30/minute")
async def analyze(request: Request, body: SecurityRequest):  # noqa: ARG001
    if classifier is None:
        raise HTTPException(status_code=503, detail="AI 模型未就緒，請稍後再試。")

    print(f"🔮 AI 深度分析中: {body.content[:20]}...")

    # 取得 Top_k=5 的所有星等機率
    raw_results = classifier(body.content, top_k=5)
    prob_dict = {res['label']: res['score'] for res in raw_results}

    # 定義 0-100 的權重
    weights = {
        "1 star": 0,
        "2 stars": 25,
        "3 stars": 50,
        "4 stars": 75,
        "5 stars": 100
    }

    # 計算加權得分並轉為整數百分比
    # Formula: Score = Σ (Prob_i * Weight_i)
    raw_score = sum(prob_dict[label] * weights[label] for label in weights)
    trust_score_pct = int(round(raw_score))
    trust_score_pct = max(5, min(95, trust_score_pct))

    is_danger = trust_score_pct <= 55
    risk_pct = 100 - trust_score_pct

    return {
        "label": "Danger" if is_danger else "Safe",
        "trust_score": trust_score_pct,
        "risk_percentage": risk_pct,
        "reason": f"AI 偵測到高達 {risk_pct}% 的負面語意特徵，具備潛在誘導風險。" if is_danger else "語意特徵正常。"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
