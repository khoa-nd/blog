"""Step 5b: what if the filing were a scan? Text search then depends on OCR; vision doesn't care.

Every Bank of America page is turned into a picture and read back with Tesseract (cached, ~8 min).
Then three retrievers search only that report, on all 94 questions answered by it alone:
  text layer BM25 (the digital PDF), OCR BM25 (the scan), vision, and OCR BM25 + vision.

    python scan_experiment.py
"""
import json
import os
import random

import numpy as np
import pymupdf
from rank_bm25 import BM25Okapi

from config import DATA, PDF_DIR, VISION_EDGE
from ingest import page_text
from score import hit, ndcg
from search import Vision, load_pages, rrf, tokens

DOC = "bank_of_america_2024"


def ocr_pages():
    path = os.path.join(DATA, f"ocr_{DOC}.jsonl")
    done = {json.loads(l)["page_id"]: json.loads(l)["text"] for l in open(path)} if os.path.exists(path) else {}
    pdf = pymupdf.open(os.path.join(PDF_DIR, f"{DOC}.pdf"))
    with open(path, "a") as f:
        for i, page in enumerate(pdf):
            pid = f"{DOC}#{i + 1}"
            if pid in done:
                continue
            scan = pymupdf.open()
            p = scan.new_page(width=page.rect.width, height=page.rect.height)
            p.insert_image(p.rect, pixmap=page.get_pixmap(dpi=150))   # the "scan": pixels only
            done[pid] = page_text(scan[0], "eng")[0]
            f.write(json.dumps({"page_id": pid, "text": done[pid]}) + "\n")
    return done


def ranker(texts, ids):
    bm25 = BM25Okapi([tokens(t) for t in texts])
    return lambda q: [(ids[i], 0.0) for i in np.argsort(-bm25.get_scores(tokens(q)))[:50]]


def main():
    pages = [p for p in load_pages() if p["doc"] == DOC]
    ids = [p["page_id"] for p in pages]
    ocr = ocr_pages()
    questions = []
    for split in ("val", "test"):
        for line in open(os.path.join(DATA, f"{split}.jsonl")):
            r = json.loads(line)
            if {p.split("#")[0] for p in r["gold"]} == {DOC}:
                questions.append(r)
    vision = Vision(index=f"vision_{VISION_EDGE}")
    keep = [i for i, pid in enumerate(vision.ids) if pid.startswith(DOC + "#")]

    def vision_search(q):
        s = vision.scores(q)[1][keep]
        return [(vision.ids[keep[i]], 0.0) for i in np.argsort(-s)[:50]]

    text_bm25 = ranker([p["text"] for p in pages], ids)
    ocr_bm25 = ranker([ocr[i] for i in ids], ids)
    systems = {"text layer BM25": text_bm25, "OCR BM25 (scan)": ocr_bm25, "vision (scan)": vision_search,
               "OCR BM25 + vision": lambda q: rrf([ocr_bm25(q), vision_search(q)])}
    scores = {name: [] for name in systems}
    hits = {name: [] for name in systems}
    for q in questions:
        for name, fn in systems.items():
            ranked = [p for p, _ in fn(q["query"])]
            scores[name].append(ndcg(ranked, q["gold"], 5))
            hits[name].append(hit(ranked, q["gold"], 3))
    rng = random.Random(0)
    base = scores["OCR BM25 (scan)"]
    print(f"{len(questions)} questions answered by {DOC} alone; search limited to its {len(ids)} pages\n")
    print(f"{'retriever':<20}{'nDCG@5':>8}{'Hit@3':>8}   Δ nDCG@5 vs OCR BM25 [95% CI]")
    for name in systems:
        line = f"{name:<20}{np.mean(scores[name]):8.3f}{np.mean(hits[name]):8.3f}"
        if name != "OCR BM25 (scan)":
            d = [a - b for a, b in zip(scores[name], base)]
            boots = sorted(np.mean(rng.choices(d, k=len(d))) for _ in range(1000))
            line += f"   {np.mean(d):+.3f} [{boots[25]:+.3f}, {boots[974]:+.3f}]"
        print(line)


if __name__ == "__main__":
    main()
