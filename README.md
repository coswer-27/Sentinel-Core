# 🛡️ Sentinel-Core: AI-Powered Security Shield

Sentinel-Core 是一個基於微服務架構的資安防護工具，結合 **BERT 深度學習** 與 **高效規則引擎**，即時偵測網頁中的詐騙資訊、惡意內容與釣魚網域。

---

## 🚀 專案核心亮點 (Core Highlights)

- **混合偵測引擎 (Hybrid Engine) [v2.2]**: 
  - **L1 快速過濾**: 利用 Regex 規則引擎秒級攔截已知詐騙模式（如：加 LINE、投資飆股、中獎通知）。
  - **L2 深度分析**: 透過 BERT 多國語言模型進行語意辨識，挖掘隱藏的誘騙意圖與情緒操縱。
- **上下文感知 (Context Awareness) [v2.1]**: 自動採集來源網域 (URL) 與觸發時間戳記，提供更精準的風險評估背景。
- **工業級健壯性**: 內建 **81 項自動化單元測試**，確保核心邏輯、資安防護與數據模型 100% 穩定運作。

---

## 🏗️ 系統架構 (Architecture)

1. **API Gateway (Port 8000)**: 入口網關，負責流量監控、SSRF 防護、以及將請求分流至不同微服務。
2. **NLP Service (Port 8001)**: AI 運算單元，執行 BERT 模型推論。
3. **Link Scanner (Port 8002) [New]**: 連結掃描引擎，整合 Google Safe Browsing 與啟發式檢測。
4. **Chrome Extension (MV3)**: 前端偵測插件，改採 **Service Worker (background.js)** 架構以符合現代瀏覽器安全規範。
5. **SQLite Database**: 非同步紀錄偵測日誌。

---

## 🔒 資安防禦機制 (Security Hardening)

- **SSRF 阻斷**: 嚴格禁止對私有 IP (如 localhost, 127.0.0.1, 192.168.x.x) 的請求，防止攻擊者探測內部網路。
- **XSS 跨站腳本防護**: 透過 `escapeHTML` 轉義機制，防止惡意選取內容或 API 回傳值造成代碼注入。
- **日誌注入防護 (Log Injection)**: 對 URL 與時間戳記進行嚴格字元過濾，確保系統紀錄不被惡意竄改。
- **流量限制 (Rate Limiting)**: 導入 `slowapi` 實作每 IP 每分鐘限制 10 次請求，防止服務遭濫用。
- **單點故障隔離 (Fault Isolation)**：資料庫紀錄由 FastAPI BackgroundTasks 異步處理，即便資料庫發生 Locked 或連線異常，核心分析功能依然保持穩定，不影響使用者體驗。

---

## 📜 版本紀錄 (Changelog)
#### **v2.4 - 連結掃描整合與前端架構重構 (最新)**
* **[微服務] 連結掃描引擎 (service_link_scanner)**：新增獨立服務，支援 Google Safe Browsing (GSB) 惡意網址對比與 Redirect 重新導向追蹤。
* **[偵測] 啟發式網址分析**：支援 Punycode 偽裝偵測、可疑 TLD (.xyz/.tk) 識別。
* **[前端] MV3 架構重構**：導入 `background.js` (Service Worker) 處理通訊，修復 Content Script 在非 HTTPS 頁面無法 fetch 本地 API 的限制。
* **[UI] 堆疊式通知優化**：重構 Toast UI，支援 Flex 堆疊顯示，解決多重預警重疊問題 (UI-04)。
* **[資安] 全域 SSRF 強化**：實作 `assert_public_http_url` 驗證器，嚴格禁止探測內部私有網路。

#### **v2.3 - 數據持久化與背景任務**
* **[資料庫] 異步日誌系統**：導入 `aiosqlite` 實作非同步掃描紀錄，確保偵測數據持久化。
* **[穩定性] 背景任務處理**：使用 FastAPI `BackgroundTasks` 執行資料庫寫入，確保 I/O 延遲不影響 API 回應速度。
* **[監控] 統計接口 (/stats)**：新增即時數據分析 API，支援回傳總掃描次數與平均信任得分。
* **[測試] 健壯性提升**：補齊資料庫邊界測試，並實作全域 Mock 邏輯防止測試污染真實數據。
* **[資安] Git 安全強化**：完善 `.gitignore` 規範，杜絕 `.db` 與 `.env` 敏感檔案上傳風險。

#### **v2.2 - 混合偵測與自動化測試**
* **[核心] 規則引擎整合**：實作 `RulesEngine`，支援 Regex 關鍵字與精確網域黑名單比對。
* **[優化] 效能加強**：命中規則後回傳 `[快速攔截]`，節省 100% 的 AI 算力成本與延遲。
* **[品質] 81 項自動化測試**：建立全量測試套件，達成 100% 測試通過率。
* **[架構] 標準化導入**：優化 `sys.path` 邏輯，修復底線資料夾命名規範之模組導入問題。

#### **v2.1 - 上下文感知與安全性強化**
* **[功能] URL & Timestamp 採集**：插件自動同步當前頁面網址，並進行隱私參數剝離。
* **[資安] SSRF 防禦**：於 Pydantic 模型實作私有網路 URL 阻斷。

