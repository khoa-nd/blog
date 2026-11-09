"""Every setting in one place. Scripts import from here, so a change is made once."""
import os

DATA = "data"
PDF_DIR = os.path.join(DATA, "pdfs")
RUNS = "runs"

# Corpus: ViDoRe v3 Finance (English). Six 2024 10-K reports, 2,942 pages, 309 questions
# with human-checked relevant pages. CC BY 4.0 annotations; the 10-Ks are public SEC filings.
DATASET = "vidore/vidore_v3_finance_en"
DATASET_COMMIT = "main"
VAL_SIZE = 100  # the rest is test; the test file is locked by its hash

# Text retrieval
DENSE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Vision retrieval (late interaction). 250M parameters, runs on a laptop.
VISION_MODEL = "ModernVBERT/colmodernvbert"
VISION_EDGE = 1024  # longest edge in pixels before the processor tiles the page; 2048 is the model default
RENDER_DPI = 110    # page image for embedding and for the answerer

# Answering
TOP_K = 3                     # pages handed to the answerer
LOCAL_VLM = "Qwen/Qwen3.5-0.8B"
CLAUDE_MODEL = "claude-opus-5-5"
# Claude Opus 5.5 prices per 1M tokens (Nov 2026). Images are billed as input tokens.
# Trying a cheaper model? claude-haiku-5-5 is $0.10 / $0.50; change both lines and re-run the eval.
PRICE_IN, PRICE_OUT = 4.00, 20.00


def device():
    import torch
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"
