"""Read the failures of a run: where error analysis starts.

    python show.py runs/bm25-filter --n 5            # questions where no relevant page made the top 3
    python show.py runs/ans-local-text --n 5          # answers with the lowest scores
"""
import argparse
import json
import os

from config import DATA


def main(args):
    items = {}
    for split in ("val", "test"):
        path = os.path.join(DATA, f"{split}.jsonl")
        if os.path.exists(path):
            items.update({json.loads(l)["id"]: json.loads(l) for l in open(path)})
    if os.path.exists(os.path.join(args.run, "answers.jsonl")):
        rows = [json.loads(l) for l in open(os.path.join(args.run, "answers.jsonl"))]
        rows.sort(key=lambda r: (r["number_recall"] if r["number_recall"] is not None else r["token_f1"]))
        for r in rows[: args.n]:
            print(f"Q{r['id']}: {r['query']}")
            print(f"  GOLD : {r['gold'][:220]}")
            print(f"  PRED : {r['answer'][:220]}")
            print(f"  pages: {', '.join(p + (' *' if ok else '') for p, ok in zip(r['pages'], r['pages_relevant']))}"
                  f"   (* = labeled relevant)  cited: {r['citations']}\n")
        return
    rows = [json.loads(l) for l in open(os.path.join(args.run, "retrieval.jsonl"))]
    misses = [r for r in rows if r["hit3"] == 0]
    print(f"{len(misses)} of {len(rows)} questions have no relevant page in the top 3\n")
    for r in misses[: args.n]:
        item = items[r["id"]]
        print(f"Q{r['id']} [{', '.join(item['content_type'])}] {item['query']}")
        print(f"  relevant: {', '.join(f'{p} ({s})' for p, s in item['gold'].items())}")
        print(f"  top 3   : {', '.join(r['ranked'][:3])}\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("run")
    p.add_argument("--n", type=int, default=5)
    main(p.parse_args())
