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
