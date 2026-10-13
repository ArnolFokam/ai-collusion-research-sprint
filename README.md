# AI collusion research sprint: pricing harness

A small harness for measuring how often LLM pricing agents reach collusive-like prices in a
repeated duopoly, built for the [Apart Research AI Collusion Research Sprint](https://apartresearch.com/sprints/ai-collusion-research-sprint-2026-10-23-to-2026-10-25) (Oct 2026).

The setup follows Fish, Gonczarowski & Shorrer, [*Algorithmic Collusion by Large Language Models*](https://arxiv.org/abs/2404.00806):
two LLM firms repeatedly set prices in a Calvano et al. logit-demand market, see only the
price history and their own notes, and cannot communicate. Any model on [OpenRouter](https://openrouter.ai) can be the agent.

## Architecture

```mermaid
flowchart LR
    CFG["Config (TOML)<br/>model + conditions"] --> RUN["Runner<br/>one process per run"]
    RUN --> SIM["Round loop"]
    SIM --> AGENT["Agents<br/>LLM or scripted"]
    AGENT <-->|"prompt / JSON price"| API[("OpenRouter")]
    SIM --> MARKET["Market<br/>demand, profits,<br/>Nash and monopoly"]
    SIM --> FILES["Run files<br/>transcript, rounds, metrics"]
    FILES --> REPORT["Report<br/>table and plots"]
```

How it fits together:

- **Config:** a TOML file names the model and a grid of conditions (prompt, alpha, memory length, temperature)
  plus the number of runs per condition.
- **CLI:** `python -m harness run` expands the grid into runs, skips any that already finished, and starts
  each remaining run in its own subprocess, a few at a time. `report` rebuilds the summary and plots from saved files.
- **One run:** `run_one` builds two firms, a market, and an agent per firm, then plays a fixed number of rounds.
- **Each round:** both firms get a prompt built from their own history (recent market outcomes plus the plans and
  insights they wrote last round) and price at the same time. They never see each other's reasoning, only prices.
- **Market:** takes the two prices and returns quantities and profits from a logit demand model. It also provides the two
  reference points everything is measured against: the competitive (Nash) price and the joint-monopoly price.
- **Agents:** an OpenRouter agent sends the prompt to the chosen model and validates the JSON reply, retrying on failure.
  A scripted agent posts fixed prices and makes no API calls, for free dry runs and metric checks.
- **Saved files:** every API call goes to the transcript, each round's outcome and the agents' notes go to
  `rounds.jsonl`, and a run's summary goes to `metrics.json`, which is written last.
- **Metrics and report:** metrics turn the saved prices and profits into indices (0 = Nash, 1 = monopoly), and the report
  aggregates runs into a summary table and three plots. Both read only saved files, so they never need the API.

See [CLAUDE.md](CLAUDE.md) for the per-round sequence diagram and step-by-step playbooks (written so a coding
assistant can run the usual tasks without exploring the code).

## Setup

**Stack:** Python 3.11+, [uv](https://docs.astral.sh/uv/) for environment and dependencies, the OpenAI SDK pointed at
[OpenRouter](https://openrouter.ai), pydantic, numpy/scipy, polars, matplotlib, pytest. Needs an OpenRouter account
with an API key.

```bash
uv sync
cp .env.example .env        # then put your OpenRouter key in .env
uv run pytest               # 16 tests, no network or API key needed
```

## Run

```bash
uv run python -m harness run --config configs/dry.toml     # free: scripted agents at known prices
uv run python -m harness run --config configs/smoke.toml   # cheap: 20 real calls, a fraction of a cent
uv run python -m harness plan --config configs/pilot.toml  # size and estimated cost; runs nothing
uv run python -m harness run --config configs/pilot.toml --yes  # the actual run: 300 rounds, P1 vs P2, ~$3
uv run python -m harness report --config configs/smoke.toml  # rebuild summary + plots from saved runs
```

A config (TOML) names a model and a grid of conditions (prompt, alpha, memory length, temperature)
with `n_runs` repetitions each. Finished runs are skipped, so an interrupted job resumes.

## What a run saves (`runs/<name>/<condition>/run_NNN/`)

| file | contents |
|---|---|
| `metadata.json` | condition, config, market parameters, Nash/monopoly benchmarks, code and library versions |
| `transcript.jsonl.gz` | **every API call**: exact messages sent, raw response, errors and retries |
| `rounds.jsonl` | per-round prices, quantities, profits, and each agent's observations/plans/insights |
| `trajectory.csv` | per-round price and profit indices |
| `metrics.json` | run summary (written last, doubles as the "done" marker) |

`runs/<name>/report/` holds `summary.csv` and three plots (outcomes, trajectories, collusive-run rates).

## Measuring collusion

Prices are placed on an index where **0 = Nash (competitive)** and **1 = joint monopoly (full collusion)**.
Price alone can mislead: a model that overprices out of anchoring pushes the index above 1 while
*losing* money, so the profit index (same scale, on profits) should be read alongside it.

## Layout

```
harness/market.py    demand, profits, Nash and monopoly benchmarks
harness/prompts.py   prompts and prompt construction
harness/agent.py     OpenRouter agent and scripted agent
harness/sim.py       the repeated game
harness/plan.py, transcript.py, metrics.py, report.py, runner.py, config.py
```

## Attribution

The market model and prompts are re-implemented from
[luciasauer/algorithmic_pricing_llms](https://github.com/luciasauer/algorithmic_pricing_llms) (MIT).
See [THIRD_PARTY.md](THIRD_PARTY.md) for the license notice and the deliberate differences.
