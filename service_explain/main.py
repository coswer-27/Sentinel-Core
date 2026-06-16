import logging
import sys
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

# 將當前目錄與專案根目錄加入路徑
current_dir = Path(__file__).parent
root_dir = current_dir.parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from explainer.llm_explainer import explain  # noqa: E402

try:
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=root_dir / ".env")
except Exception:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NlpSignal(BaseModel):
    category: Optional[str] = None
    trust_score: Optional[int] = None
    confidence: Optional[float] = None


class UrlSignal(BaseModel):
    label: Optional[str] = None
    reason: Optional[str] = None
    hop_count: Optional[int] = None
    final_url: Optional[str] = None


class BehaviorSignal(BaseModel):
    score: Optional[int] = None
    flags: Optional[list[str]] = None


class ExplainRequest(BaseModel):
    nlp: Optional[NlpSignal] = None
    url: Optional[UrlSignal] = None
    behavior: Optional[BehaviorSignal] = None
    text_snippet: Optional[str] = None


app = FastAPI(title="Sentinel Explain Service")


@app.get("/health")
async def health():
    import os

    return {"status": "ok", "llm_enabled": bool(os.getenv("GEMINI_API_KEYS") or os.getenv("GEMINI_API_KEY"))}


@app.post("/explain")
async def explain_endpoint(body: ExplainRequest):
    data = body.model_dump(exclude_none=True)
    result = explain(data)
    logger.info("[Explain] 來源=%s", result.get("source"))
    return result


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8004)
