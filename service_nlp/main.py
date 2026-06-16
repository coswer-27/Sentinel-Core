import logging
import uvicorn
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException

# 將當前目錄與專案根目錄加入路徑，確保導入正常
current_dir = Path(__file__).parent
root_dir = current_dir.parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from detectors.bert_engine import BertDetector
from common.models import AnalyzeRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        app.state.detector = BertDetector()
        logger.info("[NLP] 模型就緒")
    except RuntimeError as e:
        logger.error("[NLP] 模型載入失敗: %s", e)
        raise
    yield

app = FastAPI(title="Sentinel NLP Service", lifespan=lifespan)

@app.get("/health")
async def health():
    if not hasattr(app.state, "detector"):
        raise HTTPException(status_code=503, detail="模型未就緒")
    return {"status": "ok", "model": "loaded"}

@app.post("/analyze")
async def nlp_endpoint(body: AnalyzeRequest):
    try:
        # H-2: 雖然接收了 url/timestamp，但目前僅用於日誌紀錄 (審計)
        if body.url:
            logger.info("[NLP] 分析請求來源 URL: %s", body.url)

        result = app.state.detector.analyze(body.content)
    except RuntimeError as e:
        logger.error("[NLP] 推論失敗: %s", e)
        raise HTTPException(status_code=500, detail=f"推論失敗: {e}")

    category = result["category"]
    is_scam = category != "safe"
    confidence = result["confidence"]
    if is_scam:
        reason = f"偵測為「{result['category_desc']}」（信心 {confidence:.0%}）"
    else:
        reason = f"未偵測到明顯詐騙特徵（信心 {confidence:.0%}）"

    return {
        "trust_score": result["trust_score"],
        "label": "Danger" if is_scam else "Safe",
        "reason": reason,
        "category": category,
        "category_desc": result["category_desc"],
        "confidence": confidence,
        "scam_probability": result["scam_probability"],
    }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
