"""Step 1: download the six 10-Ks and the questions, split val/test, extract each page's text layer.

data/pdfs/*.pdf   the six annual reports (27 MB)
data/pages.jsonl  one row per page: page_id, doc, page (1-based), text
data/val.jsonl    100 questions to tune on
data/test.jsonl   209 questions you only score in Step 7

    python prep_data.py
"""
import hashlib
import json
import os
import random

import fsspec
import pyarrow.parquet as pq
import pymupdf

from config import DATA, DATASET, DATASET_COMMIT, PDF_DIR, VAL_SIZE

BASE = f"https://huggingface.co/datasets/{DATASET}/resolve/{DATASET_COMMIT}/"
DOCS = ["bank_of_america_2024", "citigroup_2024", "goldman_sachs_2024",
        "jpmorgan_chase_2024", "morgan_stanley_2024", "wells_fargo_2024"]


def read_parquet(fs, path, columns=None):
    with fs.open(BASE + path, "rb", block_size=2**20) as f:
        return pq.ParquetFile(f).read(columns=columns).to_pylist()


def main():
    os.makedirs(PDF_DIR, exist_ok=True)
    fs = fsspec.filesystem("https")
    for doc in DOCS:
        dest = os.path.join(PDF_DIR, f"{doc}.pdf")
        if not os.path.exists(dest):
            with fs.open(BASE + f"pdfs/{doc}.pdf", "rb") as src, open(dest, "wb") as out:
                out.write(src.read())

    # The corpus parquet also holds 1.3 GB of page images. Read only the three small
    # columns we need: Parquet stores columns separately, so this downloads a few MB.
    corpus = []
    for i in range(3):
        corpus += read_parquet(fs, f"corpus/test-0000{i}-of-00003.parquet",
                               ["corpus_id", "doc_id", "page_number_in_doc"])
    page_of = {int(r["corpus_id"]): (r["doc_id"], int(r["page_number_in_doc"]) + 1) for r in corpus}

    pages = []
    for doc in DOCS:
        pdf = pymupdf.open(os.path.join(PDF_DIR, f"{doc}.pdf"))
        for i, page in enumerate(pdf):
            pages.append({"page_id": f"{doc}#{i + 1}", "doc": doc, "page": i + 1,
                          "text": page.get_text("text")})
    with open(os.path.join(DATA, "pages.jsonl"), "w") as f:
        for p in pages:
            f.write(json.dumps(p) + "\n")
    known = {p["page_id"] for p in pages}

    queries = [q for q in read_parquet(fs, "queries/test-00000-of-00001.parquet") if q["language"] == "english"]
    gold = {}
    for r in read_parquet(fs, "qrels/test-00000-of-00001.parquet"):
        doc, page = page_of[int(r["corpus_id"])]
        gold.setdefault(int(r["query_id"]), {})[f"{doc}#{page}"] = int(r["score"])
    rows = []
    for q in queries:
        g = gold[int(q["query_id"])]
        assert set(g) <= known, "a gold page is missing from the PDFs"
        rows.append({"id": int(q["query_id"]), "query": q["query"], "answer": q["answer"],
                     "query_types": list(q["query_types"]), "content_type": list(q["content_type"]),
                     "format": q["query_format"], "gold": g})
    rows.sort(key=lambda r: r["id"])
    random.Random(0).shuffle(rows)

    def write(name, part):
        with open(os.path.join(DATA, name), "w") as f:
            for r in part:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    write("val.jsonl", rows[:VAL_SIZE])
    write("test.jsonl", rows[VAL_SIZE:])
    digest = hashlib.sha256(open(os.path.join(DATA, "test.jsonl"), "rb").read()).hexdigest()[:16]
    empty = sum(1 for p in pages if len(p["text"].strip()) < 50)
    print(f"pages {len(pages):,} ({empty} with almost no text layer) | val {VAL_SIZE} | test {len(rows) - VAL_SIZE}")
    print(f"gold pages per question {sum(len(r['gold']) for r in rows) / len(rows):.1f}")
    print(f"test.jsonl sha256 {digest}  <- write this down; it must never change")


if __name__ == "__main__":
    main()
