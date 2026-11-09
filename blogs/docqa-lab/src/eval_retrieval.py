"""Step 2-4: score a retriever on a split. Writes runs/<name>/retrieval.jsonl and prints the
headline numbers plus a breakdown by content type, the table the capstone asks for.

    python eval_retrieval.py --retriever bm25 --name bm25
    python eval_retrieval.py --retriever vision --name vision-1024 --index vision_1024
    python eval_retrieval.py --retriever hybrid --name hybrid --filter
"""
import argparse
import json
import os
import time

import numpy as np

from config import DATA, RUNS, VISION_EDGE
from score import hit, mrr, ndcg, recall
from search import make


def summarize(rows, label):
    m = {k: np.mean([r[k] for r in rows]) for k in ("ndcg5", "recall5", "hit3", "mrr")}
    return f"{label:<14} n={len(rows):3d}  nDCG@5 {m['ndcg5']:.3f}  Recall@5 {m['recall5']:.3f}  Hit@3 {m['hit3']:.3f}  MRR {m['mrr']:.3f}"


def main(args):
    items = [json.loads(line) for line in open(os.path.join(DATA, f"{args.split}.jsonl"))][: args.limit]
    retriever = make(args.retriever, filter_companies=args.filter, index=args.index)
    out_dir = os.path.join(RUNS, args.name)
    os.makedirs(out_dir, exist_ok=True)
    rows, latency = [], []
    for item in items:
        t = time.time()
        ranked = [pid for pid, _ in retriever.search(item["query"], k=20)]
        latency.append(time.time() - t)
        g = item["gold"]
        rows.append({"id": item["id"], "ranked": ranked, "ndcg5": ndcg(ranked, g, 5), "recall5": recall(ranked, g, 5),
                     "hit3": hit(ranked, g, 3), "mrr": mrr(ranked, g), "content_type": item["content_type"],
                     "query_types": item["query_types"]})
    with open(os.path.join(out_dir, "retrieval.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(summarize(rows, args.name))
    for ct in ("Text", "Table", "Chart"):
        part = [r for r in rows if ct in r["content_type"]]
        if part:
            print(summarize(part, f"  has {ct}"))
    for qt in ("numerical", "multi-hop", "compare-contrast"):
        part = [r for r in rows if qt in r["query_types"]]
        if part:
            print(summarize(part, f"  {qt}"))
    lat = np.array(latency) * 1000
    print(f"latency per query: p50 {np.percentile(lat, 50):.0f} ms, p95 {np.percentile(lat, 95):.0f} ms")
    json.dump({"name": args.name, **{k: float(np.mean([r[k] for r in rows])) for k in ("ndcg5", "recall5", "hit3", "mrr")},
               "p95_ms": float(np.percentile(lat, 95))}, open(os.path.join(out_dir, "summary.json"), "w"))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--retriever", choices=["bm25", "dense", "vision", "hybrid"], required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--split", default="val", help="val, test, or your own data/<name>.jsonl")
    p.add_argument("--filter", action="store_true", help="search only the reports of companies named in the question")
    p.add_argument("--index", default=f"vision_{VISION_EDGE}", help="vision index folder under data/")
    p.add_argument("--limit", type=int)
    main(p.parse_args())
