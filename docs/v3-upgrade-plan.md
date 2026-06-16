# Sentinel-Core v3.0 升級規劃

> AI 跨域資安應用期末專案 — 技術深化方向

---

## 現況診斷

### 已完成（v2.4-stable）
- Chrome Extension MV3（Service Worker + Shadow DOM）
- API Gateway（rate limiting、錯誤遮罩）
- NLP 服務（BERT 情感分析 → 信任分數）
- Link Scanner（GSB + Punycode/TLD 啟發式 + redirect 追蹤）
- 共用 SSRF 防護（`common/validators.py`）
- 非同步 SQLite 日誌（`aiosqlite`）
- 81 項 pytest，覆蓋率 88.5%

### 核心問題

目前 L2 引擎使用 `nlptown/bert-base-multilingual-uncased-sentiment`，這是評論好評度模型（1-5 星），用加權換算成信任分數。學術上站不住腳，且對台灣常見詐騙話術沒有針對性。

---

## v3.0 四大升級方向

---

### 方向 1：Fine-tuned 台灣詐騙語意模型

**目標：** 將現有 sentiment BERT 替換為針對台灣詐騙話術 fine-tune 的分類模型。

#### 模型選型

| 模型 | 參數量 | 特點 |
|------|--------|------|
| `DistilBERT-multilingual` | 66M | 輕量，推論快，適合即時場景 |
| `RoBERTa-base` | 125M | 更穩健，詐騙偵測研究主流選擇 |
| `bert-base-chinese` | 110M | 針對中文預訓練，繁體表現較好 |

研究顯示 RoBERTa-MHARC（RoBERTa + 多頭注意力）在電信詐騙偵測上顯著優於 BERT baseline。

#### 訓練資料來源

```
正樣本（詐騙）：
├── 165 反詐騙專線公布的詐騙話術範例
├── TWCERT/CC 資安通報文字
├── PTT Gossiping 詐騙案例討論串
├── 台灣新聞報導中的詐騙對話截圖 OCR
├── 假 LINE 客服、假投資群組的公開截圖文字
└── 行政院打詐辦公室公告案例

負樣本（正常）：
├── 一般客服對話
├── 正常商業廣告文案
└── 新聞正文段落
```

#### 分類標籤（多分類）

| 標籤 | 描述 | 台灣常見案例 |
|------|------|------------|
| `phishing` | 假冒官方要求驗證帳號 | 假銀行、假健保署 |
| `investment_scam` | 假投資、假虛擬幣 | 假Line群組老師 |
| `romance_scam` | 感情詐騙話術 | 假交友軍官 |
| `parcel_scam` | 假包裹/物流通知 | 假7-11、假黑貓 |
| `gov_impersonation` | 假冒政府機關 | 假檢察官電話 |
| `safe` | 正常文字 | — |

#### 評估指標

- Precision / Recall / F1（各類別 + macro avg）
- 混淆矩陣（哪類詐騙最容易互相誤判）
- 對比實驗：baseline（現有 sentiment model）vs fine-tuned

#### 後端修改

```
service_nlp/
├── detectors/
│   ├── bert_engine.py       ← 改為載入 fine-tuned model
│   └── model/               ← 本地模型權重
└── train/                   ← 新增訓練腳本（可選）
    ├── prepare_dataset.py
    └── fine_tune.py
```

---

### 方向 2：Multimodal 網頁截圖視覺分析

**目標：** 詐騙網站常視覺模仿真實機構（logo、排版、色彩），純文字無法偵測「視覺欺騙」。加入截圖分析形成多模態融合。

#### 架構

```
截圖  →  ViT / EfficientNet-B0  →  visual_score  ─┐
URL   →  existing link scanner  →  url_score     ─┤→ Late Fusion → Final Score
文字  →  fine-tuned BERT        →  text_score    ─┘
```

研究基準：NetPhish-Mix（ViT + URL graph fusion）達到 F1: 0.977、ROC-AUC: 0.997。

#### Chrome Extension 端

