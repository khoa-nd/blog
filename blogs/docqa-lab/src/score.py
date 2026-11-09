"""The yardstick. Retrieval metrics against human-labeled pages, and answer checks that need no judge model.

gold is {page_id: 1 or 2}: 2 = the page holds the full answer, 1 = it holds a required piece.
"""
import math
import re
import string
from collections import Counter


def ndcg(ranked, gold, k=5):
    dcg = sum(gold.get(p, 0) / math.log2(i + 2) for i, p in enumerate(ranked[:k]))
    ideal = sorted(gold.values(), reverse=True)[:k]
    idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def recall(ranked, gold, k=5):
    return len(set(ranked[:k]) & set(gold)) / len(gold) if gold else 0.0


def hit(ranked, gold, k=5):
    """1 if any page in the top k is labeled relevant: the minimum an answerer needs."""
    return float(any(p in gold for p in ranked[:k]))


def mrr(ranked, gold):
    for i, p in enumerate(ranked):
        if p in gold:
            return 1.0 / (i + 1)
    return 0.0


# ---- answers --------------------------------------------------------------

def yes_no(text):
    first = re.sub(r"[^a-z]", " ", text.lower()).split()[:1]
    return first[0] if first and first[0] in ("yes", "no") else None


NUM = re.compile(r"(?<![\w.])[-−]?\$?\(?\d[\d,]*(?:\.\d+)?\)?(?:\s*(?:%|percent|billion|million|thousand|bn|mm))?", re.I)
SCALE = {"billion": 1e9, "bn": 1e9, "million": 1e6, "mm": 1e6, "thousand": 1e3}


def numbers(text):
    """Every number in the text as a float, with its scale word applied. Years are left out:
    they are usually restated from the question, so matching them proves nothing."""
    out = []
    for m in NUM.finditer(text.replace("−", "-")):
        raw = m.group(0).lower()
        digits = re.sub(r"[^\d.]", "", raw.split()[0] if " " in raw else raw.rstrip("%"))
        digits = re.sub(r"[a-z%]", "", digits)
        if not digits or digits == ".":
            continue
        value = float(digits)
        if re.fullmatch(r"(19|20)\d\d", digits):
            continue
        for word, mult in SCALE.items():
            if raw.endswith(word):
                value *= mult
        out.append(value)
    return out


def same_number(a, b, tol=0.01):
    """Equal within 1%, also across a unit shift (18.8 billion vs 18,841 million vs 18,841)."""
    for scale in (1, 1e3, 1e6, 1e9, 1e-3, 1e-6, 1e-9):
        x = a * scale
        if abs(x - b) <= tol * max(abs(b), 1e-9):
            return True
    return False


def number_recall(pred, gold_answer):
    """Share of the gold answer's numbers that appear in the prediction. None if gold has none."""
    g = numbers(gold_answer)
    if not g:
        return None
    p = numbers(pred)
    return sum(any(same_number(x, y) for x in p) for y in g) / len(g)


def normalize(text):
    text = text.lower()
    text = "".join(ch for ch in text if ch not in string.punctuation)
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    return text.split()


def token_f1(pred, gold):
    p, g = normalize(pred), normalize(gold)
    common = sum((Counter(p) & Counter(g)).values())
    if not common:
        return 0.0
    precision, rec = common / len(p), common / len(g)
    return 2 * precision * rec / (precision + rec)


def citation_precision(cited, gold):
    """Share of the pages the answer cites that humans marked relevant. None if nothing was cited."""
    return sum(c in gold for c in cited) / len(cited) if cited else None
