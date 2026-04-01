import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from transformers import pipeline

app = FastAPI()

# --- [關鍵 1] CORS 最強防禦：解決 OPTIONS / 405 問題 ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],  # 務必維持 ["*"] 才能自動處理 OPTIONS
    allow_headers=["*"],
)

# --- [關鍵 2] 模型預載入：解決啟動過慢問題 ---
print("⏳ [System] 正在初始化 BERT 模型...")
start_time = time.time()

# 這裡使用全域變數，確保啟動即就緒
try:
    # 使用與你 Log 中對應的模型
    classifier = pipeline("sentiment-analysis", model="nlptown/bert-base-multilingual-uncased-sentiment")
    print(f"✅ [System] 模型載入成功！耗時: {time.time() - start_time:.2f} 秒")
except Exception as e:
    print(f"❌ [System] 模型載入失敗: {e}")

class AnalysisRequest(BaseModel):
    content: str

@app.post("/analyze")
async def analyze(data: AnalysisRequest):
    print(f"📡 收到分析請求，內容長度: {len(data.content)}")
    
    # 直接使用全域的 classifier
    result = classifier(data.content)
    
    # 範例邏輯：將星等轉為分數
    label = result[0]['label'] # 例如 "1 star"
    stars = int(label.split()[0])
    trust_score = stars * 20
    
    return {
        "label": "Danger" if stars <= 2 else "Safe",
        "trust_score": trust_score,
        "reason": f"AI 偵測到語意情緒為 {label}，判定風險權重為 {100 - trust_score}%。"
    }

if __name__ == "__main__":
    import uvicorn
    # 建議直接執行 python main.py，或者用 uvicorn main:app --reload
    uvicorn.run(app, host="127.0.0.1", port=8000)