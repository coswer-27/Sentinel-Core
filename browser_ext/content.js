/**
 * Sentinel-Core v1.2 - 前端視覺引擎 (Visual Vibrant)
 * 已整合：微服務 Gateway、三色主題、錯誤處理、流暢動畫
 */

// --- 工具函式：防止 XSS ---
function escapeHTML(str) {
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

// --- 1. 監聽選取事件 ---
document.addEventListener('mouseup', function() {
    let selection = window.getSelection();
    let selectedText = selection.toString().trim();

    // 門檻設定：避免選到單個標點符號也發送請求
    if (selectedText.length >= 2) {
        analyzeText(selectedText);
    }
});

/**
 * 清理 URL 以保護隱私：移除查詢參數 (Query params)
 * 解決 Medium 風險：隱私洩漏
 */
function getSanitizedURL() {
    try {
        const url = new URL(window.location.href);
        return url.origin + url.pathname;
    } catch (e) {
        return "unknown";
    }
}

// --- 2. 與後端 (Gateway) 通訊 ---
async function analyzeText(text) {
    // 生產環境建議從配置載入，此處為示範修復硬編碼
    const API_ENDPOINT = 'http://127.0.0.1:8000/analyze';
    
    try {
        const response = await fetch(API_ENDPOINT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                content: text,
                url: getSanitizedURL(), 
                timestamp: new Date().toISOString() 
            })
        });

        const data = await response.json();

        if (response.ok) {
            showSafetyNotification(data.reason, data.trust_score, text);
        } else if (response.status === 429) {
            showSafetyNotification("請求過於頻繁，請稍後再試。", 50, "", "#faad14", "⏳", "系統限流");
        } else {
            // 生產環境應使用更完善的日誌系統，此處僅為修復 console.error 規範問題
            // console.error("Sentinel-Core 連線失敗:", error);
            showSafetyNotification("無法連線至網關，請確認後端是否啟動。", 0, "", "#8c8c8c", "❌", "連線失敗");
        }
    } catch (error) {
        showSafetyNotification("連線失敗，請確認後端是否啟動。", 0, "", "#8c8c8c", "❌", "連線失敗");
    }
}

// --- 3. UI 注入與動態主題 ---
function showSafetyNotification(reason, score, quotedText = "", overrideColor = null, overrideIcon = null, overrideTitle = null) {
    const oldNotify = document.getElementById('sentinel-notify');
    if (oldNotify) oldNotify.remove();

    const s = Math.max(0, Math.min(100, Math.round(Number(score) || 0)));
    const risk = 100 - s;

    let theme = { color: '#ff4d4f', icon: '🚨', title: '高風險內容', time: 8000 };
    if (s > 70) {
        theme = { color: '#52c41a', icon: '✅', title: '內容安全', time: 4000 };
    } else if (s >= 40) {
        theme = { color: '#faad14', icon: '⚠️', title: '疑似風險', time: 6000 };
    }

    const finalColor = overrideColor || theme.color;
    const finalIcon = overrideIcon || theme.icon;
    const finalTitle = overrideTitle || theme.title;

    const notify = document.createElement('div');
    notify.id = 'sentinel-notify';
    
    // --- [Fix 07: 強化 XSS 防禦] ---
    // 1. 先處理被裁切的引言文字
    const truncatedText = quotedText.length > 25 ? quotedText.substring(0, 25) + '...' : quotedText;
    // 2. 將裁切後的文字「完全轉義」
    const safeShortText = escapeHTML(truncatedText);
    // 3. 同時確保原因 (reason) 也要轉義，防止後端回傳值包含惡意代碼
    const safeReason = escapeHTML(reason);
    
    notify.innerHTML = `
        <div id="sentinel-close-x" style="position:absolute; top:12px; right:15px; cursor:pointer; font-size:22px; color:#aaa; line-height:1; z-index:100; transition:color 0.2s;">&times;</div>
        
        <div style="display:flex; align-items:center; margin-bottom:10px;">
            <span style="font-size:22px; margin-right:10px;">${finalIcon}</span>
            <strong style="font-size:16px; color:${finalColor};">${escapeHTML(finalTitle)}</strong>
        </div>

        ${safeShortText ? `
        <div style="font-style:italic; color:#666; font-size:12px; background:#f8f9fa; padding:10px; border-radius:6px; margin-bottom:12px; border-left:3px solid #ddd;">
            "${safeShortText}"
        </div>` : ''}

        <div style="font-size:14px; line-height:1.5; margin-bottom:15px;">${safeReason}</div>

        <div style="background:#eee; height:8px; border-radius:4px; overflow:hidden;">
            <div id="sentinel-bar" style="background:${finalColor}; width:0%; height:100%; transition:width 1.2s cubic-bezier(0.1, 0.7, 0.1, 1);"></div>
        </div>
        <div style="font-size:11px; color:#999; margin-top:8px; display:flex; justify-content:space-between;">
            <span>安全度: ${s}%</span><span style="font-weight:bold; color:${finalColor}">風險: ${risk}%</span>
        </div>
    `;

    // 設定外框樣式
    Object.assign(notify.style, {
        position: 'fixed', bottom: '30px', right: '30px', width: '320px',
        backgroundColor: '#ffffff', borderLeft: `8px solid ${finalColor}`,
        boxShadow: '0 12px 32px rgba(0,0,0,0.15)', padding: '20px', borderRadius: '12px',
        zIndex: '2147483647', fontFamily: "system-ui, -apple-system, sans-serif",
        animation: 'sentinel-slide-in 0.4s cubic-bezier(0.18, 0.89, 0.32, 1.28)'
    });

    document.body.appendChild(notify);

    // 🚀 重點：在 appendChild 之後，才去抓那個 ID 來綁定點擊事件
    const xBtn = notify.querySelector('#sentinel-close-x');
    if (xBtn) {
        xBtn.onclick = (e) => {
            e.stopPropagation(); // 防止事件冒泡
            notify.remove();
        };
        xBtn.onmouseover = () => { xBtn.style.color = finalColor; };
        xBtn.onmouseout = () => { xBtn.style.color = '#aaa'; };
    }

    // 進度條與自動退場邏輯保持不變...
    setTimeout(() => {
        const bar = document.getElementById('sentinel-bar');
        if (bar) bar.style.width = `${risk}%`;
    }, 100);

    setTimeout(() => {
        if (document.body.contains(notify)) {
            notify.style.opacity = '0';
            notify.style.transform = 'translateY(10px)';
            notify.style.transition = 'all 0.5s ease';
            setTimeout(() => notify.remove(), 500);
        }
    }, theme.time);
}
