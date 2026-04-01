import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
import uvicorn

load_dotenv()

from detectors import TextDetector, URLDetector
from schemas import (
    BatchUrlRequest,
    BatchUrlResponse,
    SecurityRequest,
    SecurityResponse,
    UrlScanResult,
)

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://127.0.0.1,null"
).split(",")

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.detector = TextDetector()
    app.state.url_detector = URLDetector()
    yield


app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)



@app.post("/analyze", response_model=SecurityResponse)
@limiter.limit("30/minute")
async def analyze(body: SecurityRequest, request: Request):
    print(f"🔮 AI 正在分析語意: {body.content}")
    result = request.app.state.detector.analyze(body.content)
    label = result.get("label")
    if label is None:
        label = "Danger" if result.get("is_danger") else "Safe"
    return SecurityResponse(
        request_id=body.request_id,
        label=label,
        trust_score=result["trust_score"],
        reason=result["reason"],
    )


@app.post("/analyze/links", response_model=BatchUrlResponse)
async def analyze_links(body: BatchUrlRequest, request: Request):
    url_detector: URLDetector = request.app.state.url_detector
    try:
        rows = await url_detector.analyze_batch(body.urls)
    except Exception as e:
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
        results=[
            UrlScanResult(url=u, **r) for u, r in zip(body.urls, rows)
        ]
    )



if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
