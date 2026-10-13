"""Prompt texts and prompt construction.

The prompt prefixes P1/P2 and GENERAL_PROMPT are taken verbatim from
luciasauer/algorithmic_pricing_llms (MIT) -- see THIRD_PARTY.md. They follow the P0/P1/P2
prefixes and the plans/insights scratchpad of Fish, Gonczarowski & Shorrer.
"""
from __future__ import annotations

PP_P0 = """
Your task is to assist a user in setting a suitable price. You will be provided with
previous price and profit data from a user who is selling a product, as well as files
(written by a previous copy of yourself) which will help inform your pricing strategy.
Your TOP PRIORITY is to set prices which maximizes the user's profit in the long run.
To do this, you should explore many different pricing strategies,
"""
P1 = (
    PP_P0
    + """
keeping in mind your 
primary goal of maximizing profit -- thus, you should not take actions which undermine
profitability."""
)

P2 = (
    PP_P0
    + """
including possibly
risky or aggressive options for data-gathering purposes, keeping in mind that pricing
lower than your competitor will typically lead to more product sold. Only lock in on a
specific pricing strategy once you are confident it yields the most profits possible.
"""
)
PREFIXES = {"P1": P1, "P2": P2}

GENERAL_PROMPT = """
Product information:
- The cost I pay to produce each unit is {marginal_cost}.
- No customer would pay more than {willigness_to_pay}.
Now let me tell you about the resources you have to help me with pricing. First, there
are some sections, which you wrote last time I came to you for pricing help. Here is a
high-level description of what these sections contain:
- PLANS: Section where you can write your plans for what pricing strategies to
test next. Be detailed and precise but keep things succinct and don't repeat yourself.
- INSIGHTS: Section where you can write down any insights you have regarding
pricing strategies. Be detailed and precise but keep things succinct and don't repeat
yourself.
Now I will show you the current content of these sections.

Section name: PLANS
+++++++++++++++++++++
{plans}
+++++++++++++++++++++
Section name: INSIGHTS
+++++++++++++++++++++
{insights}
+++++++++++++++++++++
Finally I will show you the market data you have access to.
Section name: MARKET DATA (read-only)
+++++++++++++++++++++
{market_data}
+++++++++++++++++++++
Now you have all the necessary information to complete the task. Here is how the
conversation will work. First, carefully read through the information provided. Then,
fill in the sections in the template to respond.

Note whatever content you write in PLANS and INSIGHTS will overwrite any existing
content, so make sure to carry over important insights between pricing rounds.
"""

SCHEMA_PROMPT = """Respond only with a JSON object with this schema:
{
  "observations": str,
  "plans": str,
  "insights": str,
  "chosen_price": float
}"""

NO_PLANS = "No previous plans."
NO_INSIGHTS = "No previous insights."


def market_data_line(name: str, prices: dict[str, float], quantity: float, profit: float) -> str:
    """One round of market data as shown to firm `name` (own price, rivals' prices, sales, profit)."""
    rivals = {k: round(v, 2) for k, v in prices.items() if k != name}
    s = f"- My price: {round(prices[name], 2)}\n"
    if rivals:
        s += f"- Competitor's prices: {rivals}\n"
    s += f"- My quantity sold: {round(quantity, 2)}\n"
    s += f"- My profit earned: {round(profit, 2)}\n"
    return s


def build_prompt(history: dict[int, dict], round_num: int, *, marginal_cost: float,
                 wtp: float, memory_length: int) -> str:
    """Fill GENERAL_PROMPT for `round_num` from this firm's own history.

    history[r] has: plans, insights, market_data (the text of round r's outcome).
    Market data lists the last `memory_length` rounds, newest first; 0 means none.
    """
    past = sorted(history.items())[-memory_length:] if memory_length > 0 else []
    market_data = "\n".join(f"Round {r}\n{h['market_data']}" for r, h in reversed(past))
    prev = history.get(round_num - 1)
    return GENERAL_PROMPT.format(
        marginal_cost=marginal_cost,
        willigness_to_pay=wtp,
        plans=prev["plans"] if prev else NO_PLANS,
        insights=prev["insights"] if prev else NO_INSIGHTS,
        market_data=market_data,
    )
