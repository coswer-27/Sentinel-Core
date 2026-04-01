# Sentinel-Core 🛡️
**AI 驅動的即時詐騙與偏激語意偵測系統**

Sentinel-Core 是一款瀏覽器擴充功能，旨在透過 BERT 自然語言處理模型，即時分析網頁選取文字的詐騙風險與語意偏好，並提供直觀的視覺化風險報告。

## 🚀 v1.0 核心功能
- **即時文字偵測**：滑鼠選取文字後自動觸發後端 AI 分析。
- **BERT 加權評分**：採用 `nlptown/bert-base-multilingual-uncased-sentiment` 模型，透過機率分布計算精確的風險百分比。
- **安全防禦機制**：
  - **XSS 防護**：前端使用 DOM API 注入技術，杜絕腳本注入。
  - **DoS 防護**：後端實作 SlowAPI 流量限制（30 req/min）。
  - **長度校驗**：限制分析文字長度，避免 ML 資源耗盡。

## 🛠️ 技術棧 (Tech Stack)
- **Frontend**: JavaScript (Chrome Extension V3), CSS3 (Animations)
- **Backend**: FastAPI, Python 3.9+, Uvicorn
- **AI Model**: Transformers (BERT), PyTorch
- **Security**: Slowapi, Pydantic (Data Validation)

## 📦 安裝與啟動
1. **後端啟動**:
   ```bash
   cd core-engine
   pip install -r requirements.txt
   python main.py
2. **插件掛載:**
- 開啟 Chrome chrome://extensions/
- 開啟「開發者模式」
- 點擊「載入解壓縮擴充功能」，選取 browser-ext 目錄。