// Sentinel-Core popup — 主控台
const GATEWAY = "http://127.0.0.1:8000";
const STORAGE_KEY = "sc_enabled";

// ---------- 防護開關（與 content.js 共用 chrome.storage）----------
const toggle = document.getElementById("protection-toggle");
const toggleDesc = document.getElementById("toggle-desc");

function reflectToggle(enabled) {
    toggle.checked = enabled;
    toggleDesc.textContent = enabled
        ? "選取文字與滑過連結時自動偵測"
        : "防護已暫停，網頁不會被掃描";
}

chrome.storage.local.get({ [STORAGE_KEY]: true }, (res) => {
    reflectToggle(res[STORAGE_KEY] !== false);
});

toggle.addEventListener("change", () => {
    const enabled = toggle.checked;
    chrome.storage.local.set({ [STORAGE_KEY]: enabled });
    reflectToggle(enabled);
});

// ---------- 後端狀態 ----------
const pill = document.getElementById("status-pill");
const statusLabel = document.getElementById("status-label");

function setStatus(state, label) {
    pill.dataset.state = state;
    statusLabel.textContent = label;
}

async function checkHealth() {
    try {
        const controller = new AbortController();
        const t = setTimeout(() => controller.abort(), 2500);
        const res = await fetch(`${GATEWAY}/health`, { signal: controller.signal });
        clearTimeout(t);
        if (res.ok) {
            setStatus("online", "服務連線中");
            return true;
        }
        setStatus("offline", "後端異常");
        return false;
    } catch {
        setStatus("offline", "後端離線");
        return false;
    }
}

// ---------- 統計 ----------
const elTotal = document.getElementById("stat-total");
const elAvg = document.getElementById("stat-avg");
const elAvgFill = document.getElementById("stat-avg-fill");

function avgColor(score) {
    if (score >= 70) return getComputedStyle(document.documentElement).getPropertyValue("--safe");
    if (score >= 40) return getComputedStyle(document.documentElement).getPropertyValue("--warn");
    return getComputedStyle(document.documentElement).getPropertyValue("--danger");
}

async function loadStats() {
    try {
        const res = await fetch(`${GATEWAY}/stats`);
        if (!res.ok) throw new Error("stats unavailable");
        const data = await res.json();
        const total = Number(data.total) || 0;
        const avg = Math.round(Number(data.avg_score) || 0);
        elTotal.textContent = total.toLocaleString();
        elAvg.textContent = total > 0 ? avg : "—";
        if (total > 0) {
            requestAnimationFrame(() => {
                elAvgFill.style.width = `${Math.max(0, Math.min(100, avg))}%`;
                elAvgFill.style.background = avgColor(avg);
            });
        }
    } catch {
        elTotal.textContent = "—";
        elAvg.textContent = "—";
    }
}

// ---------- 近期掃描 ----------
const recentList = document.getElementById("recent-list");

const TONE = {
    danger: { color: "var(--danger)", soft: "rgba(220,38,38,0.14)" },
    safe: { color: "var(--safe)", soft: "rgba(22,163,74,0.14)" },
    neutral: { color: "var(--muted)", soft: "rgba(100,116,139,0.12)" },
};

function toneFor(label, score) {
    const l = String(label || "").toLowerCase();
    if (l === "danger" || l === "malicious") return TONE.danger;
    if (l === "suspicious") return TONE.danger;
    if (l === "safe") return TONE.safe;
    return Number(score) < 40 ? TONE.danger : TONE.neutral;
}

function relTime(iso) {
    if (!iso) return "";
    const t = Date.parse(iso.includes("T") ? iso : iso.replace(" ", "T") + "Z");
    if (Number.isNaN(t)) return "";
    const diff = Math.max(0, Date.now() - t);
    const min = Math.floor(diff / 60000);
    if (min < 1) return "剛剛";
    if (min < 60) return `${min} 分鐘前`;
    const hr = Math.floor(min / 60);
    if (hr < 24) return `${hr} 小時前`;
    return `${Math.floor(hr / 24)} 天前`;
}

