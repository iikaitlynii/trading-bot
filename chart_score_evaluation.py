"""Summarize observed chart scores and subsequent paper-research outcomes."""
import csv
import os
from collections import defaultdict
from statistics import mean, median

SOURCE = "paper/chart_outcomes.csv"
OUTPUT = "paper/chart_score_evaluation.csv"
REPORT = "paper/chart_score_report.txt"
FIELDS = ["horizon_sessions", "score_band", "observations", "starting_sessions", "mean_return_pct", "median_return_pct", "positive_pct"]

def main():
    groups = defaultdict(list)
    if os.path.exists(SOURCE):
        with open(SOURCE, newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                try:
                    score = float(row["evidence_score"])
                    change = float(row["return_pct"])
                except (ValueError, KeyError, TypeError):
                    continue
                if not (0 <= score <= 100 and -100 <= change <= 100000):
                    continue
                horizon = row.get("horizon_sessions", "")
                if horizon not in ("1", "5", "20"):
                    continue
                band = "high" if score >= 70 else "medium" if score >= 50 else "low"
                groups[(horizon, band)].append((change, row.get("market_session", "")))
    rows = []
    lines = ["CHART SCORE EVALUATION — SIMULATED RESEARCH ONLY",
             "Observations may overlap and are not independent. These are descriptive results, not predictions.", ""]
    for horizon in ("1", "5", "20"):
        lines.append(f"{horizon}-session outcomes:")
        for band in ("low", "medium", "high"):
            values = groups[(horizon, band)]
            returns = [value for value, _ in values]
            count = len(returns)
            sessions = len({session for _, session in values if session})
            row = {"horizon_sessions": horizon, "score_band": band, "observations": count,
                   "starting_sessions": sessions,
                   "mean_return_pct": round(mean(returns), 4) if count else "",
                   "median_return_pct": round(median(returns), 4) if count else "",
                   "positive_pct": round(100 * sum(value > 0 for value in returns) / count, 2) if count else ""}
            rows.append(row)
            status = "early data" if count < 30 or sessions < 20 else "descriptive sample"
            lines.append(f"  {band}: {count} observations, {sessions} starting sessions; mean {row['mean_return_pct']}%; {status}")
        lines.append("")
    lines.append("Do not change trading rules based on these preliminary results.")
    os.makedirs("paper", exist_ok=True)
    with open(OUTPUT, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with open(REPORT, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
