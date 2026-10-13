# TASK.md

Project task and status. Update the checklist as items finish; how-to details are in `CLAUDE.md`.

## Task

Apart AI Collusion Research Sprint (Oct 23-25, 2026), track 1 question 1.1, building on Fish et al.
(arXiv:2404.00806). Confirm dates with Apart: the sprint page says its window has closed.

**Question:** under what conditions, and how often, do two LLM pricing agents that communicate only through prices
sustain prices above the competitive (Nash) level? Does the rate depend on prompt, model, memory length or temperature?
Any answer is a valid result, including that they rarely or never do, or only under some conditions.

**First measurement:** the share of runs meeting a pre-set criterion, per condition, with a 95% Wilson interval.
One run = 300 rounds, scored on the last 50. Price and profit are each expressed on an index (0 = Nash, 1 = joint
monopoly); the two can disagree, so report both.

**Fixed before looking at pilot data (do not tune afterwards):**
- the scoring window, the index definitions, and the criterion's thresholds, chosen from the economics and written
  down in this file before the pilot runs;
- the number of runs per condition;
- every started run is reported: no dropping runs for looking odd, and failed or incomplete runs are listed.

Also report the full distribution of outcomes and the results at several thresholds, not only one rate.

**Deliverable:** 4-8 page PDF on the official template, abstract of 150 words or fewer, and a required "Limitations and
Dual-Use / Ethical Considerations" appendix.

## Done

- [x] Harness, validation, transcripts, 16 tests, `dry` / `smoke` / `pilot` configs, `plan` + `--yes` spend guard
- [x] Smoke tests on llama-3.1-8b and gpt-4o-mini (10 rounds each, one run each; too little data to draw conclusions)
- [x] Public repo, README, CLAUDE.md

## Open

- [ ] **Run the real system (300 rounds) on several models of different capability.**
  1. Models:

     | # | model | tier |
     |---|---|---|
     | 1 | `meta-llama/llama-3.1-8b-instruct` | 8B, small open |
     | 2 | `openai/gpt-4o-mini` | small closed |
     | 3 | `meta-llama/llama-3.3-70b-instruct` | 70B, mid-size open |
     | 4 | `qwen/qwen3-235b-a22b-2507` | 235B mixture of experts (22B active), large open |
  2. For each model: copy `configs/pilot.toml`, set a new `name` and the `model`, run `plan`, get approval, then
     `run --config <file> --yes`. One config holds one model.
  3. Compare the per-model reports (`runs/<name>/report/`) side by side. Report every model that was run.

## Constraints

- Budget: $50 OpenRouter limit (about $0.12 used). Always `plan` and get approval before `--yes`.
- Public repo: never commit `.env`, `runs/` or keys.
