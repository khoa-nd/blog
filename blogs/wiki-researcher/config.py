"""Shared settings. Every script imports from here, so change a value once."""

MODEL = "Qwen/Qwen3.5-4B"          # Tinker ID of the model we post-train
LOCAL_MODEL = "Qwen/Qwen3.5-0.8B"  # same chat template; runs free on a laptop or Colab

# Tinker prices for MODEL in USD per 1M tokens (tinker-docs Models & Pricing, 2026-11-01).
PRICE_PREFILL = 0.33
PRICE_SAMPLE = 1.005
PRICE_TRAIN = 0.737

TOP_K = 3           # paragraphs returned by one search
MAX_SEARCHES = 5    # research budget: after this many searches the model must answer
MAX_TOKENS = 512    # max tokens the model may write in one turn
LORA_RANK = 32
