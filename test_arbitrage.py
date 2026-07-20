from kalshi_client import KalshiMarket
from polymarket_client import PolymarketMarket
from matcher import MatchedEvent
from arbitrage import evaluate_match


def make_kalshi(yes_ask_cents: float) -> KalshiMarket:
    return KalshiMarket(
        ticker="TEST-K", event_ticker="TEST", title="Test event",
        yes_bid=yes_ask_cents - 1, yes_ask=yes_ask_cents,
        no_bid=100 - yes_ask_cents - 1, no_ask=100 - yes_ask_cents,
        volume=1000, status="open", close_time="2026-12-31T00:00:00Z",
    )


def make_polymarket(yes_price: float) -> PolymarketMarket:
    return PolymarketMarket(
        id="1", question="Test event", slug="test-event", condition_id="0x1",
        outcomes=["Yes", "No"], outcome_prices=[yes_price, 1 - yes_price],
        volume=1000.0, active=True, closed=False, end_date="2026-12-31T00:00:00Z",
    )


def test_no_arb_when_prices_agree():
    # Kalshi YES at 60c, Polymarket YES at 0.60 -- combined cost of the
    # hedge (buy YES Kalshi + buy NO Polymarket) = 0.60 + 0.40 = 1.00
    match = MatchedEvent(make_kalshi(60), make_polymarket(0.60), similarity=95.0)
    result = evaluate_match(match, kalshi_fee_rate=0, polymarket_fee_rate=0, slippage_buffer=0)
    assert abs(result.raw_spread) < 1e-9
    assert not result.is_true_arb


def test_true_arb_when_kalshi_cheap():
    # Kalshi thinks YES is only worth 40c, Polymarket thinks YES is worth 60c.
    # Buy YES on Kalshi (0.40) + buy NO on Polymarket (0.40) = 0.80 cost
    # for a contract that always pays exactly $1 -> 20% raw edge.
    match = MatchedEvent(make_kalshi(40), make_polymarket(0.60), similarity=95.0)
    result = evaluate_match(match, kalshi_fee_rate=0, polymarket_fee_rate=0, slippage_buffer=0)
    assert result.raw_spread > 0.19
    assert result.is_true_arb
    assert result.direction == "buy_yes_kalshi_no_polymarket"


def test_fees_can_erase_a_thin_edge():
    # Only a 1.5% raw spread -- realistic fee + slippage assumptions should
    # wipe this out, which is the whole point of separating raw vs net edge.
    match = MatchedEvent(make_kalshi(50), make_polymarket(0.515), similarity=95.0)
    result = evaluate_match(match, kalshi_fee_rate=0.01, polymarket_fee_rate=0.0, slippage_buffer=0.01)
    assert result.raw_spread < 0.02
    assert not result.is_true_arb


def test_stake_split_sums_to_one():
    match = MatchedEvent(make_kalshi(35), make_polymarket(0.60), similarity=95.0)
    result = evaluate_match(match, kalshi_fee_rate=0, polymarket_fee_rate=0, slippage_buffer=0)
    assert abs(result.kalshi_stake_fraction + result.polymarket_stake_fraction - 1.0) < 1e-9


if __name__ == "__main__":
    test_no_arb_when_prices_agree()
    test_true_arb_when_kalshi_cheap()
    test_fees_can_erase_a_thin_edge()
    test_stake_split_sums_to_one()
    print("All tests passed.")
