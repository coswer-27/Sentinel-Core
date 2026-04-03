function escapeHTML(str) {
    const div = document.createElement("div");
    div.textContent = String(str);
    return div.innerHTML;
}

function truncateUrl(url, max = 50) {
    try {
        return url.length > max ? url.slice(0, max) + "\u2026" : url;
    } catch {
        return url;
    }
}

function getSanitizedURL() {
    try {
        const url = new URL(window.location.href);
        return url.origin + url.pathname;
    } catch (e) {
        return "unknown";
    }
}

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
document.addEventListener('mouseup', function() {
    const selectedText = window.getSelection().toString().trim();
    if (selectedText.length >= 2) {
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
                url: getSanitizedURL(),
            },
        });

        showSafetyNotification(data.reason, data.trust_score, text);
    } catch (error) {
        const msg = String(error && error.message != null ? error.message : error);
        if (msg.includes("429")) {
            showSafetyNotification("請求過於頻繁...", 50, "", "#faad14", "⏳", "系統限流");
        } else {
            showSafetyNotification("連線失敗...", 0, "", "#8c8c8c", "❌", "連線失敗");
        }
    }
}

// --- 3. 共用通知容器（右下角 flex 堆疊）---
function getOrCreateNotificationStack() {
    let stack = document.getElementById("sentinel-notification-stack");
    if (!stack) {
        stack = document.createElement("div");
        stack.id = "sentinel-notification-stack";
        Object.assign(stack.style, {
            position: "fixed",
            bottom: "24px",
            right: "24px",
            zIndex: "2147483647",
            display: "flex",
            flexDirection: "column",
            gap: "10px",
            alignItems: "flex-end",
            pointerEvents: "none",
        });
        if (!document.getElementById('sentinel-anim-style')) {
            const styleTag = document.createElement('style');
            styleTag.id = 'sentinel-anim-style';
            styleTag.textContent = `
                @keyframes sentinel-slide-in {
                    from { opacity: 0; transform: translateX(20px); }
                    to   { opacity: 1; transform: translateX(0); }
                }
                @keyframes sentinel-fade-in {
                    from { opacity: 0; transform: translateY(20px); }
                    to   { opacity: 1; transform: translateY(0); }
                }
            `;
            document.head.appendChild(styleTag);
        }
        (document.body || document.documentElement).appendChild(stack);
    }
    return stack;
}

// --- 共用 Toast 樣式基底 ---
const SC_TOAST_BASE_STYLE = {
    maxWidth: "min(360px, calc(100vw - 32px))",
    backgroundColor: "#ffffff",
    color: "#333",
    borderRadius: "10px",
    fontSize: "14px",
    lineHeight: "1.6",
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
    boxShadow: "0 6px 24px rgba(0,0,0,0.45)",
    padding: "14px 18px",
    wordBreak: "break-word",
    whiteSpace: "normal",
};

