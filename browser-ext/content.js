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
            showSafetyNotification(data.reason, data.trust_score);
        }
    } catch (error) {
        console.error("Sentinel-Core 連線失敗:", error);
    }
}

// --- 3. UI 注入函式 (Toast Notification) ---
function showSafetyNotification(reason, score) {
    if (document.getElementById('sentinel-notify')) return;

    const notify = document.createElement('div');
    notify.id = 'sentinel-notify';

    Object.assign(notify.style, {
        position: 'fixed',
        bottom: '30px',
        right: '30px',
        width: '320px',
        backgroundColor: '#ffffff',
        color: '#333',
        borderLeft: '6px solid #ff4d4f',
        boxShadow: '0 10px 25px rgba(0,0,0,0.2)',
        padding: '20px',
        borderRadius: '8px',
        zIndex: '1000000',
        fontFamily: "'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
        animation: 'sentinel-fade-in 0.4s ease-out'
    });

    notify.innerHTML = `
        <div style="display: flex; align-items: center; margin-bottom: 10px;">
            <span style="font-size: 24px; margin-right: 10px;">⚠️</span>
            <strong style="font-size: 16px; color: #ff4d4f;">偵測到潛在風險！</strong>
        </div>
        <div style="font-size: 14px; line-height: 1.5; margin-bottom: 12px;">
            ${reason}
        </div>
        <div style="background: #f5f5f5; border-radius: 4px; height: 8px; width: 100%; position: relative;">
            <div style="background: #ff4d4f; width: ${100 - score}%; height: 100%; border-radius: 4px;"></div>
        </div>
        <div style="font-size: 11px; color: #888; margin-top: 5px; text-align: right;">
            危險指數: ${100 - score}%
        </div>
    `;

    const styleTag = document.createElement('style');
    styleTag.textContent = `
        @keyframes sentinel-fade-in {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
    `;
    document.head.appendChild(styleTag);

    document.body.appendChild(notify);

    setTimeout(() => {
        notify.style.opacity = '0';
        notify.style.transition = 'opacity 0.5s ease';
        setTimeout(() => notify.remove(), 500);
    }, 6000);
}

// --- 主動鏈結掃描模組 ---
const BACKEND_URL = "http://127.0.0.1:8000";
const scannedUrls = new Set();

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
            if (host === currentHost || host === "") continue;
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

    tip.textContent = text;
    // 固定右下角，不需要動態計算座標
    tip.style.visibility = "visible";
    tip.style.opacity = "1";
}

function showFloatingTooltip(targetEl) {
    scTooltipActiveTarget = targetEl;
    positionFloatingTooltip(targetEl);
}

function initSentinelFloatingTooltips() {
    if (scTooltipListenersBound) return;
    scTooltipListenersBound = true;

    document.addEventListener(
        "mouseover",
        (e) => {
            const t = e.target.closest("[data-sc-tooltip]");
            if (!t || !document.documentElement.contains(t)) return;
            if (scTooltipActiveTarget === t) return;
            showFloatingTooltip(t);
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
      .sc-badge { font-size: 0.85em; margin-left: 4px; cursor: help; vertical-align: middle; }
      .sc-malicious { outline: 2px solid red; border-radius: 2px; }
      .sc-suspicious { background: #fff3cd; border-radius: 2px; }
      a.sc-flagged-malicious { outline: 2px solid #dc3545 !important; }
      a.sc-flagged-suspicious { background: rgba(255,193,7,0.2) !important; }
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

    const badge = document.createElement("span");
    const lower = result.label.toLowerCase();
    badge.className = `sc-badge sc-${lower}`;
    badge.textContent = result.label === "Malicious" ? "⚠️" : "❓";
    if (result.label === "Malicious") {
        badge.title = `⚠️ 危險：${result.reason}`;
    } else {
        badge.title = `❓ 可疑：${result.reason}`;
    }

    anchorEl.setAttribute("data-sc-status", lower);
    anchorEl.classList.add(`sc-flagged-${lower}`);
    anchorEl.insertAdjacentElement("afterend", badge);
}

async function scanNewLinks(anchors) {
    const fresh = anchors.filter((a) => !scannedUrls.has(a.href));
    if (fresh.length === 0) return;

    fresh.forEach((a) => scannedUrls.add(a.href));

    let toast = document.getElementById("sc-scanning-toast");
    if (!toast) {
        toast = document.createElement("div");
        toast.id = "sc-scanning-toast";
        toast.style.cssText =
            "position:fixed;bottom:20px;right:20px;background:#333;color:#fff;padding:10px 16px;border-radius:8px;z-index:99999;font-size:13px;";
        document.body.appendChild(toast);
    }
    toast.textContent = `🔍 Sentinel 掃描中... (0/${fresh.length})`;

    try {
        const data = await sentinelBackendFetch(`${BACKEND_URL}/analyze/links`, {
            method: "POST",
            body: { urls: fresh.map((a) => a.href) },
        });

        const urlMap = new Map(fresh.map((a) => [a.href, a]));
        data.results.forEach((result) => {
            const el = urlMap.get(result.url);
            if (el) injectWarningUI(el, result);
        });

        const dangerous = data.results.filter((r) => r.label === "Malicious").length;
        const suspicious = data.results.filter((r) => r.label === "Suspicious").length;
        toast.textContent = `✅ 掃描完成：${dangerous} 危險 / ${suspicious} 可疑 / ${fresh.length} 個連結`;
    } catch (err) {
        toast.textContent = "⚠️ 掃描失敗，後端無法連線";
        fresh.forEach((a) => scannedUrls.delete(a.href));
    } finally {
        setTimeout(() => {
            const t = document.getElementById("sc-scanning-toast");
            if (t) t.remove();
        }, 5000);
    }
}

async function scanAllLinks() {
    const anchors = extractPageLinks();
    await scanNewLinks(anchors);
}

const debouncedObserve = debounce(() => {
    const newAnchors = extractPageLinks().filter((a) => !scannedUrls.has(a.href));
    if (newAnchors.length > 0) scanNewLinks(newAnchors);
}, 800);

const observer = new MutationObserver(() => {
    debouncedObserve();
});

function bootSentinelLinkScanner() {
    initSentinelFloatingTooltips();
    scanAllLinks();
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["href"] });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootSentinelLinkScanner);
} else {
    bootSentinelLinkScanner();
}
