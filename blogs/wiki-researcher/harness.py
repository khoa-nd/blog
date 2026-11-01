"""The agent harness: question -> searches -> answer, recorded token by token.

The same code runs evaluation, collects SFT data and produces RL rollouts, so the
model is trained in exactly the environment it is tested in.
"""
import re
from dataclasses import dataclass, field

from config import MAX_SEARCHES, MAX_TOKENS, TOP_K
from score import f1

SYSTEM = """You are a research agent. You answer questions by searching Wikipedia.

Each reply contains exactly one action:
- To search, write a short query inside <search></search> and stop. The results arrive in the next message.
- When you know the answer, write only the answer inside <answer></answer>: a name, date, number, or yes/no.

Example. Question: Who directed the film in which Tom Hanks plays a FedEx employee stranded on an island?
Reply 1: <search>Tom Hanks FedEx employee stranded island film</search>
Reply 2: <search>Cast Away 2000 film director</search>
Reply 3: <answer>Robert Zemeckis</answer>

Most questions need two facts: find the first, then search for the second. Never answer before you have searched."""

SYSTEM_CLOSED_BOOK = """Answer the question from memory.
Write only the final answer inside <answer></answer>: a name, date, number, or yes/no."""


@dataclass
class Sample:
    tokens: list
    logprobs: list
    stop_reason: str  # "stop" (end of turn) or "length" (hit MAX_TOKENS)


@dataclass
class Episode:
    id: str
    question: str
    answers: list
    prompt: list                                  # chat-template tokens of system + question
    tokens: list = field(default_factory=list)    # everything after the prompt
    sampled: list = field(default_factory=list)   # 1 = the model wrote this token, 0 = the harness did
    logprobs: list = field(default_factory=list)  # sampler logprob per token (0.0 for harness tokens)
    searches: list = field(default_factory=list)
    answer: str = ""
    end: str = ""          # answer | no_action | length | budget
    prefill: int = 0       # tokens sent to the sampler, summed over turns (for cost)
    generated: int = 0     # tokens the sampler produced

    @property
    def reward(self):
        return f1(self.answer, self.answers) if self.end == "answer" else 0.0


class LocalPolicy:
    """Runs the model with transformers on your own machine: free, slow, no logprobs."""

    def __init__(self, name):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(name)
        device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
        self.model = AutoModelForCausalLM.from_pretrained(name, dtype="auto").to(device)
        self.end = self.tokenizer.convert_tokens_to_ids("<|im_end|>")

    async def sample(self, ids, temperature):
        x = self.torch.tensor([ids], device=self.model.device)
        out = self.model.generate(x, attention_mask=self.torch.ones_like(x), max_new_tokens=MAX_TOKENS,
                                  do_sample=temperature > 0, temperature=temperature or None,
                                  top_p=None, top_k=None, eos_token_id=self.end)
        new = out[0, len(ids):].tolist()
        return Sample(new, [0.0] * len(new), "stop" if new and new[-1] == self.end else "length")


class TinkerPolicy:
    """Samples from a model on Tinker: a base model or one of your checkpoints."""

    def __init__(self, sampling_client):
        import tinker
        self.tinker = tinker
        self.client = sampling_client
        self.tokenizer = sampling_client.get_tokenizer()
        self.end = self.tokenizer.convert_tokens_to_ids("<|im_end|>")

    async def sample(self, ids, temperature):
        params = self.tinker.SamplingParams(max_tokens=MAX_TOKENS, temperature=temperature, stop=[self.end])
        result = await self.client.sample_async(prompt=self.tinker.ModelInput.from_ints(ids),
                                                num_samples=1, sampling_params=params)
        seq = result.sequences[0]
        if seq.logprobs is None:
            raise RuntimeError("the sampler returned no logprobs; RL needs them")
        return Sample(list(seq.tokens), list(seq.logprobs), seq.stop_reason)


def chat_prompt(tokenizer, system, question):
    return tokenizer.apply_chat_template(
        [{"role": "system", "content": system}, {"role": "user", "content": question}],
        add_generation_prompt=True, enable_thinking=False, tokenize=True, return_dict=False)


def user_turn(tokenizer, content):
    """Tokens that close the model's turn, add a user message and open the next model turn.

    Built by hand instead of re-rendering the whole chat: the Qwen template drops the
    empty <think></think> from earlier turns, which would change tokens the model
    already produced. test_harness.py checks this string against the real template.
    """
    text = f"\n<|im_start|>user\n{content}<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
    return tokenizer.encode(text, add_special_tokens=False)


def format_results(docs):
    if not docs:
        return "<result>\nNo results. Try other keywords.\n</result>"
    return "<result>\n" + "\n\n".join(f"[{d['title']}] {d['text']}" for d in docs) + "\n</result>"


async def run_episode(policy, searcher, item, temperature=0.0, closed_book=False,
                      top_k=TOP_K, max_searches=MAX_SEARCHES):
    tok = policy.tokenizer
    system = SYSTEM_CLOSED_BOOK if closed_book else SYSTEM
    ep = Episode(item["id"], item["question"], item["answers"], chat_prompt(tok, system, item["question"]))

    def add(tokens, logprobs, sampled):
        ep.tokens += tokens
        ep.logprobs += logprobs
        ep.sampled += [sampled] * len(tokens)

    while True:
        ids = ep.prompt + ep.tokens
        out = await policy.sample(ids, temperature)
        ep.prefill += len(ids)
        ep.generated += len(out.tokens)
        add(out.tokens, out.logprobs, 1)
        if out.stop_reason == "length":
            ep.end = "length"
            return ep
        if not out.tokens or out.tokens[-1] != policy.end:  # some samplers leave out the stop token
            add([policy.end], [0.0], 0)
        reply = tok.decode(out.tokens, skip_special_tokens=True)

        answer = re.search(r"<answer>(.*?)</answer>", reply, re.S)
        if answer:
            ep.answer, ep.end = answer.group(1).strip(), "answer"
            return ep
        query = re.search(r"<search>(.*?)</search>", reply, re.S)
        if closed_book or not query:
            ep.end = "no_action"
            return ep
        if len(ep.searches) == max_searches:
            ep.end = "budget"
            return ep

        ep.searches.append(query.group(1).strip())
        content = format_results(searcher.search(ep.searches[-1], top_k))
        if len(ep.searches) == max_searches:
            content += "\nThat was your last search. Reply with <answer></answer> now."
        env = user_turn(tok, content)
        add(env, [0.0] * len(env), 0)
