"""AI gateway: one call for every AI job, routed by config/routes.yaml.

gateway.run(task, data) returns a dict that matches the task's JSON schema. Behind it:
per-task routes with fallbacks, schema validation with one repair retry, a daily budget that
falls back to free models, a log row per call (llm_call), and optional shadow calls that run a
second model on a share of a task so models can be compared on real data.
"""
import json
import os
import random
import re
import time
from pathlib import Path

import httpx
import jsonschema
import yaml
from psycopg.types.json import Jsonb

from .tasks import TASKS


class GatewayError(Exception):
    pass


def first_json(text):
    """Return the first JSON object in a reply, ignoring code fences or chatter around it."""
    text = text.strip()
    if text.startswith("{"):
        return text
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("no JSON object in reply")
    return match.group(0)


class Gateway:
    def __init__(self, conn, routes="config/routes.yaml", fake=False, rng=None, http=None):
        cfg = yaml.safe_load(Path(routes).read_text())
        self.conn, self.fake = conn, fake
        self.models, self.tasks = cfg["models"], cfg["tasks"]
        self.budget = (cfg.get("budget") or {}).get("usd_per_day")
        self.shadow = cfg.get("shadow") or {}
        self.rng = rng or random.Random()
        self.http = http or httpx.Client(timeout=120)
        self._anthropic = None

    # ---------- public ----------
    def run(self, task, data):
        route = ["fake"] if self.fake else [self.tasks[task]["model"], *self.tasks[task].get("fallback", [])]
        errors = []
        for name in route:
            model = self.models[name]
            if sum(model["price"]) > 0 and self.over_budget():
                errors.append(f"{name}: daily budget spent")
                continue
            try:
                out = self.call(task, name, data)
            except GatewayError as e:
                errors.append(f"{name}: {e}")
                continue
            self.maybe_shadow(task, name, data)
            return out
        raise GatewayError(f"{task}: every route failed ({'; '.join(errors)})")

    def spent_today(self):
        row = self.conn.execute("select coalesce(sum(cost_usd), 0) as usd from llm_call "
                                "where at >= date_trunc('day', now())").fetchone()
        return float(row["usd"])

    def over_budget(self):
        return self.budget is not None and self.spent_today() >= self.budget

    # ---------- one model ----------
    def call(self, task, name, data, shadow=False):
        spec, model = TASKS[task], self.models[name]
        prompt, started = spec.prompt(data), time.time()
        tokens_in = tokens_out = 0
        error, out = None, None
        try:
            for attempt in range(2):
                text, used_in, used_out = self.provider(model, task, spec, prompt, data)
                tokens_in, tokens_out = tokens_in + used_in, tokens_out + used_out
                try:
                    out = json.loads(first_json(text))
                    jsonschema.validate(out, spec.schema)
                    error = None
                    break
                except (ValueError, jsonschema.ValidationError) as e:
                    error, out = f"invalid output: {str(e).splitlines()[0][:200]}", None
                    prompt = spec.prompt(data) + f"\n\nYour last reply was invalid ({error}). Reply with corrected JSON only."
            if out is None:
                raise GatewayError(error)
            return out
        except GatewayError as e:
            error = str(e)
            raise
        except Exception as e:  # network errors, HTTP errors, SDK errors
            error = f"{type(e).__name__}: {str(e)[:200]}"
            raise GatewayError(error) from e
        finally:
            price_in, price_out = model["price"]
            keep = out if (shadow or task in self.shadow) else None
            self.conn.execute(
                "insert into llm_call (task, provider, model, ok, shadow, input_tokens, output_tokens, cost_usd, "
                "latency_ms, error, output) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (task, model["provider"], name, out is not None, shadow, tokens_in, tokens_out,
                 (tokens_in * price_in + tokens_out * price_out) / 1e6, int((time.time() - started) * 1000),
                 error, Jsonb(keep) if keep is not None else None))

    def maybe_shadow(self, task, primary, data):
        cfg = self.shadow.get(task)
        if self.fake or not cfg or cfg["model"] == primary or self.rng.random() >= cfg.get("share", 0):
            return
        try:
            self.call(task, cfg["model"], data, shadow=True)
        except GatewayError:
            pass  # a failed shadow call is logged and never blocks the pipeline

    # ---------- providers ----------
    def provider(self, model, task, spec, prompt, data):
        kind = model["provider"]
        if kind == "fake":
            return json.dumps(spec.fake(data)), 0, 0
        if kind == "gemini":
            return self.gemini(model, spec, prompt)
        if kind == "openai_compat":
            return self.openai_compat(model, spec, prompt)
        if kind == "anthropic":
            return self.anthropic(model, spec, prompt)
        raise GatewayError(f"unknown provider {kind}")

    @staticmethod
    def key(env):
        value = os.environ.get(env)
        if not value:
            raise GatewayError(f"{env} is not set")
        return value

    def gemini(self, model, spec, prompt):
        r = self.http.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model['id']}:generateContent",
            headers={"x-goog-api-key": self.key(model.get("key_env", "GEMINI_API_KEY"))},
            json={"systemInstruction": {"parts": [{"text": spec.system}]},
                  "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                  "generationConfig": {"responseMimeType": "application/json"}})
        if r.status_code != 200:
            raise GatewayError(f"HTTP {r.status_code}: {r.text[:200]}")
        body = r.json()
        parts = body["candidates"][0]["content"]["parts"]
        usage = body.get("usageMetadata", {})
        # Thinking tokens are billed as output on Gemini, so count them too.
        out_tokens = usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)
        return "".join(p.get("text", "") for p in parts), usage.get("promptTokenCount", 0), out_tokens

    def openai_compat(self, model, spec, prompt):
        body = {"model": model["id"], "messages": [{"role": "system", "content": spec.system},
                                                   {"role": "user", "content": prompt}]}
        if model.get("json_mode", True):
            body["response_format"] = {"type": "json_object"}
        r = self.http.post(f"{model['base_url']}/chat/completions",
                           headers={"Authorization": f"Bearer {self.key(model['key_env'])}"}, json=body)
        if r.status_code != 200:
            raise GatewayError(f"HTTP {r.status_code}: {r.text[:200]}")
        body = r.json()
        usage = body.get("usage") or {}
        return body["choices"][0]["message"]["content"] or "", usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)

    def anthropic(self, model, spec, prompt):
        import anthropic
        self.key("ANTHROPIC_API_KEY")
        self._anthropic = self._anthropic or anthropic.Anthropic()
        output_config = {"format": {"type": "json_schema", "schema": spec.schema}}
        if model.get("effort"):
            output_config["effort"] = model["effort"]
        request = dict(model=model["id"], max_tokens=16000, system=spec.system,
                       messages=[{"role": "user", "content": prompt}], output_config=output_config)
        if model.get("server_fallback"):
            # On a safety decline the API retries on Anthropic's recommended fallback model.
            response = self._anthropic.beta.messages.create(**request, betas=["server-side-fallback-2026-07-01"],
                                                            fallbacks="default")
        else:
            response = self._anthropic.messages.create(**request)
        if response.stop_reason == "refusal":
            raise GatewayError("model declined the request")
        text = next((b.text for b in response.content if b.type == "text"), "")
        return text, response.usage.input_tokens, response.usage.output_tokens
