"""Build research observations from public Solana wallet events.

Read-only research bridge:
- Reads public wallet balance-change events.
- Fetches public market data only.
- Never reads private keys, signs transactions, or submits trades.
- Skips events when trustworthy price/liquidity data is unavailable.
"""

import csv
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone

EVENTS_FILE = "smart_money/wallet_events.csv"
OBS_FILE = "smart_money/observations.csv"
WATCHLIST_FILE = "smart_money/wallet_watchlist.json"
DEX_URL = "https://api.dexscreener.com/latest/dex/tokens/{}"
MIN_LIQUIDITY_USD = 10000.0

FIELDS = [
    "observation_id", "observed_at_utc", "source_label", "wallet_label",
    "token", "contract", "mint", "network", "entry_price_usd",
    "source_count", "wallet_quality", "wallet_consensus",
    "social_confirmation", "liquidity_quality", "momentum_confirmation",
    "risk_quality",
]


def load_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def wallet_labels():
    if not os.path.exists(WATCHLIST_FILE):
        return {}
    try:
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    labels = {}
    for item in data.get("wallets", []):
        if isinstance(item, dict) and item.get("address"):
            labels[item["address"]] = item.get("label") or item["address"][:8]
    return labels


def fetch_market(mint):
    url = DEX_URL.format(urllib.parse.quote(mint, safe=""))
    req = urllib.request.Request(url, headers={"User-Agent": "trading-bot-research/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    usable = []
    for pair in payload.get("pairs") or []:
        try:
            price = float(pair.get("priceUsd"))
            liquidity = float((pair.get("liquidity") or {}).get("usd") or 0)
        except (TypeError, ValueError):
            continue
        if price > 0:
            usable.append((liquidity, price, pair))
    if not usable:
        return None
    usable.sort(key=lambda x: x[0], reverse=True)
    liquidity, price, pair = usable[0]
    return {
        "price": price,
        "liquidity": liquidity,
        "symbol": ((pair.get("baseToken") or {}).get("symbol") or "UNKNOWN"),
    }


def liquidity_score(liquidity):
    # Conservative research-only quality bands.
    if liquidity >= 1_000_000:
        return 90
    if liquidity >= 250_000:
        return 75
    if liquidity >= 50_000:
        return 60
    if liquidity >= MIN_LIQUIDITY_USD:
        return 45
    return 20


def main():
    os.makedirs("smart_money", exist_ok=True)
    events = load_csv(EVENTS_FILE)
    existing = load_csv(OBS_FILE)
    seen = {r.get("observation_id", "") for r in existing}
    labels = wallet_labels()
    new_rows = []
    skipped = 0
    cache = {}

    for event in events:
        if event.get("direction") != "ACQUIRE":
            continue
        mint = (event.get("mint") or "").strip()
        wallet = (event.get("wallet") or "").strip()
        signature = (event.get("signature") or "").strip()
        if not mint or not wallet or not signature:
            skipped += 1
            continue

        obs_id = "|".join([signature, wallet, mint])
        if obs_id in seen:
            continue

        if mint not in cache:
            try:
                cache[mint] = fetch_market(mint)
            except Exception as exc:
                print("Public market read failed:", mint, str(exc))
                cache[mint] = None
        market = cache[mint]
        if not market or market["liquidity"] < MIN_LIQUIDITY_USD:
            skipped += 1
            continue

        liq_quality = liquidity_score(market["liquidity"])
        label = labels.get(wallet, wallet[:8])
        # Unknown qualities stay neutral rather than being invented as strong.
        row = {
            "observation_id": obs_id,
            "observed_at_utc": event.get("event_time_utc") or event.get("observed_at_utc") or datetime.now(timezone.utc).isoformat(),
            "source_label": label,
            "wallet_label": label,
            "token": market["symbol"],
            "contract": mint,
            "mint": mint,
            "network": "solana",
            "entry_price_usd": market["price"],
            "source_count": 1,
            "wallet_quality": 50,
            "wallet_consensus": 50,
            "social_confirmation": 50,
            "liquidity_quality": liq_quality,
            "momentum_confirmation": 50,
            "risk_quality": 50 if liq_quality >= 40 else 20,
        }
        new_rows.append(row)
        seen.add(obs_id)

    if new_rows:
        exists = os.path.exists(OBS_FILE)
        with open(OBS_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            if not exists:
                writer.writeheader()
            writer.writerows(new_rows)

    print("PUBLIC WALLET EVENT -> RESEARCH OBSERVATION BRIDGE")
    print("Events read:", len(events))
    print("New research observations:", len(new_rows))
    print("Skipped for missing/weak public data:", skipped)
    print("No wallet keys, signing, exchange access, or real trades are used.")


if __name__ == "__main__":
    main()
