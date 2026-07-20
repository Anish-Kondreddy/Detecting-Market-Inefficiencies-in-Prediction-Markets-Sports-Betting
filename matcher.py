from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from kalshi_client import KalshiMarket
from polymarket_client import PolymarketMarket

# Words that add noise to similarity scoring without adding meaning
STOPWORDS = {
    "will", "the", "a", "an", "be", "by", "in", "on", "at", "to", "of",
    "is", "are", "for", "before", "after", "than", "or", "and",
}


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = [t for t in text.split() if t not in STOPWORDS]
    return " ".join(tokens)


@dataclass
class MatchedEvent:
    kalshi_market: KalshiMarket
    polymarket_market: PolymarketMarket
    similarity: float   # 0-100, token-set ratio

    @property
    def kalshi_yes_prob(self) -> float | None:
        return self.kalshi_market.yes_implied_prob

    @property
    def polymarket_yes_prob(self) -> float | None:
        return self.polymarket_market.yes_implied_prob


def find_matches(
    kalshi_markets: list[KalshiMarket],
    polymarket_markets: list[PolymarketMarket],
    min_similarity: float = 78.0,
    min_volume_kalshi: int = 0,
    min_volume_polymarket: float = 0.0,
) -> list[MatchedEvent]:
    matches: list[MatchedEvent] = []

    k_filtered = [k for k in kalshi_markets if k.volume >= min_volume_kalshi and k.yes_ask is not None]
    p_filtered = [p for p in polymarket_markets if p.volume >= min_volume_polymarket and p.yes_implied_prob is not None]

    k_normalized = [(k, _normalize(k.title)) for k in k_filtered]
    p_normalized = [(p, _normalize(p.question)) for p in p_filtered]

    for k_market, k_text in k_normalized:
        best_score = 0.0
        best_p = None
        for p_market, p_text in p_normalized:
            score = fuzz.token_set_ratio(k_text, p_text)
            if score > best_score:
                best_score = score
                best_p = p_market

        if best_p is not None and best_score >= min_similarity:
            matches.append(MatchedEvent(k_market, best_p, best_score))

    matches.sort(key=lambda m: m.similarity, reverse=True)
    return matches
