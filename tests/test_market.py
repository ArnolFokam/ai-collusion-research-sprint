import pytest

from harness.market import Market


def test_benchmarks_match_calvano():
    m = Market()
    assert m.nash_prices == pytest.approx([1.4729, 1.4729], abs=1e-3)
    assert m.monopoly_prices == pytest.approx([1.9250, 1.9250], abs=1e-3)


@pytest.mark.parametrize("alpha", [3.2, 10.0])
def test_benchmarks_scale_with_alpha(alpha):
    base, m = Market(), Market(alpha=alpha)
    assert m.nash_prices[0] == pytest.approx(base.nash_prices[0] * alpha, rel=1e-4)
    assert m.monopoly_prices[0] == pytest.approx(base.monopoly_prices[0] * alpha, rel=1e-4)


def test_collusion_is_profitable_and_unstable():
    m = Market()
    nash, mono = m.nash_prices, m.monopoly_prices
    assert m.profits(mono).sum() > m.profits(nash).sum()
    # at the monopoly price a firm gains by undercutting its rival: collusion needs enforcement
    assert m.profits([mono[0] - 0.05, mono[1]])[0] > m.profits(mono)[0]


def test_rejects_bad_prices():
    with pytest.raises(ValueError):
        Market().quantities([1.0, float("nan")])
