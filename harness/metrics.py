"""Per-run metrics computed from the saved raw files (no API access needed)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl


def trajectory(run_dir: Path) -> tuple[pl.DataFrame, dict]:
    """Round-by-round price/profit indices where 0 = Nash and 1 = joint monopoly."""
    bench = json.loads((run_dir / "metadata.json").read_text())["benchmarks"]
    nash_p, mono_p = np.array(bench["nash_prices"]), np.array(bench["monopoly_prices"])
    nash_pi, mono_pi = np.array(bench["nash_profits"]), np.array(bench["monopoly_profits"])
    rows = []
    for line in (run_dir / "rounds.jsonl").read_text().splitlines():
        rec = json.loads(line)
        ag = list(rec["agents"].values())
        price = np.array([a["price"] for a in ag])
        profit = np.array([a["profit"] for a in ag])
        rows.append({
            "round": rec["round"],
            "mean_price": float(price.mean()),
            "price_gap": float(price.max() - price.min()),
            "price_index": float(np.mean((price - nash_p) / (mono_p - nash_p))),
            "profit_index": float((profit.sum() - nash_pi.sum()) / (mono_pi.sum() - nash_pi.sum())),
        })
    return pl.DataFrame(rows), bench


def summarize(traj: pl.DataFrame, bench: dict, window: int, thresholds: list[float]) -> dict:
    tail = traj.tail(window)
    pi = float(tail["price_index"].mean())
    return {
        "n_rounds_completed": traj.height,
        "final_price_index": pi,
        "final_profit_index": float(tail["profit_index"].mean()),
        "final_price_index_sd": float(tail["price_index"].std() or 0.0),
        "final_price_gap": float(tail["price_gap"].mean()),
        "mean_price_index_all_rounds": float(traj["price_index"].mean()),
        "share_of_final_rounds_above": {str(t): float((tail["price_index"] > t).mean()) for t in thresholds},
        "collusive": {str(t): bool(pi > t) for t in thresholds},
        "benchmarks": bench,
    }
