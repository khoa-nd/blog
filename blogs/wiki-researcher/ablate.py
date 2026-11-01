"""Step 5: compare runs on the same questions with 95% bootstrap confidence intervals.

python ablate.py runs/test-base runs/test-sft runs/test-grpo
The first run is the baseline; every other run gets a paired difference against it.
"""
import json
import random
import sys


def load(run):
    rows = {}
    for line in open(f"{run}/episodes.jsonl"):
        r = json.loads(line)
        rows[r["id"]] = r
    return rows


def ci(values, rng, n=1000):
    means = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n)]


runs = sys.argv[1:]
data = [load(r) for r in runs]
ids = sorted(set.intersection(*(set(d) for d in data)))
rng = random.Random(0)
base = [data[0][i]["f1"] for i in ids]
print(f"{len(ids)} shared questions\n")
print(f"{'run':<22}{'F1':>7}{'95% CI':>16}{'EM':>7}{'searches':>10}{'$/q':>9}{'Δ F1 vs first':>24}")
for run, d in zip(runs, data):
    f1s = [d[i]["f1"] for i in ids]
    lo, hi = ci(f1s, rng)
    mean = lambda key: sum(d[i][key] for i in ids) / len(ids)
    searches = sum(len(d[i]["searches"]) for i in ids) / len(ids)
    delta = ""
    if d is not data[0]:
        diffs = [a - b for a, b in zip(f1s, base)]
        dlo, dhi = ci(diffs, rng)
        delta = f"{sum(diffs) / len(diffs):+.3f} [{dlo:+.3f}, {dhi:+.3f}]"
    print(f"{run:<22}{mean('f1'):>7.3f}{f'[{lo:.3f}, {hi:.3f}]':>16}{mean('em'):>7.3f}"
          f"{searches:>10.2f}{mean('usd'):>9.4f}{delta:>24}")
print("\nA difference is real only if its interval does not contain 0.")
