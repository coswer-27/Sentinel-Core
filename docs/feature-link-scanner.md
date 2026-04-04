# feature/link-scanner 開發說明文件

> **分支：** `feature/link-scanner` → 目標合入 `main`
> **作者：** SengQ1011
> **最後更新：** 2026-04-03

---

## 概覽

本分支實作了 Sentinel-Core 的**連結掃描功能**，是 v1.1 微服務架構重建後的核心新模組。
主要變更涵蓋：全新 `service_link_scanner` 微服務、API Gateway 新端點、Chrome 擴充功能重構，
以及跨服務的安全性強化。

共計：**28 個檔案異動，+1,246 / -117 行**

---

## 新增功能一覽

| 功能 | 說明 |
|------|------|
| 連結批次掃描 | Hover 連結自動觸發，批次送後端分析 |
| Google Safe Browsing 整合 | GSB v4 Lookup API，偵測 MALWARE / PHISHING 等 4 種威脅 |
| 啟發式檢測 | Punycode 國際化網域偵測 + 可疑 TLD（.xyz .tk 等 7 種） |
| Redirect 追蹤 | 最多 5 層重新導向，超過 3 層判為 Suspicious |
| Badge 注入 | 掃描完成後於連結旁注入 `Malicious` / `Suspicious` 標記 |
| Shadow DOM 支援 | 遞迴掃描 Web Component 內部連結 |
| Toast 堆疊通知 | 右下角 flex 堆疊，避免通知重疊（修復 UI-04）|
| SSRF 防護 | 輸入驗證層封鎖私有 IP / 迴環位址 |

---

## 架構變更

### 新增：`service_link_scanner/`（Port 8002）

本分支從零建立連結掃描微服務，取代原先的 `core-engine/`（port 衝突已解決）。

```
service_link_scanner/
├── main.py              # FastAPI 入口，/health + /analyze/links
├── schemas.py           # UrlScanResult, BatchUrlResponse（服務輸出 Schema）
├── requirements.txt
└── url_scan/
    ├── __init__.py      # 只匯出 URLDetector
    ├── base.py          # BaseDetector ABC（保留備用，URLDetector 不繼承）
    └── url_detector.py  # 核心偵測邏輯（232 行）
```

**`URLDetector` 掃描流程：**

```
輸入 URLs（批次）
  → 並行 get_final_url()（asyncio.gather，最多 5 層 redirect）
  → 去重後批次送 GSB v4 threatMatches:find（每批最多 500）
  → 每個 URL 判斷：GSB 命中 > 啟發式 > Redirect 層數 > Safe
  → 回傳 UrlScanResult 列表
```

**評分規則：**

| 狀況 | label | trust_score |
|------|-------|-------------|
| GSB 命中 | Malicious | 0 |
| Punycode / 可疑 TLD | Suspicious | 40 |
| Redirect > 3 層 | Suspicious | 50 |
| 無威脅 | Safe | 90 |

---

### 變更：`api_gateway/main.py`

新增 `/analyze/links` 端點，代理請求至 `service_link_scanner`（Port 8002）。

| 端點 | Rate Limit | 說明 |
|------|-----------|------|
| `/analyze` (既有) | `GATEWAY_RATE_LIMIT`（預設 10/min） | NLP 文字分析 |
| `/analyze/links` (新增) | 30/min | 連結掃描，轉發至 Port 8002 |

其他調整：
- 加入 `SlowAPIMiddleware`，使 Rate Limit 在 middleware 層生效
- CORS 新增 `GET` method（支援 `/health`）
- `URL_SERVICE_URL` 從 `.env` 讀取（預設 `http://127.0.0.1:8002/analyze/links`）

---

### 新增：`common/validators.py`

跨服務共用的 URL 輸入驗證，集中維護 SSRF 防護規則。

```python
assert_public_http_url(url)
# 驗證：
# 1. scheme 必須為 http / https
# 2. 長度 ≤ 2048 字元
# 3. 禁止私有 IP：127.x / 192.168.x / 10.x / 172.16-31.x / 169.254.x / IPv6 loopback
```

`common/models.py` 新增 `BatchUrlRequest`，`check_urls` 驗證器呼叫此函式。

---

### 重構：`browser_ext/`

#### 新增 `background.js`（Service Worker）

解決 MV3 Content Script 在非 HTTPS 頁面無法直接 fetch `127.0.0.1` 的 Private Network Access（PNA）限制。

