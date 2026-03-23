// --- 1. 監聽選取事件 ---
console.log("📍 開始掛載監聽器...");

document.addEventListener('mouseup', function(event) {
    // 加上這行測試，只要滑鼠放開，不管有沒有選到字都要有反應
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
        const response = await fetch('http://127.0.0.1:8000/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                request_id: "ui-test-" + Date.now(),
                payload_type: "text",
                content: text,
                url: window.location.href
            })
        });

        const data = await response.json();

        // 如果後端判斷為危險，則顯示通知
        if (data.label === "Danger") {
            showSafetyNotification(data.reason, data.trust_score);
        }
    } catch (error) {
        console.error("Sentinel-Core 連線失敗:", error);
    }
}

// --- 3. UI 注入函式 (Toast Notification) ---
function showSafetyNotification(reason, score) {
    // 檢查是否已經有通知存在，避免重複彈出
    if (document.getElementById('sentinel-notify')) return;

    const notify = document.createElement('div');
    notify.id = 'sentinel-notify';
    
    // 設定樣式 (使用 JS Inline Style 確保樣式隔離)
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

    // 注入動畫 CSS
    const styleTag = document.createElement('style');
    styleTag.textContent = `
        @keyframes sentinel-fade-in {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
    `;
    document.head.appendChild(styleTag);

    document.body.appendChild(notify);

    // 6秒後自動移除
    setTimeout(() => {
        notify.style.opacity = '0';
        notify.style.transition = 'opacity 0.5s ease';
        setTimeout(() => notify.remove(), 500);
    }, 6000);
}