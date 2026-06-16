"""
A4 獨立煙霧測試：載入實際 fine-tuned 模型，驗證 6 類代表句的分類結果。
（不經過 pytest 的全域 mock，直接以真實模型推論。）

執行：
    python service_nlp/train/smoke_test_engine.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from detectors.bert_engine import BertDetector  # noqa: E402

CASES = [
    ("您的網路銀行帳號偵測到異常登入，請點擊連結驗證身分以免凍結", "phishing"),
    ("老師帶你買飆股穩賺不賠，加LINE進群免費領取明牌", "investment_scam"),
    ("親愛的我是駐外軍官，因戰地無法領薪需要你幫忙代收包裹", "romance_scam"),
    ("您的包裹因地址不全無法配送，請點連結更新收件資訊", "parcel_scam"),
    ("我是地檢署檢察官，您涉及洗錢案請將存款轉入安全帳戶", "gov_impersonation"),
    ("明天下午三點開會，地點在三樓會議室，記得帶筆電", "safe"),
]


def main():
    detector = BertDetector()
    passed = 0
    print(f"{'預期':<18}{'預測':<18}{'信任分':>6}{'信心':>8}  文字")
    print("-" * 88)
    for text, expected in CASES:
        r = detector.analyze(text)
        ok = r["category"] == expected
        passed += ok
        mark = "✓" if ok else "✗"
        print(f"{mark} {expected:<16}{r['category']:<18}{r['trust_score']:>6}{r['confidence']:>8.3f}  {text[:22]}")

    print("-" * 88)
    print(f"通過 {passed}/{len(CASES)}")
    # 空字串分支
    empty = detector.analyze("")
    assert empty["category"] == "safe" and empty["trust_score"] == 50, "空字串分支異常"
    print("空字串分支: OK")
    if passed != len(CASES):
        raise SystemExit(1)
    print("A4 smoke test PASSED")


if __name__ == "__main__":
    main()
