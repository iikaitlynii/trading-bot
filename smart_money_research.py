"""Smart-money/KOL research layer — simulation only.

This module does NOT connect to wallets, exchanges, Axiom, or brokerage accounts and
cannot execute trades. It provides the scoring/data structure we can later feed with
public, read-only observations and evaluate against subsequent market performance.
"""

import csv
import json
import os
from datetime import datetime, timezone

DATA_DIR = "smart_money"
OBSERVATIONS_FILE = os.path.join(DATA_DIR, "observations.csv")
SCORES_FILE = os.path.join(DATA_DIR, "latest_scores.csv")
REPUTATION_FILE = os.path.join(DATA_DIR, "source_reputation.json")

# Research weights. These are intentionally simple until forward data exists.
WEIGHTS = {
    "wallet_quality": 0.30,
    "wallet_consensus": 0.20,
    "social_confirmation": 0.15,
    "liquidity_quality": 0.15,
    "momentum_confirmation": 0.10,
    "risk_quality": 0.10,
}


def clamp(value, low=0.0, high=100.0):
    return max(low, min(high, float(value)))


def load_reputation():
    if not os.path.exists(REPUTATION_FILE):
        return {}
    with open(REPUTATION_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def score_observation(row):
    components = {key: clamp(row.get(key, 0)) for key in WEIGHTS}
    score = sum(components[key] * weight for key, weight in WEIGHTS.items())

    # Hard research vetoes: weak liquidity or severe risk should not receive a
    # high-confidence label even when social/wallet activity looks exciting.
    if components["liquidity_quality"] < 40 or components["risk_quality"] < 40:
        label = "REJECT"
    elif score >= 75:
        label = "HIGH_INTEREST"
    elif score >= 60:
        label = "WATCH"
    else:
        label = "LOW_INTEREST"
    return round(score, 2), label


def read_observations():
    if not os.path.exists(OBSERVATIONS_FILE):
        return []
    with open(OBSERVATIONS_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    rows = read_observations()
    now = datetime.now(timezone.utc).isoformat()
    scored = []

    for row in rows:
        score, label = score_observation(row)
        scored.append({
            "evaluated_at_utc": now,
            "token": row.get("token", "UNKNOWN"),
            "contract": row.get("contract", ""),
            "network": row.get("network", ""),
            "source_count": row.get("source_count", "0"),
            "signal_score": score,
            "research_label": label,
        })

    fields = [
        "evaluated_at_utc", "token", "contract", "network", "source_count",
        "signal_score", "research_label"
    ]
    with open(SCORES_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(scored)

    print("SMART-MONEY / KOL RESEARCH ENGINE")
    print("Simulation/research only — no trades or wallet actions can be executed.")
    print("Observations evaluated:", len(scored))
    print("High-interest signals:", sum(r["research_label"] == "HIGH_INTEREST" for r in scored))
    print("Watch signals:", sum(r["research_label"] == "WATCH" for r in scored))
    print("Rejected signals:", sum(r["research_label"] == "REJECT" for r in scored))


if __name__ == "__main__":
    main()