// --- 4. NLP 文字選取 Toast（三色主題 + 可選 override）---
function showSafetyNotification(
    reason,
    score,
    quotedText = "",
    overrideColor = null,
    overrideIcon = null,
    overrideTitle = null
) {
    // if (document.getElementById("sentinel-notify")) return;

    const raw = Number(score);
    const s = Math.max(0, Math.min(100, Math.round(Number.isFinite(raw) ? raw : 0)));
    const risk = 100 - s;

    let theme;
    if (overrideColor != null) {
        theme = {
            color: overrideColor,
            icon: overrideIcon != null ? overrideIcon : "⚠️",
            title: overrideTitle != null ? overrideTitle : "通知",
            time: 6000,
        };
    } else if (s > 70) {
        theme = { color: "#52c41a", icon: "✅", title: "內容安全", time: 4000 };
    } else if (s >= 40) {
        theme = { color: "#faad14", icon: "⚠️", title: "疑似風險", time: 6000 };
    } else {
        theme = { color: "#ff4d4f", icon: "🚨", title: "高風險內容", time: 8000 };
    }

    const safeReason = escapeHTML(reason);
    const safeTitle = escapeHTML(theme.title);
    const safeIcon = escapeHTML(theme.icon);
    const qt = typeof quotedText === "string" ? quotedText : "";
    const truncated = qt.length > 25 ? qt.slice(0, 25) + "…" : qt;
    const safeQuote = escapeHTML(truncated);
    const quoteBlock =
        qt.trim().length > 0
            ? `<div style="font-size: 12px; color: #666; margin-bottom: 10px; padding: 8px; background: #f5f5f5; border-radius: 4px; border-left: 3px solid ${theme.color};">「${safeQuote}」</div>`
            : "";

    const notify = document.createElement("div");
    notify.id = "sentinel-notify";

    Object.assign(notify.style, {
        width: "320px",
        backgroundColor: "#ffffff",
        color: "#333",
        borderLeft: `6px solid ${theme.color}`,
        boxShadow: "0 10px 25px rgba(0,0,0,0.2)",
        padding: "20px",
        borderRadius: "8px",
        fontFamily: "'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
        fontSize: "14px",
        lineHeight: "1.5",
        pointerEvents: "auto",
        animation: "sentinel-fade-in 0.4s ease-out",
        wordBreak: "break-word",
    });

    notify.innerHTML = `
        <div style="display: flex; align-items: center; margin-bottom: 10px;">
            <span style="font-size: 24px; margin-right: 10px;">${safeIcon}</span>
            <strong style="font-size: 16px; color: ${theme.color};">${safeTitle}</strong>
        </div>
        ${quoteBlock}
        <div style="font-size: 14px; line-height: 1.5; margin-bottom: 12px;">
            ${safeReason}
        </div>
        <div style="background: #f0f0f0; border-radius: 4px; height: 8px; width: 100%; overflow: hidden;">
            <div class="sentinel-risk-fill" style="background: ${theme.color}; width: 0%; height: 100%; border-radius: 4px; transition: width 0.65s cubic-bezier(0.4, 0, 0.2, 1);"></div>
        </div>
        <div style="font-size: 11px; color: #888; margin-top: 5px; text-align: right;">
            危險指數: ${risk}%
        </div>
    `;

    getOrCreateNotificationStack().appendChild(notify);

    const fill = notify.querySelector(".sentinel-risk-fill");
    if (fill) {
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                fill.style.width = `${risk}%`;
            });
        });
    }

    setTimeout(() => {
        notify.style.transition = "opacity 0.5s ease";
        notify.style.opacity = "0";
        setTimeout(() => notify.remove(), 500);
    }, theme.time);
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
            new URL(href);
            // if (new URL(href).hostname === currentHost) continue;
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

function injectLinkToast(anchorEl, text) {
    anchorEl.setAttribute("data-sc-toast", text);
}

// --- Link Scan Toast（掛在 notification stack，hover 時顯示）---
const SC_LINK_TOAST_ID = "sc-link-toast";
let scLinkToastActiveTarget = null;
let scLinkToastListenersBound = false;

function getOrCreateLinkToast() {
    let el = document.getElementById(SC_LINK_TOAST_ID);
    if (!el) {
        el = document.createElement("div");
        el.id = SC_LINK_TOAST_ID;
        el.setAttribute("role", "status");
        Object.assign(el.style, {
            ...SC_TOAST_BASE_STYLE,
            width: "320px",
            pointerEvents: "none",
            display: "none",
            opacity: "0",
            transition: "opacity 0.15s ease",
            borderLeft: "6px solid #4fc3f7",
            order: "9999",
        });
        getOrCreateNotificationStack().appendChild(el);
    }
    return el;
}

function hideLinkToast() {
    const el = document.getElementById(SC_LINK_TOAST_ID);
    if (el) {
        el.style.opacity = "0";
        setTimeout(() => { el.style.display = "none"; }, 150);
    }
    scLinkToastActiveTarget = null;
}

