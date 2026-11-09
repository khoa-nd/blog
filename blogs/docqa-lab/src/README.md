# 10-K Lens

Ask questions about six 2024 bank 10-K reports (2,942 pages) and get answers that cite their
pages and highlight the evidence. Built step by step in the hands-on tutorial:
https://nguyendangkhoa.info/blogs/hands-on-multimodal-document-qa-vision-first-rag.html

## Quick start

```bash
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -r requirements.txt
python prep_data.py                      # PDFs, questions, page text, val/test split
python -m unittest test_score test_search test_answer
python eval_retrieval.py --retriever bm25 --name bm25 --filter
python vision_index.py --edge 1024       # ~50 min on an M1; resumable
python eval_retrieval.py --retriever hybrid --name hybrid --filter
uvicorn app:app --port 8000              # then open http://localhost:8000
```

## Files

| File | Step | What it does |
|---|---|---|
| `config.py` | 0 | Every setting in one place |
| `prep_data.py` | 1 | Download the 10-Ks and the ViDoRe v3 questions; page text; val/test split + hash |
| `score.py`, `test_score.py` | 1 | nDCG@5, Recall@5, Hit@3, MRR; answer checks with no judge model |
| `search.py` | 2-3 | BM25, dense, vision (MaxSim), hybrid (RRF), company filter |
| `eval_retrieval.py`, `show.py` | 2-3 | Score a retriever by content type; read the misses |
| `vision_index.py`, `compress.py` | 3 | Late-interaction page index; prune or pool it |
| `answer.py`, `highlight.py` | 4 | Answer from pages (local Qwen3.5 or Claude); highlight the evidence |
| `eval_answers.py`, `ablate.py` | 4-5 | End-to-end answer scores; paired bootstrap confidence intervals |
| `scan_experiment.py` | 5 | Turn one report into a scan: OCR text search vs vision |
| `app.py`, `static/index.html` | 6 | API + web viewer, with a question log and feedback |
| `ingest.py`, `ocr_demo.py`, `label.py` | 2, 6 | Add your own PDFs (OCR for scans); see OCR on one page; build your own gold set |

## Data

ViDoRe v3 Finance (EN), `vidore/vidore_v3_finance_en` on Hugging Face: annotations CC BY 4.0;
the 10-K filings are public SEC documents. Record your `test.jsonl` hash here: `55f73d8c9557afa0`.
