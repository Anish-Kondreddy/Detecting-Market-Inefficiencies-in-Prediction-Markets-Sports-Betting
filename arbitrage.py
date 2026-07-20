from __future__ import annotations

from dataclasses import dataclass

from matcher import MatchedEvent

DEFAULT_KALSHI_FEE_RATE = 0.01     # ~1% of stake, rough approximation
DEFAULT_POLYMARKET_FEE_RATE = 0.00
DEFAULT_SLIPPAGE_BUFFER = 0.01     # 1 cent of cushion per leg


@dataclass
class ArbResult:
    event: MatchedEvent
    direction: str                 # "buy_yes_kalshi_no_polymarket" or reverse
    kalshi_price: float
    polymarket_price: float
    raw_spread: float              # simple probability spread, no fees
    net_edge: float                # spread after fees/slippage buffer
    is_true_arb: bool              # net_edge > 0
    kalshi_stake_fraction: float   # fraction of total stake to each leg
    polymarket_stake_fraction: float


def _stake_split(price_a: float, price_b: float) -> tuple[float, float]:
    total = price_a + price_b
    if total == 0:
        return 0.5, 0.5
    return price_a / total, price_b / total


def evaluate_match(
    match: MatchedEvent,
    kalshi_fee_rate: float = DEFAULT_KALSHI_FEE_RATE,
    polymarket_fee_rate: float = DEFAULT_POLYMARKET_FEE_RATE,
    slippage_buffer: float = DEFAULT_SLIPPAGE_BUFFER,
) -> ArbResult | None:

    k_yes = match.kalshi_yes_prob
    p_yes = match.polymarket_yes_prob
    if k_yes is None or p_yes is None:
        return None

    k_no = 1 - k_yes  # approx -- ideally use the actual NO ask, not 1-YES
    p_no = 1 - p_yes

    # Direction A: YES on Kalshi, NO on Polymarket
    cost_a = k_yes + p_no
    # Direction B: YES on Polymarket, NO on Kalshi
    cost_b = p_yes + k_no

    if cost_a <= cost_b:
        direction = "buy_yes_kalshi_no_polymarket"
        raw_cost = cost_a
        leg_prices = (k_yes, p_no)
    else:
        direction = "buy_yes_polymarket_no_kalshi"
        raw_cost = cost_b
        leg_prices = (p_yes, k_no)

    raw_spread = 1 - raw_cost

    total_fee_rate = kalshi_fee_rate + polymarket_fee_rate
    net_edge = raw_spread - total_fee_rate - slippage_buffer

    k_frac, p_frac = _stake_split(*leg_prices)

    return ArbResult(
        event=match,
        direction=direction,
        kalshi_price=k_yes,
        polymarket_price=p_yes,
        raw_spread=raw_spread,
        net_edge=net_edge,
        is_true_arb=net_edge > 0,
        kalshi_stake_fraction=k_frac,
        polymarket_stake_fraction=p_frac,
    )


def scan_for_arbs(
    matches: list[MatchedEvent],
    min_raw_spread: float = 0.0,
) -> list[ArbResult]:
    """Evaluate every matched event and return results sorted by net edge."""
    results = []
    for m in matches:
        r = evaluate_match(m)
        if r is not None and r.raw_spread >= min_raw_spread:
            results.append(r)
    results.sort(key=lambda r: r.net_edge, reverse=True)
    return results