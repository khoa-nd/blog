"""Step 4: online GRPO in the agent harness.

Each step: take Q new train questions, run G episodes per question with the current
weights, reward = F1, advantage = reward - mean reward of the same question's group.
Groups where every episode scored the same teach nothing and are skipped.

python train_grpo.py --init-state tinker://.../sft-e2-state --steps 30
"""
import argparse
import asyncio
import json
import os

import tinker

from config import LORA_RANK, MODEL, PRICE_PREFILL, PRICE_SAMPLE, PRICE_TRAIN
from datums import rl_datum
from harness import TinkerPolicy, run_episode
from search import Searcher


async def main(args):
    service = tinker.ServiceClient()
    if args.init_state:
        trainer = await service.create_training_client_from_state_async(args.init_state)
    else:
        trainer = await service.create_lora_training_client_async(base_model=MODEL, rank=LORA_RANK)
    items = [json.loads(line) for line in open("data/train.jsonl")][args.offset :]
    searcher, gate = Searcher(), asyncio.Semaphore(128)
    os.makedirs(f"runs/{args.name}", exist_ok=True)
    spent = 0.0

    for step in range(1, args.steps + 1):
        policy = TinkerPolicy(await trainer.save_weights_and_get_sampling_client_async())
        batch = items[(step - 1) * args.questions : step * args.questions]

        async def attempt(item):
            async with gate:
                return await run_episode(policy, searcher, item, temperature=args.temperature)

        groups = await asyncio.gather(*(asyncio.gather(*(attempt(it) for _ in range(args.group)))
                                        for it in batch))
        data, skipped = [], 0
        for group in groups:
            rewards = [e.reward for e in group]
            if max(rewards) - min(rewards) < 1e-6:
                skipped += 1
                continue
            mean = sum(rewards) / len(rewards)
            data += [rl_datum(e, e.reward - mean) for e in group]

        if data:
            fwd = await trainer.forward_backward_async(data, "importance_sampling")
            opt = await trainer.optim_step_async(tinker.AdamParams(learning_rate=args.lr))
            await fwd.result_async()
            await opt.result_async()

        episodes = [e for g in groups for e in g]
        spent += sum(e.prefill * PRICE_PREFILL + e.generated * PRICE_SAMPLE for e in episodes) / 1e6
        spent += sum(d.model_input.length for d in data) * PRICE_TRAIN / 1e6
        log = {"step": step, "reward": sum(e.reward for e in episodes) / len(episodes),
               "skipped_groups": skipped / len(groups),
               "searches": sum(len(e.searches) for e in episodes) / len(episodes),
               "answered": sum(e.end == "answer" for e in episodes) / len(episodes),
               "budget_hit": sum(e.end in ("budget", "length") for e in episodes) / len(episodes),
               "tokens": sum(len(e.tokens) for e in episodes) / len(episodes), "usd": round(spent, 2)}
        print("  ".join(f"{k} {v:.3f}" if isinstance(v, float) else f"{k} {v}" for k, v in log.items()), flush=True)
        with open(f"runs/{args.name}/train_log.jsonl", "a") as f:
            f.write(json.dumps(log) + "\n")

        if step % args.save_every == 0 or step == args.steps:
            name = f"{args.name}-s{step}"
            sampler = await (await trainer.save_weights_for_sampler_async(name=name)).result_async()
            state = await (await trainer.save_state_async(name=name + "-state")).result_async()
            print(f"saved {name}\n  sampler: {sampler.path}\n  state:   {state.path}")
            with open("runs/checkpoints.jsonl", "a") as f:
                f.write(json.dumps({"name": name, "sampler": sampler.path, "state": state.path}) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--init-state", help="tinker:// state path from train_sft.py; omit to start from the base model")
    p.add_argument("--name", default="grpo")
    p.add_argument("--steps", type=int, default=30)
    p.add_argument("--questions", type=int, default=32, help="questions per step")
    p.add_argument("--group", type=int, default=8, help="episodes per question")
    p.add_argument("--lr", type=float, default=4e-5)
    p.add_argument("--temperature", type=float, default=1.0)
    p.add_argument("--offset", type=int, default=1500, help="skip the questions used for SFT")
    p.add_argument("--save-every", type=int, default=10)
    asyncio.run(main(p.parse_args()))
