# 🛡️ Sentinel-Core: AI-Powered Security Shield

Sentinel-Core 是一個基於微服務架構的資安防護工具，利用 BERT 模型進行語意分析，即時偵測網頁中的詐騙資訊與惡意內容。

---

## 🚀 v1.1 更新亮點：微服務架構與安全性強化

本版本實現了後端解耦，提升了系統的健壯性與可擴展性。

### 🏗️ 系統架構 (Microservices)
- **API Gateway (Port: 8000)**: 
  - 統一入口，負責處理 CORS 跨域請求。
  - 導入 `slowapi` 進行流量限制 (Rate Limiting)。
  - 實作透明轉發邏輯，對接內部 NLP 服務。
- **NLP Service (Port: 8001)**: 
  - 核心偵測單元，運行 `BERT-base-multilingual` 模型。
  - 採用 `lifespan` 資源管理，優化模型載入與記憶體回收。

### 🔒 安全性與異常處理 (Security Features)
- **輸入校驗**: 透過 Pydantic 限制 content 長度為 1-5000 字元，防止惡意長文本攻擊。
- **流量控制**: 限制每個 IP 每分鐘最多 10 次請求，回傳 `429 Too Many Requests`。
- **精確錯誤代碼**:
  - `502 Bad Gateway`: NLP 服務內部異常。
  - `503 Service Unavailable`: NLP 服務未啟動。
  - `504 Gateway Timeout`: AI 推論逾時。
- **專業日誌**: 全面採用 Python `logging` 模組取代 `print`，具備時間戳記與層級分類。

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
#### 1.開啟 Chrome 瀏覽器，進入 ```chrome://extensions/。
#### 2.開啟「開發者模式」。
#### 3.點擊「載入解壓縮擴充功能」，選擇專案中的 browser-ext 資料夾。

## 📡 API 規格
偵測請求 (POST `/analyze`)  
Body:
```
{
    "content": "待檢測的文字內容"
}
```
Response:
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
- [ ] v1.2：前端「紅、橘、綠」動態視覺回饋系統（In Progress）  
- [ ] v2.0：加入 Regex 關鍵字過濾與多重偵測引擎  


---