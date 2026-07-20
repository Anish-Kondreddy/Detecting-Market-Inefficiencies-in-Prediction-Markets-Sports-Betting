from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone

from arbitrage import ArbResult, scan_for_arbs
from kalshi_client import fetch_open_markets
from matcher import find_matches
from polymarket_client import fetch_active_markets


def print_report(arbs: list[ArbResult], top_n: int = 20) -> None:
    if not arbs:
        print("No matched events found at all -- check API connectivity "
              "or loosen --min-similarity.")
        return

    true_arbs = [a for a in arbs if a.is_true_arb]
    print(f"\nMatched events analyzed: {len(arbs)}")
    print(f"True arbitrage opportunities (net of assumed fees): {len(true_arbs)}\n")

    print(f"{'Event (Kalshi title)':55s} {'Kalshi':>8s} {'Poly':>8s} {'Raw spread':>11s} {'Net edge':>9s}")
    print("-" * 100)
    for a in arbs[:top_n]:
        title = a.event.kalshi_market.title[:53]
        print(
            f"{title:55s} {a.kalshi_price:8.3f} {a.polymarket_price:8.3f} "
            f"{a.raw_spread:11.3%} {a.net_edge:9.3%}"
        )


def save_csv(arbs: list[ArbResult], path: str) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp_utc", "kalshi_ticker", "kalshi_title", "polymarket_slug",
            "polymarket_question", "match_similarity", "kalshi_yes_price",
            "polymarket_yes_price", "raw_spread", "net_edge", "is_true_arb",
            "direction", "kalshi_stake_fraction", "polymarket_stake_fraction",
        ])
        ts = datetime.now(timezone.utc).isoformat()
        for a in arbs:
            writer.writerow([
                ts,
                a.event.kalshi_market.ticker,
                a.event.kalshi_market.title,
                a.event.polymarket_market.slug,
                a.event.polymarket_market.question,
                round(a.event.similarity, 1),
                round(a.kalshi_price, 4),
                round(a.polymarket_price, 4),
                round(a.raw_spread, 4),
                round(a.net_edge, 4),
                a.is_true_arb,
                a.direction,
                round(a.kalshi_stake_fraction, 4),
                round(a.polymarket_stake_fraction, 4),
            ])
    print(f"\nSaved {len(arbs)} rows to {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Kalshi vs Polymarket arb scanner")
    parser.add_argument("--min-similarity", type=float, default=78.0,
                         help="Min fuzzy title-match score (0-100) to treat two markets as the same event")
    parser.add_argument("--min-spread", type=float, default=0.0,
                         help="Only report matches with raw spread >= this (e.g. 0.02 = 2%%)")
    parser.add_argument("--kalshi-pages", type=int, default=5)
    parser.add_argument("--polymarket-max", type=int, default=1000)
    parser.add_argument("--out", type=str, default="arb_scan_results.csv")
    args = parser.parse_args()

    print("Fetching Kalshi markets...")
    kalshi_markets = fetch_open_markets(limit_pages=args.kalshi_pages)
    print(f"  -> {len(kalshi_markets)} open Kalshi markets")

    print("Fetching Polymarket markets...")
    polymarket_markets = fetch_active_markets(max_markets=args.polymarket_max)
    print(f"  -> {len(polymarket_markets)} active Polymarket markets")

    print("Matching events across platforms...")
    matches = find_matches(kalshi_markets, polymarket_markets, min_similarity=args.min_similarity)
    print(f"  -> {len(matches)} candidate matches")

    print("Scanning for arbitrage...")
    arbs = scan_for_arbs(matches, min_raw_spread=args.min_spread)

    print_report(arbs)
    save_csv(arbs, args.out)


if __name__ == "__main__":
    main()
