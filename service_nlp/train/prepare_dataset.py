"""
建立 6 類詐騙語料資料集。

流程：
1. 讀取 seeds/<label>.txt 的人工真實話術種子
2. 以 templates.py 的句型 + 槽位做組合式資料增強（seeded，可重現）
3. 合併、去重、平衡各類別至 TARGET_PER_CLASS
4. 分層（stratified）切分 train/val/test = 70/15/15
5. 輸出 data/processed/{train,val,test}.jsonl 與 label_map.json，並印出統計

執行：
    python service_nlp/train/prepare_dataset.py
"""
import json
import random
import sys
from itertools import product
from pathlib import Path

# Windows 主控台預設 cp1252，強制 UTF-8 以正確輸出中文統計
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 確保可從專案任何位置執行
THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from templates import TEMPLATES, SLOTS  # noqa: E402

SEED = 42
TARGET_PER_CLASS = 700
SPLIT = (0.70, 0.15, 0.15)  # train / val / test

SEEDS_DIR = THIS_DIR / "seeds"
OUT_DIR = THIS_DIR / "data" / "processed"

LABELS = [
    "phishing",
    "investment_scam",
    "romance_scam",
    "parcel_scam",
    "gov_impersonation",
    "safe",
]


def load_seeds(label: str) -> list[str]:
    """讀取單一類別的人工種子（# 註解與空行略過）。"""
    path = SEEDS_DIR / f"{label}.txt"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]


def render_templates(label: str, rng: random.Random) -> list[str]:
    """以槽位組合展開模板；組合過多時隨機抽樣，確保多樣且可重現。"""
    templates = TEMPLATES.get(label, [])
    slots = SLOTS.get(label, {})
    out: list[str] = []

    for tpl in templates:
        keys = [k for k in slots if "{" + k + "}" in tpl]
        if not keys:
            out.append(tpl)
            continue
        value_lists = [slots[k] for k in keys]
        combos = list(product(*value_lists))
        rng.shuffle(combos)
        # 每個模板最多取 200 種組合，避免單一模板灌爆
        for combo in combos[:200]:
            mapping = dict(zip(keys, combo))
            out.append(tpl.format(**mapping))
    return out


def build_label_pool(label: str, rng: random.Random) -> list[str]:
    """種子 + 模板增強 → 去重 → 洗牌 → 取 TARGET_PER_CLASS。"""
    pool = load_seeds(label) + render_templates(label, rng)
    deduped = list(dict.fromkeys(s.strip() for s in pool if s.strip()))
    rng.shuffle(deduped)
    return deduped[:TARGET_PER_CLASS]


def stratified_split(items: list[str], rng: random.Random):
    """對單一類別做 70/15/15 切分。"""
    shuffled = items[:]
    rng.shuffle(shuffled)
    n = len(shuffled)
    n_train = int(n * SPLIT[0])
    n_val = int(n * SPLIT[1])
    return (
        shuffled[:n_train],
        shuffled[n_train : n_train + n_val],
        shuffled[n_train + n_val :],
    )


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    rng = random.Random(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    label_map = {label: idx for idx, label in enumerate(LABELS)}

    splits = {"train": [], "val": [], "test": []}
    per_class_counts = {}

    for label in LABELS:
        pool = build_label_pool(label, rng)
        per_class_counts[label] = len(pool)
        tr, va, te = stratified_split(pool, rng)
        for split_name, texts in zip(("train", "val", "test"), (tr, va, te)):
            splits[split_name].extend(
                {"text": t, "label": label, "label_id": label_map[label]} for t in texts
            )

    # 跨類別洗牌
    for split_name in splits:
        rng.shuffle(splits[split_name])
        write_jsonl(OUT_DIR / f"{split_name}.jsonl", splits[split_name])

    (OUT_DIR / "label_map.json").write_text(
        json.dumps(label_map, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # --- 統計輸出 ---
    print("=" * 56)
    print(f"資料集建立完成  (seed={SEED}, target/class={TARGET_PER_CLASS})")
    print("=" * 56)
    print(f"{'類別':<20}{'總數':>8}{'train':>8}{'val':>7}{'test':>7}")
    print("-" * 56)
    for label in LABELS:
        total = per_class_counts[label]
        n_tr = int(total * SPLIT[0])
        n_va = int(total * SPLIT[1])
        n_te = total - n_tr - n_va
        print(f"{label:<20}{total:>8}{n_tr:>8}{n_va:>7}{n_te:>7}")
    print("-" * 56)
    print(
        f"{'合計':<20}"
        f"{sum(per_class_counts.values()):>8}"
        f"{len(splits['train']):>8}"
        f"{len(splits['val']):>7}"
        f"{len(splits['test']):>7}"
    )
    print("=" * 56)
    print(f"輸出目錄: {OUT_DIR}")
    print(f"標籤對應: {label_map}")


if __name__ == "__main__":
    main()
