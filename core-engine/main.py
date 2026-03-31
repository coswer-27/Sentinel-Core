import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from detectors import TextDetector
from schemas import SecurityRequest, SecurityResponse

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://127.0.0.1,null"
).split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.detector = TextDetector()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)


@app.post("/analyze", response_model=SecurityResponse)
async def analyze(request: SecurityRequest, req: Request):
    print(f"🔮 AI 正在分析語意: {request.content}")
    result = req.app.state.detector.analyze(request.content)
    return SecurityResponse(
        request_id=request.request_id,
        label="Danger" if result["is_danger"] else "Safe",
        trust_score=result["trust_score"],
        reason=result["reason"]
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
