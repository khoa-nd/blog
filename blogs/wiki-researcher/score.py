"""Exact Match and F1, normalized the way SQuAD and HotpotQA do it."""
import re
import string
from collections import Counter


def normalize(text):
    text = text.lower()
    text = "".join(ch for ch in text if ch not in set(string.punctuation))
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    return " ".join(text.split())


def exact_match(prediction, answers):
    return float(any(normalize(prediction) == normalize(a) for a in answers))


def f1(prediction, answers):
    best = 0.0
    for answer in answers:
        pred, gold = normalize(prediction).split(), normalize(answer).split()
        # yes/no/noanswer must match exactly, as in the official HotpotQA script
        if {" ".join(pred), " ".join(gold)} & {"yes", "no", "noanswer"} and pred != gold:
            continue
        common = sum((Counter(pred) & Counter(gold)).values())
        if common == 0:
            continue
        precision, recall = common / len(pred), common / len(gold)
        best = max(best, 2 * precision * recall / (precision + recall))
    return best