```js
// background.js — 截圖當前分頁
async function captureAndAnalyze(tabId) {
    const dataUrl = await chrome.tabs.captureVisibleTab(null, { format: "jpeg", quality: 80 })
    return sentinelBackendFetch("/analyze/visual", {
        method: "POST",
        body: JSON.stringify({ screenshot: dataUrl, url: currentUrl })
    })
}
```

#### 新增服務：service_vision（port 8003）

```
service_vision/
├── main.py             # FastAPI，接收 base64 截圖
├── requirements.txt    # torch, torchvision, Pillow
└── vision/
    ├── __init__.py
    └── vision_detector.py  # EfficientNet-B0 前向推論
```

#### 視覺模型偵測目標

- Logo 位置與相似度（偽造 logo 通常解析度低、位置異常）
- 表單密度（正常網站不會在首頁放多個密碼欄位）
- SSL 鎖頭偽造（圖片中假裝有鎖頭圖示）
- 色彩方案（高度模仿特定銀行/政府網站的配色）

#### API Gateway 新增路由

```python
# api_gateway/main.py
@app.post("/analyze/visual")
async def analyze_visual(request: VisualScanRequest):
    # 轉發至 service_vision:8003
```

---

### 方向 3：LLM 可解釋推理層（XAI）

**目標：** 將多引擎偵測結果彙整，透過 LLM 生成人類可讀的具體推理，從「黑盒分類器」升級為「推理透明的 AI 決策系統」。

#### 觸發條件

任一引擎信心超過閾值時觸發 LLM 解釋：
- BERT trust_score ≤ 40
- URL scan label = Malicious
- 行為分析 risk_score ≥ 70

#### Prompt 設計

```python
EXPLAIN_PROMPT = """
你是一位專業的資安分析師，使用者剛剛瀏覽了一個可疑頁面。
以下是多維度自動偵測結果，請根據這些訊號進行推理：

[語意分析] 信任分數：{bert_score}/100，偵測類別：{bert_label}
[URL 分析] 風險等級：{url_label}，redirect 跳轉：{hop_count} 層，最終域名：{final_url}
[行為分析] 觸發異常：{behavior_flags}
[原始文字] {text_snippet}

請用繁體中文回覆，包含：
1. 這為何可能是詐騙（具體理由，引用上述偵測訊號）
2. 最關鍵的風險訊號（1-2 點）
3. 給使用者的具體建議行動

語氣：清晰、直接、不過度驚嚇，字數控制在 100 字以內。
"""
```

#### 多 Agent 進階架構

```
Agent 1（語意分析師）: 分析 BERT 結果 + 觸發的 regex 規則
        ↓
Agent 2（URL 安全師）: 分析 link scanner 結果 + redirect 鏈
        ↓
Agent 3（裁決者）:     彙整兩個 agent 意見 → 最終判決 + 解釋
```

#### 新增服務：service_explain（port 8004）

```
service_explain/
├── main.py         # FastAPI，接收多引擎結果
├── requirements.txt
└── explainer/
    ├── __init__.py
    └── llm_explainer.py  # 呼叫 Claude / OpenAI API
```

#### 前端展示

```
現在：⚠️ Danger — 信任分 23/100

升級後：
⚠️ 高風險詐騙警示
BERT 偵測到假冒銀行客服話術（信任分 23）；
連結經歷 4 層 redirect 指向可疑 .tk 域名；
頁面包含偽造表單，密碼欄位提交目標為外部域名。
→ 建議立即關閉此頁面，不要輸入任何個人資料。
```

---

### 方向 4：頁面行為異常偵測

**目標：** 釣魚網站的特徵不只在「說什麼」，更在「做什麼」——JS 混淆、動態代碼注入、表單劫持、點擊劫持。

#### content.js 行為特徵擷取

