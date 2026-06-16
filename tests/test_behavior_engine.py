import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api_gateway"))

from behavior_engine import score_behavior, fuse  # noqa: E402


# ---------------------------------------------------------------------------
# score_behavior
# ---------------------------------------------------------------------------

def test_score_clean_page_is_zero():
    r = score_behavior({})
    assert r["score"] == 0
    assert r["critical"] is False


def test_external_password_form_is_critical():
    r = score_behavior({"external_password_form": True})
    assert r["score"] == 60
    assert r["critical"] is True
    assert any("外部" in f for f in r["flags"])


def test_overlay_with_password_field_is_critical():
    r = score_behavior({"transparent_overlay": True, "password_field_count": 1})
    assert r["critical"] is True


def test_overlay_without_password_not_critical():
    r = score_behavior({"transparent_overlay": True})
    assert r["critical"] is False


def test_noisy_signals_are_not_scored():
    # 模擬 Google：大量動態腳本/混淆腳本/跨來源 iframe，但無關鍵釣魚訊號
    r = score_behavior({
        "obfuscated_script": True, "dynamic_script_inject": 80,
        "cross_origin_iframe_count": 10, "password_field_count": 1,
    })
    assert r["score"] == 0
    assert r["critical"] is False


def test_score_capped_at_100():
    feats = {
        "external_password_form": True, "transparent_overlay": True,
        "form_action_external": True, "suspicious_tld": True,
    }
    assert score_behavior(feats)["score"] == 100


# ---------------------------------------------------------------------------
# fuse
# ---------------------------------------------------------------------------

def test_fuse_behavior_only_safe():
    f = fuse(20)
    assert f["fusion_score"] == 20
    assert f["trust_score"] == 80
    assert f["label"] == "Safe"


def test_fuse_critical_escalates_to_danger():
    f = fuse(60, critical=True)
    assert f["label"] == "Danger"
    assert f["fusion_score"] >= 80


def test_fuse_url_malicious_escalates_even_if_behavior_low():
    f = fuse(0, url_trust=0, url_label="Malicious")
    assert f["label"] == "Danger"


def test_fuse_weak_signals_never_reach_danger_without_critical():
    # 即使弱訊號累加到很高，沒有 critical 也不會是 Danger
    f = fuse(100, critical=False)
    assert f["label"] == "Suspicious"


def test_fuse_url_suspicious_floors_label():
    # 行為 0、URL 被判可疑 → 不應被稀釋成 Safe
    f = fuse(0, url_trust=50, url_label="Suspicious")
    assert f["label"] == "Suspicious"


def test_fuse_weighted_risk_space():
    # behavior risk 40, url_trust 40 -> url_risk 60
    # 0.55*40 + 0.45*60 = 22 + 27 = 49 -> Suspicious
    f = fuse(40, url_trust=40, url_label="Suspicious")
    assert f["fusion_score"] == 49
    assert f["label"] == "Suspicious"
