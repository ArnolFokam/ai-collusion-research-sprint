"""The repeated pricing game: each round every firm prices, the market clears, outcomes are logged."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from harness.market import Market
from harness.prompts import build_prompt, market_data_line


async def simulate(market: Market, agents: list, n_rounds: int, memory_length: int,
                   out_dir: Path) -> None:
    """Run the game and write `rounds.jsonl` (one line per round, with every agent's full output)."""
    names = [a.name for a in agents]
    history: dict[str, dict[int, dict]] = {n: {} for n in names}
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "rounds.jsonl", "w") as f:
        for r in range(1, n_rounds + 1):
            prompts = [build_prompt(history[a.name], r, marginal_cost=market.c, wtp=market.wtp,
                                    memory_length=memory_length) for a in agents]
            answers = await asyncio.gather(*(a.act(p, r) for a, p in zip(agents, prompts)))
            prices = {a.name: ans.chosen_price for a, ans in zip(agents, answers)}
            q = market.quantities(list(prices.values()))
            pi = market.profits(list(prices.values()))
            rec = {"round": r, "agents": {}}
            for i, (a, ans) in enumerate(zip(agents, answers)):
                history[a.name][r] = {
                    "plans": ans.plans, "insights": ans.insights,
                    "market_data": market_data_line(a.name, prices, float(q[i]), float(pi[i])),
                }
                rec["agents"][a.name] = {
                    "price": ans.chosen_price, "quantity": float(q[i]), "profit": float(pi[i]),
                    "observations": ans.observations, "plans": ans.plans, "insights": ans.insights,
                }
            f.write(json.dumps(rec) + "\n")
            f.flush()
