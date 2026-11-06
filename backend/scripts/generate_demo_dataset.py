from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def generate(days: int = 240, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    commodities = {
        "Wheat": (2450, 0.55, 28),
        "Rice": (3150, 0.35, 35),
        "Onion": (1800, 0.95, 110),
        "Tomato": (2200, 1.15, 150),
        "Potato": (1450, 0.65, 60),
        "Mustard": (5650, 0.40, 48),
    }
    markets = [
        ("Gujarat", "Ahmedabad", "Ahmedabad APMC"),
        ("Gujarat", "Rajkot", "Rajkot APMC"),
        ("Maharashtra", "Pune", "Pune Market"),
        ("Madhya Pradesh", "Indore", "Indore Mandi"),
        ("Rajasthan", "Jaipur", "Jaipur Mandi"),
        ("Uttar Pradesh", "Lucknow", "Lucknow Mandi"),
    ]
    start = pd.Timestamp("2025-01-01")
    rows = []
    for commodity, (base, trend, seasonal) in commodities.items():
        for state, district, market in markets:
            market_factor = rng.uniform(0.94, 1.08)
            previous = base * market_factor
            for day in range(days):
                date = start + pd.Timedelta(days=day)
                wave = seasonal * np.sin(2 * np.pi * day / 90)
                drift = trend * (day / 30)
                shock = rng.normal(0, max(base * 0.008, 5))
                previous = max(100, previous + drift / 30 + (wave / 30) + shock)
                modal = round(previous, 2)
                spread = max(10, modal * rng.uniform(0.025, 0.065))
                rows.append({
                    "arrival_date": date.strftime("%Y-%m-%d"),
                    "state": state,
                    "district": district,
                    "market": market,
                    "commodity": commodity,
                    "variety": "FAQ",
                    "min_price": round(modal - spread, 2),
                    "max_price": round(modal + spread, 2),
                    "modal_price": modal,
                    "arrivals": round(float(rng.uniform(18, 260)), 2),
                    "unit": "Rs/Quintal",
                })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=240)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=ROOT / "demo_data" / "india_commodity_demo.csv")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    data = generate(args.days, args.seed)
    data.to_csv(args.output, index=False)
    print(f"Wrote {len(data):,} synthetic records to {args.output}")
