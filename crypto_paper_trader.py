import json
import os
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

TICKERS = ["DOGE-USD", "SHIB-USD", "PEPE-USD", "BONK-USD"]
STARTING_CASH = 5000.0
FAST_MA = 20
SLOW_MA = 50
REGIME_MA_DAYS = 100
MAX_WEIGHT = 0.10
MIN_CASH_RESERVE = 0.60
STATE_FILE = "crypto_paper/state.json"
JOURNAL_FILE = "crypto_paper/journal.csv"
SIGNALS_FILE = "crypto_paper/latest_signals.csv"
PERFORMANCE_FILE = "crypto_paper/performance.csv"

# Simulation only. This program never connects to a crypto exchange
# and never places real orders.


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"cash": STARTING_CASH, "positions": {}, "last_run_date": None}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    os.makedirs("crypto_paper", exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def append_csv(path, rows):
    if not rows:
        return
    os.makedirs("crypto_paper", exist_ok=True)
    df = pd.DataFrame(rows)
    exists = os.path.exists(path)
    df.to_csv(path, mode="a", header=not exists, index=False)


def get_close(ticker):
    data = yf.download(ticker, period="1y", interval="1d", auto_adjust=False, progress=False)
    close = data["Close"]
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]
    return close.dropna()


def portfolio_value(state, prices):
    value = float(state["cash"])
    for ticker, pos in state["positions"].items():
        value += float(pos["units"]) * float(prices.get(ticker, pos["entry_price"]))
    return value


def previous_value():
    if not os.path.exists(PERFORMANCE_FILE):
        return STARTING_CASH
    try:
        df = pd.read_csv(PERFORMANCE_FILE)
        return float(df.iloc[-1]["paper_value"]) if len(df) else STARTING_CASH
    except Exception:
        return STARTING_CASH


def main():
    os.makedirs("crypto_paper", exist_ok=True)
    state = load_state()
    today = datetime.now(timezone.utc).date().isoformat()

    if state.get("last_run_date") == today:
        print("Crypto paper trader already processed", today)
        return

    prices = {}
    signals = []

    for ticker in TICKERS:
        close = get_close(ticker)
        if len(close) < REGIME_MA_DAYS:
            signals.append({"date_utc": today, "ticker": ticker, "signal": "NO_DATA"})
            continue
        price = float(close.iloc[-1])
        fast = float(close.iloc[-FAST_MA:].mean())
        slow = float(close.iloc[-SLOW_MA:].mean())
        regime = float(close.iloc[-REGIME_MA_DAYS:].mean())
        bullish = price > regime and fast > slow
        prices[ticker] = price
        signals.append({
            "date_utc": today,
            "ticker": ticker,
            "close": round(price, 10),
            "ma20": round(fast, 10),
            "ma50": round(slow, 10),
            "ma100": round(regime, 10),
            "signal": "BULLISH" if bullish else "DEFENSIVE",
        })

    pd.DataFrame(signals).to_csv(SIGNALS_FILE, index=False)
    journal = []

    for row in signals:
        ticker = row["ticker"]
        if ticker in state["positions"] and row.get("signal") != "BULLISH":
            pos = state["positions"].pop(ticker)
            price = float(prices.get(ticker, pos["entry_price"]))
            proceeds = float(pos["units"]) * price
            state["cash"] += proceeds
            journal.append({"date_utc": today, "ticker": ticker, "action": "SIM_SELL", "price": price, "units": pos["units"], "reason": "defensive_or_missing_signal"})

    account_value = portfolio_value(state, prices)
    max_invested = account_value * (1 - MIN_CASH_RESERVE)
    current_invested = account_value - float(state["cash"])

    for row in signals:
        ticker = row["ticker"]
        if row.get("signal") != "BULLISH" or ticker in state["positions"] or ticker not in prices:
            continue
        available_risk_capital = max(0.0, max_invested - current_invested)
        target = min(account_value * MAX_WEIGHT, available_risk_capital, float(state["cash"]))
        if target < 25:
            continue
        price = float(prices[ticker])
        units = target / price
        state["cash"] -= target
        current_invested += target
        state["positions"][ticker] = {"units": units, "entry_price": price, "entry_date": today}
        journal.append({"date_utc": today, "ticker": ticker, "action": "SIM_BUY", "price": price, "units": units, "reason": "bullish_signal"})

    ending = portfolio_value(state, prices)
    prev = previous_value()
    daily_pnl = ending - prev
    daily_return = (ending / prev - 1) * 100 if prev else 0.0
    total_return = (ending / STARTING_CASH - 1) * 100

    state["last_run_date"] = today
    save_state(state)
    append_csv(JOURNAL_FILE, journal)
    append_csv(PERFORMANCE_FILE, [{
        "date_utc": today,
        "paper_value": round(ending, 2),
        "cash": round(float(state["cash"]), 2),
        "open_positions": len(state["positions"]),
        "daily_pnl": round(daily_pnl, 2),
        "daily_return_pct": round(daily_return, 4),
        "total_return_pct": round(total_return, 4),
    }])

    print("MEMECOIN PAPER TRADER — SIMULATION ONLY")
    print("UTC date:", today)
    print("Ending paper value: $", round(ending, 2))
    print("Cash: $", round(float(state["cash"]), 2))
    print("Open simulated positions:", list(state["positions"].keys()))
    print("New simulated actions:", len(journal))
    print("No exchange orders were sent.")


if __name__ == "__main__":
    main()
