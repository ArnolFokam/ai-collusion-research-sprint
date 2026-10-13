"""Repeated Bertrand market with logit demand (Calvano et al. 2020; Fish et al. 2024 setup).

q_i = beta * exp((a - p_i/alpha)/mu) / (exp(a0/mu) + sum_j exp((a - p_j/alpha)/mu))
profit_i = q_i * (p_i/alpha - c)

`alpha` rescales the currency (prices are quoted in alpha units); `beta` scales quantities.
Re-implemented from the plain-logit special case (sigma = 0, one product group) of the
logic in luciasauer/algorithmic_pricing_llms (MIT) -- see THIRD_PARTY.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

import numpy as np
from scipy.optimize import minimize, minimize_scalar

WTP_FACTOR = 4.51  # "no customer would pay more than WTP_FACTOR * alpha" (value used by the source repo)


@dataclass(frozen=True)
class Market:
    n_firms: int = 2
    a: float = 2.0       # product quality, identical across firms
    a0: float = 0.0      # outside option
    mu: float = 0.25     # product differentiation
    beta: float = 100.0  # quantity scale
    c: float = 1.0       # marginal cost (in base currency)
    alpha: float = 1.0   # currency scale

    @property
    def wtp(self) -> float:
        return WTP_FACTOR * self.alpha

    def quantities(self, p) -> np.ndarray:
        p = np.asarray(p, dtype=float)
        if p.shape != (self.n_firms,) or not np.all(np.isfinite(p)):
            raise ValueError(f"bad prices: {p}")
        z = (self.a - p / self.alpha) / self.mu
        w = np.exp(z - z.max())                      # stabilised softmax with an outside option
        outside = np.exp(self.a0 / self.mu - z.max())
        return self.beta * w / (outside + w.sum())

    def profits(self, p) -> np.ndarray:
        return self.quantities(p) * (np.asarray(p, dtype=float) / self.alpha - self.c)

    @cached_property
    def monopoly_prices(self) -> list[float]:
        """Prices maximising joint profit (full collusion)."""
        lo = self.c * self.alpha
        res = minimize(lambda p: -self.profits(p).sum(), np.full(self.n_firms, lo + 0.1),
                       bounds=[(lo, None)] * self.n_firms, method="L-BFGS-B",
                       options={"ftol": 1e-15, "gtol": 1e-10, "maxiter": 5000})
        return [float(x) for x in res.x]

    @cached_property
    def nash_prices(self) -> list[float]:
        """One-shot Nash equilibrium by iterated best response."""
        lo, hi = self.c * self.alpha, max(self.monopoly_prices)
        p = np.full(self.n_firms, (lo + hi) / 2)
        for _ in range(1000):
            new = p.copy()
            for i in range(self.n_firms):
                def neg(x, i=i):
                    q = new.copy(); q[i] = x
                    return -self.profits(q)[i]
                new[i] = minimize_scalar(neg, bounds=(lo, hi), method="bounded",
                                         options={"xatol": 1e-12}).x
            done = np.linalg.norm(new - p) < 1e-9
            p = new
            if done:
                break
        return [float(x) for x in p]

    def benchmarks(self) -> dict:
        nash, mono = self.nash_prices, self.monopoly_prices
        return {"nash_prices": nash, "monopoly_prices": mono,
                "nash_profits": self.profits(nash).tolist(),
                "monopoly_profits": self.profits(mono).tolist()}
