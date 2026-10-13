"""Cost/size plan for a config, computed without running anything."""
from __future__ import annotations

import json
import urllib.request

from harness.config import Config

# Token model measured on gpt-4o-mini pilot runs (partial, 30 rounds x 6 runs, 352 calls):
#   prompt tokens ~= BASE + PER_ROUND * (rounds of history in the prompt); ~276 completion tokens per call.
# Other models tokenise differently, so treat the cost as a rough estimate (+-30%).
PROMPT_BASE = 629
PROMPT_PER_HISTORY_ROUND = 48.3
COMPLETION_TOKENS = 276
CONFIRM_ABOVE_CALLS = 100   # real configs larger than this need --yes


def prices_per_token(model: str) -> tuple[float, float] | None:
    """(prompt, completion) USD per token from OpenRouter's public model list; None if unavailable."""
    try:
        data = json.load(urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=15))["data"]
        p = next(m["pricing"] for m in data if m["id"] == model)
        return float(p["prompt"]), float(p["completion"])
    except Exception:
        return None


def make_plan(cfg: Config, fetch_prices: bool = True) -> dict:
    conds = cfg.conditions()
    todo = [(ci, ri) for ci in range(len(conds)) for ri in range(cfg.n_runs)
            if not (cfg.run_dir(conds[ci], ri) / "metrics.json").exists()]
    calls = in_tok = 0
    for ci, _ in todo:
        mem = int(conds[ci]["memory"])
        for r in range(1, cfg.n_rounds + 1):
            hist = min(r - 1, mem) if mem > 0 else 0
            in_tok += 2 * (PROMPT_BASE + PROMPT_PER_HISTORY_ROUND * hist)
            calls += 2
    out_tok = calls * COMPLETION_TOKENS
    plan = {"model": "scripted (dry run)" if cfg.dry_run else cfg.model, "conditions": len(conds),
            "runs_total": len(conds) * cfg.n_runs, "runs_to_do": len(todo), "rounds_per_run": cfg.n_rounds,
            "api_calls": 0 if cfg.dry_run else calls, "est_input_tokens": 0 if cfg.dry_run else int(in_tok),
            "est_output_tokens": 0 if cfg.dry_run else int(out_tok), "est_cost_usd": 0.0 if cfg.dry_run else None}
    if not cfg.dry_run and fetch_prices and (pr := prices_per_token(cfg.model)):
        plan["est_cost_usd"] = round(in_tok * pr[0] + out_tok * pr[1], 4)
    return plan


def needs_confirmation(plan: dict, cfg: Config) -> bool:
    return not cfg.dry_run and plan["api_calls"] > CONFIRM_ABOVE_CALLS


def format_plan(plan: dict) -> str:
    cost = plan["est_cost_usd"]
    cost = "unknown (model price not found)" if cost is None else (f"~${cost:.2f}" if cost >= 0.1 else f"~${cost:.4f}")
    return (f"model: {plan['model']}\n"
            f"conditions: {plan['conditions']} | runs: {plan['runs_to_do']} to do of {plan['runs_total']} "
            f"| rounds per run: {plan['rounds_per_run']}\n"
            f"API calls: {plan['api_calls']:,} | est. tokens: {plan['est_input_tokens']:,} in, "
            f"{plan['est_output_tokens']:,} out\n"
            f"est. cost: {cost} (rough, +-30%)")
