from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from transformers import pipeline  # 🚀 關鍵：導入 AI 套件
import uvicorn

app = FastAPI()

# 保持 CORS 設定，讓前端能連線
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🛠️ 第一次執行會下載模型 (約 200~500MB)，請耐心等候
# 我們使用多語言 BERT 模型來分析語意偏向
print("⏳ 正在載入 AI 模型，請稍候...")
classifier = pipeline(
    "sentiment-analysis", 
    model="nlptown/bert-base-multilingual-uncased-sentiment"
)
print("✅ AI 模型載入完成！")

class SecurityRequest(BaseModel):
    content: str

@app.post("/analyze")
async def analyze(request: SecurityRequest):
    print(f"🔮 AI 深度分析中: {request.content[:20]}...")
    
    # 1. 取得 Top_k=5 的所有星等機率
    raw_results = classifier(request.content, top_k=5)
    prob_dict = {res['label']: res['score'] for res in raw_results}
    
    # 2. 定義 0-100 的權重
    weights = {
        "1 star": 0,    # 極度危險
        "2 stars": 25,
        "3 stars": 50,
        "4 stars": 75,
        "5 stars": 100   # 極度安全
    }
    
    # 3. 計算加權得分並轉為「整數百分比」
    # Formula: Score = Σ (Prob_i * Weight_i)
    raw_score = sum(prob_dict[label] * weights[label] for label in weights)
    trust_score_pct = int(round(raw_score)) # 四捨五入成整數
    
    # 限制在 5% 到 95% 之間，避免 UI 邊界不好看
    trust_score_pct = max(5, min(95, trust_score_pct))
    
    # 4. 判斷 Danger 門檻 (建議設在 50% 或 55%)
    is_danger = trust_score_pct <= 55
    risk_pct = 100 - trust_score_pct

    return {
        "label": "Danger" if is_danger else "Safe",
        "trust_score": trust_score_pct,  # 這就是你要的整數 %
        "risk_percentage": risk_pct,     # 危險佔比 %
        "reason": f"AI 偵測到高達 {risk_pct}% 的負面語意特徵，具備潛在誘導風險。" if is_danger else "語意特徵正常。"
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)