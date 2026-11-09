"""Step 5: read the retrieved pages and answer, citing pages and quoting the evidence.

Two answerers with the same contract: answer(question, pages) -> dict(answer, citations, quote, ...)
  local   Qwen3.5-0.8B on your laptop, free, slow, weak
  claude  Claude through the Anthropic API (set ANTHROPIC_API_KEY), structured JSON output

Pages go in as images (what the capstone teaches) or as their text layer (--input text), so you
can measure which one the answerer reads better.

    python answer.py "Did JPMorganChase execute more than half of its $30 billion buyback?"
"""
import argparse
import base64
import io
import json
import re
import sys
import time

from config import CLAUDE_MODEL, LOCAL_VLM, PRICE_IN, PRICE_OUT, TOP_K, device

INSTRUCTIONS = """You answer questions about company annual reports (10-K filings) using ONLY the pages provided.
Each page starts with a label: P1, P2, P3.
Rules:
- If the pages do not contain the answer, say "Not found in the provided pages."
- Start yes/no questions with "Yes" or "No".
- Keep every number exactly as printed, with its unit (e.g. $18.8 billion, 12.5%).
- Cite the labels of the pages you used (P1, P2, ...).
- quote: copy one short phrase (3-12 words) exactly as it appears on a cited page, the one that best supports the answer."""

LOCAL_FORMAT = """Reply in exactly three lines:
ANSWER: <one to three sentences>
PAGES: <labels of the pages you used, like P1, P2>
QUOTE: <a short phrase copied exactly from one of those pages>"""

SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "string"}},
        "quote": {"type": "string"},
    },
    "required": ["answer", "citations", "quote"],
    "additionalProperties": False,
}


def label(i, page_id):
    """Small models copy ids badly, so pages are labeled P1, P2, ... and mapped back after."""
    doc, page = page_id.split("#")
    return f"P{i + 1} ({doc.replace('_', ' ')}, page {page}):"


def page_text(page_id, pages_by_id):
    return pages_by_id[page_id]["text"][:6000]


def parse_lines(text, allowed):
    def field(name):
        m = re.search(rf"^{name}:\s*(.*)$", text, re.M | re.I)
        return m.group(1).strip() if m else ""

    answer = field("ANSWER") or text.strip().split("\n")[0]
    labels = re.findall(r"\bP(\d+)\b", field("PAGES"))
    cited = [allowed[int(n) - 1] for n in labels if 0 < int(n) <= len(allowed)]
    return {"answer": answer, "citations": list(dict.fromkeys(cited)), "quote": field("QUOTE").strip('"')}


class Local:
    name = "local"

    def __init__(self, model=LOCAL_VLM):
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor
        self.torch, self.dev = torch, device()
        self.proc = AutoProcessor.from_pretrained(model)
        self.model = AutoModelForImageTextToText.from_pretrained(model, dtype=torch.bfloat16).to(self.dev).eval()

    def answer(self, question, page_ids, images=None, texts=None):
        content = []
        for i, pid in enumerate(page_ids):
            content.append({"type": "text", "text": label(i, pid)})
            if images:
                content.append({"type": "image", "image": images[i]})
            else:
                content.append({"type": "text", "text": texts[i]})
        content.append({"type": "text", "text": f"{INSTRUCTIONS}\n\n{LOCAL_FORMAT}\n\nQuestion: {question}"})
        inputs = self.proc.apply_chat_template([{"role": "user", "content": content}], add_generation_prompt=True,
                                               tokenize=True, return_dict=True, return_tensors="pt",
                                               enable_thinking=False).to(self.dev)
        t = time.time()
        with self.torch.no_grad():
            out = self.model.generate(**inputs, max_new_tokens=160, do_sample=False)
        n_in = inputs["input_ids"].shape[1]
        text = self.proc.decode(out[0][n_in:], skip_special_tokens=True)
        return {**parse_lines(text, page_ids), "raw": text, "tokens_in": n_in,
                "tokens_out": int(out.shape[1] - n_in), "seconds": time.time() - t, "usd": 0.0}


class Claude:
    name = "claude"

    def __init__(self, model=CLAUDE_MODEL):
        import anthropic
        self.client, self.model = anthropic.Anthropic(), model

    def answer(self, question, page_ids, images=None, texts=None):
        content = []
        for i, pid in enumerate(page_ids):
            content.append({"type": "text", "text": label(i, pid)})
            if images:
                buf = io.BytesIO()
                images[i].save(buf, format="PNG")
                data = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
                content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}})
            else:
                content.append({"type": "text", "text": texts[i]})
        content.append({"type": "text", "text": f"Question: {question}"})
        t = time.time()
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=2000,
            system=INSTRUCTIONS,
            messages=[{"role": "user", "content": content}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",  # if a safety classifier declines, the API retries on a fallback model
        )
        if response.stop_reason == "refusal":
            data = {"answer": "Refused.", "citations": [], "quote": ""}
        else:
            data = json.loads(next(b.text for b in response.content if b.type == "text"))
        u = response.usage
        cited = [page_ids[int(n) - 1] for c in data["citations"] for n in re.findall(r"\d+", c)[:1] if 0 < int(n) <= len(page_ids)]
        return {**data, "citations": list(dict.fromkeys(cited)),
                "tokens_in": u.input_tokens, "tokens_out": u.output_tokens, "seconds": time.time() - t,
                "usd": (u.input_tokens * PRICE_IN + u.output_tokens * PRICE_OUT) / 1e6}


def make(name):
    return {"local": Local, "claude": Claude}[name]()


def main(args):
    from search import load_pages, make as make_retriever
    from vision_index import render
    retriever = make_retriever(args.retriever, filter_companies=True)
    ids = [pid for pid, _ in retriever.search(args.question, k=args.k)]
    print("pages:", ", ".join(ids), file=sys.stderr)
    by_id = {p["page_id"]: p for p in load_pages()}
    images = [render(by_id[p]["doc"], by_id[p]["page"]) for p in ids] if args.input == "image" else None
    texts = [page_text(p, by_id) for p in ids] if args.input == "text" else None
    result = make(args.answerer).answer(args.question, ids, images=images, texts=texts)
    print(json.dumps({k: v for k, v in result.items() if k != "raw"}, indent=1))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("question")
    p.add_argument("--answerer", default="local", choices=["local", "claude"])
    p.add_argument("--retriever", default="bm25", choices=["bm25", "dense", "vision", "hybrid"])
    p.add_argument("--input", default="image", choices=["image", "text"])
    p.add_argument("--k", type=int, default=TOP_K)
    main(p.parse_args())
