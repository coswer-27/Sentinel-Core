# 🛡️ Sentinel-Core AI 混合安全引擎 (AI Hybrid Security Engine)

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-00a393.svg)
![Transformers](https://img.shields.io/badge/HuggingFace-Transformers-orange.svg)
![SQLite](https://img.shields.io/badge/Database-SQLite%20(WAL)-blue.svg)
![Security](https://img.shields.io/badge/Security-JWT%20%7C%20API%20Key-red.svg)

> 本專案為資安專題開發之「混合式 AI 網路安全防護系統」，旨在透過微服務架構，提供即時、高效且具備多國語言分析能力的惡意內容與釣魚連結攔截服務。

---

## 🌟 專案簡介 (Project Overview)

**Sentinel-Core** 是一套專為防範社交工程、釣魚網站與惡意連結所設計的防護引擎。我們揚棄了傳統單一的防護模式，採用**「規則引擎 (Rule-based) + AI 語意分析 (NLP) + 網址掃描 (URL Scan)」**的三重混合防護架構。

透過整合客戶端（瀏覽器擴充功能）與後端微服務 API 網關，系統能即時擷取網頁內容並進行非同步的風險評估，最終將 0~100 的信任分數 (Trust Score) 反饋給使用者，達成零延遲的無縫防護。

---

## 🚀 核心功能與亮點 (Key Features)

* **🧠 混合式防護引擎 (Hybrid Detection)**
  * **L1 規則引擎：** 針對已知高風險特徵進行毫秒級快速攔截。
  * **L2 AI 語意分析：** 採用 Hugging Face BERT 多語系模型，搭配自研「權重映射演算法」，將文字情緒與語意特徵轉化為資安信任分數。
  * **L3 連結掃描器：** 針對 URL 進行深度解析與風險特徵比對。
* **🛡️ 企業級安全防護 (Security Common)**
  * **API Key 存取控制：** 嚴格限制內部微服務的呼叫權限，防止算力資源遭惡意濫用。
  * **JWT 認證機制：** 保護後台統計與敏感數據 API。
  * **SSRF 全域防護：** 實作嚴謹的網域解析與私有 IP 阻斷機制，防範伺服器端請求偽造攻擊。
  * **API 限流 (Rate Limiting)：** 整合 `slowapi` 阻擋 DDoS 與惡意爬蟲。
* **⚡ 高併發效能優化 (Performance)**
  * 採用 **FastAPI** 搭配非同步 (Async) 微服務呼叫。
  * 資料庫啟用 **SQLite WAL (Write-Ahead Logging) 模式**，並針對統計欄位建立索引 (Indexing)，徹底解決高併發背景寫入時的 Database Locked 問題。

---

## 🛠️ 技術架構 (Tech Stack)

* **後端核心：** Python 3, FastAPI, Uvicorn, HTTPX
* **AI 與模型：** Hugging Face `transformers`, PyTorch, `bert-base-multilingual`
* **資料庫：** SQLite, `aiosqlite` (非同步操作)
* **安全套件：** `python-jose` (JWT), `passlib`, `slowapi`
* **前端與客戶端：** 原生 JavaScript (Browser Extension)
* **CI/CD：** GitHub Actions (自動化代碼檢查)

---

## 📂 系統目錄結構 (Project Structure)

```text
Sentinel-Core/
├── api_gateway/              # API 網關 (系統中樞神經)
│   ├── main.py               # 網關路由與安全攔截
│   ├── database.py           # 非同步資料庫連線池與日誌寫入
│   └── rules_engine.py       # L1 規則引擎
├── service_nlp/              # AI 語意分析微服務
│   ├── detectors/
│   │   └── bert_engine.py    # BERT 模型載入與權重轉換邏輯
│   └── main.py               # NLP 服務 API
├── service_link_scanner/     # URL 連結掃描微服務
│   └── url_scan/             # 網址解析與特徵擷取模組
├── common/                   # 跨微服務通用模組
│   ├── models.py             # Pydantic 資料驗證模型
│   ├── validators.py         # 網址格式與安全驗證
│   └── security.py           # JWT, API Key 與 SSRF 防護邏輯
├── browser_ext/              # 瀏覽器擴充功能客戶端
│   ├── background.js         # 背景監聽腳本
│   └── content.js            # 網頁 DOM 解析腳本
└── tests/                    # 單元測試與整合測試

```

---

## ⚙️ 快速啟動 (Getting Started)

### 1. 環境準備

請確保您的系統已安裝 Python 3.10+，並建議使用虛擬環境 (Virtual Environment)。

```bash
# 建立並啟動虛擬環境
python -m venv venv
source venv/bin/activate  # Windows 請使用 venv\Scripts\activate

# 安裝系統相依套件
pip install -r requirements.txt

```

### 2. 環境變數設定

複製 `.env.example` 並重新命名為 `.env`，根據需求配置以下金鑰：

```ini
GATEWAY_API_KEY=your-api-key-here
JWT_SECRET=your-jwt-secret-key
GATEWAY_RATE_LIMIT=30/minute

```

### 3. 啟動微服務

系統包含三個主要服務，建議開啟三個終端機分別啟動（或使用我們提供的 `start-dev.ps1` 腳本）：

```bash
# 啟動 NLP 微服務 (Port: 8001)
uvicorn service_nlp.main:app --port 8001

# 啟動 Link Scanner 微服務 (Port: 8002)
uvicorn service_link_scanner.main:app --port 8002

# 啟動 API Gateway (Port: 8000)
uvicorn api_gateway.main:app --port 8000 --reload

```

---

## 📚 API 使用範例 (API Endpoints)

API 網關提供 Swagger UI 互動式文件，服務啟動後可至：`http://127.0.0.1:8000/docs` 查看。

### 1. 內容分析 (需 API Key)

* **Endpoint:** `POST /analyze`
* **Headers:** `X-API-Key: <your_api_key>`

```json
{
  "content": "恭喜您獲得中獎資格，請點擊連結領取...",
  "url": "[http://suspicious-link.com](http://suspicious-link.com)",
  "timestamp": "2026-06-24T12:00:00Z"
}

```

### 2. 系統統計 (需 JWT 認證)

* **Endpoint:** `GET /stats`
* **Headers:** `Authorization: Bearer <your_jwt_token>`
* **Response:** 回傳總掃描次數與平均信任分數。

---
