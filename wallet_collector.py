"""Read-only Solana wallet research collector.

This module reads PUBLIC blockchain data only. It does not use private keys, cannot
sign transactions, cannot move funds, and cannot execute trades.
"""

import csv
import json
import os
import time
import urllib.request
from datetime import datetime, timezone

RPC_URL = "https://api.mainnet-beta.solana.com"
WATCHLIST_FILE = "smart_money/wallet_watchlist.json"
STATE_FILE = "smart_money/wallet_state.json"
EVENTS_FILE = "smart_money/wallet_events.csv"


def rpc_call(method, params):
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }).encode("utf-8")
    req = urllib.request.Request(
        RPC_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if "error" in result:
        raise RuntimeError(result["error"])
    return result.get("result")


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, sort_keys=True)


def normalize_watchlist(raw):
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw.get("solana_wallets", [])
    return []


def append_events(rows):
    if not rows:
        return
    os.makedirs(os.path.dirname(EVENTS_FILE), exist_ok=True)
    exists = os.path.exists(EVENTS_FILE)
    fields = ["observed_at_utc", "wallet_label", "wallet", "mint", "previous_amount", "current_amount", "change", "event"]
    with open(EVENTS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def get_token_balances(wallet):
    result = rpc_call(
        "getTokenAccountsByOwner",
        [wallet, {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"}, {"encoding": "jsonParsed"}],
    )
    balances = {}
    for item in (result or {}).get("value", []):
        info = item["account"]["data"]["parsed"]["info"]
        mint = info["mint"]
        amount = float(info["tokenAmount"].get("uiAmount") or 0.0)
        balances[mint] = balances.get(mint, 0.0) + amount
    return balances


def main():
    os.makedirs("smart_money", exist_ok=True)
    watchlist = normalize_watchlist(load_json(WATCHLIST_FILE, {"solana_wallets": []}))
    state = load_json(STATE_FILE, {})
    now = datetime.now(timezone.utc).isoformat()
    events = []

    if not watchlist:
        print("WALLET COLLECTOR: no public wallets configured yet.")
        print("Research-only collector is ready; add public addresses under solana_wallets in smart_money/wallet_watchlist.json.")
        return

    for entry in watchlist:
        if isinstance(entry, str):
            wallet = entry.strip()
            label = "unlabeled"
        else:
            wallet = entry.get("wallet", "").strip()
            label = entry.get("label", "unlabeled")
        if not wallet:
            continue
        try:
            current = get_token_balances(wallet)
        except Exception as exc:
            print("Wallet read failed:", label, str(exc))
            continue

        previous = state.get(wallet, {}).get("balances", {})
        all_mints = set(previous) | set(current)
        for mint in sorted(all_mints):
            old = float(previous.get(mint, 0.0))
            new = float(current.get(mint, 0.0))
            change = new - old
            if abs(change) < 1e-12:
                continue
            events.append({
                "observed_at_utc": now,
                "wallet_label": label,
                "wallet": wallet,
                "mint": mint,
                "previous_amount": old,
                "current_amount": new,
                "change": change,
                "event": "ACQUIRE_OR_INCREASE" if change > 0 else "REDUCE_OR_EXIT",
            })

        state[wallet] = {"label": label, "balances": current, "last_checked_utc": now}
        time.sleep(0.4)

    save_json(STATE_FILE, state)
    append_events(events)
    print("WALLET COLLECTOR COMPLETE")
    print("Public wallets checked:", len(watchlist))
    print("New token-balance events:", len(events))
    print("No private keys or trading permissions are used.")


if __name__ == "__main__":
    main()
