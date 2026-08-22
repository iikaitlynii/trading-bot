"""Build wallet/KOL reputation from forward outcomes — research/paper only."""

import csv
import json
import os
from collections import defaultdict

DATA_DIR = "smart_money"
OUTCOMES_FILE = os.path.join(DATA_DIR, "outcomes.csv")
REPUTATION_FILE = os.path.join(DATA_DIR, "source_reputation.json")
MIN_SAMPLES = 10
PREFERRED_HORIZON = 24


def clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, float(x)))


def load_rows():
    if not os.path.exists(OUTCOMES_FILE):
        return []
    with open(OUTCOMES_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    rows = load_rows()
    grouped = defaultdict(list)

    # Use one consistent forward horizon so a single signal is not counted 3 times.
    for row in rows:
        try:
            horizon = int(float(row.get("horizon_hours", 0) or 0))
            ret = float(row.get("return_pct", ""))
        except (TypeError, ValueError):
            continue
        if horizon != PREFERRED_HORIZON:
            continue
        source = (row.get("source_label") or "unknown").strip()
        if not source or source == "unknown":
            continue
        grouped[source].append(ret)

    reputation = {}
    for source, returns in grouped.items():
        n = len(returns)
        wins = sum(r > 0 for r in returns)
        win_rate = 100.0 * wins / n if n else 0.0
        avg_return = sum(returns) / n if n else 0.0
        evidence = min(100.0, 100.0 * n / MIN_SAMPLES)

        # Conservative score: evidence matters, and extreme single-token returns
        # cannot dominate the reputation calculation.
        return_component = clamp(50.0 + max(-25.0, min(25.0, avg_return)) * 2.0)
        score = clamp(0.45 * win_rate + 0.35 * return_component + 0.20 * evidence)

        reputation[source] = {
            "horizon_hours": PREFERRED_HORIZON,
            "samples": n,
            "wins": wins,
            "win_rate_pct": round(win_rate, 2),
            "average_forward_return_pct": round(avg_return, 4),
            "evidence_strength_pct": round(evidence, 2),
            "reputation_score": round(score, 2),
            "status": "ESTABLISHED" if n >= MIN_SAMPLES else "INSUFFICIENT_DATA",
        }

    with open(REPUTATION_FILE, "w", encoding="utf-8") as f:
        json.dump(reputation, f, indent=2, sort_keys=True)

    print("SMART-MONEY REPUTATION UPDATE")
    print("Research/paper only — no trading actions are possible.")
    print("24h forward outcomes used:", sum(len(v) for v in grouped.values()))
    print("Sources scored:", len(reputation))
    print("Established sources:", sum(v["status"] == "ESTABLISHED" for v in reputation.values()))


if __name__ == "__main__":
    main()
