import asyncio
import unittest

from transformers import AutoTokenizer

from config import MODEL
from harness import SYSTEM, Sample, chat_prompt, run_episode, user_turn

tok = AutoTokenizer.from_pretrained(MODEL)
END = tok.convert_tokens_to_ids("<|im_end|>")


class ScriptedPolicy:
    """Replays fixed replies, so the harness can be tested without a model."""

    def __init__(self, replies):
        self.tokenizer, self.end, self.replies = tok, END, list(replies)

    async def sample(self, ids, temperature):
        tokens = tok.encode(self.replies.pop(0), add_special_tokens=False) + [END]
        return Sample(tokens, [-0.5] * len(tokens), "stop")


class FakeSearcher:
    def search(self, query, k=3):
        return [{"title": "Arthur's Magazine", "text": "Arthur's Magazine was published from 1844 to 1846."}]


ITEM = {"id": "q1", "question": "Which magazine started first?", "answers": ["Arthur's Magazine"]}


def run(replies, **kw):
    return asyncio.run(run_episode(ScriptedPolicy(replies), FakeSearcher(), ITEM, **kw))


class HarnessTest(unittest.TestCase):
    def test_user_turn_matches_chat_template(self):
        # Our hand-built tokens must equal what the template renders for the next turn.
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "Q"}]
        prompt = chat_prompt(tok, SYSTEM, "Q")
        reply = tok.encode("<search>x</search>", add_special_tokens=False) + [END]
        ours = prompt + reply + user_turn(tok, "<result>R</result>")
        rendered = tok.apply_chat_template(
            msgs + [{"role": "assistant", "content": "<search>x</search>"},
                    {"role": "user", "content": "<result>R</result>"}],
            add_generation_prompt=True, enable_thinking=False, tokenize=False)
        # The template drops the old turn's empty <think> block; everything else must match.
        expected = rendered.replace("<|im_start|>assistant\n<search>", "<|im_start|>assistant\n<think>\n\n</think>\n\n<search>")
        self.assertEqual(tok.decode(ours), expected)

    def test_search_then_answer(self):
        ep = run(["<search>Arthur's Magazine</search>", "<answer>Arthur's Magazine</answer>"])
        self.assertEqual(ep.end, "answer")
        self.assertEqual(ep.searches, ["Arthur's Magazine"])
        self.assertEqual(ep.reward, 1.0)

    def test_masks_line_up(self):
        ep = run(["<search>a</search>", "<answer>b</answer>"])
        self.assertEqual(len(ep.tokens), len(ep.sampled))
        self.assertEqual(len(ep.tokens), len(ep.logprobs))
        self.assertIn("1844", tok.decode([t for t, s in zip(ep.tokens, ep.sampled) if s == 0]))
        self.assertNotIn("1844", tok.decode([t for t, s in zip(ep.tokens, ep.sampled) if s == 1]))

    def test_no_action_scores_zero(self):
        ep = run(["I think it is Arthur's Magazine."])
        self.assertEqual((ep.end, ep.reward), ("no_action", 0.0))

    def test_budget_forces_answer(self):
        ep = run(["<search>a</search>"] * 3 + ["<answer>Arthur's Magazine</answer>"], max_searches=3)
        self.assertEqual((len(ep.searches), ep.end), (3, "answer"))
        self.assertIn("last search", tok.decode(ep.tokens))

    def test_budget_exceeded(self):
        ep = run(["<search>a</search>"] * 3, max_searches=2)
        self.assertEqual(ep.end, "budget")


if __name__ == "__main__":
    unittest.main()
