from __future__ import annotations

import time
from dataclasses import dataclass

import requests

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
FALLBACK_BASE_URL = "https://external-api.kalshi.com/trade-api/v2"

HEADERS = {"User-Agent": "arb-research-project/1.0"}


@dataclass
class KalshiMarket:
    ticker: str
    event_ticker: str
    title: str
    yes_bid: float | None   # cents, 0-100
    yes_ask: float | None
    no_bid: float | None
    no_ask: float | None
    volume: int
    status: str
    close_time: str

    @property
    def yes_implied_prob(self) -> float | None:
        if self.yes_ask is None:
            return None
        return self.yes_ask / 100.0

    @property
    def no_implied_prob(self) -> float | None:
        if self.no_ask is None:
            return None
        return self.no_ask / 100.0


def _get(session: requests.Session, base: str, path: str, params: dict) -> dict:
    resp = session.get(f"{base}{path}", params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_open_markets(limit_pages: int = 5, page_size: int = 200) -> list[KalshiMarket]:
    session = requests.Session()
    markets: list[KalshiMarket] = []
    cursor = None

    for base in (BASE_URL, FALLBACK_BASE_URL):
        try:
            for _ in range(limit_pages):
                params = {"limit": page_size, "status": "open"}
                if cursor:
                    params["cursor"] = cursor
                data = _get(session, base, "/markets", params)
                for m in data.get("markets", []):
                    markets.append(
                        KalshiMarket(
                            ticker=m.get("ticker", ""),
                            event_ticker=m.get("event_ticker", ""),
                            title=m.get("title", ""),
                            yes_bid=m.get("yes_bid"),
                            yes_ask=m.get("yes_ask"),
                            no_bid=m.get("no_bid"),
                            no_ask=m.get("no_ask"),
                            volume=m.get("volume", 0),
                            status=m.get("status", ""),
                            close_time=m.get("close_time", ""),
                        )
                    )
                cursor = data.get("cursor")
                if not cursor:
                    break
                time.sleep(0.2)  # be a polite citizen of the API
            return markets  # success on this host, don't try the fallback
        except requests.RequestException as e:
            print(f"[kalshi] host {base} failed ({e}), trying fallback...")
            markets = []
            continue

    raise RuntimeError("Could not reach any Kalshi API host")


if __name__ == "__main__":
    ms = fetch_open_markets(limit_pages=1)
    print(f"Fetched {len(ms)} Kalshi markets")
    for m in ms[:5]:
        print(m.ticker, m.title, m.yes_implied_prob)
