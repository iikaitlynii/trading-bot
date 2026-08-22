"""Read-only public Solana wallet activity collector for research.

Safety boundaries:
- No private keys are read or stored.
- No transaction signing or submission exists in this module.
- No exchange, broker, or copy-trading integration exists.
- The output is research data only and is NOT used to place real trades.

Add public wallet addresses to smart_money/wallet_watchlist.json when you have
specific wallets you want to research. Empty watchlists are valid and safe.
"""

import csv
import json
import os
import time
import urllib.request
from datetime import datetime, timezone

RPC_URL = os.environ.get("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
WATCHLIST_FILE = "smart_money/wallet_watchlist.json"
EVENTS_FILE = "smart_money/wallet_events.csv"
STATE_FILE = "smart_money/wallet_collector_state.json"
MAX_SIGNATURES_PER_WALLET = 20


def rpc_call(method, params):
    body = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }).encode("utf-8")
    req = urllib.request.Request(
        RPC_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("error"):
        raise RuntimeError(payload["error"])
    return payload.get("result")


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def existing_event_keys():
    if not os.path.exists(EVENTS_FILE):
        return set()
    keys = set()
    with open(EVENTS_FILE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            keys.add((row.get("signature", ""), row.get("mint", ""), row.get("direction", "")))
    return keys


def token_balances_for_owner(meta, owner, side):
    result = {}
    balances = meta.get(side, []) or []
    for item in balances:
        if item.get("owner") != owner:
            continue
        mint = item.get("mint")
        ui = item.get("uiTokenAmount", {})
        amount = ui.get("uiAmount")
        if mint and amount is not None:
            result[mint] = result.get(mint, 0.0) + float(amount)
    return result


def extract_wallet_events(wallet, signature, tx):
    if not tx or not tx.get("meta"):
        return []
    meta = tx["meta"]
    pre = token_balances_for_owner(meta, wallet, "preTokenBalances")
    post = token_balances_for_owner(meta, wallet, "postTokenBalances")
    block_time = tx.get("blockTime")
    event_time = (
        datetime.fromtimestamp(block_time, tz=timezone.utc).isoformat()
        if block_time else datetime.now(timezone.utc).isoformat()
    )
    events = []
    for mint in sorted(set(pre) | set(post)):
        delta = post.get(mint, 0.0) - pre.get(mint, 0.0)
        if abs(delta) < 1e-12:
            continue
        events.append({
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "event_time_utc": event_time,
            "wallet": wallet,
            "signature": signature,
            "mint": mint,
            "direction": "ACQUIRE" if delta > 0 else "DISPOSE",
            "token_delta": delta,
        })
    return events


def append_events(events):
    if not events:
        return
    os.makedirs("smart_money", exist_ok=True)
    fields = [
        "observed_at_utc", "event_time_utc", "wallet", "signature",
        "mint", "direction", "token_delta"
    ]
    exists = os.path.exists(EVENTS_FILE)
    with open(EVENTS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerows(events)


def main():
    os.makedirs("smart_money", exist_ok=True)
    watchlist = load_json(WATCHLIST_FILE, {"solana_wallets": []})
    wallets = [w.strip() for w in watchlist.get("solana_wallets", []) if w.strip()]
    state = load_json(STATE_FILE, {"last_run_utc": None, "wallets_checked": 0})
    known = existing_event_keys()
    new_events = []
    errors = []

    for wallet in wallets:
        try:
            signatures = rpc_call(
                "getSignaturesForAddress",
                [wallet, {"limit": MAX_SIGNATURES_PER_WALLET}],
            ) or []
            for item in reversed(signatures):
                signature = item.get("signature")
                if not signature:
                    continue
                tx = rpc_call(
                    "getTransaction",
                    [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}],
                )
                for event in extract_wallet_events(wallet, signature, tx):
                    key = (event["signature"], event["mint"], event["direction"])
                    if key not in known:
                        known.add(key)
                        new_events.append(event)
                time.sleep(0.08)
        except Exception as exc:
            errors.append(f"{wallet}: {exc}")

    append_events(new_events)
    state.update({
        "last_run_utc": datetime.now(timezone.utc).isoformat(),
        "wallets_checked": len(wallets),
        "new_events": len(new_events),
        "errors": errors,
    })
    save_json(STATE_FILE, state)

    print("READ-ONLY SOLANA WALLET RESEARCH COLLECTOR")
    print("Wallets checked:", len(wallets))
    print("New token balance-change events:", len(new_events))
    print("Errors:", len(errors))
    if not wallets:
        print("Watchlist is empty. Add only public wallet addresses you intentionally want to research.")
    print("No transactions were signed or submitted.")


if __name__ == "__main__":
    main()
