"""Forward outcome tracker for smart-money/KOL research — simulation only.

Reads research observations, fetches PUBLIC token prices, and records what happened
AFTER each signal. It cannot sign transactions, move funds, connect to an exchange,
or place trades.
"""

import csv
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone

DATA_DIR = "smart_money"
OBSERVATIONS_FILE = os.path.join(DATA_DIR, "observations.csv")
OUTCOMES_FILE = os.path.join(DATA_DIR, "outcomes.csv")

DEXSCREENER_TOKEN_URL = "https://api.dexscreener.com/latest/dex/tokens/{}"
HORIZONS_HOURS = [1, 24, 168]  # 1 hour, 1 day, 7 days


def parse_time(value):
    if not value:
        return None
    value = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def observation_id(row):
    existing = row.get("observation_id", "").strip()
    if existing:
        return existing
    parts = [
        row.get("observed_at_utc", ""),
        row.get("source_label", row.get("wallet_label", "unknown")),
        row.get("contract", row.get("mint", "")),
    ]
    return "|".join(parts)


def fetch_public_price(contract):
    contract = (contract or "").strip()
    if not contract:
        return None, None
    url = DEXSCREENER_TOKEN_URL.format(urllib.parse.quote(contract, safe=""))
    req = urllib.request.Request(url, headers={"User-Agent": "trading-bot-research/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    pairs = payload.get("pairs") or []
    usable = []
    for pair in pairs:
        price = safe_float(pair.get("priceUsd"))
        liquidity = safe_float((pair.get("liquidity") or {}).get("usd")) or 0.0
        if price is not None and price > 0:
            usable.append((liquidity, price, pair))
    if not usable:
        return None, None

    # Prefer the most liquid available market to reduce noisy price observations.
    usable.sort(key=lambda x: x[0], reverse=True)
    _, price, pair = usable[0]
    return price, {
        "dex": pair.get("dexId", ""),
        "pair_address": pair.get("pairAddress", ""),
        "liquidity_usd": round(safe_float((pair.get("liquidity") or {}).get("usd")) or 0.0, 2),
    }


def existing_keys(rows):
    return {(r.get("observation_id", ""), r.get("horizon_hours", "")) for r in rows}


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    observations = load_csv(OBSERVATIONS_FILE)
    existing = load_csv(OUTCOMES_FILE)
    seen = existing_keys(existing)
    now = datetime.now(timezone.utc)
    new_rows = []

    if not observations:
        print("SMART-MONEY OUTCOME TRACKER: no observations available yet.")
        print("Research-only tracker is ready and will evaluate future observations.")
        return

    price_cache = {}
    for row in observations:
        obs_id = observation_id(row)
        observed = parse_time(row.get("observed_at_utc") or row.get("timestamp_utc"))
        contract = (row.get("contract") or row.get("mint") or "").strip()
        entry_price = safe_float(row.get("entry_price_usd") or row.get("price_usd"))
        if not observed or not contract or entry_price is None or entry_price <= 0:
            continue

        age_hours = (now - observed).total_seconds() / 3600.0
        due = [h for h in HORIZONS_HOURS if age_hours >= h and (obs_id, str(h)) not in seen]
        if not due:
            continue

        if contract not in price_cache:
            try:
                price_cache[contract] = fetch_public_price(contract)
            except Exception as exc:
                print("Price read failed for", contract, str(exc))
                price_cache[contract] = (None, None)
        current_price, market = price_cache[contract]
        if current_price is None:
            continue

        change_pct = (current_price / entry_price - 1.0) * 100.0
        for horizon in due:
            new_rows.append({
                "observation_id": obs_id,
                "source_label": row.get("source_label", row.get("wallet_label", "unknown")),
                "token": row.get("token", "UNKNOWN"),
                "contract": contract,
                "network": row.get("network", "solana"),
                "observed_at_utc": observed.isoformat(),
                "evaluated_at_utc": now.isoformat(),
                "horizon_hours": horizon,
                "entry_price_usd": entry_price,
                "outcome_price_usd": current_price,
                "return_pct": round(change_pct, 4),
                "profitable": "YES" if change_pct > 0 else "NO",
                "dex": (market or {}).get("dex", ""),
                "pair_address": (market or {}).get("pair_address", ""),
                "liquidity_usd": (market or {}).get("liquidity_usd", ""),
            })
            seen.add((obs_id, str(horizon)))

    if new_rows:
        fields = [
            "observation_id", "source_label", "token", "contract", "network",
            "observed_at_utc", "evaluated_at_utc", "horizon_hours",
            "entry_price_usd", "outcome_price_usd", "return_pct", "profitable",
            "dex", "pair_address", "liquidity_usd"
        ]
        exists = os.path.exists(OUTCOMES_FILE)
        with open(OUTCOMES_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            if not exists:
                writer.writeheader()
            writer.writerows(new_rows)

    print("SMART-MONEY FORWARD OUTCOME TRACKER")
    print("Simulation/research only — no trades were sent.")
    print("Observations available:", len(observations))
    print("New forward outcomes recorded:", len(new_rows))
    print("Horizons tracked: 1h, 24h, 7d")


if __name__ == "__main__":
    main()