function renderRecent(items) {
    recentList.innerHTML = "";
    if (!items || items.length === 0) {
        const li = document.createElement("li");
        li.className = "recent-empty";
        li.textContent = "尚無掃描紀錄";
        recentList.appendChild(li);
        return;
    }
    for (const it of items) {
        const tone = toneFor(it.label, it.trust_score);
        const li = document.createElement("li");
        li.className = "recent-item";

        const dot = document.createElement("span");
        dot.className = "recent-dot";
        dot.style.background = tone.color;
        dot.style.setProperty("--dot-soft", tone.soft);

        const main = document.createElement("div");
        main.className = "recent-main";
        const text = document.createElement("div");
        text.className = "recent-text";
        text.textContent = (it.content || "").trim() || "（無內容）";
        const sub = document.createElement("div");
        sub.className = "recent-sub";
        sub.textContent = relTime(it.created_at) || (it.label || "");
        main.append(text, sub);

        const score = document.createElement("span");
        score.className = "recent-score";
        score.style.setProperty("--score-color", tone.color);
        score.textContent = Number.isFinite(Number(it.trust_score)) ? it.trust_score : "—";

        li.append(dot, main, score);
        recentList.appendChild(li);
    }
}

async function loadRecent() {
    try {
        const res = await fetch(`${GATEWAY}/recent?limit=6`);
        if (!res.ok) throw new Error("recent unavailable");
        const data = await res.json();
        renderRecent(data.items);
    } catch {
        renderRecent([]);
    }
}

// ---------- 受信任網域白名單（與 content.js 共用 chrome.storage）----------
const allowInput = document.getElementById("allow-input");
const allowAddBtn = document.getElementById("allow-add");
const allowListEl = document.getElementById("allow-list");
const allowEmptyEl = document.getElementById("allow-empty");

function normalizeDomain(raw) {
    let d = String(raw || "").trim().toLowerCase();
    if (!d) return "";
    d = d.replace(/^[a-z]+:\/\//, "").replace(/\/.*$/, "").replace(/:\d+$/, "");
    if (!/^[a-z0-9.-]+\.[a-z]{2,}$/.test(d)) return "";
    return d;
}

function getAllowlist() {
    return new Promise((res) => {
        chrome.storage.local.get({ sc_allowlist: [] }, (r) => {
            res(Array.isArray(r.sc_allowlist) ? r.sc_allowlist : []);
        });
    });
}

function renderAllowlist(list) {
    allowListEl.innerHTML = "";
    if (!list || list.length === 0) {
        allowEmptyEl.classList.remove("hidden");
        return;
    }
    allowEmptyEl.classList.add("hidden");
    for (const d of list) {
        const chip = document.createElement("span");
        chip.className = "allow-chip";
        const label = document.createElement("span");
        label.textContent = d;
        const rm = document.createElement("button");
        rm.type = "button";
        rm.setAttribute("aria-label", `移除 ${d}`);
        rm.textContent = "×";
        rm.addEventListener("click", () => removeDomain(d));
        chip.append(label, rm);
        allowListEl.appendChild(chip);
    }
}

async function addDomain() {
    const d = normalizeDomain(allowInput.value);
    if (!d) { allowInput.focus(); return; }
    const list = await getAllowlist();
    if (!list.includes(d)) list.push(d);
    chrome.storage.local.set({ sc_allowlist: list });
    allowInput.value = "";
    renderAllowlist(list);
}

async function removeDomain(d) {
    const list = (await getAllowlist()).filter((x) => x !== d);
    chrome.storage.local.set({ sc_allowlist: list });
    renderAllowlist(list);
}

allowAddBtn.addEventListener("click", addDomain);
allowInput.addEventListener("keydown", (e) => { if (e.key === "Enter") addDomain(); });
getAllowlist().then(renderAllowlist);

(async function init() {
    const online = await checkHealth();
    if (online) {
        loadStats();
        loadRecent();
    }
})();