```
content.js → chrome.runtime.sendMessage({ type: "SENTINEL_BACKEND_FETCH" })
               → background.js service worker
                    → fetch("http://127.0.0.1:8000/...")
```

所有後端請求改為透過 `sentinelBackendFetch()` 包裝函式發送。

#### `content.js` 主要變更

| 功能 | 舊版 | 新版 |
|------|------|------|
| 後端通訊 | 直接 `fetch()` | `sentinelBackendFetch()` 經 background 中繼 |
| 連結掃描 | 無 | hover `<a>` 觸發，批次掃描 + 快取 |
| 掃描快取 | 無 | `scannedUrls: Set` + `scannedResults: Map` + `pendingScans: Set` |
| MutationObserver | 無 | debounce 800ms，DOM 變動後重新注入已快取結果（修復 Google 動態 DOM）|
| Tooltip | 無 | 右下角固定，掃描中 / 完成 / 失敗三態 |
| Badge | 無 | Malicious/Suspicious 連結旁插入 `span.sc-badge` |
| Shadow DOM | 無 | `collectAnchorsFromRoot` 遞迴掃 `shadowRoot` |
| Toast 通知 | `style.display="none"` 隱藏舊通知 | `oldNotify.remove()` 物理移除（UI-04）|
| 通知容器 | 單一 `#sentinel-notify` | `#sentinel-notification-stack` flex 堆疊 |

---

## 安全性修正（本分支）

| ID | 問題 | 修正方式 |
|----|------|---------|
| C-3 / SSRF | `BatchUrlRequest` 未驗證私有 IP，URLDetector redirect 可觸達內網 | `common/validators.py` + `BatchUrlRequest.check_urls` 驗證 |
| H-2 | `analyze_batch` 失敗時 `str(e)` 傳回前端，洩漏內部訊息 | 改回通用訊息，完整 stack trace 寫入 `logger.error(..., exc_info=True)` |
| H-1 | service_link_scanner 無 CORS（內部服務不應開放） | 不加 `CORSMiddleware`，僅 Gateway 有 CORS |

---

## 測試

本分支新增以下測試檔案：

| 檔案 | 測試目標 |
|------|---------|
| `tests/test_links_api.py` | `/analyze/links` 端點（正常 + 例外路徑）|
| `tests/test_url_detector.py` | `URLDetector.heuristic_check`（Punycode / 可疑 TLD / 安全）|
| `api_gateway/tests/test_gateway.py` | Gateway 路由、Rate Limit、下游服務代理 |

**執行方式：**
```bash
PYTHONPATH=. python -m pytest tests/ -v
```

---

## CI/CD 變更（`.github/workflows/backend-check.yml`）

- Lint 範圍新增 `service_link_scanner/`
- 依賴安裝改為各服務個別安裝，避免版本衝突：
  ```yaml
  pip install -r api_gateway/requirements.txt
  pip install -r service_nlp/requirements.txt
  pip install -r service_link_scanner/requirements.txt
  ```

---

## 環境變數

在 `.env`（參考 `.env.example`）補充以下設定：

```dotenv
# 必填（連結掃描服務 URL）
URL_SERVICE_URL=http://127.0.0.1:8002/analyze/links

# 選填（無此 Key 時 GSB 檢查會略過，僅做啟發式）
GOOGLE_SAFE_BROWSING_API_KEY=your_key_here
```

**取得 GSB API Key：**
1. [Google Cloud Console](https://console.cloud.google.com) > 啟用 Safe Browsing API
2. APIs & Services > Credentials > Create API Key
3. 詳見 `.env.example` 中的完整說明

---

## 本機開發啟動

```powershell
# 一鍵啟動三個服務（api_gateway + service_nlp + service_link_scanner）
./start-dev.ps1
```

驗證連結掃描功能可用：
```bash
curl -X POST http://127.0.0.1:8000/analyze/links \
  -H "Content-Type: application/json" \
  -d '{"urls": ["http://testsafebrowsing.appspot.com/s/malware.html"]}'
# 預期回傳 label: "Malicious"
```

---

## 已知限制

- GSB API Key 未設定時，**僅執行啟發式 + Redirect 偵測**，無法偵測已知惡意 URL
- GSB Lookup API URL 明文傳送至 Google（隱私敏感場景可改 Update API）
- GSB v4 僅限非商業用途（商業用途請改 [Web Risk API](https://cloud.google.com/web-risk)）
