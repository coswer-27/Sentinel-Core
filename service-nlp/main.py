import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from detectors.bert_engine import BertDetector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TRUST_THRESHOLD = 55


class AnalyzeRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)

    @field_validator("content")
    @classmethod
    def strip_and_check(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("content 不可為空白")
        return v


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
        trust_score = app.state.detector.analyze(body.content)
    except RuntimeError as e:
        logger.error("[NLP] 推論失敗: %s", e)
        raise HTTPException(status_code=500, detail=f"推論失敗: {e}")
    return {
        "trust_score": trust_score,
        "label": "Danger" if trust_score <= TRUST_THRESHOLD else "Safe",
        "reason": f"AI 分析信任度為 {trust_score}%",
    }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
