"""
評估 fine-tuned 詐騙分類模型，並與舊版 baseline（情感星等模型）對比。

評估兩個測試集：
  1. in-distribution（test.jsonl）：與訓練同分布（模板/種子切分），代表上限
  2. out-of-distribution（seeds/ood_test.jsonl）：手寫真實風格 + 難負樣本，
     代表真實泛化能力（更可信，也是報告應強調的數字）

產出（service_nlp/train/reports/）：
  classification_report_{indist,ood}.txt
  confusion_matrix_{indist,ood}.png
  metrics.json（含兩組 6 類指標 + baseline vs fine-tuned 二元對比）

執行：
    python service_nlp/train/evaluate.py
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

THIS_DIR = Path(__file__).resolve().parent
DATA_DIR = THIS_DIR / "data" / "processed"
SEEDS_DIR = THIS_DIR / "seeds"
MODEL_DIR = THIS_DIR.parent / "detectors" / "model"
REPORTS_DIR = THIS_DIR / "reports"

LABEL_ORDER = ["phishing", "investment_scam", "romance_scam", "parcel_scam", "gov_impersonation", "safe"]

# 舊 baseline（與現行 bert_engine.py 相同的情感→信任分數邏輯）
BASELINE_MODEL = "nlptown/bert-base-multilingual-uncased-sentiment"
BASELINE_STAR_WEIGHTS = {"1 star": 0, "2 stars": 25, "3 stars": 50, "4 stars": 75, "5 stars": 100}
BASELINE_TRUST_THRESHOLD = 55  # trust_score <= 55 視為 Danger(scam)


def load_jsonl(path: Path):
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [r["text"] for r in rows], [r["label"] for r in rows]


def load_finetuned():
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
    model.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    return tokenizer, model, device


def predict_finetuned(texts, tokenizer, model, device):
    id2label = model.config.id2label
    preds = []
    for i in range(0, len(texts), 64):
        chunk = texts[i : i + 64]
        enc = tokenizer(chunk, truncation=True, max_length=128, padding=True, return_tensors="pt").to(device)
        with torch.no_grad():
            logits = model(**enc).logits
        preds.extend(id2label[idx] for idx in logits.argmax(dim=-1).tolist())
    return preds


def predict_baseline_binary(texts, classifier):
    out = []
    for t in texts:
        results = classifier(t, top_k=5)
        prob = {r["label"]: r["score"] for r in results}
        score = sum(prob.get(lbl, 0.0) * w for lbl, w in BASELINE_STAR_WEIGHTS.items())
        out.append("scam" if round(score) <= BASELINE_TRUST_THRESHOLD else "safe")
    return out


def to_binary(label):
    return "safe" if label == "safe" else "scam"


def binary_metrics(y_true_bin, y_pred_bin):
    p, r, f1, _ = precision_recall_fscore_support(
        y_true_bin, y_pred_bin, labels=["scam"], average="binary", pos_label="scam", zero_division=0
    )
    acc = float(np.mean([a == b for a, b in zip(y_true_bin, y_pred_bin)]))
    return {"accuracy": acc, "precision": float(p), "recall": float(r), "f1": float(f1)}


def save_confusion(y_true, y_pred, suffix, title):
    cm = confusion_matrix(y_true, y_pred, labels=LABEL_ORDER)
    fig, ax = plt.subplots(figsize=(8, 7))
    ConfusionMatrixDisplay(cm, display_labels=LABEL_ORDER).plot(
        ax=ax, cmap="Blues", xticks_rotation=45, colorbar=False
    )
    ax.set_title(title)
    plt.tight_layout()
    plt.savefig(REPORTS_DIR / f"confusion_matrix_{suffix}.png", dpi=150)
    plt.close(fig)


def evaluate_split(name, suffix, texts, y_true, ft, baseline_clf):
    tokenizer, model, device = ft
    y_pred = predict_finetuned(texts, tokenizer, model, device)

    report_txt = classification_report(y_true, y_pred, labels=LABEL_ORDER, digits=4, zero_division=0)
    (REPORTS_DIR / f"classification_report_{suffix}.txt").write_text(report_txt, encoding="utf-8")
    print(f"\n===== [{name}] fine-tuned 6 類分類報告 =====")
    print(report_txt)
    title_en = {"indist": "Confusion Matrix (in-distribution test)",
                "ood": "Confusion Matrix (out-of-distribution / real-style)"}.get(suffix, "Confusion Matrix")
    save_confusion(y_true, y_pred, suffix, title_en)

    report_dict = classification_report(y_true, y_pred, labels=LABEL_ORDER, output_dict=True, zero_division=0)

    # 二元對比
    y_true_bin = [to_binary(l) for l in y_true]
    ft_bin = binary_metrics(y_true_bin, [to_binary(l) for l in y_pred])
    bl_bin = binary_metrics(y_true_bin, predict_baseline_binary(texts, baseline_clf))

    print(f"----- [{name}] 二元詐騙偵測對比（scam vs safe）-----")
    print(f"{'模型':<20}{'acc':>9}{'prec':>9}{'recall':>9}{'f1':>9}")
    print(f"{'baseline(情感星等)':<16}{bl_bin['accuracy']:>9.4f}{bl_bin['precision']:>9.4f}{bl_bin['recall']:>9.4f}{bl_bin['f1']:>9.4f}")
    print(f"{'fine-tuned(本專案)':<16}{ft_bin['accuracy']:>9.4f}{ft_bin['precision']:>9.4f}{ft_bin['recall']:>9.4f}{ft_bin['f1']:>9.4f}")

    return {
        "macro_f1": report_dict["macro avg"]["f1-score"],
        "accuracy": report_dict["accuracy"],
        "per_class": {k: report_dict[k] for k in LABEL_ORDER},
        "binary_baseline": bl_bin,
        "binary_finetuned": ft_bin,
    }


def main():
    if not (MODEL_DIR / "config.json").exists():
        raise SystemExit(f"找不到 fine-tuned 模型於 {MODEL_DIR}，請先執行 fine_tune.py")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    ft = load_finetuned()
    print("[eval] 載入 baseline（情感星等）模型...")
    baseline_clf = pipeline("sentiment-analysis", model=BASELINE_MODEL)

    metrics = {}

    x_id, y_id = load_jsonl(DATA_DIR / "test.jsonl")
    metrics["in_distribution"] = evaluate_split("同分布 test", "indist", x_id, y_id, ft, baseline_clf)

    ood_path = SEEDS_DIR / "ood_test.jsonl"
    if ood_path.exists():
        x_ood, y_ood = load_jsonl(ood_path)
        metrics["out_of_distribution"] = evaluate_split("OOD 真實風格", "ood", x_ood, y_ood, ft, baseline_clf)

    (REPORTS_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    print("總結")
    for split_key, label in [("in_distribution", "同分布"), ("out_of_distribution", "OOD 真實風格")]:
        if split_key in metrics:
            m = metrics[split_key]
            print(f"[{label}] 6類 macro-F1={m['macro_f1']:.4f}  "
                  f"二元 fine-tuned F1={m['binary_finetuned']['f1']:.4f}  "
                  f"baseline F1={m['binary_baseline']['f1']:.4f}")
    print(f"報告輸出於: {REPORTS_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
