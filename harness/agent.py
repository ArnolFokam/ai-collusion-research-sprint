"""Pricing agents: an LLM agent behind OpenRouter, and a scripted agent for dry runs."""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
import time
from pathlib import Path

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, field_validator

from harness.prompts import SCHEMA_PROMPT

OPENROUTER_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")  # override for tests
MAX_ATTEMPTS = 8
log = logging.getLogger("harness")


class PricingAnswer(BaseModel):
    """What the model must return each round."""
    observations: str = "No previous observations."
    plans: str = "No previous plans."
    insights: str = "No previous insights."
    chosen_price: float

    @field_validator("chosen_price")
    @classmethod
    def _sane(cls, v: float) -> float:
        if not math.isfinite(v) or v <= 0:
            raise ValueError(f"chosen_price must be a positive number, got {v}")
        return v


def _extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise
        return json.loads(m.group(0))


ROOT = Path(__file__).resolve().parent.parent
KEY_NAMES = ("OPENROUTER_API_KEY", "OPEN_ROUTER_API_KEY")   # both spellings are accepted


def _read_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.removeprefix("export ").split("=", 1)
            out[k.strip()] = v.strip().strip("\"'")
    return out


def load_api_key(env_path: Path = ROOT / ".env") -> tuple[str, str]:
    """Return (key, source). The project's .env wins over the shell environment."""
    dotenv = _read_dotenv(env_path)
    for source, store in ((".env", dotenv), ("environment", os.environ)):
        for name in KEY_NAMES:
            if store.get(name):
                return store[name], f"{source}:{name}"
    raise RuntimeError(f"No OpenRouter key: set one of {KEY_NAMES} in {env_path} or the environment")


def api_key() -> str:
    key, source = load_api_key()
    log.info("OpenRouter key loaded from %s", source)   # never log the key itself
    return key


class OpenRouterAgent:
    """LLM pricing agent that talks to any model through OpenRouter."""

    def __init__(self, name: str, prefix: str, model: str, temperature: float = 0.7,
                 seed: int | None = None, json_mode: bool = True, transcript=None):
        self.name, self.prefix, self.model = name, prefix, model
        self.transcript = transcript
        self.temperature, self.seed, self.json_mode = temperature, seed, json_mode
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0, "retries": 0}
        # max_retries=0: the SDK would otherwise retry HTTP errors silently; we retry ourselves so
        # every attempt lands in the transcript.
        self._client = AsyncOpenAI(base_url=OPENROUTER_URL, api_key=api_key(), max_retries=0, timeout=120)

    async def act(self, prompt: str, round_num: int) -> PricingAnswer:
        kwargs = dict(
            model=self.model,
            messages=[{"role": "system", "content": SCHEMA_PROMPT},
                      {"role": "system", "content": self.prefix},
                      {"role": "user", "content": prompt}],
            temperature=self.temperature,
        )
        if self.json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if self.seed is not None:
            kwargs["seed"] = self.seed
        last: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            entry = {"agent": self.name, "round": round_num, "attempt": attempt, "model": self.model,
                     "request": kwargs}
            t0 = time.time()
            raw = None
            try:
                resp = await self._client.chat.completions.create(**kwargs)
                entry["response"] = resp.model_dump(mode="json")   # raw: content, finish_reason, usage, provider, reasoning
                raw = resp.choices[0].message.content
                if resp.usage:
                    self.usage["prompt_tokens"] += resp.usage.prompt_tokens or 0
                    self.usage["completion_tokens"] += resp.usage.completion_tokens or 0
                self.usage["calls"] += 1
                answer = PricingAnswer(**_extract_json(raw))
                entry["outcome"] = "ok"
                return answer
            except Exception as e:  # parsing, validation, network, rate limit
                last = e
                entry["outcome"] = "error"
                entry["error"] = f"{type(e).__name__}: {e}"
                self.usage["retries"] += 1
                log.warning("%s round %d attempt %d failed: %s", self.name, round_num, attempt, e)
            finally:
                entry["seconds"] = round(time.time() - t0, 3)
                if self.transcript:
                    self.transcript.log(**entry)
            await asyncio.sleep(min(2 ** attempt, 30))
        raise RuntimeError(f"{self.name} round {round_num}: gave up after {MAX_ATTEMPTS} attempts") from last


class ScriptedAgent:
    """Always posts a fixed price. For dry runs and metric validation; makes no API calls."""

    def __init__(self, name: str, price: float, transcript=None):
        self.name, self.price, self.transcript = name, price, transcript
        self.usage = {"calls": 0}

    async def act(self, prompt: str, round_num: int) -> PricingAnswer:
        self.usage["calls"] += 1
        if self.transcript:
            self.transcript.log(agent=self.name, round=round_num, attempt=1, model="scripted",
                                request={"messages": [{"role": "user", "content": prompt}]},
                                response={"chosen_price": self.price}, outcome="ok")
        return PricingAnswer(chosen_price=self.price)
