function escapeHTML(str) {
    const div = document.createElement("div");
    div.textContent = String(str);
    return div.innerHTML;
}

// 安全 markdown-lite：先 escape（防 XSS），再轉常見語法。
// LLM（Gemini）解釋常含 **粗體**、*斜體*、- 條列、換行。
function scFormatMarkdownLite(text) {
    let s = escapeHTML(text == null ? "" : String(text));
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/__([^_]+)__/g, "<strong>$1</strong>");
    s = s.replace(/\*([^*\n]+)\*/g, "<em>$1</em>");
    s = s.replace(/^[ \t]*[-•]\s+/gm, "・");
    s = s.replace(/\n/g, "<br>");
    return s;
}

function truncateUrl(url, max = 50) {
    try {
        return url.length > max ? url.slice(0, max) + "…" : url;
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

function hostOf(u) {
    try {
        return new URL(u).hostname.toLowerCase();
    } catch {
        return "";
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

// =====================================================================
//  Sentinel 設計系統（tokens + icon）— 套用於所有注入 UI，確保一致性
// =====================================================================

// 號誌語意色：安全 / 可疑 / 危險 / 掃描中
const SC_PALETTE = {
    safe:       { base: "#16a34a", soft: "rgba(22,163,74,0.10)",  ring: "rgba(22,163,74,0.28)" },
    suspicious: { base: "#d97706", soft: "rgba(217,119,6,0.10)",  ring: "rgba(217,119,6,0.28)" },
    malicious:  { base: "#dc2626", soft: "rgba(220,38,38,0.10)",  ring: "rgba(220,38,38,0.30)" },
    scanning:   { base: "#0ea5e9", soft: "rgba(14,165,233,0.10)", ring: "rgba(14,165,233,0.28)" },
    neutral:    { base: "#64748b", soft: "rgba(100,116,139,0.10)", ring: "rgba(100,116,139,0.24)" },
};

// 連結標記用的純色（外框）— 與號誌色一致
const SC_STATUS_COLORS = {
    safe:       SC_PALETTE.safe.base,
    suspicious: SC_PALETTE.suspicious.base,
    malicious:  SC_PALETTE.malicious.base,
    default:    SC_PALETTE.scanning.base,
};

// monoline SVG icon（stroke = currentColor，由父層 color 決定顏色）
const SC_ICON = {
    shieldCheck: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l7 3v5c0 4.4-3 7.2-7 8.7-4-1.5-7-4.3-7-8.7V6l7-3z"/><path d="M9 12l2 2 4-4"/></svg>`,
    shieldAlert: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l7 3v5c0 4.4-3 7.2-7 8.7-4-1.5-7-4.3-7-8.7V6l7-3z"/><path d="M12 8.5v4"/><path d="M12 16h.01"/></svg>`,
    alertTriangle: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 4.3 2.5 18a2 2 0 0 0 1.7 3h15.6a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0z"/><path d="M12 9.5v4"/><path d="M12 17h.01"/></svg>`,
    radar: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7.5"/><path d="M21 21l-4.3-4.3"/></svg>`,
    spinner: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2.4" stroke-linecap="round"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-opacity="0.22"/><path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor"/></svg>`,
    cpu: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="6" width="12" height="12" rx="2.5"/><rect x="9.5" y="9.5" width="5" height="5" rx="1"/><path d="M9 2v2M15 2v2M9 20v2M15 20v2M2 9h2M2 15h2M20 9h2M20 15h2"/></svg>`,
    wifiOff: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 2l20 20"/><path d="M8.5 16.4a5 5 0 0 1 7 0"/><path d="M5 12.9a10 10 0 0 1 3.3-2.2M19 12.9a10 10 0 0 0-5.4-2.7"/><path d="M2 8.8a16 16 0 0 1 4.3-2.6M22 8.8a16 16 0 0 0-9.6-2.7"/><path d="M12 20h.01"/></svg>`,
    clock: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 1.8"/></svg>`,
    close: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6l12 12M18 6 6 18"/></svg>`,
};

// 風險分級 → 主題（icon 用 key，顏色用 palette）
function scThemeForScore(s) {
    if (s > 70) return { tone: "safe", icon: "shieldCheck", title: "內容安全", time: 4200 };
    if (s >= 40) return { tone: "suspicious", icon: "alertTriangle", title: "疑似風險", time: 6500 };
    return { tone: "malicious", icon: "shieldAlert", title: "高風險內容", time: 8500 };
}

// =====================================================================
//  Shadow DOM 覆蓋層（toast stack + tooltip 共用一個隔離根）
// =====================================================================

let _scShadow = null;
let _scToastStack = null;
let _scTipEl = null;

function scStyleSheet() {
    return `
    :host { all: initial; }
    * { box-sizing: border-box; }
    .sc-stack {
        position: fixed; bottom: 22px; right: 22px;
        display: flex; flex-direction: column; gap: 12px; align-items: flex-end;
        max-width: min(380px, calc(100vw - 28px));
        pointer-events: none;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang TC", "Microsoft JhengHei", Roboto, sans-serif;
    }

    .sc-card {
        --tone: ${SC_PALETTE.neutral.base};
        --tone-soft: ${SC_PALETTE.neutral.soft};
        --tone-ring: ${SC_PALETTE.neutral.ring};
        position: relative; width: 340px; max-width: 100%;
        background: #ffffff;
        border-radius: 14px;
        padding: 16px 18px 17px;
        color: #1f2937;
        pointer-events: auto;
        overflow: hidden;
        box-shadow:
            0 1px 2px rgba(15,23,42,0.06),
            0 8px 18px -6px rgba(15,23,42,0.16),
            0 18px 40px -12px rgba(15,23,42,0.24);
        border: 1px solid rgba(15,23,42,0.06);
        transform: translateY(14px); opacity: 0;
        animation: sc-rise 0.42s cubic-bezier(0.16,1,0.3,1) forwards;
    }
    .sc-card.sc-leaving { animation: sc-fall 0.32s ease forwards; }
    .sc-card::before {
        content: ""; position: absolute; inset: 0 auto 0 0; width: 4px;
        background: var(--tone);
    }

    .sc-head { display: flex; align-items: center; gap: 11px; }
    .sc-chip {
        flex: 0 0 auto; width: 38px; height: 38px; border-radius: 11px;
        display: grid; place-items: center;
        background: var(--tone-soft); color: var(--tone);
        box-shadow: inset 0 0 0 1px var(--tone-ring);
    }
    .sc-chip svg { width: 21px; height: 21px; }
    .sc-titles { min-width: 0; flex: 1; }
    .sc-title { font-size: 15px; font-weight: 650; letter-spacing: -0.01em; color: var(--tone); line-height: 1.25; }
    .sc-sub { font-size: 11.5px; color: #94a3b8; margin-top: 1px; letter-spacing: 0.02em; }

    .sc-x {
        flex: 0 0 auto; width: 26px; height: 26px; margin: -4px -4px 0 0;
        border-radius: 8px; display: grid; place-items: center;
        color: #cbd5e1; cursor: pointer; transition: all 0.16s ease;
    }
    .sc-x svg { width: 15px; height: 15px; }
    .sc-x:hover { color: var(--tone); background: var(--tone-soft); }

    .sc-quote {
        margin-top: 13px; padding: 9px 11px; border-radius: 9px;
        background: #f8fafc; border: 1px solid rgba(15,23,42,0.05);
        font-size: 12px; color: #64748b; line-height: 1.5;
    }
    .sc-quote b { color: #475569; font-weight: 600; }

    .sc-reason { margin-top: 12px; font-size: 13.5px; line-height: 1.6; color: #334155; }

    .sc-ai {
        margin-top: 13px; padding: 11px 12px; border-radius: 10px;
        background: var(--tone-soft);
        border: 1px solid var(--tone-ring);
    }
    .sc-ai-head { display: flex; align-items: center; gap: 6px; margin-bottom: 5px; }
    .sc-ai-head svg { width: 14px; height: 14px; color: var(--tone); }
    .sc-ai-head span { font-size: 11.5px; font-weight: 700; letter-spacing: 0.04em; color: var(--tone); text-transform: uppercase; }
    .sc-ai-body { font-size: 12.5px; line-height: 1.6; color: #334155; }
    .sc-ai-body strong { font-weight: 700; color: var(--tone); }
    .sc-ai-body em { font-style: italic; }

    .sc-meter-wrap { margin-top: 15px; }
    .sc-meter-row { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 6px; }
    .sc-meter-label { font-size: 11px; color: #94a3b8; letter-spacing: 0.03em; }
    .sc-meter-val { font-size: 13px; font-weight: 700; color: var(--tone); font-variant-numeric: tabular-nums; }
    .sc-meter-val small { font-size: 10px; font-weight: 500; color: #cbd5e1; }
    .sc-track { height: 7px; border-radius: 999px; background: #eef2f6; overflow: hidden; }
    .sc-fill {
        height: 100%; width: 0%; border-radius: 999px;
        background: linear-gradient(90deg, color-mix(in srgb, var(--tone) 70%, white), var(--tone));
        transition: width 0.8s cubic-bezier(0.22,1,0.36,1);
    }

    @keyframes sc-rise { to { transform: translateY(0); opacity: 1; } }
    @keyframes sc-fall { to { transform: translateY(8px); opacity: 0; } }
    @keyframes sc-spin { to { transform: rotate(360deg); } }

    /* ---- 頁面安全掃描 loading / 結果 pill ---- */
    .sc-pill {
        --tone: ${SC_PALETTE.scanning.base};
        --tone-soft: ${SC_PALETTE.scanning.soft};
        display: inline-flex; align-items: center; gap: 9px;
        max-width: min(320px, calc(100vw - 32px));
        background: #ffffff; color: #1f2937;
        border-radius: 999px; padding: 7px 15px 7px 8px;
        border: 1px solid rgba(15,23,42,0.06);
        box-shadow: 0 1px 2px rgba(15,23,42,0.06), 0 8px 20px -8px rgba(15,23,42,0.22);
        font-size: 12.5px; font-weight: 600; letter-spacing: -0.005em;
        pointer-events: none; opacity: 0; transform: translateY(8px);
        transition: opacity 0.2s ease, transform 0.2s ease;
    }
    .sc-pill.visible { opacity: 1; transform: translateY(0); }
    .sc-pill-ic {
        flex: 0 0 auto; width: 24px; height: 24px; border-radius: 8px;
        display: grid; place-items: center; background: var(--tone-soft); color: var(--tone);
    }
    .sc-pill-ic svg { width: 15px; height: 15px; }
    .sc-pill-ic.spin svg { animation: sc-spin 1.1s linear infinite; }
    .sc-pill-text { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

    /* ---- link hover tooltip ---- */
    .sc-tip {
        position: fixed; max-width: 290px;
        background: #ffffff; color: #1f2937;
        border-radius: 11px; padding: 11px 13px 12px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang TC", "Microsoft JhengHei", Roboto, sans-serif;
        box-shadow:
            0 1px 2px rgba(15,23,42,0.06),
            0 10px 28px -8px rgba(15,23,42,0.26);
        border: 1px solid rgba(15,23,42,0.07);
        pointer-events: none; opacity: 0; display: none;
        transform: translateY(4px);
        transition: opacity 0.16s ease, transform 0.16s ease;
        --tone: ${SC_PALETTE.scanning.base};
        --tone-soft: ${SC_PALETTE.scanning.soft};
    }
    .sc-tip.visible { display: block; opacity: 1; transform: translateY(0); }
    .sc-tip-row { display: flex; align-items: center; gap: 8px; }
    .sc-tip-ic {
        flex: 0 0 auto; width: 26px; height: 26px; border-radius: 8px;
        display: grid; place-items: center; background: var(--tone-soft); color: var(--tone);
    }
    .sc-tip-ic svg { width: 16px; height: 16px; }
    .sc-tip-ic.spin svg { animation: sc-spin 1.1s linear infinite; }
    .sc-tip-text { font-size: 13px; line-height: 1.45; font-weight: 550; color: #1f2937; }
    .sc-tip-redirect {
        font-size: 11px; color: #475569; margin-top: 7px; padding: 5px 8px;
        background: var(--tone-soft); border-radius: 7px; line-height: 1.4;
    }
    .sc-tip-redirect b { color: var(--tone); font-weight: 700; word-break: break-all; }
    .sc-tip-url { font-size: 10.5px; color: #94a3b8; margin-top: 6px; padding-left: 34px; word-break: break-all; line-height: 1.4; }

    /* ---- 惡意連結點擊攔截 modal ---- */
    .sc-modal-backdrop {
        position: fixed; inset: 0;
        background: rgba(15, 23, 42, 0.55);
        backdrop-filter: blur(2px);
        display: grid; place-items: center;
        pointer-events: auto; opacity: 0;
        transition: opacity 0.18s ease;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang TC", "Microsoft JhengHei", Roboto, sans-serif;
    }
    .sc-modal-backdrop.visible { opacity: 1; }
    .sc-modal {
        --tone: ${SC_PALETTE.malicious.base};
        --tone-soft: ${SC_PALETTE.malicious.soft};
        width: 340px; max-width: calc(100vw - 40px);
        background: #fff; border-radius: 16px; padding: 22px 22px 18px;
        box-shadow: 0 24px 60px -12px rgba(15, 23, 42, 0.5);
        transform: translateY(12px) scale(0.98);
        transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .sc-modal-backdrop.visible .sc-modal { transform: translateY(0) scale(1); }
    .sc-modal-ic {
        width: 48px; height: 48px; border-radius: 14px; margin-bottom: 14px;
        display: grid; place-items: center; color: var(--tone); background: var(--tone-soft);
        box-shadow: inset 0 0 0 1px ${SC_PALETTE.malicious.ring};
    }
    .sc-modal-ic svg { width: 26px; height: 26px; }
    .sc-modal-title { font-size: 17px; font-weight: 700; letter-spacing: -0.01em; color: #0f172a; }
    .sc-modal-body { font-size: 13px; line-height: 1.6; color: #475569; margin-top: 8px; }
    .sc-modal-body b { color: var(--tone); word-break: break-all; }
    .sc-modal-dest {
        margin-top: 12px; padding: 9px 11px; border-radius: 9px;
        background: #f8fafc; border: 1px solid rgba(15,23,42,0.06);
        font-size: 11.5px; color: #64748b; word-break: break-all; line-height: 1.5;
    }
    .sc-modal-actions { display: flex; gap: 10px; margin-top: 18px; }
    .sc-btn {
        flex: 1; border: none; cursor: pointer; border-radius: 10px;
        padding: 11px 12px; font-size: 13px; font-weight: 650;
        font-family: inherit; transition: all 0.16s ease;
    }
    .sc-btn-primary { background: #0f172a; color: #fff; }
    .sc-btn-primary:hover { background: #1e293b; }
    .sc-btn-ghost { background: transparent; color: var(--tone); box-shadow: inset 0 0 0 1.5px ${SC_PALETTE.malicious.ring}; }
    .sc-btn-ghost:hover { background: var(--tone-soft); }
    `;
}

function scOverlay() {
    if (_scShadow) return _scShadow;
    const host = document.createElement("div");
    host.id = "sentinel-overlay-root";
    Object.assign(host.style, {
        position: "fixed", top: "0", left: "0", width: "0", height: "0",
        zIndex: "2147483647", pointerEvents: "none", overflow: "visible",
    });
    const shadow = host.attachShadow({ mode: "closed" });
    const style = document.createElement("style");
    style.textContent = scStyleSheet();
    _scToastStack = document.createElement("div");
    _scToastStack.className = "sc-stack";
    _scTipEl = document.createElement("div");
    _scTipEl.className = "sc-tip";
    shadow.append(style, _scToastStack, _scTipEl);
    (document.body || document.documentElement).appendChild(host);
    _scShadow = shadow;
    return shadow;
}

// --- 防護開關 + 受信任網域白名單（與 popup 共用 chrome.storage.local）---
let _scEnabled = true;
let _scAllowlist = [];   // 小寫 hostname 陣列
try {
    chrome.storage.local.get({ sc_enabled: true, sc_allowlist: [] }, (r) => {
        _scEnabled = r.sc_enabled !== false;
        _scAllowlist = Array.isArray(r.sc_allowlist) ? r.sc_allowlist : [];
    });
    chrome.storage.onChanged.addListener((changes, area) => {
        if (area !== "local") return;
        if (changes.sc_enabled) _scEnabled = changes.sc_enabled.newValue !== false;
        if (changes.sc_allowlist) {
            _scAllowlist = Array.isArray(changes.sc_allowlist.newValue)
                ? changes.sc_allowlist.newValue : [];
        }
    });
} catch (e) {
    // 非擴充環境（測試）時靜默略過
}

// host 是否在白名單（含子網域）
function isAllowlisted(href) {
    const host = hostOf(href);
    if (!host) return false;
    return _scAllowlist.some((d) => {
        const e = String(d).toLowerCase().trim();
        return e && (host === e || host.endsWith("." + e));
    });
}

// --- 1. 監聽選取事件 ---
document.addEventListener('mouseup', function() {
    if (!_scEnabled) return;
    const selectedText = window.getSelection().toString().trim();
    if (selectedText.length >= 2) {
        analyzeText(selectedText);
    }
});

// --- 2. 與後端通訊 ---
async function analyzeText(text) {
    try {
        const rawUrl = getSanitizedURL();
        const isPublicUrl = rawUrl !== "unknown" && !/^https?:\/\/(localhost|127\.|192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.)/i.test(rawUrl);
        const data = await sentinelBackendFetch("http://127.0.0.1:8000/analyze", {
            method: "POST",
            body: {
                content: text,
                url: isPublicUrl ? rawUrl : null,
            },
        });

        showSafetyNotification(data.reason, data.trust_score, text, null, null, null, data.explanation);
    } catch (error) {
        const msg = String(error && error.message != null ? error.message : error);
        if (msg.includes("429")) {
            showSafetyNotification("請求過於頻繁，請稍候片刻再試。", 50, "", "suspicious", "clock", "系統限流");
        } else {
            showSafetyNotification("無法連線至 Sentinel 後端，請確認本機服務已啟動。", 0, "", "neutral", "wifiOff", "連線失敗");
        }
    }
}

// --- 3. NLP 文字選取 Toast（Shadow DOM + 號誌主題 + 可選 override）---
function showSafetyNotification(
    reason,
    score,
    quotedText = "",
    overrideTone = null,
    overrideIcon = null,
    overrideTitle = null,
    explanation = null
) {
    const raw = Number(score);
    const s = Math.max(0, Math.min(100, Math.round(Number.isFinite(raw) ? raw : 0)));

    let tone, iconKey, title, time;
    if (overrideTone != null) {
        tone = overrideTone;
        iconKey = overrideIcon || "alertTriangle";
        title = overrideTitle || "通知";
        time = 6500;
    } else {
        const t = scThemeForScore(s);
        tone = t.tone; iconKey = t.icon; title = t.title; time = t.time;
    }
    const pal = SC_PALETTE[tone] || SC_PALETTE.neutral;

    const safeReason = escapeHTML(reason);
    const aiBody = explanation ? scFormatMarkdownLite(explanation) : "";
    const explanationBlock = aiBody
        ? `<div class="sc-ai"><div class="sc-ai-head">${SC_ICON.cpu}<span>AI 分析師</span></div><div class="sc-ai-body">${aiBody}</div></div>`
        : "";

    const qt = typeof quotedText === "string" ? quotedText : "";
    const truncated = qt.length > 32 ? qt.slice(0, 32) + "…" : qt;
    const quoteBlock = qt.trim().length > 0
        ? `<div class="sc-quote">選取內容　<b>「${escapeHTML(truncated)}」</b></div>`
        : "";

    // 是否顯示信任分數量表（override 通知如連線失敗則不顯示）
    const showMeter = overrideTone == null;
    const meterBlock = showMeter
        ? `<div class="sc-meter-wrap">
               <div class="sc-meter-row">
                   <span class="sc-meter-label">信任分數</span>
                   <span class="sc-meter-val">${s}<small> / 100</small></span>
               </div>
               <div class="sc-track"><div class="sc-fill"></div></div>
           </div>`
        : "";

    scOverlay();
    const card = document.createElement("div");
    card.className = "sc-card";
    card.style.setProperty("--tone", pal.base);
    card.style.setProperty("--tone-soft", pal.soft);
    card.style.setProperty("--tone-ring", pal.ring);
    card.innerHTML = `
        <div class="sc-head">
            <div class="sc-chip">${SC_ICON[iconKey] || SC_ICON.alertTriangle}</div>
            <div class="sc-titles">
                <div class="sc-title">${escapeHTML(title)}</div>
                <div class="sc-sub">SENTINEL · 即時偵測</div>
            </div>
            <div class="sc-x" role="button" aria-label="關閉">${SC_ICON.close}</div>
        </div>
        ${quoteBlock}
        <div class="sc-reason">${safeReason}</div>
        ${explanationBlock}
        ${meterBlock}
    `;
    _scToastStack.appendChild(card);

    const xBtn = card.querySelector(".sc-x");
    const dismiss = () => {
        card.classList.add("sc-leaving");
        setTimeout(() => card.remove(), 320);
    };
    if (xBtn) xBtn.addEventListener("click", (e) => { e.stopPropagation(); dismiss(); });

    const fill = card.querySelector(".sc-fill");
    if (fill) {
        requestAnimationFrame(() => requestAnimationFrame(() => { fill.style.width = `${s}%`; }));
    }

    setTimeout(dismiss, time);
}

// --- 主動鏈結掃描模組 ---
const BACKEND_URL = "http://127.0.0.1:8000";
const scannedUrls = new Set();

const scannedResults = new Map(); // href -> result，用於 Google DOM 刷新後重新注入
const pendingScans = new Set();   // 正在掃描中的 href，避免重複觸發

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

// 在 anchor 上記錄掃描結果（供 tooltip 讀取）
function injectLinkToast(anchorEl, status, text) {
    anchorEl.setAttribute("data-sc-status", status);
    anchorEl.setAttribute("data-sc-toast", text);
}

// --- Link Scan Tooltip（共用 Shadow DOM 覆蓋層）---
let _scTipActiveTarget = null;
let _scTipListenersBound = false;
let _scTipHideTimer = null;

// status -> tooltip 內 icon
const SC_TIP_ICON = {
    safe: "shieldCheck",
    suspicious: "alertTriangle",
    malicious: "shieldAlert",
    scanning: "spinner",
    default: "radar",
};

function showSCTooltip(anchorEl, text, status, url = "", spin = false, meta = null) {
    scOverlay();
    if (_scTipHideTimer) { clearTimeout(_scTipHideTimer); _scTipHideTimer = null; }
    const pal = SC_PALETTE[status] || SC_PALETTE.scanning;
    const iconKey = SC_TIP_ICON[status] || SC_TIP_ICON.default;
    const safeText = escapeHTML(text);
    const safeUrl = url ? escapeHTML(truncateUrl(url)) : "";

    // B: 轉址鏈（後端回傳 final_url / hop_count 才顯示）
    let redirectHtml = "";
    if (meta) {
        const origHost = hostOf(url);
        const finalHost = hostOf(meta.finalUrl);
        const hops = Number(meta.hopCount);
        const redirected = hops > 0 || (finalHost && origHost && finalHost !== origHost);
        if (redirected) {
            const prefix = hops > 0 ? `經 ${hops} 層轉址 → ` : "最終 → ";
            redirectHtml = `<div class="sc-tip-redirect">${prefix}<b>${escapeHTML(finalHost || meta.finalUrl)}</b></div>`;
        }
    }

    _scTipEl.style.setProperty("--tone", pal.base);
    _scTipEl.style.setProperty("--tone-soft", pal.soft);
    _scTipEl.innerHTML = `
        <div class="sc-tip-row">
            <span class="sc-tip-ic${spin ? " spin" : ""}">${SC_ICON[iconKey]}</span>
            <span class="sc-tip-text">${safeText}</span>
        </div>
        ${redirectHtml}
        ${safeUrl ? `<div class="sc-tip-url">${safeUrl}</div>` : ""}
    `;

    _scTipEl.style.display = "block";
    const TIP_W = 290;
    const TIP_H = _scTipEl.offsetHeight || 56;
    const rect = anchorEl.getBoundingClientRect();
    let top = rect.bottom + 8;
    let left = rect.left;
    if (left + TIP_W > window.innerWidth - 8) left = window.innerWidth - TIP_W - 8;
    if (left < 8) left = 8;
    if (top + TIP_H > window.innerHeight - 8) top = rect.top - TIP_H - 8;
    _scTipEl.style.top = `${top}px`;
    _scTipEl.style.left = `${left}px`;
    requestAnimationFrame(() => { _scTipEl.classList.add("visible"); });
}

function hideSCTooltip() {
    if (!_scTipEl) return;
    _scTipEl.classList.remove("visible");
    _scTipHideTimer = setTimeout(() => { _scTipHideTimer = null; if (_scTipEl) _scTipEl.style.display = "none"; }, 160);
    _scTipActiveTarget = null;
}

function showSCTooltipForEl(anchorEl) {
    const text = anchorEl.getAttribute("data-sc-toast");
    if (!text) { hideSCTooltip(); return; }
    const status = anchorEl.getAttribute("data-sc-status") || "default";
    const result = scannedResults.get(anchorEl.href);
    const meta = result ? { finalUrl: result.final_url, hopCount: result.hop_count } : null;
    showSCTooltip(anchorEl, text, status, anchorEl.href || "", false, meta);
}

function initSentinelLinkToasts() {
    if (_scTipListenersBound) return;
    _scTipListenersBound = true;

    document.addEventListener("mouseover", (e) => {
        // 已掃描：直接顯示 tooltip
        const t = e.target.closest("[data-sc-toast]");
        if (t && document.documentElement.contains(t)) {
            if (_scTipActiveTarget !== t) {
                _scTipActiveTarget = t;
                showSCTooltipForEl(t);
            }
            return;
        }
        // 未掃描：hover 時觸發掃描
        const a = e.target.closest("a[href]");
        if (a) scanOnHover(a);
    }, true);

    document.addEventListener("mouseout", (e) => {
        const from = e.target.closest("[data-sc-toast]");
        if (!from) return;
        const rel = e.relatedTarget;
        if (rel && (from === rel || from.contains(rel))) return;
        hideSCTooltip();
    }, true);
}

// 連結標記外框（套在頁面 anchor 上，無法進 Shadow DOM）
function ensureScanStyles() {
    if (document.getElementById("sc-styles")) return;
    const style = document.createElement("style");
    style.id = "sc-styles";
    style.textContent = `
      a.sc-flagged-safe, a.sc-flagged-suspicious, a.sc-flagged-malicious {
        border-radius: 3px !important;
        outline-offset: 2px !important;
        transition: outline-color 0.18s ease, box-shadow 0.18s ease !important;
      }
      a.sc-flagged-safe {
        outline: 2px solid ${SC_STATUS_COLORS.safe} !important;
        box-shadow: 0 0 0 3px ${SC_PALETTE.safe.soft} !important;
        text-decoration-color: ${SC_STATUS_COLORS.safe} !important;
      }
      a.sc-flagged-suspicious {
        outline: 2px solid ${SC_STATUS_COLORS.suspicious} !important;
        box-shadow: 0 0 0 3px ${SC_PALETTE.suspicious.soft} !important;
        text-decoration-color: ${SC_STATUS_COLORS.suspicious} !important;
      }
      a.sc-flagged-malicious {
        outline: 2px solid ${SC_STATUS_COLORS.malicious} !important;
        box-shadow: 0 0 0 3px ${SC_PALETTE.malicious.soft} !important;
        text-decoration-color: ${SC_STATUS_COLORS.malicious} !important;
      }
    `;
    document.head.appendChild(style);
}

function injectWarningUI(anchorEl, result) {
    ensureScanStyles();

    if (result.label === "Safe") {
        anchorEl.classList.add("sc-flagged-safe");
        injectLinkToast(anchorEl, "safe", "安全：未發現已知威脅");
        return;
    }

    const lower = result.label.toLowerCase();
    const isMalicious = result.label === "Malicious";
    const toastText = isMalicious
        ? `危險：${result.reason}`
        : `可疑：${result.reason}`;

    anchorEl.classList.add(`sc-flagged-${lower}`);
    injectLinkToast(anchorEl, lower, toastText);
}

async function scanOnHover(anchorEl) {
    if (!_scEnabled) return;
    const href = anchorEl.href;
    if (!href || scannedUrls.has(href) || pendingScans.has(href)) return;
    if (isAllowlisted(href)) return;  // D: 受信任網域不掃描

    pendingScans.add(href);
    scannedUrls.add(href);

    showSCTooltip(anchorEl, "Sentinel 掃描中…", "scanning", href, true);

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
                showSCTooltipForEl(anchorEl);
            } else {
                hideSCTooltip();
            }
        } else {
            hideSCTooltip();
        }
    } catch (err) {
        showSCTooltip(anchorEl, "掃描失敗，後端無法連線", "malicious", "", false);
        scannedUrls.delete(href);
        setTimeout(() => hideSCTooltip(), 3000);
    } finally {
        pendingScans.delete(href);
    }
}

// --- A: 惡意連結點擊攔截 ---
let _scModalOpen = false;

function scShowBlockModal(anchorEl, result) {
    if (_scModalOpen) return;
    scOverlay();
    _scModalOpen = true;

    const href = anchorEl.href;
    const finalHost = hostOf(result && result.final_url ? result.final_url : href) || hostOf(href);
    const reason = (result && result.reason) ? result.reason : "此連結被標記為惡意網站。";
    const hops = result ? Number(result.hop_count) : -1;
    const destLine = hops > 0
        ? `經 ${hops} 層轉址，最終指向 ${escapeHTML(finalHost)}`
        : `最終指向 ${escapeHTML(finalHost)}`;

    const backdrop = document.createElement("div");
    backdrop.className = "sc-modal-backdrop";
    backdrop.innerHTML = `
        <div class="sc-modal" role="alertdialog" aria-modal="true">
            <div class="sc-modal-ic">${SC_ICON.shieldAlert}</div>
            <div class="sc-modal-title">惡意連結警告</div>
            <div class="sc-modal-body">${escapeHTML(reason)}</div>
            <div class="sc-modal-dest">${destLine}</div>
            <div class="sc-modal-actions">
                <button class="sc-btn sc-btn-ghost" data-act="go">仍要前往</button>
                <button class="sc-btn sc-btn-primary" data-act="back">返回安全</button>
            </div>
        </div>
    `;
    _scShadow.appendChild(backdrop);
    requestAnimationFrame(() => backdrop.classList.add("visible"));

    const close = () => {
        backdrop.classList.remove("visible");
        setTimeout(() => backdrop.remove(), 200);
        _scModalOpen = false;
    };
    backdrop.addEventListener("click", (e) => {
        const act = e.target && e.target.getAttribute ? e.target.getAttribute("data-act") : null;
        if (e.target === backdrop || act === "back") {
            close();
        } else if (act === "go") {
            close();
            const tgt = anchorEl.target === "_blank" ? "_blank" : "_self";
            window.open(href, tgt);
        }
    });
}

function initSentinelClickGuard() {
    document.addEventListener("click", (e) => {
        if (!_scEnabled) return;
        const a = e.target && e.target.closest ? e.target.closest("a[href]") : null;
        if (!a || a.getAttribute("data-sc-status") !== "malicious") return;
        if (isAllowlisted(a.href)) return;
        e.preventDefault();
        e.stopPropagation();
        if (e.stopImmediatePropagation) e.stopImmediatePropagation();
        scShowBlockModal(a, scannedResults.get(a.href));
    }, true);
}

const debouncedObserve = debounce(() => {
    // Google 等動態頁面會替換 DOM 節點，需重新注入已快取的結果
    extractPageLinks().forEach((a) => {
        if (scannedResults.has(a.href) && !a.getAttribute("data-sc-toast")) {
            injectWarningUI(a, scannedResults.get(a.href));
        }
    });
}, 800);

// 載入後動態注入的 <script> 計數（行為偵測訊號之一）
let _scDynamicScripts = 0;

const observer = new MutationObserver((mutations) => {
    for (const m of mutations) {
        for (const n of m.addedNodes) {
            if (n.nodeName === "SCRIPT") _scDynamicScripts++;
        }
    }
    debouncedObserve();
});

// =====================================================================
//  方向 4：頁面行為異常偵測（DOM 啟發式）+ 融合評分
// =====================================================================

function _scDetectTransparentOverlay() {
    try {
        const cx = Math.floor(window.innerWidth / 2);
        const cy = Math.floor(window.innerHeight / 2);
        const el = document.elementFromPoint(cx, cy);
        if (!el || el === document.body || el === document.documentElement) return false;
        const r = el.getBoundingClientRect();
        const coversMost =
            r.width >= window.innerWidth * 0.85 && r.height >= window.innerHeight * 0.85;
        if (!coversMost) return false;
        const cs = getComputedStyle(el);
        const z = parseInt(cs.zIndex, 10);
        const opacity = parseFloat(cs.opacity);
        const transparentBg =
            cs.backgroundColor === "rgba(0, 0, 0, 0)" || cs.backgroundColor === "transparent";
        const highZ = Number.isFinite(z) && z >= 1000;
        const positioned = cs.position === "fixed" || cs.position === "absolute";
        return opacity < 0.2 || (transparentBg && highZ && positioned);
    } catch {
        return false;
    }
}

function _scDetectObfuscatedScript() {
    const scripts = document.querySelectorAll("script:not([src])");
    for (const s of scripts) {
        const t = s.textContent || "";
        if (t.length < 200) continue;
        const hexEsc = (t.match(/\\x[0-9a-f]{2}/gi) || []).length;
        const longB64 = /[A-Za-z0-9+/]{120,}={0,2}/.test(t);
        const evalAtob =
            /\b(eval|atob|unescape|Function)\s*\(/.test(t) && /[A-Za-z0-9+/]{60,}/.test(t);
        if (hexEsc > 20 || longB64 || evalAtob) return true;
    }
    return false;
}

function extractBehaviorFeatures() {
    const host = location.hostname.toLowerCase();
    const forms = Array.from(document.querySelectorAll("form"));
    let formActionExternal = false;
    let externalPasswordForm = false;
    for (const f of forms) {
        const action = f.getAttribute("action") || "";
        let actionHost = "";
        try {
            actionHost = action ? new URL(action, location.href).hostname.toLowerCase() : "";
        } catch {
            actionHost = "";
        }
        const external = actionHost && actionHost !== host;
        if (external) {
            formActionExternal = true;
            if (f.querySelector('input[type="password"]')) externalPasswordForm = true;
        }
    }

    const iframes = Array.from(document.querySelectorAll("iframe[src]"));
    let crossOriginIframes = 0;
    for (const fr of iframes) {
        try {
            const h = new URL(fr.src, location.href).hostname.toLowerCase();
            if (h && h !== host) crossOriginIframes++;
        } catch {
            /* ignore */
        }
    }

    return {
        password_field_count: document.querySelectorAll('input[type="password"]').length,
        external_password_form: externalPasswordForm,
        form_action_external: formActionExternal,
        hidden_input_count: document.querySelectorAll('input[type="hidden"]').length,
        iframe_count: iframes.length,
        cross_origin_iframe_count: crossOriginIframes,
        transparent_overlay: _scDetectTransparentOverlay(),
        obfuscated_script: _scDetectObfuscatedScript(),
        dynamic_script_inject: _scDynamicScripts,
        suspicious_tld: /\.(top|xyz|tk|pw|gq|cf|ml)$/.test(host),
    };
}

// --- 頁面安全掃描 loading / 結果 pill ---
let _scPillEl = null;
let _scPillTimer = null;

function _scEnsurePill() {
    scOverlay();
    if (!_scPillEl) {
        _scPillEl = document.createElement("div");
        _scPillEl.className = "sc-pill";
        _scToastStack.appendChild(_scPillEl);  // 併入右下角堆疊，避免與 toast 重疊
    }
    if (_scPillTimer) { clearTimeout(_scPillTimer); _scPillTimer = null; }
    return _scPillEl;
}

function scShowScanPill() {
    const pill = _scEnsurePill();
    const pal = SC_PALETTE.scanning;
    pill.style.setProperty("--tone", pal.base);
    pill.style.setProperty("--tone-soft", pal.soft);
    pill.innerHTML = `<span class="sc-pill-ic spin">${SC_ICON.spinner}</span><span class="sc-pill-text">掃描本頁安全性…</span>`;
    requestAnimationFrame(() => pill.classList.add("visible"));
}

function scResolveScanPill(tone, iconKey, text, autoHideMs) {
    const pill = _scEnsurePill();
    const pal = SC_PALETTE[tone] || SC_PALETTE.neutral;
    pill.style.setProperty("--tone", pal.base);
    pill.style.setProperty("--tone-soft", pal.soft);
    pill.innerHTML = `<span class="sc-pill-ic">${SC_ICON[iconKey]}</span><span class="sc-pill-text">${escapeHTML(text)}</span>`;
    pill.classList.add("visible");
    if (autoHideMs) _scPillTimer = setTimeout(scHideScanPill, autoHideMs);
}

function scHideScanPill() {
    if (_scPillTimer) { clearTimeout(_scPillTimer); _scPillTimer = null; }
    if (_scPillEl) _scPillEl.classList.remove("visible");
}

// 蒐集頁面連結（去重、排除白名單與已掃過）→ Map<href, anchor[]>
// 外部連結優先，再補同網域，合併到上限（同網域也要掃：被入侵站點/測試站的惡意連結常為同網域路徑）。
function _scCollectPageLinks(cap) {
    const host = location.hostname.toLowerCase();
    const ext = new Map();
    const same = new Map();
    for (const a of extractPageLinks()) {
        let href = "";
        try { href = a.href; } catch { continue; }
        if (!href || !/^https?:/i.test(href)) continue;
        const h = hostOf(href);
        if (!h) continue;
        if (isAllowlisted(href) || scannedUrls.has(href)) continue;
        const bucket = h === host ? same : ext;
        if (!bucket.has(href)) bucket.set(href, []);
        bucket.get(href).push(a);
    }
    const map = new Map();
    for (const src of [ext, same]) {          // 外部優先
        for (const [href, anchors] of src) {
            if (map.size >= cap) break;
            map.set(href, anchors);
        }
        if (map.size >= cap) break;
    }
    return map;
}

// 套用批次連結掃描結果：快取 + 預先標記（安全連結不加外框，避免整頁雜訊）
function _scApplyLinkResults(results, anchorMap) {
    let malicious = 0;
    let suspicious = 0;
    for (const r of results || []) {
        if (!r || !r.url) continue;
        scannedUrls.add(r.url);
        scannedResults.set(r.url, r);
        if (r.label === "Malicious") malicious++;
        else if (r.label === "Suspicious") suspicious++;
        for (const a of (anchorMap.get(r.url) || [])) {
            if (r.label === "Safe") {
                injectLinkToast(a, "safe", "安全：未發現已知威脅");  // 僅快取，hover 可見，不加外框
            } else {
                injectWarningUI(a, r);   // 可疑/惡意 → 外框徽記 + 啟用點擊攔截
            }
        }
    }
    return { malicious, suspicious };
}

// 合併「行為/頁面URL」與「連結」結果 → 呈現 pill 或警告卡
function _scPresentPageResult(behavior, counts) {
    const behaviorDanger = behavior && behavior.label === "Danger";
    const behaviorSuspicious = behavior && behavior.label === "Suspicious";
    const { malicious, suspicious } = counts;

    if (behaviorDanger || malicious > 0) {
        scHideScanPill();
        let reason = "";
        if (behaviorDanger) {
            const flags = behavior.behavior_flags || [];
            reason = flags.length ? flags.join("、") + "。" : "此頁面偵測到可疑的行為特徵。";
            if (behavior.url && behavior.url.label === "Malicious") {
                reason += " 此頁網址亦被標記為惡意。";
            }
        }
        if (malicious > 0) {
            reason += (reason ? " " : "") + `本頁含 ${malicious} 個惡意連結，請勿點擊。`;
        }
        const explanation = behaviorDanger ? behavior.explanation : null;
        const trust = behaviorDanger ? behavior.trust_score : 0;
        showSafetyNotification(reason, trust, "", "malicious", "shieldAlert", "本頁面高風險", explanation);
        return;
    }

    if (behaviorSuspicious || suspicious > 0) {
        let txt;
        if (suspicious > 0 && !behaviorSuspicious) txt = `本頁含 ${suspicious} 個可疑連結`;
        else if (suspicious > 0) txt = `本頁有可疑特徵，含 ${suspicious} 個可疑連結`;
        else txt = "本頁面有可疑特徵";
        scResolveScanPill("suspicious", "alertTriangle", txt, 5000);
        return;
    }

    scResolveScanPill("safe", "shieldCheck", "本頁面未發現風險", 2500);
}

let _scPageAssessed = false;
async function assessPageBehavior() {
    if (!_scEnabled || _scPageAssessed) return;
    if (!/^https?:/i.test(location.href)) return;
    if (/^https?:\/\/(localhost|127\.|192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.)/i.test(location.href)) return;
    if (isAllowlisted(location.href)) return;
    _scPageAssessed = true;

    const features = extractBehaviorFeatures();
    const anchorMap = _scCollectPageLinks(40);   // 上限 40（外部優先，含同網域）
    const linkUrls = [...anchorMap.keys()];
    scShowScanPill();  // loading 提示

    const [behaviorR, linksR] = await Promise.allSettled([
        sentinelBackendFetch(`${BACKEND_URL}/analyze/behavior`, {
            method: "POST",
            body: { url: getSanitizedURL(), features },
        }),
        linkUrls.length
            ? sentinelBackendFetch(`${BACKEND_URL}/analyze/links`, {
                  method: "POST",
                  body: { urls: linkUrls },
              })
            : Promise.resolve(null),
    ]);

    const behavior = behaviorR.status === "fulfilled" ? behaviorR.value : null;
    const linkData = linksR.status === "fulfilled" ? linksR.value : null;

    if (!behavior && !linkData) { scHideScanPill(); return; }  // 後端離線 → 靜默

    const counts = linkData
        ? _scApplyLinkResults(linkData.results, anchorMap)
        : { malicious: 0, suspicious: 0 };

    _scPresentPageResult(behavior, counts);
}

function bootSentinelLinkScanner() {
    initSentinelLinkToasts();
    initSentinelClickGuard();
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["href"] });
    // 延遲評估，讓動態內容/腳本先載入
    setTimeout(assessPageBehavior, 1800);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootSentinelLinkScanner);
} else {
    bootSentinelLinkScanner();
}
