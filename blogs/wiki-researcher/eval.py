"""Run the agent on a split, score every answer, write runs/<name>/.

python eval.py --name base                          base model on Tinker, val split
python eval.py --name closed --closed-book          no search: the floor
python eval.py --name sft-e2 --model-path tinker://...   one of your checkpoints
python eval.py --name local --local --limit 10      free, on your own machine
"""
import argparse
import asyncio
import json
import os
import time

from config import LOCAL_MODEL, MAX_SEARCHES, MODEL, PRICE_PREFILL, PRICE_SAMPLE, TOP_K
from harness import LocalPolicy, TinkerPolicy, run_episode
from score import exact_match, f1


async def make_policy(args):
    if args.local:
        return LocalPolicy(LOCAL_MODEL)
    import tinker
    service = tinker.ServiceClient()
    if args.model_path:
        return TinkerPolicy(await service.create_sampling_client_async(model_path=args.model_path))
    return TinkerPolicy(await service.create_sampling_client_async(base_model=MODEL))


def cost(ep):
    return (ep.prefill * PRICE_PREFILL + ep.generated * PRICE_SAMPLE) / 1e6


def record(ep, tokenizer, free=False):
    return {"id": ep.id, "question": ep.question, "answers": ep.answers, "prediction": ep.answer,
            "em": exact_match(ep.answer, ep.answers), "f1": f1(ep.answer, ep.answers),
            "searches": ep.searches, "end": ep.end, "prefill": ep.prefill,
            "generated": ep.generated, "usd": 0.0 if free else cost(ep),
            "trace": tokenizer.decode(ep.tokens, skip_special_tokens=False)}


def summarize(rows):
    n = len(rows)
    mean = lambda key: sum(r[key] for r in rows) / n
    return {"n": n, "em": mean("em"), "f1": mean("f1"),
            "searches": sum(len(r["searches"]) for r in rows) / n,
            "answered": sum(r["end"] == "answer" for r in rows) / n,
            "usd_per_q": mean("usd"), "usd_total": sum(r["usd"] for r in rows)}


async def main(args):
    items = [json.loads(line) for line in open(f"data/{args.split}.jsonl")][: args.limit]
    policy = await make_policy(args)
    searcher = None
    if not args.closed_book:
        from search import Searcher  # built in Step 2
        searcher = Searcher()
    gate = asyncio.Semaphore(1 if args.local else args.concurrency)
    out_dir = f"runs/{args.name}"
    os.makedirs(out_dir, exist_ok=True)
    started, rows = time.time(), []

    async def one(item):
        async with gate:
            ep = await run_episode(policy, searcher, item, temperature=0.0, closed_book=args.closed_book,
                                   top_k=args.top_k, max_searches=args.max_searches)
        rows.append(record(ep, policy.tokenizer, free=args.local))
        if len(rows) % 25 == 0 or args.local:
            print(f"  {len(rows)}/{len(items)}  F1 so far {summarize(rows)['f1']:.3f}", flush=True)

    await asyncio.gather(*(one(item) for item in items))
    rows.sort(key=lambda r: r["id"])
    with open(f"{out_dir}/episodes.jsonl", "w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = summarize(rows) | {"split": args.split, "model_path": args.model_path or MODEL,
                                 "top_k": args.top_k, "max_searches": args.max_searches,
                                 "seconds": round(time.time() - started)}
    json.dump(summary, open(f"{out_dir}/summary.json", "w"), indent=2)
    print(f"\n{args.name}: EM {summary['em']:.3f}  F1 {summary['f1']:.3f}  "
          f"searches {summary['searches']:.2f}  answered {summary['answered']:.0%}  "
          f"${summary['usd_per_q']:.4f}/q  (total ${summary['usd_total']:.2f}, {summary['seconds']}s)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    p.add_argument("--split", default="val", choices=["val", "test", "train"])
    p.add_argument("--model-path", help="tinker://... checkpoint; default is the base model")
    p.add_argument("--local", action="store_true", help="run LOCAL_MODEL with transformers")
    p.add_argument("--closed-book", action="store_true")
    p.add_argument("--limit", type=int)
    p.add_argument("--top-k", type=int, default=TOP_K)
    p.add_argument("--max-searches", type=int, default=MAX_SEARCHES)
    p.add_argument("--concurrency", type=int, default=32)
    asyncio.run(main(p.parse_args()))