#### **v1.2 - 視覺動態與資安防禦**
* **[核心] 前端三段式主題引擎**：實作 🟢 綠、🟡 橘、🔴 紅 三色動態 UI。
* **[資安] XSS 防護**：新增 `escapeHTML` 函式，阻斷前端 HTML/Script 惡意注入。
* **[資安] 數值校正**：導入 Score Clamping，解決 API 回傳異常值導致的 UI 溢出。
* **[優化] 錯誤處理**：整合 429 限流與 503 斷線狀態之語意化 UI 標題。

#### **v1.1 - 微服務架構重構**
* **[架構] 拆分微服務**：解耦為 `API Gateway` 與 `NLP Service` 獨立運作。
* **[資源] Lifespan 管理**：使用 FastAPI Lifespan 管理模型載入與非同步 Client。
* **[流量] Rate Limiting**：導入 `slowapi` 實作每分鐘 10 次請求限制。
* **[日誌] Logging 導入**：全面取代 print，具備時間戳記與錯誤層級分類。

#### **v1.0 - 基礎原型建立**
* **[AI] BERT 整合**：導入 `transformers` 進行基礎語意分析。
* **[插件] Chrome Extension**：實作文字選取監聽與基礎通知彈窗。

---


### 🛠️ 安裝與啟動步驟 (Sentinel-Core v2.4)

本專案採用微服務架構，啟動前請確保已完成環境依賴安裝，並依序啟動後端服務。

---

#### 1. 基礎環境準備
請確保您的開發環境已安裝 **Python 3.9+**。在專案根目錄執行以下指令安裝所有必要套件：

```powershell
pip install -r requirements.txt
```

> **備註**：由於 BERT 模型較大，初次啟動 `service_nlp` 時系統會自動下載預訓練權重（約 600MB），請保持網路暢通。

---

#### 2. 啟動服務 (需開啟兩個獨立終端機)

#### 🚀 第一步：啟動 NLP 偵測服務 (AI 運算核心)
這是系統的「大腦」，負責深度的語意分析。
```powershell
# 進入資料夾並執行
cd service_nlp
python main.py
```
* **檢查點**：終端機出現 `INFO: [NLP] 模型就緒` 即代表成功。
* **預設位址**：`http://127.0.0.1:8001`

#### 🛡️ 第二步：啟動 API 網關 (流量與規則控管)
這是系統的「門神」，負責攔截已知詐騙與流量限制。
```powershell
# 進入另一個終端機，回到根目錄後執行
cd api_gateway
python main.py
```
* **檢查點**：出現 `Uvicorn running on http://127.0.0.1:8000`。
* **預設位址**：`http://127.0.0.1:8000`

#### 🚀 第三步：啟動連結掃描服務 (惡意網址偵測)
```powershell
cd service_link_scanner
python main.py
```
檢查點：終端機顯示啟發式偵測器已就緒。
預設位址：`http://127.0.0.1:8002`

> **備註**：首次啟動 `api_gateway` 時，系統會自動在根目錄建立 `sentinel_logs.db` 檔案。該檔案已列入 `.gitignore` 以確保數據隱私。
---

#### 3. 執行自動化測試 (環境驗證)
為確保您的 `sys.path` 導入與各項防禦邏輯（SSRF, Regex）在您的機器上運作正常，請在**根目錄**執行：

```powershell
python -m pytest tests/ -v
```
* **合格指標**：應看到 **81 PASSED** 的綠色結果。

---

#### 4. 瀏覽器擴充功能掛載 (Chrome Extension)

1.  開啟 Chrome 瀏覽器，進入 `chrome://extensions/`。
2.  開啟右上角的 **「開發者模式」**。
3.  點擊左上角 **「載入解壓縮擴充功能」**。
4.  選擇專案目錄中的 `browser_ext` 資料夾完成掛載。

---

#### 🧪 快速功能測試案例

| 測試類型 | 選取文字內容 | 預期結果 (UI) | 攔截層級 |
| :--- | :--- | :--- | :--- |
| **已知詐騙** | "趕快加我 LINE 領取飆股資訊！" | 🔴 紅色通知：顯示 `[快速攔截]` | Rules Engine (L1) |
| **安全內容** | "今天的天氣真好，適合去圖書館。" | 🟢 綠色通知：顯示 `Safe` 與評分 | BERT NLP (L2) |
| **格式錯誤** | (選取超過 5000 字的長文) | ⚪ 灰色通知：顯示 `422 格式錯誤` | Pydantic Model |
| **連線失敗** | (關閉 8000 埠後執行) | ⚪ 灰色通知：顯示 `連線失敗` | Extension Logic |
| **惡意連結** | `http://apple-login.xyz` | 🔴 顯示 `[惡意網域]` | Link Scanner (L1.5) |
| **重新導向** | (多層跳轉連結) | ⚠️ 顯示 `可疑重新導向` | Link Scanner (L1.5) |

---

## 📡 API 規格

### 1. 內容分析接口
- **Endpoint**: `POST /analyze`
- **功能**: 執行規則攔截與 AI 語意辨識。
- **Rate Limit**: 30 請求/分鐘 (v2.4 調整)。

### 2. 統計數據接口
- **Endpoint**: `GET /stats`
- **功能**: 獲取系統累計偵測數據。
- **Response**:
```json
{
  "total": 42,
  "avg_score": 75.5
}
```
### 3. 連結分析接口
- **Endpoint**: `POST /analyze/links`
- **功能**: 批次掃描頁面連結安全性。
- **Rate Limit**: 30 請求/分鐘。
---