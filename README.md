# 🛡️ Sentinel-Core: AI-Powered Security Shield

Sentinel-Core 是一個基於微服務架構的資安防護工具，利用 BERT 模型進行語意分析，即時偵測網頁中的詐騙資訊與惡意內容。

---

## 🚀 v1.2 更新：視覺動態與資安防禦強化

本版本不僅提升了使用者體驗 (UX)，更針對前端注入攻擊與系統健壯性進行了深度加固。

### 🎨 核心功能 (Features)
- **三段式主題引擎 (Tri-color Theme)**: 
  - 🟢 **Safe (Score > 70)**: 內容安全，綠色視覺回饋，4秒自動消失。
  - 🟡 **Warning (40-70)**: 疑似風險，橘色視覺警示，6秒自動消失。
  - 🔴 **Danger (Score < 40)**: 高風險內容，紅色視覺警告，8秒自動消失。
- **儀表板進度條動畫**: 實作動態風險值滑動效果，增加「掃描感」。
- **語意化錯誤回饋**: 針對 `429 (限流)` 與 `5xx (斷線)` 提供專屬 UI 標題與圖示，不再誤報。

### 🔒 資安防禦機制 (Security Hardening)
- **XSS 跨站腳本防護**: 透過 `escapeHTML` 過濾機制，防止選取內容或 API 回傳值造成惡意代碼注入。
- **數值邊界校正 (Score Clamping)**: 確保信任分數恆定在 $0 \le s \le 100$ 區間，防止 UI 進度條溢出。
- **流量限制 (Rate Limiting)**: 每 IP 每分鐘限制 10 次請求，確保服務可用性。

---

## 🏗️ 系統架構

1. **API Gateway (Port 8000)**: 入口網關，負責流量限制、跨域處理 (CORS) 與請求轉發。
2. **NLP Service (Port 8001)**: AI 運算單元，執行 BERT 語意分析模型與推論。

---

## 📜 版本紀錄 (Changelog)

#### **v1.2 - 視覺動態與資安防禦 (2026-04-02)**
* **[核心] 前端三段式主題引擎**：實作 🟢 綠、🟡 橘、🔴 紅 三色動態 UI。
* **[資安] XSS 防護**：新增 `escapeHTML` 函式，阻斷前端 HTML/Script 惡意注入。
* **[資安] 數值校正**：導入 Score Clamping，解決 API 回傳異常值導致的 UI 溢出。
* **[優化] 錯誤處理**：整合 429 限流與 503 斷線狀態之語意化 UI 標題。

#### **v1.1 - 微服務架構重構 (2026-03-31)**
* **[架構] 拆分微服務**：解耦為 `API Gateway` 與 `NLP Service` 獨立運作。
* **[資源] Lifespan 管理**：使用 FastAPI Lifespan 管理模型載入與非同步 Client。
* **[流量] Rate Limiting**：導入 `slowapi` 實作每分鐘 10 次請求限制。
* **[日誌] Logging 導入**：全面取代 print，具備時間戳記與錯誤層級分類。

#### **v1.0 - 基礎原型建立 (2026-03-24)**
* **[AI] BERT 整合**：導入 `transformers` 進行基礎語意分析。
* **[插件] Chrome Extension**：實作文字選取監聽與基礎通知彈窗。

---

## 🛠️ 安裝與啟動步驟

### 1. 安裝必要依賴
請確保你的環境中已安裝 Python 3.9+，並執行以下指令：
```
powershell
pip install fastapi uvicorn transformers torch httpx slowapi pydantic
```
### 2. 啟動服務 (需開啟兩個終端機)
第一步：啟動 NLP 偵測引擎
```
PowerShell
cd service-nlp
python main.py
```
  預期輸出：`INFO: [NLP] 模型就緒`

第二步：啟動 API 網關
```
PowerShell
cd api-gateway
python main.py
```
  預期輸出：`INFO: Uvicorn running on http://127.0.0.1:8000`

### 3. 瀏覽器擴充功能
#### 1.開啟 Chrome 瀏覽器，進入 `chrome://extensions/` 並開啟「開發者模式」。
#### 2.點擊「載入解壓縮擴充功能」，選擇專案中的  `browser-ext` 資料夾。

## 📡 API 規格
 - Endpoint: `POST /analyze`
 - Request Body:  
 ```
 {"content": "待檢測的文字內容"}
 ```
 - Response:
```
{
  "trust_score": 85,
  "label": "Safe",
  "reason": "AI 分析信任度為 85%"
}
```
## 📅 開發路線圖（Roadmap）

- [x] v1.0：基礎 BERT 偵測與 Chrome 插件整合  
- [x] v1.1：微服務重構、流量限制與健壯性強化  
- [x] v1.2：前端「紅、橘、綠」動態視覺回饋系統（In Progress）  
- [ ] v2.0：加入 Regex 關鍵字過濾與多重偵測引擎  


---