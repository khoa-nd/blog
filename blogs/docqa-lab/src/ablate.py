"""Step 7: compare runs on the same questions, with 95% bootstrap confidence intervals.

The first run is the baseline; every other run gets a paired difference against it.

    python ablate.py runs/test-bm25 runs/test-vision runs/test-hybrid            # nDCG@5
    python ablate.py runs/ans-text runs/ans-image --metric number_recall          # answers
"""
import argparse
import json
import os
import random


def load(run, metric):
    path = os.path.join(run, "retrieval.jsonl")
    if not os.path.exists(path) or metric not in json.loads(open(path).readline()):
        path = os.path.join(run, "answers.jsonl")
    rows = {}
    for line in open(path):
        r = json.loads(line)
        if r.get(metric) is not None:
            rows[r["id"]] = float(r[metric])
    return rows


def ci(values, rng, n=1000):
    means = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n)]


def main(args):
    rng = random.Random(0)
    runs = {r.rstrip("/"): load(r, args.metric) for r in args.runs}
    names = list(runs)
    common = sorted(set.intersection(*(set(v) for v in runs.values())))
    base = names[0]
    print(f"{args.metric} on {len(common)} shared questions, 95% bootstrap CI ({args.n} resamples)\n")
    print(f"{'run':<34}{'mean':>8}   {'95% CI':<17}{'Δ vs ' + os.path.basename(base):>18}   {'95% CI of Δ'}")
    for name in names:
        vals = [runs[name][i] for i in common]
        lo, hi = ci(vals, rng, args.n)
        line = f"{os.path.basename(name):<34}{sum(vals) / len(vals):8.3f}   [{lo:.3f}, {hi:.3f}]"
        if name != base:
            diff = [runs[name][i] - runs[base][i] for i in common]
            dlo, dhi = ci(diff, rng, args.n)
            verdict = "real" if dlo > 0 or dhi < 0 else "could be luck"
            line += f"{sum(diff) / len(diff):+18.3f}   [{dlo:+.3f}, {dhi:+.3f}]  {verdict}"
        print(line)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("runs", nargs="+")
    p.add_argument("--metric", default="ndcg5")
    p.add_argument("--n", type=int, default=1000)
    main(p.parse_args())
