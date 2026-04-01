// --- 0. 經 background 請求本機 API（避開 PNA：非 HTTPS 頁面無法直接 fetch 127.0.0.1）---
function sentinelBackendFetch(url, options = {}) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(
      {
        type: "SENTINEL_BACKEND_FETCH",
        url,
        method: options.method || "GET",
        headers: options.headers,
        body: options.body,
      },
      (res) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }
        if (!res || !res.ok) {
          const hint = res && res.error ? res.error : `HTTP ${res ? res.status : "?"}`;
          reject(new Error(hint));
          return;
        }
        resolve(res.data);
      }
    );
  });
}

// --- 1. 監聽選取事件 ---
console.log("📍 開始掛載監聽器...");

document.addEventListener('mouseup', function(event) {
    console.log("🖱️ 偵測到滑鼠放開動作");

    let selection = window.getSelection();
    let selectedText = selection.toString().trim();

    console.log("📝 選取的文字內容:", selectedText);

    if (selectedText.length >= 2) {
        console.log("🚀 文字長度達標，準備發送給後端...");
        analyzeText(selectedText);
    }
});

// --- 2. 與後端通訊 ---
async function analyzeText(text) {
    try {
        const data = await sentinelBackendFetch("http://127.0.0.1:8000/analyze", {
            method: "POST",
            body: {
                request_id: "ui-test-" + Date.now(),
                payload_type: "text",
                content: text,
                url: window.location.href,
            },
        });

        if (data.label === "Danger") {
            showSafetyNotification(data.reason, data.trust_score, text);
        }
    } catch (error) {
        console.error("Sentinel-Core 連線失敗:", error);
    }
}

// --- 3. UI 注入函式 ---
function showSafetyNotification(reason, score, quotedText = "") {
    // 【修復 UI-04】物理移除舊通知，確保新通知取代而非重疊
    const oldNotify = document.getElementById('sentinel-notify');
    if (oldNotify) oldNotify.remove();

    const notify = document.createElement('div');
    notify.id = 'sentinel-notify';

    const scoreNum = Number(score);
    const safeScore = Number.isFinite(scoreNum)
        ? Math.max(0, Math.min(100, Math.round(scoreNum)))
        : 0;
    const themeColor = safeScore <= 30 ? '#ff4d4f' : '#faad14';
    const qt = typeof quotedText === 'string' ? quotedText : '';
    const shortText = qt.length > 25 ? qt.substring(0, 25) + '...' : qt;
    const risk = 100 - safeScore;


    Object.assign(notify.style, {
        position: 'fixed', bottom: '30px', right: '30px', width: '320px',
        backgroundColor: '#ffffff', color: '#333', borderLeft: `6px solid ${themeColor}`,
        boxShadow: '0 10px 25px rgba(0,0,0,0.2)', padding: '20px', borderRadius: '8px',
        zIndex: '1000000', fontFamily: "'Segoe UI', Roboto, sans-serif",
        animation: 'sentinel-slide-in 0.4s ease-out'
    });

    const headerRow = document.createElement('div');
    Object.assign(headerRow.style, { display: 'flex', alignItems: 'center', marginBottom: '8px' });
    const iconSpan = document.createElement('span');
    iconSpan.style.fontSize = '20px';
    iconSpan.style.marginRight = '10px';
    iconSpan.textContent = '🚨';
    const titleStrong = document.createElement('strong');
    Object.assign(titleStrong.style, { fontSize: '15px', color: '#ff4d4f' });
    titleStrong.textContent = '分析報告：高風險內容';
    headerRow.appendChild(iconSpan);
    headerRow.appendChild(titleStrong);

    const quoteBox = document.createElement('div');
    Object.assign(quoteBox.style, {
        fontStyle: 'italic', color: '#666', fontSize: '12px', background: '#f9f9f9',
        padding: '8px', borderRadius: '4px', marginBottom: '10px', borderLeft: '3px solid #ddd'
    });
    quoteBox.textContent = shortText ? `"${shortText}"` : '""';

    const reasonRow = document.createElement('div');
    Object.assign(reasonRow.style, { fontSize: '14px', lineHeight: '1.4', marginBottom: '12px' });
    const reasonLabel = document.createElement('strong');
    reasonLabel.textContent = '原因：';
    reasonRow.appendChild(reasonLabel);
    reasonRow.appendChild(document.createTextNode(typeof reason === 'string' ? reason : ''));

    const barOuter = document.createElement('div');
    Object.assign(barOuter.style, {
        background: '#eee', height: '10px', borderRadius: '5px',
        overflow: 'hidden', position: 'relative'
    });
    const barInner = document.createElement('div');
    Object.assign(barInner.style, {
        background: '#ff4d4f', width: `${risk}%`, height: '100%', transition: 'width 0.8s ease'
    });
    barOuter.appendChild(barInner);

    const footerRow = document.createElement('div');
    Object.assign(footerRow.style, {
        fontSize: '12px', color: '#666', marginTop: '6px',
        display: 'flex', justifyContent: 'space-between'
    });
    const trustSpan = document.createElement('span');
    trustSpan.textContent = `信任值: ${safeScore}%`;
    const riskSpan = document.createElement('span');
    Object.assign(riskSpan.style, { fontWeight: 'bold', color: '#ff4d4f' });
    riskSpan.textContent = `風險佔比: ${risk}%`;
    footerRow.appendChild(trustSpan);
    footerRow.appendChild(riskSpan);

    notify.appendChild(headerRow);
    notify.appendChild(quoteBox);
    notify.appendChild(reasonRow);
    notify.appendChild(barOuter);
    notify.appendChild(footerRow);

    // 注入動畫 CSS（id 去重，避免重複注入）
    if (!document.getElementById('sentinel-style')) {
        const styleTag = document.createElement('style');
        styleTag.id = 'sentinel-style';
        styleTag.textContent = `
            @keyframes sentinel-slide-in {
                from { opacity: 0; transform: translateX(50px); }
                to { opacity: 1; transform: translateX(0); }
            }
        `;
        document.head.appendChild(styleTag);
    }

    document.body.appendChild(notify);

    // 【修復 UI-04】確保 6 秒後移除的是「當前這一個」DOM 實例
    setTimeout(() => {
        if (document.body.contains(notify)) {
            notify.style.opacity = '0';
            notify.style.transition = 'opacity 0.5s';
            setTimeout(() => {
                if (document.body.contains(notify)) notify.remove();
            }, 500);
        }
    }, 6000);
}

