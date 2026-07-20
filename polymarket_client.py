from __future__ import annotations

import json
from dataclasses import dataclass

import requests

GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
HEADERS = {"User-Agent": "arb-research-project/1.0"}


@dataclass
class PolymarketMarket:
    id: str
    question: str
    slug: str
    condition_id: str
    outcomes: list[str]
    outcome_prices: list[float]   # aligned with `outcomes`, each in [0, 1]
    volume: float
    active: bool
    closed: bool
    end_date: str

    @property
    def yes_implied_prob(self) -> float | None:
        """Most Polymarket binary markets use outcomes ["Yes", "No"]."""
        for outcome, price in zip(self.outcomes, self.outcome_prices):
            if outcome.strip().lower() == "yes":
                return price
        return None

    @property
    def no_implied_prob(self) -> float | None:
        for outcome, price in zip(self.outcomes, self.outcome_prices):
            if outcome.strip().lower() == "no":
                return price
        return None


def _parse_market(m: dict) -> PolymarketMarket | None:
    # Gamma returns outcomes / outcomePrices as JSON-encoded strings, not
    # native arrays -- this trips up almost everyone the first time.
    try:
        outcomes = json.loads(m.get("outcomes", "[]"))
        prices = json.loads(m.get("outcomePrices", "[]"))
        prices = [float(p) for p in prices]
    except (json.JSONDecodeError, TypeError, ValueError):
        return None

    if not outcomes or not prices or len(outcomes) != len(prices):
        return None

    return PolymarketMarket(
        id=str(m.get("id", "")),
        question=m.get("question", ""),
        slug=m.get("slug", ""),
        condition_id=m.get("conditionId", ""),
        outcomes=outcomes,
        outcome_prices=prices,
        volume=float(m.get("volume", 0) or 0),
        active=bool(m.get("active", False)),
        closed=bool(m.get("closed", False)),
        end_date=m.get("endDate", ""),
    )


def fetch_active_markets(max_markets: int = 1000, page_size: int = 100) -> list[PolymarketMarket]:
    """Pull active, unresolved binary markets from Polymarket's Gamma API."""
    session = requests.Session()
    markets: list[PolymarketMarket] = []
    offset = 0

    while len(markets) < max_markets:
        params = {
            "limit": page_size,
            "offset": offset,
            "active": "true",
            "closed": "false",
        }
        resp = session.get(f"{GAMMA_BASE_URL}/markets", params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break

        for raw in batch:
            parsed = _parse_market(raw)
            if parsed is not None:
                markets.append(parsed)

        offset += page_size
        if len(batch) < page_size:
            break

    return markets[:max_markets]


if __name__ == "__main__":
    ms = fetch_active_markets(max_markets=50)
    print(f"Fetched {len(ms)} Polymarket markets")
    for m in ms[:5]:
        print(m.question, m.yes_implied_prob)
