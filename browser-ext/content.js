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

function showSafetyNotification(reason, score, quotedText = "") {
    // 物理移除舊通知
    const oldNotify = document.getElementById('sentinel-notify');
    if (oldNotify) oldNotify.remove();

    const notify = document.createElement('div');
    notify.id = 'sentinel-notify';
    
    // 根據分數決定顏色：極度危險(紅) vs 警告(橘)
    const themeColor = score <= 30 ? '#ff4d4f' : '#faad14';
    const shortText = quotedText.length > 25 ? quotedText.substring(0, 25) + "..." : quotedText;
    const risk = (100 - score); // 直接拿整數

    Object.assign(notify.style, {
        position: 'fixed', bottom: '30px', right: '30px', width: '320px',
        backgroundColor: '#ffffff', color: '#333', borderLeft: `6px solid ${themeColor}`,
        boxShadow: '0 10px 25px rgba(0,0,0,0.2)', padding: '20px', borderRadius: '8px',
        zIndex: '1000000', fontFamily: "'Segoe UI', Roboto, sans-serif",
        animation: 'sentinel-slide-in 0.4s ease-out'
    });

    // 在 showSafetyNotification 函式內修改 innerHTML


    notify.innerHTML = `
    <div style="display: flex; align-items: center; margin-bottom: 8px;">
        <span style="font-size: 20px; margin-right: 10px;">🚨</span>
        <strong style="font-size: 15px; color: #ff4d4f;">分析報告：高風險內容</strong>
    </div>
    
    <div style="font-style: italic; color: #666; font-size: 12px; background: #f9f9f9; padding: 8px; border-radius: 4px; margin-bottom: 10px; border-left: 3px solid #ddd;">
        "${shortText}"
    </div>

    <div style="font-size: 14px; line-height: 1.4; margin-bottom: 12px;">
        <strong>原因：</strong>${reason}
    </div>

    <div style="background: #eee; height: 10px; border-radius: 5px; overflow: hidden; position: relative;">
        <div style="background: #ff4d4f; width: ${risk}%; height: 100%; transition: width 0.8s ease;"></div>
    </div>
    
    <div style="font-size: 12px; color: #666; margin-top: 6px; display: flex; justify-content: space-between;">
        <span>信任值: ${score}%</span>
        <span style="font-weight: bold; color: #ff4d4f;">風險佔比: ${risk}%</span>
    </div>
`;

    // 注入動畫 CSS (略，保持你原本的 sentinel-slide-in)
    document.body.appendChild(notify);

    setTimeout(() => {
        if (document.body.contains(notify)) {
            notify.style.opacity = '0';
            notify.style.transition = 'opacity 0.5s';
            setTimeout(() => notify.remove(), 500);
        }
    }, 6000);
}