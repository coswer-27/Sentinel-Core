import logging
import os
import uvicorn
import httpx
import sys
from pathlib import Path

# 將當前目錄與專案根目錄加入路徑
current_dir = Path(__file__).parent
root_dir = current_dir.parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from rules_engine import engine
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from common.models import AnalyzeRequest
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NLP_URL = os.environ.get("NLP_SERVICE_URL", "http://127.0.0.1:8001/analyze")

limiter = Limiter(key_func=get_remote_address)

# 從環境變數載入限流設定
RATE_LIMIT_STR = os.environ.get("GATEWAY_RATE_LIMIT", "10/minute")

def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    logger.warning("[Gateway] Rate limit exceeded: %s", request.client)
    return JSONResponse(
        status_code=429,
        content={"detail": f"請求過於頻繁，請稍後再試。限制：{exc.detail}"},
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(timeout=10.0)
    yield
    await app.state.http_client.aclose()

app = FastAPI(title="Sentinel Gateway", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/analyze")
@limiter.limit(RATE_LIMIT_STR)
async def gateway(request: Request, body: AnalyzeRequest):
    # v2.1 Context Log
    logger.info("[Gateway] 收到請求 - 網址: %s, 時間: %s", body.url, body.timestamp)

    # --- v2.2 規則引擎攔截 ---
    # 這裡將 body.url 轉為 str，避免 Regex 比對失敗
    rule_result = engine.check(body.content, str(body.url) if body.url else None)
    
    if rule_result.get("hit"):
        logger.info("[Gateway] 規則攔截成功: %s", rule_result["reason"])
        return {
            "trust_score": rule_result["trust_score"],
            "label": "Danger",
            "reason": f"[快速攔截] {rule_result['reason']}"
        }

    # --- 若規則未命中，才走原本的 NLP 流程 ---
    try:
        resp = await request.app.state.http_client.post(
            NLP_URL, json=body.model_dump(mode='json')
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.TimeoutException:
        logger.warning("[Gateway] NLP 服務回應逾時")
        raise HTTPException(status_code=504, detail="NLP 服務回應逾時")
    except httpx.ConnectError:
        logger.error("[Gateway] 無法連線至 NLP 服務: %s", NLP_URL)
        raise HTTPException(status_code=503, detail="NLP 服務離線")
    except httpx.HTTPStatusError as e:
        logger.error("[Gateway] NLP 服務回傳錯誤: %s", e.response.status_code)
        raise HTTPException(status_code=502, detail=f"NLP 服務內部錯誤: {e.response.status_code}")
    except Exception as e:
        logger.exception("[Gateway] 未預期錯誤: %s", e)
        raise HTTPException(status_code=500, detail="內部錯誤")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
