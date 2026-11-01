"""Read a run's failures. python show.py runs/base [--n 10]"""
import argparse
import json
import random
from collections import Counter

p = argparse.ArgumentParser()
p.add_argument("run")
p.add_argument("--n", type=int, default=5)
args = p.parse_args()

rows = [json.loads(line) for line in open(f"{args.run}/episodes.jsonl")]
print("how episodes ended:", dict(Counter(r["end"] for r in rows)))
print("searches per episode:", dict(sorted(Counter(len(r["searches"]) for r in rows).items())))
failures = [r for r in rows if r["f1"] < 0.5]
print(f"{len(failures)}/{len(rows)} episodes with F1 < 0.5. A random {args.n}:\n")
for r in random.Random(0).sample(failures, min(args.n, len(failures))):
    print("=" * 100)
    print(f"Q: {r['question']}\nGOLD: {r['answers']}   PRED: {r['prediction']!r}   END: {r['end']}")
    print("-" * 100)
    print(r["trace"])
