# 🛡️ Sentinel-Core (哨兵核心)

**Sentinel-Core** 是一個結合 AI 語意分析與瀏覽器擴充功能的資安防護系統。透過即時監控網頁內容，識別潛在的詐騙資訊與社交工程威脅。

## 📊 系統架構與流程
本專案目前實作了從前端擷取到後端分析的完整閉環：

```mermaid
sequenceDiagram
    participant User as 使用者 (Browser)
    participant Ext as Sentinel Extension (Frontend)
    participant API as FastAPI Server (Backend)

    User->>Ext: 選取網頁文字 (Mouse Up)
    Ext->>API: 發送 POST /analyze (JSON Payload)
    API->>API: 執行 關鍵字/AI 語意分析
    API-->>Ext: 回傳 SecurityResponse (Score, Label, Reason)
    Note over Ext: 若 Label 為 Danger
    Ext->>User: 彈出 Alert 警告視窗