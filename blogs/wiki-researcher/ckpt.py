"""Print a checkpoint path saved in runs/checkpoints.jsonl.

python ckpt.py sft-e2          sampler path, for eval.py --model-path
python ckpt.py sft-e2 state    state path, for train_grpo.py --init-state
"""
import json
import sys

name, kind = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "sampler"
paths = [json.loads(line)[kind] for line in open("runs/checkpoints.jsonl") if json.loads(line)["name"] == name]
if not paths:
    sys.exit(f"no checkpoint named {name} in runs/checkpoints.jsonl")
print(paths[-1])