// --- 主動鏈結掃描模組 ---
const BACKEND_URL = "http://127.0.0.1:8000";
const scannedUrls = new Set();

const scannedResults = new Map(); // href -> result，用於 Google DOM 刷新後重新注入
const pendingScans = new Set();   // 正在掃描中的 href，避免重複觸發

const SC_STATUS_COLORS = {
    safe:       "#4fc3f7",  // 藍色
    suspicious: "#f59e0b",  // 橘黃色
    malicious:  "#dc3545",  // 紅色
    default:    "#4fc3f7",  // 未知 fallback
};

function debounce(fn, delay) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), delay);
    };
}

function collectAnchorsFromRoot(root, seen, currentHost, out) {
    const elements = root.querySelectorAll("a[href], area[href]");
    for (const a of elements) {
        const raw = (a.getAttribute("href") || "").trim();
        if (!raw || raw.startsWith("#") || raw.toLowerCase().startsWith("javascript:")) {
            continue;
        }
        let href = "";
        try {
            href = a.href;
        } catch {
            continue;
        }
        if (!href || seen.has(href)) continue;
        try {
            const host = new URL(href).hostname;
            // if (host === currentHost || host === "") continue;
        } catch {
            continue;
        }
        seen.add(href);
        out.push(a);
    }
    // 遞迴掃 Shadow DOM
    const allEls = root.querySelectorAll("*");
    for (const el of allEls) {
        if (el.shadowRoot) {
            collectAnchorsFromRoot(el.shadowRoot, seen, currentHost, out);
        }
    }
}

function extractPageLinks() {
    const currentHost = window.location.hostname;
    const seen = new Set();
    const out = [];
    collectAnchorsFromRoot(document, seen, currentHost, out);
    return out;
}

