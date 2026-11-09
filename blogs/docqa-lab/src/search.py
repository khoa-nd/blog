"""Four ways to find the right pages, behind one interface: search(query, k) -> [(page_id, score)].

bm25    keywords over the PDF's text layer
dense   MiniLM sentence embeddings over the text layer (max over 200-word windows)
vision  late interaction over page images: every query token finds its best patch (MaxSim)
hybrid  reciprocal rank fusion of bm25 and vision
"""
import json
import os
import re

import numpy as np

from config import DATA, DENSE_MODEL, VISION_EDGE

# Company names as people type them. Used by --filter to keep only that company's report.
ALIASES = {
    "bank_of_america_2024": ["bank of america", "bofa", "boa"],
    "citigroup_2024": ["citigroup", "citi", "citibank"],
    "goldman_sachs_2024": ["goldman"],
    "jpmorgan_chase_2024": ["jpmorgan", "jp morgan", "jpmc", "chase"],
    "morgan_stanley_2024": ["morgan stanley"],
    "wells_fargo_2024": ["wells fargo"],
}


def aliases():
    """Built-in names plus any added by ingest.py for your own documents."""
    path = os.path.join(DATA, "aliases.json")
    return {**ALIASES, **(json.load(open(path)) if os.path.exists(path) else {})}


def companies(query):
    q = query.lower()
    return {doc for doc, names in aliases().items() if any(re.search(rf"\b{re.escape(n)}", q) for n in names)}


def load_pages():
    return [json.loads(line) for line in open(os.path.join(DATA, "pages.jsonl"))]


def tokens(text):
    return re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", text.lower())


class Retriever:
    def __init__(self, filter_companies=False):
        self.filter = filter_companies

    def scores(self, query):  # -> (page_ids, np.array of scores)
        raise NotImplementedError

    def search(self, query, k=10):
        ids, s = self.scores(query)
        order = np.argsort(-s)
        if self.filter and (wanted := companies(query)):
            # One company: keep only its report. Several ("compare Citi and BofA"): rank each
            # report separately and take turns, so one bank cannot crowd out the other.
            per = {doc: [i for i in order if ids[i].split("#")[0] == doc] for doc in sorted(wanted)}
            order = [i for group in zip(*per.values()) for i in group]
        return [(ids[i], float(s[i])) for i in order[:k]]


class BM25(Retriever):
    def __init__(self, **kw):
        super().__init__(**kw)
        from rank_bm25 import BM25Okapi
        pages = load_pages()
        self.ids = [p["page_id"] for p in pages]
        self.bm25 = BM25Okapi([tokens(p["text"]) for p in pages])

    def scores(self, query):
        return self.ids, np.asarray(self.bm25.get_scores(tokens(query)))


class Dense(Retriever):
    """MiniLM reads at most 256 tokens, and a 10-K page holds 500-1,500 words. So each page is cut
    into 200-word windows and scored by its best window."""

    def __init__(self, **kw):
        super().__init__(**kw)
        import torch
        from transformers import AutoModel, AutoTokenizer
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(DENSE_MODEL)
        self.model = AutoModel.from_pretrained(DENSE_MODEL).eval()
        path = os.path.join(DATA, "dense.npz")
        if not os.path.exists(path):
            self.build(path)
        z = np.load(path)
        self.vecs, self.owner, self.ids = z["vecs"], z["owner"], [str(x) for x in z["ids"]]

    def embed(self, texts):
        with self.torch.no_grad():
            b = self.tok(texts, padding=True, truncation=True, max_length=256, return_tensors="pt")
            h = self.model(**b).last_hidden_state
            m = b["attention_mask"].unsqueeze(-1).float()
            v = (h * m).sum(1) / m.sum(1)
            return self.torch.nn.functional.normalize(v, dim=-1).numpy()

    def build(self, path):
        pages = load_pages()
        windows, owner = [], []
        for i, p in enumerate(pages):
            words = p["text"].split() or [""]
            for s in range(0, len(words), 150):
                windows.append(" ".join(words[s : s + 200]))
                owner.append(i)
                if s + 200 >= len(words):
                    break
        vecs = np.concatenate([self.embed(windows[i : i + 64]) for i in range(0, len(windows), 64)])
        np.savez(path, vecs=vecs.astype(np.float16), owner=np.array(owner), ids=np.array([p["page_id"] for p in pages]))
        print(f"dense index: {len(windows):,} windows for {len(pages):,} pages")

    def scores(self, query):
        sim = self.vecs.astype(np.float32) @ self.embed([query])[0]
        best = np.full(len(self.ids), -1.0)
        np.maximum.at(best, self.owner, sim)
        return self.ids, best


def maxsim(q, vecs, offsets):
    """Late interaction. q: (query tokens, 128). vecs: all page patches stacked (N, 128).
    For each page and each query token, keep the best-matching patch; sum over query tokens."""
    sim = vecs @ q.T                                   # (N patches, query tokens)
    best = np.maximum.reduceat(sim, offsets[:-1], axis=0)  # (pages, query tokens)
    return best.sum(axis=1)


class Vision(Retriever):
    """index: a folder under data/ written by vision_index.py (or compress.py)."""

    def __init__(self, index=f"vision_{VISION_EDGE}", **kw):
        super().__init__(**kw)
        from vision_index import load
        folder = os.path.join(DATA, index)
        self.model, self.proc, self.dev = load(VISION_EDGE)  # queries are text: the page edge does not matter
        self.ids = json.load(open(os.path.join(folder, "page_ids.json")))
        self.vecs = np.load(os.path.join(folder, "vectors.npy")).astype(np.float32)
        self.offsets = np.load(os.path.join(folder, "offsets.npy"))

    def embed_query(self, query):
        import torch
        with torch.no_grad():
            b = self.proc.process_queries([query]).to(self.dev)
            e = self.model(**b)[0]
            return e[b["attention_mask"][0].bool()].float().cpu().numpy()

    def scores(self, query):
        return self.ids, maxsim(self.embed_query(query), self.vecs, self.offsets)


def rrf(rankings, k=60):
    """Reciprocal rank fusion: a page scores sum(1 / (k + rank)) over the lists it appears in."""
    fused = {}
    for ranking in rankings:
        for rank, (pid, _) in enumerate(ranking):
            fused[pid] = fused.get(pid, 0.0) + 1.0 / (k + rank + 1)
    return sorted(fused.items(), key=lambda x: -x[1])


class Hybrid(Retriever):
    def __init__(self, parts, **kw):
        super().__init__(**kw)
        self.parts = parts

    def search(self, query, k=10):
        return rrf([p.search(query, k=50) for p in self.parts])[:k]


def make(name, filter_companies=False, index=f"vision_{VISION_EDGE}"):
    kw = {"filter_companies": filter_companies}
    if name == "bm25":
        return BM25(**kw)
    if name == "dense":
        return Dense(**kw)
    if name == "vision":
        return Vision(index=index, **kw)
    if name == "hybrid":
        return Hybrid([BM25(**kw), Vision(index=index, **kw)], **kw)
    raise ValueError(name)
