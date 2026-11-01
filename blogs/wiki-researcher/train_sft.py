"""Step 3b: LoRA SFT on Tinker, loss only on tokens the model wrote.

python train_sft.py --epochs 3
Prints a sampler path (for eval.py) and a state path (for train_grpo.py) after each epoch.
"""
import argparse
import asyncio
import json
import os
import random

import tinker

from config import LORA_RANK, MODEL, PRICE_TRAIN
from datums import sft_datum


async def main(args):
    rows = [json.loads(line) for line in open(args.data)]
    data = [sft_datum(r["prompt"], r["tokens"], r["sampled"]) for r in rows]
    tokens_per_epoch = sum(d.model_input.length for d in data)
    print(f"{len(data)} examples, {tokens_per_epoch:,} tokens/epoch, "
          f"≈ ${tokens_per_epoch * args.epochs * PRICE_TRAIN / 1e6:.2f} to train")

    service = tinker.ServiceClient()
    trainer = await service.create_lora_training_client_async(base_model=MODEL, rank=LORA_RANK)
    steps_per_epoch = (len(data) + args.batch - 1) // args.batch
    total, step = steps_per_epoch * args.epochs, 0
    rng = random.Random(0)
    os.makedirs("runs", exist_ok=True)

    for epoch in range(1, args.epochs + 1):
        rng.shuffle(data)
        for i in range(0, len(data), args.batch):
            batch = data[i : i + args.batch]
            lr = args.lr * (1 - step / total)  # linear decay to 0
            fwd = await trainer.forward_backward_async(batch, "cross_entropy")
            opt = await trainer.optim_step_async(tinker.AdamParams(learning_rate=lr))
            result = await fwd.result_async()
            await opt.result_async()
            step += 1
            logprobs = [lp for out in result.loss_fn_outputs for lp in out["logprobs"].tolist()]
            weights = [w for d in batch for w in d.loss_fn_inputs["weights"].tolist()]
            loss = -sum(lp * w for lp, w in zip(logprobs, weights)) / sum(weights)
            if step % 5 == 0 or step == total:
                print(f"epoch {epoch}  step {step}/{total}  loss {loss:.4f}  lr {lr:.2e}", flush=True)

        name = f"{args.name}-e{epoch}"
        sampler = await (await trainer.save_weights_for_sampler_async(name=name)).result_async()
        state = await (await trainer.save_state_async(name=name + "-state")).result_async()
        print(f"saved {name}\n  sampler: {sampler.path}\n  state:   {state.path}")
        with open("runs/checkpoints.jsonl", "a") as f:
            f.write(json.dumps({"name": name, "sampler": sampler.path, "state": state.path}) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="data/sft.jsonl")
    p.add_argument("--name", default="sft")
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch", type=int, default=32)
    p.add_argument("--lr", type=float, default=2e-4)
    asyncio.run(main(p.parse_args()))
