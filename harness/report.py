"""Aggregate saved per-run metrics into a summary table and plots."""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from harness.config import Config

# Dataviz palette (categorical order is fixed; colour follows the condition, not its rank).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def _style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _fig(w=8, h=4.6):
    fig, ax = plt.subplots(figsize=(w, h), facecolor=SURFACE)
    _style(ax)
    return fig, ax


def load(cfg: Config) -> list[dict]:
    base = Path(cfg.out_dir) / cfg.name
    return [json.loads(p.read_text()) | {"_dir": str(p.parent)}
            for p in sorted(base.glob("*/run_*/metrics.json"))]


def build(cfg: Config) -> Path:
    runs = load(cfg)
    if not runs:
        raise SystemExit(f"No finished runs under {Path(cfg.out_dir) / cfg.name}")
    out = Path(cfg.out_dir) / cfg.name / "report"
    out.mkdir(parents=True, exist_ok=True)
    cids = sorted({Config.cond_id(r["condition"]) for r in runs})
    color = {c: SERIES[i % len(SERIES)] for i, c in enumerate(cids)}
    by = {c: [r for r in runs if Config.cond_id(r["condition"]) == c] for c in cids}

    rows = []
    for c in cids:
        v = np.array([r["final_price_index"] for r in by[c]])
        row = {"condition": c, "n_runs": len(v), "mean_price_index": v.mean(),
               "median_price_index": float(np.median(v)), "sd": float(v.std(ddof=1)) if len(v) > 1 else 0.0,
               "mean_profit_index": float(np.mean([r["final_profit_index"] for r in by[c]]))}
        for t in cfg.thresholds:
            k = sum(r["collusive"][str(t)] for r in by[c])
            lo, hi = wilson(k, len(v))
            row |= {f"rate_above_{t}": k / len(v), f"rate_above_{t}_lo": lo, f"rate_above_{t}_hi": hi}
        rows.append(row)
    summ = pl.DataFrame(rows)
    summ.write_csv(out / "summary.csv")

    # 1. Final outcome per run (0 = Nash, 1 = joint monopoly)
    fig, ax = _fig(max(6, 1.6 * len(cids) + 3))
    rng = np.random.default_rng(0)
    for i, c in enumerate(cids):
        v = np.array([r["final_price_index"] for r in by[c]])
        ax.scatter(i + rng.uniform(-0.12, 0.12, len(v)), v, s=46, color=color[c],
                   edgecolor=SURFACE, linewidth=1.5, zorder=3)
        ax.hlines(np.median(v), i - 0.25, i + 0.25, color=INK, linewidth=2, zorder=4)
    ax.axhline(0, color=MUTED, linewidth=1); ax.axhline(1, color=MUTED, linewidth=1)
    ax.set_xlim(-0.6, len(cids) - 0.4)
    ax.text(len(cids) - 0.45, 0.02, "Nash (competitive)", ha="right", va="bottom", color=INK2, fontsize=9)
    ax.text(len(cids) - 0.45, 0.98, "Joint monopoly (full collusion)", ha="right", va="top", color=INK2, fontsize=9)
    ax.set_xticks(range(len(cids))); ax.set_xticklabels(cids, rotation=20, ha="right")
    ax.set_ylabel(f"Price index, last {cfg.final_window} rounds", color=INK2)
    ax.set_title("Where each run ends up between Nash and monopoly (bar = median)", color=INK, loc="left", fontsize=11)
    fig.tight_layout(); fig.savefig(out / "outcomes.png", dpi=160); plt.close(fig)

    # 2. Trajectories: thin runs + bold mean per condition
    fig, ax = _fig(11, 4.8)
    for c in cids:
        ts = [pl.read_csv(Path(r["_dir"]) / "trajectory.csv") for r in by[c]]
        for t in ts:
            ax.plot(t["round"], t["price_index"], color=color[c], alpha=0.22, linewidth=1)
        n = min(t.height for t in ts)
        mean = np.mean([t["price_index"].to_numpy()[:n] for t in ts], axis=0)
        ax.plot(range(1, n + 1), mean, color=color[c], linewidth=2.2, label=f"{c} (n={len(ts)})")
        ax.text(n, mean[-1], " " + c.split("_")[0], color=INK2, fontsize=9, va="center")
    ax.axhline(0, color=MUTED, linewidth=1); ax.axhline(1, color=MUTED, linewidth=1)
    ax.set_xlabel("Round", color=INK2); ax.set_ylabel("Price index (0 = Nash, 1 = monopoly)", color=INK2)
    ax.set_title("Price index over time (thin = single runs, bold = mean)", color=INK, loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=8, labelcolor=INK2, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    fig.tight_layout(); fig.savefig(out / "trajectories.png", dpi=160); plt.close(fig)

    # 3. Rate of collusive-like runs with Wilson 95% intervals, per threshold
    fig, ax = _fig(max(6, 1.8 * len(cids) + 3))
    w = 0.8 / len(cfg.thresholds)
    shades = [1.0, 0.55, 0.3]
    for j, t in enumerate(cfg.thresholds):
        for i, row in enumerate(rows):
            r, lo, hi = row[f"rate_above_{t}"], row[f"rate_above_{t}_lo"], row[f"rate_above_{t}_hi"]
            x = i - 0.4 + w * (j + 0.5)
            ax.bar(x, r, width=w * 0.9, color=color[row["condition"]], alpha=shades[j % 3], zorder=3)
            ax.vlines(x, lo, hi, color=INK, linewidth=1.4, zorder=4)
            ax.text(x, -0.02, f">{t}", ha="center", va="top", color=INK2, fontsize=8)
    ax.set_xticks(range(len(cids))); ax.set_xticklabels(cids, rotation=20, ha="right")
    ax.tick_params(axis="x", pad=16)
    ax.set_ylim(0, 1.05); ax.set_ylabel("Share of runs", color=INK2)
    ax.set_title("Share of runs whose final price index exceeds each threshold (95% Wilson CI)",
                 color=INK, loc="left", fontsize=10)
    fig.tight_layout(); fig.savefig(out / "rates.png", dpi=160); plt.close(fig)

    (out / "summary.json").write_text(json.dumps(summ.to_dicts(), indent=2))
    return out
