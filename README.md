# 🛡️ Sentinel-Core: AI-Powered Semantic Security Guard

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Status](https://img.shields.io/badge/status-v1.0--MVP-green.svg)
![AI-Model](https://img.shields.io/badge/AI-BERT--Multilingual-orange.svg)

**Sentinel-Core** 是一款基於深度學習的即時語意分析插件，旨在解決傳統安全工具無法偵測「非結構化詐騙文字」的痛點。它不僅僅是過濾網址，更是能理解語句背後的意圖與威脅。

---

## 🌟 產品核心功能 (Core Features)

### 1. 🧠 深度語意意圖辨識 (Semantic Intent Detection)
不同於傳統的關鍵字比對 (Keyword Matching)，我們採用 **BERT (Bidirectional Encoder Representations from Transformers)** 預訓練模型：
* **威脅感知**：自動識別帶有「急迫性」、「財物誘惑」與「帳號威脅」語氣的語句。
* **多語言支持**：原生支援中文、英文等多國語言，精準攔截跨國網路釣魚與社交工程攻擊。

### 2. 🛡️ 非侵入式即時防護 (Zero-Friction Protection)
* **隨選隨測 (On-Demand)**：僅在使用者主動選取網頁文字時觸發偵測，極低效能消耗。
* **異步處理架構**：採用 **FastAPI** 異步框架，從數據捕捉到 AI 分析結果回傳，反應時間低於 1 秒。

### 3. 🚨 直覺化風險視覺化 (Risk Visualization UI)
* **動態安全評分**：將複雜的 AI 權重轉化為直覺的 **Trust Score (信任分數)**。
* **智慧警告標籤**：偵測到風險時，自動在網頁右下角注入高對比度的警示 UI，顯示判斷原因與風險等級。

---

## 🛠️ 技術架構 (Technical Stack)

| 模組 | 技術關鍵字 | 核心價值 |
| :--- | :--- | :--- |
| **感知端** | **Chrome Extension V3** | 提供最穩定的網頁 DOM 監聽與選取內容擷取。 |
| **核心引擎** | **FastAPI (Python)** | 高併發處理能力，作為前端與 AI 之間的高速數據公路。 |
| **AI 大腦** | **Transformers (BERT)** | 具備上下文理解能力，識別隱藏在文字中的詐騙邏輯。 |
| **數據協議** | **Pydantic** | 確保前後端數據交換的強健性與型別安全。 |

---

## 🚀 快速開始 (Quick Start)

### 1. 環境準備
請確保您的系統已安裝 **Python 3.9+** 與 **Google Chrome**。

### 2. 啟動後端引擎 (Backend Setup)
```bash
cd core-engine
pip install -r requirements.txt
python main.py
```
*(首次啟動將自動下載預訓練模型，請保持網路暢通)*

### 3. 安裝前端插件 (Frontend Setup)
1. 開啟 Chrome 瀏覽器並輸入 `chrome://extensions/`。
2. 開啟右上角的 **「開發者模式」**。
3. 點擊 **「載入解壓縮後擴充功能」**，選擇專案中的 `browser-ext` 資料夾。

---

## 📈 未來路線 (Roadmap)
- [ ] **自動化鏈結掃描**：主動偵測網頁所有連結的潛在風險。
- [ ] **安全防護面板**：提供使用者每日受攻擊趨勢與日誌記錄。
- [ ] **社群回報機制**：結合群眾智慧，實時更新最新的社交工程樣態。