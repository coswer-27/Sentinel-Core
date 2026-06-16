import logging
import os
import uvicorn
import httpx
import sys
from datetime import datetime, timezone
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
from behavior_engine import score_behavior, fuse
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from common.models import AnalyzeRequest, BatchUrlRequest, BehaviorRequest
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NLP_URL = os.environ.get("NLP_SERVICE_URL", "http://127.0.0.1:8001/analyze")
URL_SERVICE_URL = os.environ.get("URL_SERVICE_URL", "http://127.0.0.1:8002/analyze/links")
EXPLAIN_URL = os.environ.get("EXPLAIN_SERVICE_URL", "http://127.0.0.1:8004/explain")


def should_explain(label: str | None) -> bool:
    """高風險（Danger）才觸發 LLM 可解釋層，避免對安全內容浪費呼叫。"""
    return label == "Danger"


async def _attach_explanation(client, nlp_res: dict, body) -> dict:
    """呼叫 service_explain 取得人類可讀解釋並掛到回應上；失敗則靜默略過。"""
    payload = {
        "nlp": {
            "category": nlp_res.get("category"),
            "trust_score": nlp_res.get("trust_score"),
            "confidence": nlp_res.get("confidence"),
        },
        "text_snippet": body.content,
    }
    if body.url:
        payload["url"] = {"final_url": str(body.url)}
    try:
        resp = await client.post(EXPLAIN_URL, json=payload)
        resp.raise_for_status()
        exp = resp.json()
        return {
            **nlp_res,
            "explanation": exp.get("explanation"),
            "explanation_source": exp.get("source"),
        }
    except Exception as e:
        logger.warning("[Gateway] 解釋服務呼叫失敗，略過: %s", e)
        return nlp_res

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
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
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

        # --- v3.0 高風險 → LLM 可解釋層 ---
        if should_explain(nlp_res.get("label")):
            nlp_res = await _attach_explanation(
                request.app.state.http_client, nlp_res, body
            )

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

@app.post("/analyze/links")
@limiter.limit("60/minute")
async def gateway_analyze_links(request: Request, body: BatchUrlRequest, background_tasks: BackgroundTasks):
    logger.info("[Gateway] 收到連結掃描請求 - 共 %d 個 URL", len(body.urls))
    try:
        resp = await request.app.state.http_client.post(
            URL_SERVICE_URL, json=body.model_dump()
        )
        resp.raise_for_status()
        data = resp.json()

        # --- v3.0 紀錄被標記的連結掃描（僅非 Safe，避免 hover 大量安全連結灌爆 DB）---
        ts = datetime.now(timezone.utc).isoformat()
        for item in data.get("results", []):
            if item.get("label") and item["label"] != "Safe":
                background_tasks.add_task(
                    safe_log_scan,
                    content=item.get("url") or "",
                    url=item.get("url"),
                    score=item.get("trust_score", 0),
                    label=item["label"],
                    reason=item.get("reason", ""),
                    ts=ts,
                )
        return data
    except httpx.TimeoutException:
        logger.warning("[Gateway] URL 掃描服務回應逾時")
        raise HTTPException(status_code=504, detail="URL 掃描服務回應逾時")
    except httpx.ConnectError:
        logger.error("[Gateway] 無法連線至 URL 掃描服務: %s", URL_SERVICE_URL)
        raise HTTPException(status_code=503, detail="URL 掃描服務離線")
    except httpx.HTTPStatusError as e:
        logger.error("[Gateway] URL 掃描服務回傳錯誤: %s", e.response.status_code)
        raise HTTPException(status_code=502, detail=f"URL 掃描服務內部錯誤: {e.response.status_code}")
    except Exception as e:
        logger.exception("[Gateway] 未預期錯誤: %s", e)
        raise HTTPException(status_code=500, detail="內部錯誤")

@app.post("/analyze/behavior")
@limiter.limit("60/minute")
async def gateway_analyze_behavior(request: Request, body: BehaviorRequest, background_tasks: BackgroundTasks):
    """
    v3.1 頁面行為偵測 + 多引擎融合：
    行為規則評分 → （可選）掃描頁面 URL → 融合 → Danger 時呼叫 explain 並記錄。
    """
    feats = body.features.model_dump()
    beh = score_behavior(feats)
    page_url = str(body.url) if body.url else None
    logger.info("[Gateway] 行為分析 - URL: %s, 行為分數: %s", page_url, beh["score"])

    url_trust = None
    url_label = None
    url_info = None
    if page_url:
        try:
            resp = await request.app.state.http_client.post(
                URL_SERVICE_URL, json={"urls": [page_url], "follow_redirects": False}
            )
            resp.raise_for_status()
            r = (resp.json().get("results") or [None])[0]
            if r:
                url_trust = r.get("trust_score")
                url_label = r.get("label")
                url_info = {
                    "label": url_label,
                    "final_url": r.get("final_url"),
                    "hop_count": r.get("hop_count"),
                }
        except Exception as e:
            logger.warning("[Gateway] 行為分析的 URL 掃描失敗，改為僅行為評分: %s", e)

    fusion = fuse(beh["score"], url_trust, url_label, critical=beh["critical"])
    result = {
        "behavior_score": beh["score"],
        "behavior_flags": beh["flags"],
        "url": url_info,
        "fusion_score": fusion["fusion_score"],
        "trust_score": fusion["trust_score"],
        "label": fusion["label"],
    }

    if fusion["label"] == "Danger":
        # 可解釋層（service_explain 的 ExplainRequest 已支援 behavior 欄位）
        payload = {"behavior": {"score": beh["score"], "flags": beh["flags"]}}
        if url_info:
            payload["url"] = {
                "label": url_info.get("label"),
                "final_url": url_info.get("final_url"),
                "hop_count": url_info.get("hop_count"),
            }
        try:
            eresp = await request.app.state.http_client.post(EXPLAIN_URL, json=payload)
            eresp.raise_for_status()
            exp = eresp.json()
            result["explanation"] = exp.get("explanation")
            result["explanation_source"] = exp.get("source")
        except Exception as e:
            logger.warning("[Gateway] 行為分析解釋呼叫失敗，略過: %s", e)

        # 記錄高風險頁面（併入 popup 近期掃描/統計）
        reason = "、".join(beh["flags"]) or "頁面行為異常"
        background_tasks.add_task(
            safe_log_scan,
            content=f"[頁面行為] {page_url or ''}",
            url=page_url,
            score=fusion["trust_score"],
            label="Danger",
            reason=reason,
            ts=datetime.now(timezone.utc).isoformat(),
        )

    return result

@app.get("/recent")
async def get_recent(limit: int = 8):
    """
    v3.0 近期掃描：回傳最近 N 筆掃描紀錄（供 popup 主控台顯示）。
    content 截斷至 80 字，避免回傳過長內容。
    """
    import aiosqlite
    from database import DB_PATH

    limit = max(1, min(int(limit), 50))
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT content, url, trust_score, label, reason, created_at "
                "FROM scan_logs ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            async with cursor:
                rows = await cursor.fetchall()
                items = []
                for row in rows:
                    item = dict(row)
                    content = item.get("content") or ""
                    item["content"] = content[:80]
                    items.append(item)
                return {"items": items}
    except Exception as e:
        logger.error("[Gateway] 讀取近期掃描失敗: %s", e)
        raise HTTPException(status_code=500, detail="無法讀取近期掃描")

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