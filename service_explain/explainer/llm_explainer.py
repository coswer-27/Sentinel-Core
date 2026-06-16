"""
LLM 可解釋推理層。

將多引擎偵測結果彙整，產生人類可讀的繁中風險解釋。
- 若環境有 GEMINI_API_KEYS → 呼叫 Google Gemini（預設 gemini-2.5-flash，可用環境變數覆寫）
- 否則 → 退回規則式（deterministic）解釋，確保離線 / 無金鑰也能 demo
兩條路徑回傳相同結構：{"explanation": str, "source": "llm" | "fallback"}
"""
import logging
import os

logger = logging.getLogger(__name__)

# 預設使用 flash（快又省）；可用環境變數改成 gemini-2.5-pro 以求最佳品質
EXPLAIN_MODEL = os.environ.get("SENTINEL_EXPLAIN_MODEL", "gemini-2.5-flash")


def _get_api_key() -> str | None:
    """讀取 GEMINI_API_KEYS（容許逗號分隔多把，取第一把非空）。"""
    raw = os.getenv("GEMINI_API_KEYS") or os.getenv("GEMINI_API_KEY") or ""
    for k in raw.split(","):
        k = k.strip().strip('"').strip("'")
        if k:
            return k
    return None

EXPLAIN_SYSTEM = (
    "你是一位專業的台灣資安分析師，協助一般民眾辨識網路詐騙。"
    "請根據多維度自動偵測結果進行推理，用繁體中文回覆，"
    "語氣清晰、直接、不過度驚嚇。"
)

CATEGORY_ZH = {
    "phishing": "假冒官方/平台釣魚",
    "investment_scam": "假投資詐騙",
    "romance_scam": "感情詐騙",
    "parcel_scam": "假包裹/物流詐騙",
    "gov_impersonation": "假冒政府機關（假檢警）",
    "safe": "正常內容",
}


def _fmt_signals(data: dict) -> str:
    """把多引擎訊號整理成 prompt / fallback 共用的條列文字。"""
    lines = []
    nlp = data.get("nlp") or {}
    if nlp:
        cat = nlp.get("category", "")
        lines.append(
            f"[語意分析] 類別：{CATEGORY_ZH.get(cat, cat)}，"
            f"信任分數：{nlp.get('trust_score', '?')}/100，"
            f"信心：{nlp.get('confidence', '?')}"
        )
    url = data.get("url") or {}
    if url:
        lines.append(
            f"[URL 分析] 風險等級：{url.get('label', '未知')}，"
            f"redirect 層數：{url.get('hop_count', 'N/A')}，"
            f"最終網域：{url.get('final_url', 'N/A')}"
        )
    behavior = data.get("behavior") or {}
    if behavior:
        flags = behavior.get("flags") or []
        lines.append(f"[行為分析] 風險分數：{behavior.get('score', '?')}，觸發：{', '.join(flags) or '無'}")
    return "\n".join(lines) if lines else "（無可用偵測訊號）"


def build_user_prompt(data: dict) -> str:
    signals = _fmt_signals(data)
    snippet = (data.get("text_snippet") or "")[:200]
    return (
        "使用者剛瀏覽了一個可疑頁面，以下是自動偵測結果：\n\n"
        f"{signals}\n\n"
        f"[原始文字片段] {snippet}\n\n"
        "請用繁體中文回覆，包含：\n"
        "1. 這為何可能是詐騙（引用上述具體偵測訊號）\n"
        "2. 最關鍵的 1-2 個風險訊號\n"
        "3. 給使用者的具體建議行動\n"
        "整體控制在 120 字以內。"
    )


def _fallback(data: dict) -> str:
    """無 API 金鑰時的規則式解釋（仍引用真實訊號，可離線 demo）。"""
    nlp = data.get("nlp") or {}
    url = data.get("url") or {}
    cat = nlp.get("category", "")
    parts = []

    if cat and cat != "safe":
        parts.append(
            f"AI 語意引擎將此內容判定為「{CATEGORY_ZH.get(cat, cat)}」"
            f"（信任分數僅 {nlp.get('trust_score', '?')}/100）。"
        )
    if url:
        label = url.get("label")
        if label == "Malicious":
            parts.append(f"連結經 Google Safe Browsing 標記為惡意，最終指向 {url.get('final_url', '')}。")
        elif label == "Suspicious":
            parts.append(f"連結具可疑特徵（{url.get('reason', '可疑網域/跳轉')}）。")
        hop = url.get("hop_count")
        if isinstance(hop, int) and hop > 3:
            parts.append(f"連結經過 {hop} 層轉址，可能藏匿最終釣魚頁。")

    if not parts:
        return "目前偵測訊號不足以判定為詐騙，但仍請保持警覺，勿輕易提供個資或匯款。"

    advice = "建議：不要點擊連結、不要提供帳號密碼或個資，可撥打 165 反詐騙專線查證。"
    return " ".join(parts) + " " + advice


def explain(data: dict) -> dict:
    api_key = _get_api_key()
    if not api_key:
        logger.info("[Explain] 無 GEMINI_API_KEYS，使用規則式 fallback")
        return {"explanation": _fallback(data), "source": "fallback"}

    try:
        import time

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        config = types.GenerateContentConfig(
            system_instruction=EXPLAIN_SYSTEM,
            max_output_tokens=800,
            # 關閉 thinking，避免 token 全花在思考導致回傳空字串
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )

        # Gemini 偶發 503 高負載，對暫時性錯誤做短退避重試
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=EXPLAIN_MODEL,
                    contents=build_user_prompt(data),
                    config=config,
                )
                text = (resp.text or "").strip()
                if not text:
                    return {"explanation": _fallback(data), "source": "fallback"}
                return {"explanation": text, "source": "llm", "model": EXPLAIN_MODEL}
            except Exception as e:  # noqa: PERF203
                last_err = e
                transient = any(s in str(e) for s in ("503", "UNAVAILABLE", "overloaded"))
                if transient and attempt < 2:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                raise
        raise last_err  # type: ignore[misc]
    except Exception as e:
        logger.error("[Explain] Gemini 呼叫失敗，改用 fallback: %s", e)
        return {"explanation": _fallback(data), "source": "fallback"}
