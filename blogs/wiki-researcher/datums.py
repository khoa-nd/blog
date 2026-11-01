"""Turn episodes into Tinker training examples (Datum).

A model predicts the next token, so the input is every token except the last and the
target is every token except the first. Masks are shifted the same way.
"""
import tinker


def sft_datum(prompt, tokens, sampled):
    """Cross-entropy only on tokens the model wrote; prompt and search results get weight 0."""
    full = prompt + tokens
    weights = [0.0] * len(prompt) + [float(s) for s in sampled]
    return tinker.Datum(model_input=tinker.ModelInput.from_ints(full[:-1]),
                        loss_fn_inputs={"target_tokens": full[1:], "weights": weights[1:]})


def rl_datum(ep, advantage):
    """Importance-sampling loss: push up the model's own tokens in proportion to the advantage."""
    full = ep.prompt + ep.tokens
    n = len(ep.prompt) - 1
    return tinker.Datum(model_input=tinker.ModelInput.from_ints(full[:-1]),
                        loss_fn_inputs={"target_tokens": full[1:],
                                        "logprobs": [0.0] * n + ep.logprobs,
                                        "advantages": [0.0] * n + [advantage * s for s in ep.sampled]})
