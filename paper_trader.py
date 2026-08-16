import json
import os
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN"]
STARTING_CASH = 10000.0
REGIME_MA_DAYS = 200
FAST_MA = 20
SLOW_MA = 50
MAX_WEIGHT = 0.20
STATE_FILE = "paper/state.json"
JOURNAL_FILE = "paper/journal.csv"
SIGNALS_FILE = "paper/latest_signals.csv"

# Safety: this program NEVER sends an order to a brokerage.
# It only reads market data and records simulated decisions.


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"cash": STARTING_CASH, "positions": {}, "last_run_date": None}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    os.makedirs("paper", exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def append_journal(rows):
    if not rows:
        return
    os.makedirs("paper", exist_ok=True)
    df = pd.DataFrame(rows)
    exists = os.path.exists(JOURNAL_FILE)
    df.to_csv(JOURNAL_FILE, mode="a", header=not exists, index=False)


def get_data(ticker):
    data = yf.download(ticker, period="2y", interval="1d", auto_adjust=False, progress=False)
    close = data["Close"]
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]
    return close.dropna()


def portfolio_value(state, prices):
    value = float(state["cash"])
    for ticker, pos in state["positions"].items():
        value += float(pos["shares"]) * float(prices.get(ticker, pos["entry_price"]))
    return value


def main():
    os.makedirs("paper", exist_ok=True)
    state = load_state()
    today = datetime.now(timezone.utc).date().isoformat()

    # Prevent duplicate simulated trading if the workflow is re-run the same UTC day.
    if state.get("last_run_date") == today:
        print("Paper trader already processed", today)
        return

    market = {}
    signals = []
    for ticker in TICKERS:
        close = get_data(ticker)
        if len(close) < REGIME_MA_DAYS:
            continue
        price = float(close.iloc[-1])
        fast = float(close.iloc[-FAST_MA:].mean())
        slow = float(close.iloc[-SLOW_MA:].mean())
        regime = float(close.iloc[-REGIME_MA_DAYS:].mean())
        market[ticker] = price
        bullish = price > regime and fast > slow
        signals.append({
            "date_utc": today,
            "ticker": ticker,
            "close": round(price, 4),
            "ma20": round(fast, 4),
            "ma50": round(slow, 4),
            "ma200": round(regime, 4),
            "signal": "BULLISH" if bullish else "DEFENSIVE",
        })

    pd.DataFrame(signals).to_csv(SIGNALS_FILE, index=False)
    starting_value = portfolio_value(state, market)
    journal = []

    # Exits first.
    for row in signals:
        ticker = row["ticker"]
        if ticker in state["positions"] and row["signal"] == "DEFENSIVE":
            pos = state["positions"].pop(ticker)
            proceeds = float(pos["shares"]) * float(row["close"])
            state["cash"] += proceeds
            journal.append({"date_utc": today, "ticker": ticker, "action": "SIM_SELL", "price": row["close"], "shares": pos["shares"], "reason": "defensive_signal"})

    # Entries use a conservative 20% maximum target per stock.
    current_value = portfolio_value(state, market)
    for row in signals:
        ticker = row["ticker"]
        if row["signal"] != "BULLISH" or ticker in state["positions"]:
            continue
        target_dollars = current_value * MAX_WEIGHT
        amount = min(float(state["cash"]), target_dollars)
        if amount < 50:
            continue
        shares = amount / float(row["close"])
        state["cash"] -= amount
        state["positions"][ticker] = {"shares": shares, "entry_price": float(row["close"]), "entry_date": today}
        journal.append({"date_utc": today, "ticker": ticker, "action": "SIM_BUY", "price": row["close"], "shares": shares, "reason": "bullish_signal"})

    state["last_run_date"] = today
    save_state(state)
    append_journal(journal)
    ending_value = portfolio_value(state, market)

    print("LIVE-DATA PAPER TRADER — SIMULATION ONLY")
    print("UTC date:", today)
    print("Starting paper value: $", round(starting_value, 2))
    print("Ending paper value: $", round(ending_value, 2))
    print("Cash: $", round(float(state["cash"]), 2))
    print("Open simulated positions:", list(state["positions"].keys()))
    print("New simulated actions:", len(journal))
    print("No brokerage orders were sent.")


if __name__ == "__main__":
    main()
