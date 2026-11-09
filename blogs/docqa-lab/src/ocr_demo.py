"""Turn a real 10-K page into a picture (a 'scan'), then read it back with OCR."""
import time

import pymupdf

from ingest import page_text

src = pymupdf.open("data/pdfs/jpmorgan_chase_2024.pdf")[107]          # page 108
scan = pymupdf.open()
page = scan.new_page(width=src.rect.width, height=src.rect.height)
page.insert_image(page.rect, pixmap=src.get_pixmap(dpi=150))          # pixels only, no text layer
scan.save("scanned_page.pdf")

page = pymupdf.open("scanned_page.pdf")[0]
print("text layer characters:", len(page.get_text().strip()))
t = time.time()
text, used_ocr = page_text(page, "eng")
print(f"OCR used: {used_ocr} | {time.time() - t:.1f}s | characters: {len(text)} | finds '18,841': {'18,841' in text}")
i = text.find("Aggregate")
print("text around the table row:", " | ".join(text[i : i + 130].split("\n")))