function injectTooltip(anchorEl, text) {
    anchorEl.setAttribute("data-sc-tooltip", text);
}

// --- 浮動 Tooltip（掛在 body，避免父層 overflow:hidden 裁切）---
const SC_FLOATING_TOOLTIP_ID = "sc-floating-tooltip";
let scTooltipActiveTarget = null;
let scTooltipListenersBound = false;

function getOrCreateFloatingTooltip() {
    let el = document.getElementById(SC_FLOATING_TOOLTIP_ID);
    if (!el) {
        el = document.createElement("div");
        el.id = SC_FLOATING_TOOLTIP_ID;
        el.setAttribute("role", "tooltip");
        Object.assign(el.style, {
            position: "fixed",
            zIndex: "2147483646",
            bottom: "24px",
            right: "24px",
            maxWidth: "min(420px, calc(100vw - 32px))",
            padding: "14px 18px",
            background: "#1a1a2e",
            color: "#f0f0f0",
            borderRadius: "10px",
            fontSize: "14px",
            lineHeight: "1.6",
            fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
            boxShadow: "0 6px 24px rgba(0,0,0,0.45)",
            pointerEvents: "none",
            visibility: "hidden",
            opacity: "0",
            transition: "opacity 0.15s ease",
            wordBreak: "break-word",
            whiteSpace: "normal",
            borderLeft: "4px solid #4fc3f7",
        });
        (document.body || document.documentElement).appendChild(el);
    }
    return el;
}

function hideFloatingTooltip() {
    const el = document.getElementById(SC_FLOATING_TOOLTIP_ID);
    if (el) {
        el.style.visibility = "hidden";
        el.style.opacity = "0";
    }
    scTooltipActiveTarget = null;
}


function positionFloatingTooltip(targetEl) {
    const tip = getOrCreateFloatingTooltip();
    const text = targetEl.getAttribute("data-sc-tooltip");
    if (!text) {
        hideFloatingTooltip();
        return;
    }

    const status = targetEl.getAttribute("data-sc-status") || "default";
    tip.style.borderLeft = `4px solid ${SC_STATUS_COLORS[status] ?? SC_STATUS_COLORS.default}`;
    tip.textContent = text;
    // 固定右下角，不需要動態計算座標
    tip.style.visibility = "visible";
    tip.style.opacity = "1";
}

function showFloatingTooltip(targetEl) {
    scTooltipActiveTarget = targetEl;
    positionFloatingTooltip(targetEl);
}

function showFloatingTooltipDirect(text, borderColor = SC_STATUS_COLORS.default) {
    const tip = getOrCreateFloatingTooltip();
    scTooltipActiveTarget = null;
    tip.style.borderLeft = `4px solid ${borderColor}`;
    tip.textContent = text;
    tip.style.visibility = "visible";
    tip.style.opacity = "1";
}

function initSentinelFloatingTooltips() {
    if (scTooltipListenersBound) return;
    scTooltipListenersBound = true;

    document.addEventListener(
        "mouseover",
        (e) => {
            // 已掃描：直接顯示 tooltip
            const t = e.target.closest("[data-sc-tooltip]");
            if (t && document.documentElement.contains(t)) {
                if (scTooltipActiveTarget !== t) showFloatingTooltip(t);
                return;
            }
            // 未掃描：hover 時觸發掃描
            const a = e.target.closest("a[href]");
            if (a) scanOnHover(a);
        },
        true
    );

    document.addEventListener(
        "mouseout",
        (e) => {
            const from = e.target.closest("[data-sc-tooltip]");
            if (!from) return;
            const rel = e.relatedTarget;
            if (rel && (from === rel || from.contains(rel))) return;
            hideFloatingTooltip();
        },
        true
    );
}

