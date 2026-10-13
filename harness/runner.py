"""Run one simulation (in its own process) and orchestrate many."""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

from harness import metrics
from harness.config import Config


def provenance() -> dict:
    """Which code and libraries produced a run."""
    import platform
    import subprocess
    from importlib.metadata import version

    def git(*args):
        try:
            r = subprocess.run(["git", *args], capture_output=True, text=True, timeout=10,
                               cwd=Path(__file__).parent)
            return r.stdout.strip() or None if r.returncode == 0 else None
        except Exception:
            return None
    return {"python": platform.python_version(), "openai": version("openai"),
            "numpy": version("numpy"), "scipy": version("scipy"),
            "git_commit": git("rev-parse", "--verify", "HEAD"), "git_dirty": bool(git("status", "--porcelain"))}


def run_one(cfg: Config, cond_idx: int, run_idx: int) -> None:
    """Executes inside a subprocess so each run has its own logging and failure isolation."""
    from harness.agent import OpenRouterAgent, ScriptedAgent
    from harness.market import Market
    from harness.prompts import PREFIXES
    from harness.sim import simulate
    from harness.transcript import Transcript

    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
    cond = cfg.conditions()[cond_idx]
    run_dir = cfg.run_dir(cond, run_idx)
    run_dir.mkdir(parents=True, exist_ok=True)
    market = Market(alpha=float(cond["alpha"]))
    names = ["Firm A", "Firm B"]
    transcript = Transcript(run_dir / "transcript.jsonl.gz")
    base_seed = cfg.seed + 1000 * run_idx + 100 * cond_idx

    if cfg.dry_run:  # scripted prices at known points on the Nash -> monopoly line
        nash, mono = market.nash_prices, market.monopoly_prices
        target = {"NASH": nash, "MONO": mono,
                  "HALF": [(a + b) / 2 for a, b in zip(nash, mono)]}[cond["prompt"]]
        agents = [ScriptedAgent(n, p, transcript) for n, p in zip(names, target)]
    else:
        agents = [OpenRouterAgent(n, PREFIXES[cond["prompt"]], cfg.model,
                                  temperature=float(cond["temperature"]), seed=base_seed + i,
                                  json_mode=cfg.json_mode, transcript=transcript) for i, n in enumerate(names)]

    (run_dir / "metadata.json").write_text(json.dumps({
        "condition": cond, "run_idx": run_idx, "config": cfg.to_dict(),
        "market": {k: getattr(market, k) for k in ("n_firms", "a", "a0", "mu", "beta", "c", "alpha")},
        "benchmarks": market.benchmarks(),
        "provenance": provenance(),
    }, indent=2))

    t0 = time.time()
    try:
        asyncio.run(simulate(market, agents, cfg.n_rounds, int(cond["memory"]), run_dir))
    finally:
        transcript.close()

    traj, bench = metrics.trajectory(run_dir)
    summary = metrics.summarize(traj, bench, cfg.final_window, cfg.thresholds)
    summary |= {"condition": cond, "run_idx": run_idx, "seconds": round(time.time() - t0, 1),
                "usage": {a.name: a.usage for a in agents}}
    traj.write_csv(run_dir / "trajectory.csv")
    (run_dir / "metrics.json").write_text(json.dumps(summary, indent=2))  # written last = done marker


async def run_all(cfg: Config, config_path: str) -> None:
    conds = cfg.conditions()
    jobs = [(ci, ri) for ci in range(len(conds)) for ri in range(cfg.n_runs)
            if not (cfg.run_dir(conds[ci], ri) / "metrics.json").exists()]
    total = len(conds) * cfg.n_runs
    calls = len(jobs) * cfg.n_rounds * 2
    mode = "dry run, no API calls" if cfg.dry_run else f"~{calls} API calls on {cfg.model}"
    print(f"{len(conds)} conditions x {cfg.n_runs} runs = {total}; "
          f"{total - len(jobs)} already done; {len(jobs)} to run ({mode})", flush=True)
    sem = asyncio.Semaphore(cfg.parallel)
    failures = []

    async def worker(ci: int, ri: int):
        async with sem:
            rd = cfg.run_dir(conds[ci], ri)
            rd.mkdir(parents=True, exist_ok=True)
            with open(rd / "stdout.txt", "wb") as out:
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, "-m", "harness", "one", "--config", config_path,
                    "--cond", str(ci), "--run", str(ri), stdout=out, stderr=out)
                code = await proc.wait()
            tag = f"{Config.cond_id(conds[ci])}/run_{ri:03d}"
            if code:
                failures.append(tag)
            print(("FAILED " if code else "done   ") + tag, flush=True)

    await asyncio.gather(*(worker(ci, ri) for ci, ri in jobs))
    if failures:
        print(f"{len(failures)} failed (see stdout.txt in each run dir); rerun to retry them.")
