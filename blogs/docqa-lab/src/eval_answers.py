"""Step 5-6: answer every question in a split end to end and score the answers.

Retrieval is read from an earlier eval_retrieval.py run, so the answerer is the only thing
that changes between runs (and vision pages are not re-embedded).

    python eval_answers.py --pages-from bm25-filter --name ans-local-text --input text --limit 40
    python eval_answers.py --pages-from hybrid-filter --name ans-claude-image --answerer claude
"""
import argparse
import json
import os

import numpy as np

from config import DATA, RUNS, TOP_K
from highlight import evidence_image
from score import citation_precision, number_recall, token_f1, yes_no
from search import load_pages
from vision_index import render


def main(args):
    items = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(DATA, f"{args.split}.jsonl"))}
    ranked = [json.loads(l) for l in open(os.path.join(RUNS, args.pages_from, "retrieval.jsonl"))][: args.limit]
    by_id = {p["page_id"]: p for p in load_pages()}
    from answer import make
    answerer = make(args.answerer)
    out_dir = os.path.join(RUNS, args.name)
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    with open(os.path.join(out_dir, "answers.jsonl"), "w") as f:
        for n, r in enumerate(ranked, 1):
            item, ids = items[r["id"]], r["ranked"][: args.k]
            images = [render(by_id[p]["doc"], by_id[p]["page"]) for p in ids] if args.input == "image" else None
            texts = [by_id[p]["text"][:6000] for p in ids] if args.input == "text" else None
            res = answerer.answer(item["query"], ids, images=images, texts=texts)
            gold_yn = yes_no(item["answer"]) if "boolean" in item["query_types"] else None
            shown = 0
            for pid in res["citations"]:
                shown += evidence_image(pid, res["quote"], res["answer"])[1]
            row = {"id": item["id"], "query": item["query"], "gold": item["answer"], "pages": ids,
                   "pages_relevant": [p in item["gold"] for p in ids], **{k: v for k, v in res.items() if k != "raw"},
                   "yes_no_correct": None if gold_yn is None else float(yes_no(res["answer"]) == gold_yn),
                   "number_recall": number_recall(res["answer"], item["answer"]),
                   "token_f1": token_f1(res["answer"], item["answer"]),
                   "citation_precision": citation_precision(res["citations"], item["gold"]),
                   "evidence_shown": float(shown > 0)}
            rows.append(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"{n}/{len(ranked)} f1 {np.mean([x['token_f1'] for x in rows]):.3f} | {row['seconds']:.0f}s", flush=True)

    def mean(key):
        vals = [x[key] for x in rows if x[key] is not None]
        return (np.mean(vals), len(vals)) if vals else (float("nan"), 0)

    summary = {"name": args.name, "n": len(rows)}
    print(f"\n{args.name}: {len(rows)} questions, top-{args.k} pages from {args.pages_from}, input={args.input}")
    for key, label in [("yes_no_correct", "yes/no accuracy"), ("number_recall", "number recall"),
                       ("token_f1", "token F1 vs gold"), ("citation_precision", "citation precision"),
                       ("evidence_shown", "evidence highlighted")]:
        m, n = mean(key)
        summary[key] = m
        print(f"  {label:<22} {m:.3f}  (n={n})")
    secs = np.array([x["seconds"] for x in rows])
    cost = sum(x["usd"] for x in rows)
    summary.update({"p50_s": float(np.median(secs)), "p95_s": float(np.percentile(secs, 95)), "usd_per_q": cost / len(rows)})
    print(f"  answer time p50 {np.median(secs):.1f}s, p95 {np.percentile(secs, 95):.1f}s | ${cost / len(rows):.4f}/question")
    json.dump(summary, open(os.path.join(out_dir, "summary.json"), "w"))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--pages-from", required=True, help="a runs/<name> folder written by eval_retrieval.py")
    p.add_argument("--name", required=True)
    p.add_argument("--answerer", default="local", choices=["local", "claude"])
    p.add_argument("--input", default="image", choices=["image", "text"])
    p.add_argument("--split", default="val", help="val, test, or your own data/<name>.jsonl")
    p.add_argument("--k", type=int, default=TOP_K)
    p.add_argument("--limit", type=int)
    main(p.parse_args())