function positionLinkToast(targetEl) {
    const toast = getOrCreateLinkToast();
    const text = targetEl.getAttribute("data-sc-toast");
    if (!text) {
        hideLinkToast();
        return;
    }

    const status = targetEl.getAttribute("data-sc-status") || "default";
    const color = SC_STATUS_COLORS[status] ?? SC_STATUS_COLORS.default;
    toast.style.borderLeft = `4px solid ${color}`;
    const url = targetEl.href || "";
    const safeText = escapeHTML(text);
    const safeUrl = url ? escapeHTML(truncateUrl(url)) : "";
    toast.innerHTML = `<div>${safeText}</div>${safeUrl ? `<div style="font-size:12px;color:#888;margin-top:4px;word-break:break-all;">${safeUrl}</div>` : ""}`;
    toast.style.display = "block";
    requestAnimationFrame(() => { toast.style.opacity = "1"; });
}

function showLinkToast(targetEl) {
    scLinkToastActiveTarget = targetEl;
    positionLinkToast(targetEl);
}

function showLinkToastDirect(text, borderColor = SC_STATUS_COLORS.default, url = "") {
    const toast = getOrCreateLinkToast();
    scLinkToastActiveTarget = null;
    toast.style.borderLeft = `4px solid ${borderColor}`;
    const safeText = escapeHTML(text);
    const safeUrl = url ? escapeHTML(truncateUrl(url)) : "";
    toast.innerHTML = `<div>${safeText}</div>${safeUrl ? `<div style="font-size:12px;color:#888;margin-top:4px;word-break:break-all;">${safeUrl}</div>` : ""}`;
    toast.style.display = "block";
    requestAnimationFrame(() => { toast.style.opacity = "1"; });
}

function initSentinelLinkToasts() {
    if (scLinkToastListenersBound) return;
    scLinkToastListenersBound = true;

    document.addEventListener(
        "mouseover",
        (e) => {
            // 已掃描：直接顯示 toast
            const t = e.target.closest("[data-sc-toast]");
            if (t && document.documentElement.contains(t)) {
                if (scLinkToastActiveTarget !== t) showLinkToast(t);
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
            const from = e.target.closest("[data-sc-toast]");
            if (!from) return;
            const rel = e.relatedTarget;
            if (rel && (from === rel || from.contains(rel))) return;
            hideLinkToast();
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
        injectLinkToast(anchorEl, "✅ 安全：未發現已知威脅");
        return;
    }

    const lower = result.label.toLowerCase();
    const isMalicious = result.label === "Malicious";
    const toastText = isMalicious
        ? `⚠️ 危險：${result.reason}`
        : `❓ 可疑：${result.reason}`;

    anchorEl.setAttribute("data-sc-status", lower);
    anchorEl.classList.add(`sc-flagged-${lower}`);
    injectLinkToast(anchorEl, toastText);

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

    showLinkToastDirect("🔍 Sentinel 掃描中...", SC_STATUS_COLORS.default, href);

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
                showLinkToast(anchorEl);
            } else {
                hideLinkToast();
            }
        } else {
            hideLinkToast();
        }
    } catch (err) {
        showLinkToastDirect("⚠️ 掃描失敗，後端無法連線", SC_STATUS_COLORS.malicious);
        scannedUrls.delete(href);
        setTimeout(() => hideLinkToast(), 3000);
    } finally {
        pendingScans.delete(href);
    }
}

const debouncedObserve = debounce(() => {
    // Google 等動態頁面會替換 DOM 節點，需重新注入已快取的結果
    extractPageLinks().forEach((a) => {
        if (scannedResults.has(a.href) && !a.getAttribute("data-sc-toast")) {
            injectWarningUI(a, scannedResults.get(a.href));
        }
    });
}, 800);

const observer = new MutationObserver(() => {
    debouncedObserve();
});

function bootSentinelLinkScanner() {
    initSentinelLinkToasts();
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["href"] });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootSentinelLinkScanner);
} else {
    bootSentinelLinkScanner();
}
