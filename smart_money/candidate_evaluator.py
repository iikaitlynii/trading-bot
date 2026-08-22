"""Evaluate public wallet candidates before research watchlisting.

Research/paper-trading only. This module never signs transactions, holds keys,
or executes trades. Candidate metrics must come from public/read-only observations.
"""

import csv
import json
import os

DATA_DIR = "smart_money"
CANDIDATES_FILE = os.path.join(DATA_DIR, "wallet_candidates.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "candidate_scores.csv")

MIN_HISTORY = 10


def clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, float(x)))


def safe_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def evaluate(row):
    samples = int(safe_float(row.get("samples")))
    win_rate = clamp(row.get("win_rate_pct", 0))
    avg_return = safe_float(row.get("avg_forward_return_pct"))
    consistency = clamp(row.get("consistency_pct", 0))
    liquidity_quality = clamp(row.get("liquidity_quality", 0))

    evidence = min(100.0, samples / MIN_HISTORY * 100.0)
    return_quality = clamp(50.0 + max(-20.0, min(20.0, avg_return)) * 2.5)
    score = (
        0.30 * win_rate
        + 0.25 * return_quality
        + 0.20 * consistency
        + 0.15 * liquidity_quality
        + 0.10 * evidence
    )

    if samples < MIN_HISTORY:
        status = "MORE_DATA_NEEDED"
    elif liquidity_quality < 40:
        status = "REJECT"
    elif score >= 70:
        status = "RESEARCH_CANDIDATE"
    else:
        status = "WATCH"
    return round(score, 2), status


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(CANDIDATES_FILE):
        print("CANDIDATE EVALUATOR: no candidate file yet.")
        return

    with open(CANDIDATES_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    output = []
    for row in rows:
        score, status = evaluate(row)
        output.append({
            "wallet_label": row.get("wallet_label", "unknown"),
            "public_address": row.get("public_address", ""),
            "candidate_score": score,
            "status": status,
        })

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        fields = ["wallet_label", "public_address", "candidate_score", "status"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output)

    print("PUBLIC WALLET CANDIDATE EVALUATOR")
    print("Research/paper only — no trading actions are possible.")
    print("Candidates evaluated:", len(output))
    print("Research candidates:", sum(x["status"] == "RESEARCH_CANDIDATE" for x in output))


if __name__ == "__main__":
    main()
