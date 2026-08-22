"""Wallet/KOL source reputation research — simulation only.

This module scores tracked public sources from labeled historical outcomes. It does not
connect to exchanges, wallets, Axiom, or brokerage accounts and cannot execute trades.
"""

import csv
import json
import os

DATA_DIR = "smart_money"
OUTCOMES_FILE = os.path.join(DATA_DIR, "source_outcomes.csv")
REPUTATION_FILE = os.path.join(DATA_DIR, "source_reputation.json")
MIN_SAMPLES = 10


def clamp(value, low=0.0, high=100.0):
    return max(low, min(high, float(value)))


def load_outcomes():
    if not os.path.exists(OUTCOMES_FILE):
        return []
    with open(OUTCOMES_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_reputation(rows):
    grouped = {}
    for row in rows:
        source = row.get("source", "").strip()
        if not source:
            continue
        try:
            ret = float(row.get("forward_return_pct", 0) or 0)
        except ValueError:
            continue
        item = grouped.setdefault(source, {"samples": 0, "wins": 0, "sum_return": 0.0, "sum_abs_return": 0.0})
        item["samples"] += 1
        item["wins"] += 1 if ret > 0 else 0
        item["sum_return"] += ret
        item["sum_abs_return"] += abs(ret)

    reputation = {}
    for source, stats in grouped.items():
        n = stats["samples"]
        win_rate = stats["wins"] / n * 100 if n else 0.0
        avg_return = stats["sum_return"] / n if n else 0.0
        consistency = min(100.0, n / MIN_SAMPLES * 100.0)
        # Conservative research score: require both evidence count and useful outcomes.
        raw = 0.45 * win_rate + 0.35 * clamp(50 + avg_return * 2) + 0.20 * consistency
        score = clamp(raw)
        reputation[source] = {
            "samples": n,
            "win_rate_pct": round(win_rate, 2),
            "average_forward_return_pct": round(avg_return, 2),
            "evidence_strength_pct": round(consistency, 2),
            "reputation_score": round(score, 2),
            "status": "ESTABLISHED" if n >= MIN_SAMPLES else "INSUFFICIENT_DATA",
        }
    return reputation


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    rows = load_outcomes()
    reputation = build_reputation(rows)
    with open(REPUTATION_FILE, "w", encoding="utf-8") as f:
        json.dump(reputation, f, indent=2, sort_keys=True)

    print("SOURCE REPUTATION RESEARCH")
    print("Simulation/research only — no trading actions are possible.")
    print("Labeled outcomes:", len(rows))
    print("Sources scored:", len(reputation))
    print("Established sources:", sum(v["status"] == "ESTABLISHED" for v in reputation.values()))


if __name__ == "__main__":
    main()
