"""
頁面行為評分 + 多引擎融合。

- score_behavior(features) → {"score": 0-100 風險分, "flags": [...], "critical": bool}
- fuse(behavior_score, url_trust, url_label, critical) → {"fusion_score", "trust_score", "label"}

設計原則（避免大型正常網站誤報）：
  只有「關鍵釣魚訊號」(critical) 或 URL 被判惡意才會升級為 Danger。
  壓縮/混淆腳本、動態注入腳本、跨來源 iframe 等在 Google/FB 等正常站台普遍存在，
  鑑別度低，**不列入計分**；其餘弱訊號最多只到 Suspicious。
"""
from typing import Optional

# 弱/情境訊號（僅用於 score 與 Suspicious 判定，不會單獨造成 Danger）
BEHAVIOR_RULES = {
    "external_password_form": (60, "密碼表單提交至外部網域（高度釣魚特徵）"),
    "transparent_overlay": (25, "偵測到可疑的透明覆蓋層（點擊劫持風險）"),
    "form_action_external": (10, "表單提交目標為外部網域"),
    "suspicious_tld": (15, "可疑頂級網域"),
}

# 融合權重（風險空間）
W_BEHAVIOR = 0.55
W_URL = 0.45


def _is_critical(features: dict) -> bool:
    """關鍵釣魚訊號：單獨即可判定高風險。"""
    if features.get("external_password_form"):
        return True
    # 透明覆蓋層 + 頁面有密碼欄位 → 疑似登入點擊劫持
    if features.get("transparent_overlay") and int(features.get("password_field_count", 0) or 0) > 0:
        return True
    return False


def score_behavior(features: dict) -> dict:
    score = 0
    flags: list[str] = []
    for key, (weight, label) in BEHAVIOR_RULES.items():
        if features.get(key):
            score += weight
            flags.append(label)
    score = max(0, min(score, 100))
    return {"score": score, "flags": flags, "critical": _is_critical(features)}


def _label_for_risk(risk: int) -> str:
    if risk >= 55:
        return "Danger"
    if risk >= 30:
        return "Suspicious"
    return "Safe"


def fuse(
    behavior_score: int,
    url_trust: Optional[int] = None,
    url_label: Optional[str] = None,
    critical: bool = False,
) -> dict:
    """融合行為與 URL 訊號，回傳最終風險/信任/標籤。"""
    behavior_risk = max(0, min(int(behavior_score), 100))

    if url_trust is None:
        fusion_risk = behavior_risk
    else:
        url_risk = max(0, min(100 - int(url_trust), 100))
        fusion_risk = round(W_BEHAVIOR * behavior_risk + W_URL * url_risk)

    label = _label_for_risk(fusion_risk)

    if critical or url_label == "Malicious":
        # 關鍵釣魚訊號或惡意 URL → 升級 Danger
        label = "Danger"
        fusion_risk = max(fusion_risk, 80)
    else:
        if label == "Danger":
            # 沒有關鍵訊號時，不單憑弱訊號累加判定 Danger（避免正常站台誤報）
            label = "Suspicious"
        # URL 本身被判可疑時，至少維持 Suspicious（每頁掃描時行為多為 0，不應稀釋）
        if url_label == "Suspicious" and label == "Safe":
            label = "Suspicious"

    return {
        "fusion_score": fusion_risk,
        "trust_score": 100 - fusion_risk,
        "label": label,
    }
