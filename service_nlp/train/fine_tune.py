"""
Fine-tune 中文詐騙分類模型。

Base model : hfl/chinese-roberta-wwm-ext（中文全詞遮罩 RoBERTa，繁中表現佳）
Task       : 6 類序列分類（phishing / investment_scam / romance_scam /
             parcel_scam / gov_impersonation / safe）
Data       : service_nlp/train/data/processed/{train,val}.jsonl（由 prepare_dataset.py 產生）
Output     : service_nlp/detectors/model/（tokenizer + 權重 + label_map）

執行：
    python service_nlp/train/fine_tune.py
可選環境變數：
    SENTINEL_BASE_MODEL  覆寫 base model
    SENTINEL_EPOCHS      訓練 epoch 數（預設 3）
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import torch
from datasets import load_dataset
from sklearn.metrics import accuracy_score, f1_score
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

THIS_DIR = Path(__file__).resolve().parent
DATA_DIR = THIS_DIR / "data" / "processed"
OUTPUT_DIR = THIS_DIR.parent / "detectors" / "model"
RUNS_DIR = THIS_DIR / "runs"

BASE_MODEL = os.environ.get("SENTINEL_BASE_MODEL", "hfl/chinese-roberta-wwm-ext")
EPOCHS = int(os.environ.get("SENTINEL_EPOCHS", "3"))
MAX_LEN = 128
SEED = 42


def load_label_map() -> dict:
    return json.loads((DATA_DIR / "label_map.json").read_text(encoding="utf-8"))


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "f1_macro": f1_score(labels, preds, average="macro"),
    }


def main() -> None:
    if not (DATA_DIR / "train.jsonl").exists():
        raise SystemExit("找不到 train.jsonl，請先執行 prepare_dataset.py")

    label_map = load_label_map()
    id2label = {v: k for k, v in label_map.items()}
    label2id = label_map
    num_labels = len(label_map)

    use_cuda = torch.cuda.is_available()
    print(f"[train] device = {'cuda:' + torch.cuda.get_device_name(0) if use_cuda else 'cpu'}")
    print(f"[train] base model = {BASE_MODEL}, epochs = {EPOCHS}")

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL,
        num_labels=num_labels,
        id2label=id2label,
        label2id=label2id,
    )

    ds = load_dataset(
        "json",
        data_files={
            "train": str(DATA_DIR / "train.jsonl"),
            "validation": str(DATA_DIR / "val.jsonl"),
        },
    )

    def tokenize(batch):
        enc = tokenizer(batch["text"], truncation=True, max_length=MAX_LEN)
        enc["labels"] = batch["label_id"]
        return enc

    ds = ds.map(tokenize, batched=True, remove_columns=ds["train"].column_names)
    collator = DataCollatorWithPadding(tokenizer=tokenizer)

    args = TrainingArguments(
        output_dir=str(RUNS_DIR),
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=32,
        per_device_eval_batch_size=64,
        learning_rate=2e-5,
        weight_decay=0.01,
        warmup_ratio=0.1,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        logging_steps=20,
        fp16=use_cuda,
        seed=SEED,
        report_to="none",
        save_total_limit=1,
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=ds["train"],
        eval_dataset=ds["validation"],
        processing_class=tokenizer,
        data_collator=collator,
        compute_metrics=compute_metrics,
    )

    trainer.train()
    metrics = trainer.evaluate()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(OUTPUT_DIR))
    tokenizer.save_pretrained(str(OUTPUT_DIR))
    (OUTPUT_DIR / "label_map.json").write_text(
        json.dumps(label_map, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("=" * 56)
    print("訓練完成，最佳模型已存至:", OUTPUT_DIR)
    print(f"  val accuracy : {metrics.get('eval_accuracy'):.4f}")
    print(f"  val f1_macro : {metrics.get('eval_f1_macro'):.4f}")
    print("=" * 56)


if __name__ == "__main__":
    main()
