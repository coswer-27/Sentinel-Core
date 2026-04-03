import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
import uvicorn

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

_repo_root = Path(__file__).resolve().parent.parent
_link_root = Path(__file__).resolve().parent
sys.path.insert(0, str(_repo_root))
sys.path.insert(0, str(_link_root))

from common.models import BatchUrlRequest

from url_scan import URLDetector
from schemas import BatchUrlResponse, UrlScanResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


limiter = Limiter(key_func=get_remote_address)


def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    logger.warning("[Sentinel] Rate limit exceeded: %s", request.client)
    return JSONResponse(
        status_code=429,
        content={"detail": f"請求過於頻繁，請稍後再試。限制：{exc.detail}"},
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.url_detector = URLDetector()
    yield


app = FastAPI(title="Sentinel Link Scanner", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "service_link_scanner"}


@app.post("/analyze/links", response_model=BatchUrlResponse)
@limiter.limit("30/minute")
async def analyze_links(body: BatchUrlRequest, request: Request):
    url_detector: URLDetector = request.app.state.url_detector
    try:
        rows = await url_detector.analyze_batch(body.urls)
    except Exception as e:
        logger.error("[Sentinel] analyze_batch 失敗: %s", e, exc_info=True)
        rows = [
            {
                "final_url": u,
                "trust_score": 50,
                "label": "Suspicious",
                "reason": "服務暫時無法分析此連結，請稍後再試",
            }
            for u in body.urls
        ]
    return BatchUrlResponse(
        results=[UrlScanResult(url=u, **r) for u, r in zip(body.urls, rows)]
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8002, reload=True)
