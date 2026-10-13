"""Experiment configuration: one TOML file describes a grid of conditions."""
from __future__ import annotations

import itertools
import tomllib
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class Config:
    name: str
    model: str | None = None       # OpenRouter model id, e.g. "provider/model-name"; required unless dry_run
    prompts: list[str] = field(default_factory=lambda: ["P1", "P2"])
    alphas: list[float] = field(default_factory=lambda: [1.0])
    memory_lengths: list[int] = field(default_factory=lambda: [100])
    temperatures: list[float] = field(default_factory=lambda: [0.7])
    n_runs: int = 3
    n_rounds: int = 300
    seed: int = 0
    parallel: int = 4              # concurrent runs (separate processes)
    json_mode: bool = True         # ask for response_format=json_object
    dry_run: bool = False          # scripted FakeAgents, no API calls
    final_window: int = 50         # last N rounds define a run's outcome
    thresholds: list[float] = field(default_factory=lambda: [0.5, 0.9])
    out_dir: str = "runs"

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        with open(path, "rb") as f:
            cfg = cls(**tomllib.load(f))
        if not cfg.dry_run and not cfg.model:
            raise SystemExit(f"{path}: set `model` to an OpenRouter model id (or dry_run = true)")
        return cfg

    def conditions(self) -> list[dict]:
        grid = itertools.product(
            self.prompts, self.alphas, self.memory_lengths, self.temperatures
        )
        return [
            {"prompt": p, "alpha": a, "memory": m, "temperature": t}
            for p, a, m, t in grid
        ]

    @staticmethod
    def cond_id(c: dict) -> str:
        return f"{c['prompt']}_a{c['alpha']}_m{c['memory']}_t{c['temperature']}"

    def run_dir(self, cond: dict, run_idx: int) -> Path:
        return Path(self.out_dir) / self.name / self.cond_id(cond) / f"run_{run_idx:03d}"

    def to_dict(self) -> dict:
        return asdict(self)
