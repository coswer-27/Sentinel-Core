/**
 * 由 background 代為請求本機後端，避開網頁 content script 的
 * Private Network Access（公開/非安全頁面 → 127.0.0.1 會被擋）。
 */
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type !== "SENTINEL_BACKEND_FETCH") {
    return;
  }

  (async () => {
    try {
      const headers = { ...(msg.headers || {}) };
      const init = { method: msg.method || "GET", headers };
      if (msg.body !== undefined && msg.body !== null) {
        if (!headers["Content-Type"] && !headers["content-type"]) {
          headers["Content-Type"] = "application/json";
        }
        init.body =
          typeof msg.body === "string" ? msg.body : JSON.stringify(msg.body);
      }
      const res = await fetch(msg.url, init);
      const text = await res.text();
      let data = null;
      try {
        data = text ? JSON.parse(text) : null;
      } catch {
        data = text;
      }
      sendResponse({ ok: res.ok, status: res.status, data });
    } catch (e) {
      sendResponse({
        ok: false,
        status: 0,
        data: null,
        error: e instanceof Error ? e.message : String(e),
      });
    }
  })();

  return true;
});
