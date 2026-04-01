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

// --- 2. 與後端 (Gateway) 通訊 ---
async function analyzeText(text) {
    try {
        const response = await fetch('http://127.0.0.1:8000/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            // body 增加 url 欄位
            body: JSON.stringify({ 
                content: text,
                url: window.location.href, 
                timestamp: new Date().toISOString() 
            })
        });

        const data = await response.json();

        if (response.ok) {
            showSafetyNotification(data.reason, data.trust_score, text);
        } else if (response.status === 429) {
            showSafetyNotification("請求過於頻繁，請稍後再試。", 50, "", "#faad14", "⏳", "系統限流");
        } else {
            showSafetyNotification(`偵測服務異常 (${response.status})`, 0, "", "#8c8c8c", "🛠️", "連線故障");
        }

    } catch (error) {
        console.error("Sentinel-Core 連線失敗:", error);
        showSafetyNotification("無法連線至網關，請確認後端是否啟動。", 0, "", "#8c8c8c", "❌", "連線失敗");
    }
}

// --- 3. UI 注入與動態主題 ---
function showSafetyNotification(reason, score, quotedText = "", overrideColor = null, overrideIcon = null, overrideTitle = null) {
    // 移除舊通知
    const oldNotify = document.getElementById('sentinel-notify');
    if (oldNotify) oldNotify.remove();

    // 計算數據（修復：clamp 至 0-100 防止溢出）
    const s = Math.max(0, Math.min(100, Math.round(Number(score) || 0)));
    const risk = 100 - s;

    // --- [v1.2 主題引擎] ---
    let theme = { color: '#ff4d4f', icon: '🚨', title: '高風險內容', time: 8000 }; // 預設紅色 (Danger)
    if (s > 70) {
        theme = { color: '#52c41a', icon: '✅', title: '內容安全', time: 4000 }; // 綠色 (Safe)
    } else if (s >= 40) {
        theme = { color: '#faad14', icon: '⚠️', title: '疑似風險', time: 6000 }; // 橘色 (Warning)
    }

    const finalColor = overrideColor || theme.color;
    const finalIcon = overrideIcon || theme.icon;
    const finalTitle = overrideTitle || theme.title;

    // 建立通知容器
    const notify = document.createElement('div');
    notify.id = 'sentinel-notify';
    Object.assign(notify.style, {
        position: 'fixed', bottom: '30px', right: '30px', width: '320px',
        backgroundColor: '#ffffff', borderLeft: `8px solid ${finalColor}`,
        boxShadow: '0 12px 32px rgba(0,0,0,0.15)', padding: '20px', borderRadius: '12px',
        zIndex: '2147483647', fontFamily: "system-ui, -apple-system, sans-serif",
        animation: 'sentinel-slide-in 0.4s cubic-bezier(0.18, 0.89, 0.32, 1.28)'
    });

    // 修復 XSS：使用 escapeHTML 處理所有來自外部的字串
    const shortText = quotedText.length > 25 ? quotedText.substring(0, 25) + '...' : quotedText;
    notify.innerHTML = `
        <div style="display:flex; align-items:center; margin-bottom:10px;">
            <span style="font-size:22px; margin-right:10px;">${finalIcon}</span>
            <strong style="font-size:16px; color:${finalColor};">${escapeHTML(finalTitle)}</strong>
        </div>
        ${shortText ? `
        <div style="font-style:italic; color:#666; font-size:12px; background:#f8f9fa; padding:10px; border-radius:6px; margin-bottom:12px; border-left:3px solid #ddd;">
            "${escapeHTML(shortText)}"
        </div>` : ''}
        <div style="font-size:14px; line-height:1.5; margin-bottom:15px;">${escapeHTML(reason)}</div>
        <div style="background:#eee; height:8px; border-radius:4px; overflow:hidden;">
            <div id="sentinel-bar" style="background:${finalColor}; width:0%; height:100%; transition:width 1.2s cubic-bezier(0.1, 0.7, 0.1, 1);"></div>
        </div>
        <div style="font-size:11px; color:#999; margin-top:8px; display:flex; justify-content:space-between;">
            <span>安全度: ${s}%</span><span style="font-weight:bold; color:${finalColor}">風險: ${risk}%</span>
        </div>
    `;

    // 注入動畫樣式
    if (!document.getElementById('sentinel-style')) {
        const style = document.createElement('style');
        style.id = 'sentinel-style';
        style.innerHTML = `
            @keyframes sentinel-slide-in {
                from { opacity:0; transform:translateX(50px); }
                to { opacity:1; transform:translateX(0); }
            }
        `;
        document.head.appendChild(style);
    }

    document.body.appendChild(notify);

    // 啟動進度條動畫
    setTimeout(() => {
        const bar = document.getElementById('sentinel-bar');
        if (bar) bar.style.width = `${risk}%`;
    }, 100);

    // 自動退場
    setTimeout(() => {
        if (document.body.contains(notify)) {
            notify.style.opacity = '0';
            notify.style.transform = 'translateY(10px)';
            notify.style.transition = 'all 0.5s ease';
            setTimeout(() => notify.remove(), 500);
        }
    }, theme.time);
}
