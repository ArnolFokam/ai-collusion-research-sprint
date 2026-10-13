from pathlib import Path

from harness.prompts import build_prompt, market_data_line

FIX = Path(__file__).parent / "fixtures"  # generated from the original repo's PromptManager


def _history(n):
    h = {}
    for r in range(1, n + 1):
        prices = {"Firm A": 1.5 + r / 10, "Firm B": 1.6 + r / 10}
        h[r] = {"plans": f"plan {r}", "insights": f"ins {r}",
                "market_data": market_data_line("Firm A", prices, 40.123 * r, 20.456 * r)}
    return h


def test_round_one_matches_original():
    assert build_prompt({}, 1, marginal_cost=1.0, wtp=4.51, memory_length=100) == \
        (FIX / "prompt_round1.txt").read_text()


def test_later_round_matches_original():
    assert build_prompt(_history(5), 6, marginal_cost=1.0, wtp=4.51, memory_length=100) == \
        (FIX / "prompt_round6_mem100.txt").read_text()


def test_memory_window_and_zero_memory():
    h = _history(5)
    p3 = build_prompt(h, 6, marginal_cost=1.0, wtp=4.51, memory_length=3)
    assert "Round 5" in p3 and "Round 3" in p3 and "Round 2" not in p3
    p0 = build_prompt(h, 6, marginal_cost=1.0, wtp=4.51, memory_length=0)
    assert "Round " not in p0 and "plan 5" in p0   # scratchpad survives; market history does not
