"""Step 8: serve it. One process holds the index and the answerer; a small web page asks questions,
shows the answer, and opens each cited page with the evidence highlighted.

    DOCQA_RETRIEVER=hybrid DOCQA_ANSWERER=claude uvicorn app:app --port 8000
    open http://localhost:8000

Every question is logged to runs/app_log.jsonl with its pages, answer, timing, cost and the
reader's feedback: that file is your production eval set in waiting (Step 10).
"""
import io
import json
import os
import time
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from answer import make as make_answerer
from config import RUNS, TOP_K
from highlight import evidence_image
from search import load_pages, make as make_retriever
from vision_index import render

RETRIEVER = os.environ.get("DOCQA_RETRIEVER", "bm25")
ANSWERER = os.environ.get("DOCQA_ANSWERER", "local")
INPUT = os.environ.get("DOCQA_INPUT", "text")
LOG = os.path.join(RUNS, "app_log.jsonl")

app = FastAPI(title="10-K Lens")
pages = {p["page_id"]: p for p in load_pages()}
retriever = make_retriever(RETRIEVER, filter_companies=True)
answerer = make_answerer(ANSWERER)
os.makedirs(RUNS, exist_ok=True)


class Ask(BaseModel):
    question: str


class Feedback(BaseModel):
    id: str
    helpful: bool
    note: str = ""


@app.get("/")
def index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


@app.post("/api/ask")
def ask(req: Ask):
    if not req.question.strip():
        raise HTTPException(400, "Type a question first.")
    t0 = time.time()
    hits = retriever.search(req.question, k=TOP_K)
    ids = [pid for pid, _ in hits]
    t1 = time.time()
    if INPUT == "image":
        res = answerer.answer(req.question, ids, images=[render(pages[p]["doc"], pages[p]["page"]) for p in ids])
    else:
        res = answerer.answer(req.question, ids, texts=[pages[p]["text"][:6000] for p in ids])
    record = {"id": uuid.uuid4().hex[:12], "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "question": req.question,
              "pages": ids, "answer": res["answer"], "citations": res["citations"], "quote": res["quote"],
              "retrieve_ms": round((t1 - t0) * 1000), "answer_ms": round((time.time() - t1) * 1000),
              "usd": res["usd"], "retriever": RETRIEVER, "answerer": ANSWERER, "input": INPUT}
    with open(LOG, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


@app.get("/api/page/{page_id}.png")
def page_image(page_id: str, quote: str = "", answer: str = ""):
    if page_id not in pages:
        raise HTTPException(404, f"No page {page_id}")
    img, _, _ = evidence_image(page_id, quote, answer)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png")


@app.post("/api/feedback")
def feedback(fb: Feedback):
    with open(LOG, "a") as f:
        f.write(json.dumps({"feedback_for": fb.id, "helpful": fb.helpful, "note": fb.note}) + "\n")
    return {"ok": True}
