"""Step 0: check that your key works and the model answers."""
import asyncio

import tinker

from config import MODEL


async def main():
    service = tinker.ServiceClient()
    client = await service.create_sampling_client_async(base_model=MODEL)
    tok = client.get_tokenizer()
    prompt = tok.apply_chat_template([{"role": "user", "content": "In one sentence: who wrote Hamlet?"}],
                                     add_generation_prompt=True, enable_thinking=False,
                                     tokenize=True, return_dict=False)
    result = await client.sample_async(prompt=tinker.ModelInput.from_ints(prompt), num_samples=1,
                                       sampling_params=tinker.SamplingParams(max_tokens=50, temperature=0.0))
    print(tok.decode(result.sequences[0].tokens, skip_special_tokens=True))


asyncio.run(main())
