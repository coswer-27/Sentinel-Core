import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
import uvicorn

load_dotenv()

from detectors import URLDetector
from schemas import BatchUrlRequest, BatchUrlResponse, UrlScanResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1,null").split(",")

limiter = Limiter(key_func=get_remote_address)


def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    logger.warning("[URL Service] Rate limit exceeded: %s", request.client)
    return JSONResponse(
        status_code=429,
        content={"detail": f"請求過於頻繁，請稍後再試。限制：{exc.detail}"},
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.url_detector = URLDetector()
    yield


app = FastAPI(title="Sentinel URL Scanner Service", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "url-scanner"}


@app.post("/analyze/links", response_model=BatchUrlResponse)
@limiter.limit("30/minute")
async def analyze_links(body: BatchUrlRequest, request: Request):
    url_detector: URLDetector = request.app.state.url_detector
    try:
        rows = await url_detector.analyze_batch(body.urls)
    except Exception as e:
        logger.error("[URL Service] analyze_batch 失敗: %s", e)
        rows = [
            {
                "final_url": u,
                "trust_score": 50,
                "label": "Suspicious",
                "reason": f"無法分析此連結：{str(e)}",
            }
            for u in body.urls
        ]
    return BatchUrlResponse(
        results=[UrlScanResult(url=u, **r) for u, r in zip(body.urls, rows)]
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8002, reload=True)
