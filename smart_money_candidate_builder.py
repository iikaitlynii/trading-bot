"""Build wallet-candidate metrics from our own forward-tested public observations.

This does NOT discover or recommend wallets to copy. It only aggregates wallets
already observed by the read-only research pipeline and measures their 24h outcomes.
No keys, signing, transactions, or real-money actions exist here.
"""

import csv
import os
from collections import defaultdict

DATA_DIR = "smart_money"
OBS = os.path.join(DATA_DIR, "observations.csv")
OUTCOMES = os.path.join(DATA_DIR, "outcomes.csv")
CANDIDATES = os.path.join(DATA_DIR, "wallet_candidates.csv")
FIELDS = [
    "wallet_label", "public_address", "samples", "win_rate_pct",
    "avg_forward_return_pct", "consistency_pct", "liquidity_quality",
]


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def safe_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    observations = read_csv(OBS)
    outcomes = read_csv(OUTCOMES)

    obs_by_id = {r.get("observation_id", ""): r for r in observations if r.get("observation_id")}
    groups = defaultdict(list)

    # Use only 24h outcomes so each observation contributes once.
    for outcome in outcomes:
        if str(outcome.get("horizon_hours", "")) != "24":
            continue
        obs = obs_by_id.get(outcome.get("observation_id", ""))
        if not obs:
            continue
        address = (obs.get("wallet_address") or obs.get("wallet") or "").strip()
        label = (obs.get("wallet_label") or obs.get("source_label") or "unknown").strip()
        # Older observations may not carry the raw address. Do not invent one.
        if not address:
            address = label if len(label) >= 32 else ""
        if not address:
            continue
        groups[(label, address)].append((outcome, obs))

    rows = []
    for (label, address), samples in groups.items():
        returns = [safe_float(o.get("return_pct")) for o, _ in samples]
        wins = sum(r > 0 for r in returns)
        avg_return = sum(returns) / len(returns) if returns else 0.0

        # Consistency rewards outcomes near the wallet's own average rather than
        # one huge outlier. It is descriptive research, not a profit prediction.
        if len(returns) > 1:
            mean = avg_return
            variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
            dispersion = variance ** 0.5
            consistency = max(0.0, min(100.0, 100.0 - dispersion * 5.0))
        else:
            consistency = 0.0

        liq = [safe_float(o.get("liquidity_usd")) for o, _ in samples]
        median_liq = sorted(liq)[len(liq) // 2] if liq else 0.0
        if median_liq >= 1_000_000:
            liquidity_quality = 90
        elif median_liq >= 250_000:
            liquidity_quality = 75
        elif median_liq >= 50_000:
            liquidity_quality = 60
        elif median_liq >= 10_000:
            liquidity_quality = 45
        else:
            liquidity_quality = 20

        rows.append({
            "wallet_label": label,
            "public_address": address,
            "samples": len(returns),
            "win_rate_pct": round(wins / len(returns) * 100, 2) if returns else 0,
            "avg_forward_return_pct": round(avg_return, 4),
            "consistency_pct": round(consistency, 2),
            "liquidity_quality": liquidity_quality,
        })

    rows.sort(key=lambda r: (-r["samples"], -r["win_rate_pct"], r["wallet_label"]))
    with open(CANDIDATES, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print("FORWARD-TESTED WALLET CANDIDATE BUILDER")
    print("24h observations aggregated:", sum(r["samples"] for r in rows))
    print("Wallet candidates with evidence:", len(rows))
    print("No wallet is automatically copied, promoted, or given trading permissions.")


if __name__ == "__main__":
    main()
