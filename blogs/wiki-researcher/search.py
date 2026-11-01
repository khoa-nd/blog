"""BM25 search over the paragraph corpus.

python search.py                      build the index into data/bm25 (once, ~2 min)
python search.py "Ed Wood director"   try a query
"""
import json
import sys

import bm25s
import Stemmer

INDEX = "data/bm25"
stemmer = Stemmer.Stemmer("english")


def build():
    corpus = [json.loads(line) for line in open("data/corpus.jsonl")]
    texts = [f"{doc['title']}. {doc['text']}" for doc in corpus]
    index = bm25s.BM25()
    index.index(bm25s.tokenize(texts, stopwords="en", stemmer=stemmer))
    index.save(INDEX, corpus=corpus)
    print(f"indexed {len(corpus):,} paragraphs into {INDEX}")


class Searcher:
    def __init__(self):
        self.index = bm25s.BM25.load(INDEX, load_corpus=True)

    def search(self, query, k=3):
        tokens = bm25s.tokenize([query], stopwords="en", stemmer=stemmer, show_progress=False)
        if not tokens.ids[0]:  # the query was only stopwords
            return []
        docs, _ = self.index.retrieve(tokens, k=k, show_progress=False)
        return list(docs[0])


if __name__ == "__main__":
    if len(sys.argv) == 1:
        build()
    else:
        for doc in Searcher().search(" ".join(sys.argv[1:])):
            print(f"[{doc['title']}] {doc['text'][:200]}\n")
