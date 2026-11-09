"""Step 3: embed every page image as a bag of patch vectors (late interaction).

Each page becomes ~90-1,200 vectors of 128 numbers, depending on --edge. Work is saved
every 64 pages, so you can stop it and run the same command again to resume.

    python vision_index.py --edge 1024     # ~1 s/page on an M1, ~50 min for 2,942 pages
    python vision_index.py --edge 512      # no tiling, ~0.2 s/page, 4x smaller index
"""
import argparse
import glob
import json
import os
import time

import numpy as np
import pymupdf
import torch
from PIL import Image

from config import DATA, PDF_DIR, RENDER_DPI, VISION_MODEL, device

CHUNK = 64


def render(doc, page, dpi=RENDER_DPI):
    pix = pymupdf.open(os.path.join(PDF_DIR, f"{doc}.pdf"))[page - 1].get_pixmap(dpi=dpi)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def load(edge):
    from colpali_engine.models import ColModernVBert, ColModernVBertProcessor
    dev = device()
    model = ColModernVBert.from_pretrained(VISION_MODEL, torch_dtype=torch.float32, device_map=dev).eval()
    proc = ColModernVBertProcessor.from_pretrained(VISION_MODEL)
    ip = proc.image_processor
    ip.do_image_splitting = edge > 512   # 512 = one tile, larger edges are cut into 512 px tiles
    ip.size = {"longest_edge": edge}
    return model, proc, dev


def main(args):
    out = os.path.join(DATA, f"vision_{args.edge}")
    os.makedirs(out, exist_ok=True)
    pages = [json.loads(line) for line in open(os.path.join(DATA, "pages.jsonl"))]
    model, proc, dev = load(args.edge)
    start = time.time()
    for c in range(0, len(pages), CHUNK):
        path = os.path.join(out, f"chunk_{c // CHUNK:04d}.npz")
        if os.path.exists(path):
            continue
        part = pages[c : c + CHUNK]
        vecs, lens = [], []
        with torch.no_grad():
            for i in range(0, len(part), args.batch):
                imgs = [render(p["doc"], p["page"]) for p in part[i : i + args.batch]]
                batch = proc.process_images(imgs).to(dev)
                emb = model(**batch).float().cpu().numpy()
                mask = batch["attention_mask"].cpu().numpy().astype(bool)
                for e, m in zip(emb, mask):
                    vecs.append(e[m].astype(np.float16))  # drop padding positions
                    lens.append(int(m.sum()))
        np.savez(path, vecs=np.concatenate(vecs), lens=np.array(lens), ids=np.array([p["page_id"] for p in part]))
        done = c + len(part)
        print(f"{done:5d}/{len(pages)} pages | {np.mean(lens):.0f} vectors/page | {time.time() - start:6.0f}s", flush=True)

    chunks = sorted(glob.glob(os.path.join(out, "chunk_*.npz")))
    parts = [np.load(p) for p in chunks]
    vecs = np.concatenate([p["vecs"] for p in parts])
    lens = np.concatenate([p["lens"] for p in parts])
    ids = [str(x) for p in parts for x in p["ids"]]
    np.save(os.path.join(out, "vectors.npy"), vecs)
    np.save(os.path.join(out, "offsets.npy"), np.concatenate([[0], np.cumsum(lens)]))
    json.dump(ids, open(os.path.join(out, "page_ids.json"), "w"))
    print(f"index {out}: {len(ids)} pages, {len(vecs):,} vectors, {vecs.nbytes / 1e6:.0f} MB (float16)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--edge", type=int, default=1024)
    p.add_argument("--batch", type=int, default=4)
    main(p.parse_args())
