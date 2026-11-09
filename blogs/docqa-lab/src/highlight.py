"""Step 6: show the evidence. Find the answer's quote (or its numbers) on the cited page and draw boxes.

A reviewer should never have to trust the answer: one click shows the highlighted line on the
real page. Born-digital PDFs carry exact word positions, so this costs no model call.

    python highlight.py jpmorgan_chase_2024#108 "18,841" --out evidence.png
"""
import argparse
import os
import re

import pymupdf
from PIL import Image, ImageDraw

from config import PDF_DIR, RENDER_DPI


def find_boxes(page, quote, answer=""):
    """Rectangles (PDF points) for the quote, plus every number from the answer found on the page."""
    quote = " ".join(quote.split())
    found = []
    if len(quote) >= 4:
        # Try the quote as given, then with the PDF's curly apostrophe, then its first six words
        # (a long quote often differs from the page by one word).
        rects = []
        for q in (quote, quote.replace("'", "\u2019"), " ".join(quote.split()[:6])):
            rects = page.search_for(q)
            if rects:
                break
        if rects:
            found.append(("quote", rects))
    nums = []
    for num in re.findall(r"\d[\d,]*\.?\d*", answer):
        num = num.rstrip(".,")
        if len(num.replace(",", "")) >= 2 and not re.fullmatch(r"(19|20)\d\d", num):
            nums += page.search_for(num)
    if nums:
        found.append(("numbers", nums))
    return [r for _, rs in found for r in rs], "+".join(k for k, _ in found) or "none"


def evidence_image(page_id, quote, answer="", dpi=RENDER_DPI):
    doc, number = page_id.split("#")
    page = pymupdf.open(os.path.join(PDF_DIR, f"{doc}.pdf"))[int(number) - 1]
    rects, how = find_boxes(page, quote, answer)
    pix = page.get_pixmap(dpi=dpi)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGBA")
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    k = dpi / 72  # PDF points -> pixels
    for r in rects:
        box = [r.x0 * k - 3, r.y0 * k - 2, r.x1 * k + 3, r.y1 * k + 2]
        draw.rectangle(box, fill=(255, 214, 10, 90), outline=(214, 120, 0, 255), width=2)
    return Image.alpha_composite(img, layer).convert("RGB"), len(rects), how


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("page_id")
    p.add_argument("quote")
    p.add_argument("--answer", default="")
    p.add_argument("--out", default="evidence.png")
    a = p.parse_args()
    img, n, how = evidence_image(a.page_id, a.quote, a.answer)
    img.save(a.out)
    print(f"{n} box(es) found by {how} -> {a.out}")
