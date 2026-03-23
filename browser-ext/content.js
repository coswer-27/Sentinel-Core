// 每當頁面載入時，自動傳送網頁標題給後端測試
console.log("🛡️ Sentinel-Core 偵測啟動...");

const testData = {
    request_id: "init-test-" + Date.now(),
    payload_type: "text",
    content: "這是一則測試訊息，包含關鍵字：匯款", // 測試觸發 Danger 邏輯
    url: window.location.href
};

fetch('http://127.0.0.1:8000/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(testData)
})
.then(response => response.json())
.then(data => {
    console.log("來自 Sentinel-Core 後端的分析結果：", data);
    if (data.label === "Danger") {
        alert("⚠️ 偵測到潛在風險！原因：" + data.reason);
    }
})
.catch(err => console.error("連線失敗，請檢查後端是否啟動:", err));