"""Every AI job Alexandria runs: its instructions, its JSON schema, and an offline fake.

The fake answers let the whole pipeline run with no API key (python -m alexandria nightly --fake).
Schemas follow the strictest provider rules (Claude structured outputs): every object lists all
its properties as required and sets additionalProperties to false.
"""
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Callable


def obj(**props):
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


STR = {"type": "string"}
NUM = {"type": "number"}
INT = {"type": "integer"}


def arr(item):
    return {"type": "array", "items": item}


@dataclass
class Task:
    system: str
    schema: dict
    fake: Callable[[dict], dict]

    def prompt(self, data):
        return (f"Input:\n{json.dumps(data, ensure_ascii=False, indent=1)}\n\n"
                f"Reply with JSON only, matching this JSON schema:\n{json.dumps(self.schema)}")


def _h(text, mod):
    return int(hashlib.sha256(text.encode()).hexdigest(), 16) % mod


def _fake_extract(d):
    first = d["text"].strip().split("\n")[0][:120]
    return {"is_book": True, "title": first, "authors": [], "isbn13": "", "description": "", "price": 0, "currency": ""}


def _fake_judge(d):
    return {"scores": [{"id": b["id"], "fit": 5 + _h(b["title"], 5), "depth": 6, "readability": 7,
                        "reason": f"Fake judge: {b['title']} fits {d['facet']}."} for b in d["books"]]}


def _fake_digest(d):
    """Quotes up to two sentences from each piece of evidence, citing it: no model, but a valid digest."""
    sentences = []
    for e in d["evidence"]:
        parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", e["excerpt"]) if len(p.strip()) > 20][:2]
        parts = parts or ([e["excerpt"].strip()] if e["excerpt"].strip() else [])
        sentences += [{"text": f"{e['source']}: {p[:200]}", "evidence_ids": [e["id"]]} for p in parts]
    return {"sentences": sentences[:4], "who_for": "Readers who like narrative history of ideas.",
            "math_level": "light", "red_flags": []}


def _fake_write(d):
    return {"why_you": f"It sits in your '{d['facet']}' taste, and readers rate it well.",
            "intro": (d["book"].get("description") or d["book"]["title"])[:280]}


def _fake_parse_comment(d):
    text = d["comment"].lower()
    sentiment = 0.6 if any(w in text for w in ("great", "love", "loved", "good", "hay")) else 0.0
    if any(w in text for w in ("boring", "too ", "not for", "chán")):
        sentiment -= 0.6
    return {"sentiment": max(-1.0, min(1.0, sentiment)), "aspects": [], "taste_suggestion": ""}


def _fake_parse_taste(d):
    words = [w for w in d["text"].lower().replace(",", " ").split() if len(w) > 3][:4]
    return {"slug": "-".join(words[:2]) or "new-taste", "name": d["text"][:60], "priority": 0.6,
            "keywords": words, "status": "active"}


def _fake_reflect(d):
    return {"profile_text": f"Fake reflection over {len(d['week'])} reactions.", "changes": []}


TASKS = {
    "extract": Task(
        "You read a web page from a bookstore or publisher and pull out the book it sells. "
        "If the page is not about one book, set is_book to false. Use empty strings and 0 for unknown fields. "
        "isbn13 must be 13 digits or empty.",
        obj(is_book={"type": "boolean"}, title=STR, authors=arr(STR), isbn13=STR, description=STR, price=NUM, currency=STR),
        _fake_extract),
    "judge": Task(
        "You choose books for one reader. Score each book against the reader's profile and today's taste facet: "
        "fit (0-10, how well it matches the facet and profile), depth (0-10), readability (0-10), and one short reason. "
        "Score every book in the input, using its id.",
        obj(scores=arr(obj(id=INT, fit=INT, depth=INT, readability=INT, reason=STR))),
        _fake_judge),
    "digest": Task(
        "You summarize what readers and critics say about a book, using only the evidence given. "
        "Write 3 to 5 short sentences: consensus, strengths, common criticisms. Every sentence must cite the ids of "
        "the evidence it comes from in evidence_ids. Never invent ratings, quotes or facts. Also say who the book is "
        "for, how much math it assumes (none, light, moderate, heavy), and any red flags (dated science, disputed claims).",
        obj(sentences=arr(obj(text=STR, evidence_ids=arr(INT))), who_for=STR,
            math_level={"type": "string", "enum": ["none", "light", "moderate", "heavy"]}, red_flags=arr(STR)),
        _fake_digest),
    "write": Task(
        "You write the top of a daily book page for one reader, in plain English. why_you: one sentence tying the "
        "book to the reader's taste. intro: two or three sentences introducing the book, using only the input.",
        obj(why_you=STR, intro=STR),
        _fake_write),
    "parse_comment": Task(
        "You read the reader's comment on a recommended book. sentiment: -1 (hated) to 1 (loved). aspects: what the "
        "comment praises (+) or criticizes (-), e.g. 'narrative', 'math density', 'length'. taste_suggestion: a short "
        "suggested change to the reader's taste profile, or empty if none.",
        obj(sentiment=NUM, aspects=arr(obj(name=STR, polarity={"type": "string", "enum": ["+", "-"]})), taste_suggestion=STR),
        _fake_parse_comment),
    "parse_taste": Task(
        "You turn the reader's free-text request into one change to their taste facets. Reuse an existing slug when "
        "the request adjusts an existing facet; otherwise invent a short kebab-case slug. priority is 0 to 1. "
        "keywords are 3 to 10 words or phrases that would appear in a matching book's description.",
        obj(slug=STR, name=STR, priority=NUM, keywords=arr(STR), status={"type": "string", "enum": ["active", "paused"]}),
        _fake_parse_taste),
    "reflect": Task(
        "You read one week of the reader's reactions to recommended books and propose an updated taste profile. "
        "profile_text: 3 to 5 plain sentences describing what they like and dislike. changes: priority changes "
        "for existing facet slugs only, each with a short reason. Propose nothing when the evidence is thin.",
        obj(profile_text=STR, changes=arr(obj(slug=STR, priority=NUM, reason=STR))),
        _fake_reflect),
}
