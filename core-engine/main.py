from fastapi import FastAPI
from schemas import SecurityRequest, SecurityResponse
import uvicorn

app = FastAPI()

@app.post("/analyze", response_model=SecurityResponse)
async def analyze(request: SecurityRequest):
    # 暫時的模擬邏輯
    score = 0.9
    label = "Safe"
    if "匯款" in request.content:
        score = 0.1
        label = "Danger"
    
    return SecurityResponse(
        request_id=request.request_id,
        trust_score=score,
        label=label,
        reason="Initial analysis completed"
    )

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)