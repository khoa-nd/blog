"""Step 9: add your own PDFs. Text layer first; pages without one (scans, photos) go through OCR.

    python ingest.py ~/Downloads/vinamilk_2024.pdf --alias vinamilk vnm --vision
    python ingest.py contract.pdf --ocr-lang vie      # Vietnamese scans need: brew install tesseract-lang

The PDF is copied into data/pdfs, its pages are appended to data/pages.jsonl, its aliases to
data/aliases.json (so "--filter" finds it by name), and with --vision its pages are embedded and
added to the vision index. Re-running with the same file name replaces that document.
"""
import argparse
import json
import os
import shutil
import time

import numpy as np
import pymupdf

from config import DATA, PDF_DIR, VISION_EDGE

TESSDATA = os.environ.get("TESSDATA_PREFIX", "/opt/homebrew/share/tessdata")


def page_text(page, lang):
    text = page.get_text("text")
    if len(text.strip()) >= 50:
        return text, False
    tp = page.get_textpage_ocr(language=lang, dpi=200, full=True, tessdata=TESSDATA)
    return page.get_text("text", textpage=tp), True


def main(args):
    doc_id = os.path.splitext(os.path.basename(args.pdf))[0].lower().replace(" ", "_").replace("-", "_")
    os.makedirs(PDF_DIR, exist_ok=True)
    shutil.copy(args.pdf, os.path.join(PDF_DIR, f"{doc_id}.pdf"))
    pdf = pymupdf.open(os.path.join(PDF_DIR, f"{doc_id}.pdf"))
    t, new, ocr = time.time(), [], 0
    for i, page in enumerate(pdf):
        text, used_ocr = page_text(page, args.ocr_lang)
        ocr += used_ocr
        new.append({"page_id": f"{doc_id}#{i + 1}", "doc": doc_id, "page": i + 1, "text": text, "ocr": used_ocr})
    path = os.path.join(DATA, "pages.jsonl")
    old = [json.loads(l) for l in open(path)] if os.path.exists(path) else []
    old = [p for p in old if p["doc"] != doc_id]
    with open(path, "w") as f:
        for p in old + new:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"{doc_id}: {len(new)} pages ({ocr} needed OCR) in {time.time() - t:.1f}s")

    aliases_path = os.path.join(DATA, "aliases.json")
    aliases = json.load(open(aliases_path)) if os.path.exists(aliases_path) else {}
    aliases[doc_id] = [a.lower() for a in (args.alias or [doc_id.replace("_", " ")])]
    json.dump(aliases, open(aliases_path, "w"), indent=1)

    for stale in ("dense.npz",):                      # the dense index is rebuilt on next use
        if os.path.exists(os.path.join(DATA, stale)):
            os.remove(os.path.join(DATA, stale))
    if args.vision:
        add_to_vision(new, args.edge)


def add_to_vision(new_pages, edge):
    import torch
    from vision_index import load, render
    folder = os.path.join(DATA, f"vision_{edge}")
    vecs = np.load(os.path.join(folder, "vectors.npy"))
    offsets = np.load(os.path.join(folder, "offsets.npy"))
    ids = json.load(open(os.path.join(folder, "page_ids.json")))
    doc = new_pages[0]["doc"]
    keep = [i for i, pid in enumerate(ids) if not pid.startswith(doc + "#")]
    parts = [vecs[offsets[i] : offsets[i + 1]] for i in keep]
    ids = [ids[i] for i in keep]
    model, proc, dev = load(edge)
    with torch.no_grad():
        for p in new_pages:
            batch = proc.process_images([render(p["doc"], p["page"])]).to(dev)
            emb = model(**batch)[0]
            parts.append(emb[batch["attention_mask"][0].bool()].float().cpu().numpy().astype(np.float16))
            ids.append(p["page_id"])
    np.save(os.path.join(folder, "vectors.npy"), np.concatenate(parts))
    np.save(os.path.join(folder, "offsets.npy"), np.concatenate([[0], np.cumsum([len(x) for x in parts])]))
    json.dump(ids, open(os.path.join(folder, "page_ids.json"), "w"))
    print(f"vision index now {len(ids)} pages")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("pdf")
    p.add_argument("--alias", nargs="*", help="names people use for this document's company")
    p.add_argument("--ocr-lang", default="eng")
    p.add_argument("--vision", action="store_true", help="also embed the pages into the vision index")
    p.add_argument("--edge", type=int, default=VISION_EDGE)
    main(p.parse_args())
