"""Step 9b: build a gold set for YOUR documents, 20-50 questions, in about an hour.

For each question you type, it shows the top 8 pages from BM25 (and a snippet of each). You mark
which pages hold the answer (2 = the whole answer, 1 = part of it) and type the answer. Rows go
to data/<name>.jsonl in the same format as val/test, so every eval script works on them:

    python label.py --name my_eval
    python eval_retrieval.py --retriever hybrid --name mine --split my_eval --filter
"""
import argparse
import json
import os
import re

from config import DATA
from search import BM25, load_pages


def snippet(text, query, width=160):
    words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 3]
    low = text.lower()
    hits = [low.find(w) for w in words if low.find(w) >= 0]
    start = max(0, min(hits) - 40) if hits else 0
    return " ".join(text[start : start + width].split())


def main(args):
    bm25 = BM25(filter_companies=True)
    pages = {p["page_id"]: p for p in load_pages()}
    path = os.path.join(DATA, f"{args.name}.jsonl")
    n = sum(1 for _ in open(path)) if os.path.exists(path) else 0
    print(f"Writing to {path} ({n} rows so far). Empty question to stop.\n")
    while True:
        q = input("Question: ").strip()
        if not q:
            break
        hits = bm25.search(q, k=8)
        for i, (pid, _) in enumerate(hits, 1):
            print(f"  {i}. {pid:<28} {snippet(pages[pid]['text'], q)}")
        marks = input("Relevant pages as number=score, e.g. '1=2 3=1' (or page ids like citi_2024#12=2): ").split()
        gold = {}
        for m in marks:
            key, _, score = m.partition("=")
            pid = hits[int(key) - 1][0] if key.isdigit() else key
            gold[pid] = int(score or 2)
        answer = input("Answer: ").strip()
        kind = input("Type (numerical / boolean / extractive / compare-contrast): ").strip() or "extractive"
        row = {"id": 100000 + n, "query": q, "answer": answer, "query_types": [kind], "content_type": ["Text"],
               "format": "question", "gold": gold}
        with open(path, "a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        n += 1
        print(f"Saved ({n} rows).\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--name", default="my_eval")
    main(p.parse_args())
