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

# 導入資料庫邏輯 (假設 database.py 與 main.py 在同一個資料夾)
from database import init_db, log_scan

async def safe_log_scan(*args, **kwargs):
    """
    封裝 log_scan 並加上異常處理，確保資料庫錯誤不會影響 API 回應
    """
    try:
        await log_scan(*args, **kwargs)
    except Exception as e:
        logger.error("[Gateway] 背景記錄日誌失敗: %s", e)
from rules_engine import engine
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
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
# 修改後 (Fix 08)
RATE_LIMIT_STR = os.environ.get("GATEWAY_RATE_LIMIT", "30/minute")

def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    logger.warning("[Gateway] Rate limit exceeded: %s", request.client)
    return JSONResponse(
        status_code=429,
        content={"detail": f"請求過於頻繁，請稍後再試。限制：{exc.detail}"},
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- v2.3 初始化資料庫 ---
    try:
        await init_db()
        logger.info("[Gateway] 資料庫初始化成功")
    except Exception as e:
        logger.error("[Gateway] 資料庫初始化失敗: %s", e)
    
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
async def gateway(request: Request, body: AnalyzeRequest, background_tasks: BackgroundTasks):
    logger.info("[Gateway] 收到請求 - 網址: %s, 時間: %s", body.url, body.timestamp)

    # --- v2.2 規則引擎攔截 ---
    rule_result = engine.check(body.content, body.url)
    
    if rule_result.get("hit"):
        reason_str = f"[快速攔截] {rule_result['reason']}"
        res = {
            "trust_score": rule_result["trust_score"],
            "label": "Danger",
            "reason": reason_str
        }
        
        # --- v2.3 紀錄規則攔截日誌 (改為背景任務) ---
        background_tasks.add_task(
            safe_log_scan,
            content=body.content,
            url=str(body.url) if body.url else None,
            score=res["trust_score"],
            label=res["label"],
            reason=res["reason"],
            ts=body.timestamp
        )
        
        logger.info("[Gateway] 規則攔截成功並已加入背景記錄任務")
        return res

    # --- 若規則未命中，走原本的 NLP 流程 ---
    try:
        resp = await request.app.state.http_client.post(
            NLP_URL, json=body.model_dump(mode='json')
        )
        resp.raise_for_status()
        nlp_res = resp.json()

        # --- v2.3 紀錄 NLP 分析結果日誌 (改為背景任務) ---
        background_tasks.add_task(
            safe_log_scan,
            content=body.content,
            url=str(body.url) if body.url else None,
            score=nlp_res["trust_score"],
            label=nlp_res["label"],
            reason=nlp_res["reason"],
            ts=body.timestamp
        )

        return nlp_res

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

@app.get("/stats")
async def get_stats():
    """
    v2.3 統計接口：回傳資料庫中的總掃描次數與平均信任分數
    """
    import aiosqlite
    from database import DB_PATH  # 這裡移除「.」，因為你已經在 sys.path 注入了 current_dir
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT COUNT(*) as total, AVG(trust_score) as avg_score FROM scan_logs"
            )
            async with cursor:
                row = await cursor.fetchone()
                # 處理資料庫為空的情況，避免回傳 null
                result = dict(row) if row else {"total": 0, "avg_score": 0}
                
                # 格式化平均分數（取小數點後兩位）
                if result["avg_score"] is None:
                    result["avg_score"] = 0
                else:
                    result["avg_score"] = round(result["avg_score"], 2)
                    
                return result
    except Exception as e:
        logger.error("[Gateway] 讀取統計資料失敗: %s", e)
        raise HTTPException(status_code=500, detail="無法讀取統計數據")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)