"""Step 1: download HotpotQA, write the question splits and the paragraph corpus.

data/train.jsonl  90k questions to train on
data/val.jsonl    200 questions to pick checkpoints with
data/test.jsonl   500 questions you only open in Step 5
data/corpus.jsonl every Wikipedia paragraph that appears in HotpotQA (one per title)
"""
import hashlib
import json
import os
import random

from datasets import load_dataset


def write(path, rows):
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def question(row):
    return {"id": row["id"], "question": row["question"], "answers": [row["answer"]],
            "type": row["type"], "level": row["level"]}


os.makedirs("data", exist_ok=True)
train = load_dataset("hotpotqa/hotpot_qa", "distractor", split="train")
dev = load_dataset("hotpotqa/hotpot_qa", "distractor", split="validation")

corpus, seen = [], set()
for split in (train, dev):
    for context in split["context"]:
        for title, sentences in zip(context["title"], context["sentences"]):
            if title not in seen:
                seen.add(title)
                corpus.append({"id": len(corpus), "title": title, "text": "".join(sentences).strip()})
write("data/corpus.jsonl", corpus)

rng = random.Random(0)
dev_rows = [question(r) for r in dev]
rng.shuffle(dev_rows)
write("data/test.jsonl", dev_rows[:500])
write("data/val.jsonl", dev_rows[500:700])
train_rows = [question(r) for r in train]
rng.shuffle(train_rows)
write("data/train.jsonl", train_rows)

digest = hashlib.sha256(open("data/test.jsonl", "rb").read()).hexdigest()[:16]
print(f"corpus {len(corpus):,} paragraphs | train {len(train_rows):,} | val 200 | test 500")
print(f"test.jsonl sha256 {digest}  <- write this down; it must never change")
