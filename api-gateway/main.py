import logging
import os
import uvicorn
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NLP_URL = os.environ.get("NLP_SERVICE_URL", "http://127.0.0.1:8001/analyze")

limiter = Limiter(key_func=get_remote_address)


def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    logger.warning("[Gateway] Rate limit exceeded: %s", request.client)
    return JSONResponse(
        status_code=429,
        content={"detail": f"請求過於頻繁，請稍後再試。限制：{exc.detail}"},
    )


class AnalyzeRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    url: Optional[str] = None  # v2.1 核心改動
    timestamp: Optional[str] = None

    @field_validator("content")
    @classmethod
    def strip_and_check(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("content 不可為空白")
        return v


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
@limiter.limit("10/minute")
async def gateway(request: Request, body: AnalyzeRequest):
    logger.info(f"[Gateway] 收到請求 - 網址: {body.url}, 時間: {body.timestamp}")
    try:
        resp = await request.app.state.http_client.post(
            NLP_URL, json=body.model_dump()
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
