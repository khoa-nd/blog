"""Step 4b: make the vision index smaller and check what it costs in accuracy.

A late-interaction index stores hundreds of vectors per page. Two ways to shrink it:
  prune  drop the patches that look most like "any page" (margins, white space): the vectors
         closest to the corpus-wide average carry the least information.
  pool   merge similar patches inside a page with k-means and keep the centroids.

    python compress.py --method prune --keep 0.5     # -> data/vision_1024_prune50
    python compress.py --method pool --factor 3      # -> data/vision_1024_pool3
"""
import argparse
import json
import os

import numpy as np

from config import DATA, VISION_EDGE


def kmeans(x, k, iters=8, seed=0):
    rng = np.random.default_rng(seed)
    c = x[rng.choice(len(x), k, replace=False)]
    for _ in range(iters):
        assign = np.argmax(x @ c.T, axis=1)  # vectors are unit length: dot product = cosine
        for j in range(k):
            members = x[assign == j]
            if len(members):
                c[j] = members.mean(0)
        c /= np.linalg.norm(c, axis=1, keepdims=True) + 1e-8
    return c


def main(args):
    src = os.path.join(DATA, f"vision_{args.edge}")
    vecs = np.load(os.path.join(src, "vectors.npy")).astype(np.float32)
    offsets = np.load(os.path.join(src, "offsets.npy"))
    ids = json.load(open(os.path.join(src, "page_ids.json")))
    mean = vecs.mean(0)
    mean /= np.linalg.norm(mean)
    out_vecs, lens = [], []
    for a, b in zip(offsets[:-1], offsets[1:]):
        page = vecs[a:b]
        if args.method == "prune":
            keep = max(1, int(round(len(page) * args.keep)))
            generic = page @ mean
            page = page[np.sort(np.argsort(generic)[:keep])]
        else:
            page = kmeans(page, max(1, len(page) // args.factor))
        out_vecs.append(page.astype(np.float16))
        lens.append(len(page))
    tag = f"prune{int(args.keep * 100)}" if args.method == "prune" else f"pool{args.factor}"
    dst = os.path.join(DATA, f"vision_{args.edge}_{tag}")
    os.makedirs(dst, exist_ok=True)
    out = np.concatenate(out_vecs)
    np.save(os.path.join(dst, "vectors.npy"), out)
    np.save(os.path.join(dst, "offsets.npy"), np.concatenate([[0], np.cumsum(lens)]))
    json.dump(ids, open(os.path.join(dst, "page_ids.json"), "w"))
    print(f"{dst}: {len(out):,} vectors ({len(out) / len(vecs):.0%} of {len(vecs):,}), "
          f"{out.nbytes / 1e6:.0f} MB vs {vecs.nbytes / 2 / 1e6:.0f} MB")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--edge", type=int, default=VISION_EDGE)
    p.add_argument("--method", choices=["prune", "pool"], required=True)
    p.add_argument("--keep", type=float, default=0.5)
    p.add_argument("--factor", type=int, default=3)
    main(p.parse_args())