```js
function extractBehaviorFeatures() {
    return {
        // 危險 JS 模式
        eval_count: countDynamicExecution(),      // eval() / Function() 呼叫數
        dynamic_script_inject: hasScriptInject(), // 動態插入 <script>
        obfuscated_strings: hasObfuscation(),     // 高 entropy 字串（base64/hex）

        // 表單行為
        password_field_count: document.querySelectorAll('input[type=password]').length,
        form_action_external: isFormTargetExternal(),  // 表單提交到外部域
        hidden_input_count: countHiddenInputs(),

        // 視覺欺騙
        transparent_overlay: hasClickjackingOverlay(), // 透明覆蓋層
        iframe_count: document.querySelectorAll('iframe[src]').length,
        fake_cursor: hasFakeCursor(),

        // 域名（已有）
        redirect_hops: hopCount,
        suspicious_tld: isSuspiciousTLD(currentUrl)
    }
}
```

#### 後端評分

```python
# 規則式評分（也可換成 ML 分類器）
BEHAVIOR_WEIGHTS = {
    "eval_count":           lambda v: min(v * 10, 40),
    "dynamic_script_inject": lambda v: 30 if v else 0,
    "password_field_count": lambda v: min(v * 5, 20),
    "form_action_external": lambda v: 25 if v else 0,
    "transparent_overlay":  lambda v: 35 if v else 0,
    "iframe_count":         lambda v: min(v * 5, 15),
}

def compute_behavior_score(features: dict) -> int:
    score = sum(fn(features.get(key, 0)) for key, fn in BEHAVIOR_WEIGHTS.items())
    return min(score, 100)
```

#### 新增端點

```
POST /analyze/behavior
→ 接收 extractBehaviorFeatures() 的結果
→ 回傳 behavior_score + triggered_flags
```

---

## v3.0 整體架構

```
Sentinel-Core v3.0
│
│  Chrome Extension (browser_ext/)
│  ├── content.js        — 選取文字、hover 掃描、行為特徵擷取、截圖觸發
│  └── background.js     — Service Worker 中繼
│
↓  HTTP via Service Worker
│
│  API Gateway (port 8000)
│  ├── POST /analyze          → service_nlp    (port 8001)  [L2 fine-tuned]
│  ├── POST /analyze/links    → service_link   (port 8002)  [GSB + heuristic]
│  ├── POST /analyze/visual   → service_vision (port 8003)  [EfficientNet]
│  ├── POST /analyze/behavior → api_gateway 內部評分        [行為規則]
│  └── POST /explain          → service_explain (port 8004) [LLM XAI]
│
↓  最終融合
│
└── Fusion Score = weighted(bert, url, visual, behavior)
    → 若超過閾值 → /explain → LLM 推理 → 前端顯示完整解釋
```

### 各層權重（可調參數）

```python
FUSION_WEIGHTS = {
    "bert_score":     0.30,   # 語意理解
    "url_score":      0.25,   # URL/GSB 分析
    "visual_score":   0.25,   # 截圖視覺分析
    "behavior_score": 0.20,   # 頁面行為分析
}
```

---

## 實作優先順序建議

| 優先 | 方向 | 理由 |
|------|------|------|
| 1st | 方向 1（fine-tuned 模型） | 直接替換現有弱點，學術貢獻最清晰 |
| 2nd | 方向 3（LLM 解釋層） | 代碼量少、展示效果最直觀 |
| 3rd | 方向 4（行為偵測） | 獨特視角，純前端 feature 擷取技術難度合理 |
| 4th | 方向 2（截圖分析） | 技術最複雜，視時間決定是否加入 |

---

## 參考研究

- [NetPhish-Mix: ViT + URL Multi-Modal Phishing Detection](https://etasr.com/index.php/ETASR/article/view/15759) — F1: 0.977
- [RoBERTa for Telecom Fraud Detection](https://www.researchgate.net/publication/387006628)
- [LLMs for Phishing Detection & Explainability](https://arxiv.org/pdf/2506.13746)
- [Multimodal LLMs for Phishing Webpage Detection](https://arxiv.org/abs/2408.05941)
- [Client-Side LLM Inference for URL Analysis](https://arxiv.org/pdf/2506.03656)
- [JavaSith: Browser Extension Malicious JS Analysis](https://arxiv.org/html/2505.21263v1)