function ensureScanStyles() {
    if (document.getElementById("sc-styles")) return;
    const style = document.createElement("style");
    style.id = "sc-styles";
    style.textContent = `
      .sc-badge {
        display: inline-flex;
        align-items: center;
        font-size: 0.78em;
        font-weight: 600;
        margin-left: 5px;
        padding: 1px 6px;
        border-radius: 4px;
        cursor: help;
        vertical-align: middle;
        line-height: 1.4;
        letter-spacing: 0.02em;
      }
      .sc-badge.sc-malicious {
        background: ${SC_STATUS_COLORS.malicious}1f;
        color: #b91c1c;
        border: 1px solid ${SC_STATUS_COLORS.malicious}59;
      }
      .sc-badge.sc-suspicious {
        background: ${SC_STATUS_COLORS.suspicious}1f;
        color: #92400e;
        border: 1px solid ${SC_STATUS_COLORS.suspicious}59;
      }
      a.sc-flagged-safe {
        outline: 2px solid ${SC_STATUS_COLORS.safe} !important;
        outline-offset: 2px !important;
        border-radius: 3px !important;
        text-decoration-color: ${SC_STATUS_COLORS.safe} !important;
      }
      a.sc-flagged-malicious {
        outline: 2px solid ${SC_STATUS_COLORS.malicious} !important;
        outline-offset: 2px !important;
        border-radius: 3px !important;
        text-decoration-color: ${SC_STATUS_COLORS.malicious} !important;
      }
      a.sc-flagged-suspicious {
        outline: 2px solid ${SC_STATUS_COLORS.suspicious} !important;
        outline-offset: 2px !important;
        border-radius: 3px !important;
        text-decoration-color: ${SC_STATUS_COLORS.suspicious} !important;
      }
    `;
    document.head.appendChild(style);
}

function injectWarningUI(anchorEl, result) {
    ensureScanStyles();

    if (result.label === "Safe") {
        anchorEl.setAttribute("data-sc-status", "safe");
        injectTooltip(anchorEl, "✅ 安全：未發現已知威脅");
        return;
    }

    const lower = result.label.toLowerCase();
    const isMalicious = result.label === "Malicious";
    const tooltipText = isMalicious
        ? `⚠️ 危險：${result.reason}`
        : `❓ 可疑：${result.reason}`;

    anchorEl.setAttribute("data-sc-status", lower);
    anchorEl.classList.add(`sc-flagged-${lower}`);
    injectTooltip(anchorEl, tooltipText);

    const badge = document.createElement("span");
    badge.className = `sc-badge sc-${lower}`;
    badge.textContent = isMalicious ? "⚠️ 危險" : "❓ 可疑";
    anchorEl.insertAdjacentElement("afterend", badge);
}

async function scanOnHover(anchorEl) {
    const href = anchorEl.href;
    if (!href || scannedUrls.has(href) || pendingScans.has(href)) return;

    pendingScans.add(href);
    scannedUrls.add(href);

    showFloatingTooltipDirect("🔍 Sentinel 掃描中...");

    try {
        const data = await sentinelBackendFetch(`${BACKEND_URL}/analyze/links`, {
            method: "POST",
            body: { urls: [href] },
        });

        const result = data.results[0];
        if (result) {
            scannedResults.set(result.url, result);
            injectWarningUI(anchorEl, result);
            if (document.documentElement.contains(anchorEl)) {
                showFloatingTooltip(anchorEl);
            } else {
                hideFloatingTooltip();
            }
        } else {
            hideFloatingTooltip();
        }
    } catch (err) {
        showFloatingTooltipDirect("⚠️ 掃描失敗，後端無法連線", SC_STATUS_COLORS.malicious);
        scannedUrls.delete(href);
        setTimeout(() => hideFloatingTooltip(), 3000);
    } finally {
        pendingScans.delete(href);
    }
}

const debouncedObserve = debounce(() => {
    // Google 等動態頁面會替換 DOM 節點，需重新注入已快取的結果
    extractPageLinks().forEach((a) => {
        if (scannedResults.has(a.href) && !a.getAttribute("data-sc-tooltip")) {
            injectWarningUI(a, scannedResults.get(a.href));
        }
    });
}, 800);

const observer = new MutationObserver(() => {
    debouncedObserve();
});

function bootSentinelLinkScanner() {
    initSentinelFloatingTooltips();
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["href"] });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootSentinelLinkScanner);
} else {
    bootSentinelLinkScanner();
}
