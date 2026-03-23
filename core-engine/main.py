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
    print(f"🔮 AI 正在分析語意: {request.content}")
    
    # 執行 AI 推論
    # result 會回傳 [{'label': '1 star', 'score': 0.85}]
    # 1-2 stars 代表負面/激進/異常；4-5 stars 代表中性/正面
    prediction = classifier(request.content)[0]
    label = prediction['label']
    confidence = prediction['score']

    # 判斷邏輯：如果語意過於負面或激進 (1-2 stars)，視為潛在威脅
    is_danger = label in ["1 star", "2 stars"]
    
    # 計算信任分數 (將 AI 分數轉換為百分比)
    display_score = int(confidence * 100) if not is_danger else 20

    return {
        "label": "Danger" if is_danger else "Safe",
        "trust_score": display_score,
        "reason": f"AI 偵測到異常語意偏好 ({label})。內容可能含有強迫性或詐騙誘導。" if is_danger else "語意分析正常"
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)