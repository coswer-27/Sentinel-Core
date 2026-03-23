from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from schemas import SecurityRequest, SecurityResponse
import uvicorn

app = FastAPI()

class SecurityRequest(BaseModel):
    request_id: str
    payload_type: str
    content: str
    url: Optional[str] = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # 允許所有網域來源 (開發測試用)
    allow_credentials=True,
    allow_methods=["*"],           # 允許所有 HTTP 方法 (GET, POST, etc.)
    allow_headers=["*"],           # 允許所有 Header
)

@app.post("/analyze", response_model=SecurityResponse)
async def analyze(request: SecurityRequest):
    # 預設狀態
    score = 0.95
    label = "Safe"
    reason = "此內容目前看起來是安全的。"

    # 模擬簡單的關鍵字偵測
    scam_keywords = ["匯款", "轉帳", "身分證", "中獎", "洗錢"]
    
    # 檢查內容是否包含關鍵字
    found_keywords = [word for word in scam_keywords if word in request.content]
    
    if found_keywords:
        score = 0.15
        label = "Danger"
        reason = f"偵測到可疑關鍵字：{', '.join(found_keywords)}。這可能是社交工程詐騙。"
    
    return SecurityResponse(
        request_id=request.request_id,
        trust_score=score,
        label=label,
        reason=reason # 這裡現在會動態變更了
    )

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)