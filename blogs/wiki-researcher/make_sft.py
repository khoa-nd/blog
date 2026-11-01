"""Step 3a: build SFT data by rejection sampling (STaR).

The base model tries each train question several times in the harness. We keep the
shortest attempt that searched at least once and got the answer right.

python make_sft.py --questions 1500 --tries 4
"""
import argparse
import asyncio
import json

import tinker

from config import MODEL, PRICE_PREFILL, PRICE_SAMPLE
from harness import TinkerPolicy, run_episode
from search import Searcher


async def main(args):
    items = [json.loads(line) for line in open("data/train.jsonl")][: args.questions]
    service = tinker.ServiceClient()
    client = await (service.create_sampling_client_async(model_path=args.model_path) if args.model_path
                    else service.create_sampling_client_async(base_model=MODEL))
    policy, searcher = TinkerPolicy(client), Searcher()
    gate = asyncio.Semaphore(64)
    kept, solved, usd, done = [], 0, 0.0, 0

    async def attempt(item):
        async with gate:
            return await run_episode(policy, searcher, item, temperature=args.temperature)

    async def one(item):
        nonlocal solved, usd, done
        episodes = await asyncio.gather(*(attempt(item) for _ in range(args.tries)))
        usd += sum(e.prefill * PRICE_PREFILL + e.generated * PRICE_SAMPLE for e in episodes) / 1e6
        good = [e for e in episodes if e.reward >= args.min_f1 and e.searches]
        solved += any(e.reward >= args.min_f1 for e in episodes)
        if good:
            best = min(good, key=lambda e: len(e.tokens))
            kept.append({"id": best.id, "question": best.question, "answers": best.answers,
                         "prompt": best.prompt, "tokens": best.tokens, "sampled": best.sampled,
                         "searches": best.searches, "reward": best.reward})
        done += 1
        if done % 100 == 0:
            print(f"  {done}/{len(items)}  kept {len(kept)}  ${usd:.2f}", flush=True)

    await asyncio.gather(*(one(item) for item in items))
    with open(args.out, "w") as f:
        for row in kept:
            f.write(json.dumps(row) + "\n")
    print(f"\nkept {len(kept)}/{len(items)} questions  |  solved@{args.tries} {solved / len(items):.1%}  |  "
          f"avg searches {sum(len(r['searches']) for r in kept) / max(len(kept), 1):.2f}  |  ${usd:.2f}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--questions", type=int, default=1500)
    p.add_argument("--tries", type=int, default=4)
    p.add_argument("--temperature", type=float, default=0.8)
    p.add_argument("--min-f1", type=float, default=0.8)
    p.add_argument("--model-path", help="sample from a checkpoint instead of the base model")
    p.add_argument("--out", default="data/sft.jsonl")
    asyncio.run(main(p.parse_args()))
