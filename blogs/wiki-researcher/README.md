# wiki-researcher

Post-train Qwen3.5-4B into a Wikipedia research agent on Tinker:
Eval → Harness → SFT → GRPO → Ablation. Full walkthrough:
https://nguyendangkhoa.info/blogs/hands-on-wiki-research-agent-post-training-using-sft-grpo-techniques.html

```bash
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -r requirements.txt
export TINKER_API_KEY=...

python hello_tinker.py                                   # 0  key works
python prep_data.py                                      # 1  data + corpus
python -m unittest test_score
python eval.py --name closed --closed-book               #    floor
python search.py                                         # 2  BM25 index
python -m unittest test_score test_harness
python eval.py --name base && python show.py runs/base   #    real starting point
python make_sft.py --questions 1500 --tries 4            # 3  SFT data
python train_sft.py --epochs 3
for e in 1 2 3; do python eval.py --name sft-e$e --model-path $(python ckpt.py sft-e$e); done
python train_grpo.py --init-state $(python ckpt.py sft-e2 state) --steps 30   # 4
python eval.py --split test --name test-base                                          # 5
python eval.py --split test --name test-sft  --model-path $(python ckpt.py sft-e2)
python eval.py --split test --name test-grpo --model-path $(python ckpt.py grpo-s30)
python ablate.py runs/test-base runs/test-sft runs/test-grpo
```

test.jsonl sha256 (first 16 hex): `cb4ad042f2c0ef38`
