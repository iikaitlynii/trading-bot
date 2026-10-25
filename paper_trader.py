import json
import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

from market_data import completed_history, extract_close

TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN"]
STARTING_CASH = 10000.0
REGIME_MA_DAYS = 200
FAST_MA = 20
SLOW_MA = 50
MAX_WEIGHT = 0.20
STATE_FILE = "paper/state.json"
JOURNAL_FILE = "paper/journal.csv"
SIGNALS_FILE = "paper/latest_signals.csv"
PERFORMANCE_FILE = "paper/performance.csv"
MARKET_TIMEZONE = ZoneInfo("America/New_York")
MAX_PRICE_AGE_DAYS = 4  # Allows weekends and a holiday; not an exchange calendar.

# Safety: simulation only. No brokerage connection or order submission exists.
# Legacy CSVs keep the column name "date_utc", but new rows store the actual
# latest market-session date returned by the price data.


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"cash": STARTING_CASH, "positions": {}, "last_run_date": None}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    os.makedirs("paper", exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def append_csv(path, rows):
    if not rows:
        return
    os.makedirs("paper", exist_ok=True)
    pd.DataFrame(rows).to_csv(path, mode="a", header=not os.path.exists(path), index=False)


def get_data(ticker):
    data = yf.download(ticker, period="2y", interval="1d", auto_adjust=False, progress=False)
    return extract_close(data, ticker)


def session_date(close):
    stamp = close.index[-1]
    if hasattr(stamp, "date"):
        return stamp.date().isoformat()
    return str(stamp)[:10]


def portfolio_value(state, prices):
    value = float(state["cash"])
    for ticker, pos in state["positions"].items():
        value += float(pos["shares"]) * float(prices[ticker])
    return value


def previous_paper_value():
    if not os.path.exists(PERFORMANCE_FILE):
        return STARTING_CASH
    try:
        df = pd.read_csv(PERFORMANCE_FILE)
        return STARTING_CASH if len(df) == 0 else float(df.iloc[-1]["paper_value"])
    except Exception:
        return STARTING_CASH


def main():
    os.makedirs("paper", exist_ok=True)
    state = load_state()
    series = {}
    dates = {}
    now = datetime.now(MARKET_TIMEZONE)
    today = now.date()
    completed_through = today if now.time() >= time(16) else today - timedelta(days=1)

    for ticker in TICKERS:
        try:
            close = get_data(ticker)
            close = completed_history(
                close, minimum=REGIME_MA_DAYS, today=today,
                completed_through=completed_through, max_age_days=MAX_PRICE_AGE_DAYS,
                weekdays_only=True,
            )
        except Exception as exc:
            print("Stock data unavailable for", ticker, ":", exc)
            print("Skipping entire simulated session.")
            return
        series[ticker] = close
        dates[ticker] = session_date(close)

    if len(series) != len(TICKERS):
        print("Incomplete ticker coverage; no simulated session processed.")
        return

    # All tracked stocks should agree on the latest completed U.S. market session.
    unique_dates = set(dates.values())
    if len(unique_dates) != 1:
        print("Market-session mismatch:", dates)
        print("Skipping this run rather than mixing prices from different sessions.")
        return
    trading_date = next(iter(unique_dates))
    if any(ticker not in series for ticker in state["positions"]):
        print("Skipping session: cannot price every held simulated stock.")
        return
    if state.get("last_run_date") and trading_date < state["last_run_date"]:
        print("Skipping market session older than the last processed session.")
        return

    # Guard on the actual market session, not the workflow's wall-clock date.
    # Also protect against legacy rows that were labeled with a workflow date.
    processed_dates = set()
    if os.path.exists(PERFORMANCE_FILE):
        try:
            perf = pd.read_csv(PERFORMANCE_FILE)
            processed_dates = set(perf.get("date_utc", pd.Series(dtype=str)).astype(str))
        except Exception:
            processed_dates = set()
    if state.get("last_run_date") == trading_date or trading_date in processed_dates:
        if state.get("last_run_date") != trading_date:
            state["last_run_date"] = trading_date
            save_state(state)
            print("Normalized legacy state to already-recorded market session", trading_date)
        else:
            print("Paper trader already processed market session", trading_date)
        return

    market = {}
    signals = []
    for ticker, close in series.items():
        price = float(close.iloc[-1])
        fast = float(close.iloc[-FAST_MA:].mean())
        slow = float(close.iloc[-SLOW_MA:].mean())
        regime = float(close.iloc[-REGIME_MA_DAYS:].mean())
        market[ticker] = price
        bullish = price > regime and fast > slow
        signals.append({
            "date_utc": trading_date, "ticker": ticker, "close": round(price, 4),
            "ma20": round(fast, 4), "ma50": round(slow, 4), "ma200": round(regime, 4),
            "signal": "BULLISH" if bullish else "DEFENSIVE",
        })

    pd.DataFrame(signals).to_csv(SIGNALS_FILE, index=False)
    journal = []

    for row in signals:
        ticker = row["ticker"]
        if ticker in state["positions"] and row["signal"] == "DEFENSIVE":
            pos = state["positions"].pop(ticker)
            proceeds = float(pos["shares"]) * market[ticker]
            state["cash"] += proceeds
            journal.append({"date_utc": trading_date, "ticker": ticker, "action": "SIM_SELL",
                            "price": market[ticker], "shares": pos["shares"], "reason": "defensive_signal"})

    current_value = portfolio_value(state, market)
    for row in signals:
        ticker = row["ticker"]
        if row["signal"] != "BULLISH" or ticker in state["positions"]:
            continue
        amount = min(float(state["cash"]), current_value * MAX_WEIGHT)
        if amount < 50:
            continue
        shares = amount / market[ticker]
        state["cash"] -= amount
        state["positions"][ticker] = {"shares": shares, "entry_price": market[ticker], "entry_date": trading_date}
        journal.append({"date_utc": trading_date, "ticker": ticker, "action": "SIM_BUY",
                        "price": market[ticker], "shares": shares, "reason": "bullish_signal"})

    ending_value = portfolio_value(state, market)
    previous_value = previous_paper_value()
    daily_pnl = ending_value - previous_value
    daily_return = (ending_value / previous_value - 1) * 100 if previous_value else 0.0
    total_return = (ending_value / STARTING_CASH - 1) * 100

    state["last_run_date"] = trading_date
    save_state(state)
    append_csv(JOURNAL_FILE, journal)
    append_csv(PERFORMANCE_FILE, [{
        "date_utc": trading_date, "paper_value": round(ending_value, 2),
        "cash": round(float(state["cash"]), 2), "open_positions": len(state["positions"]),
        "daily_pnl": round(daily_pnl, 2), "daily_return_pct": round(daily_return, 4),
        "total_return_pct": round(total_return, 4),
    }])

    print("LIVE-DATA PAPER TRADER — SIMULATION ONLY")
    print("Latest completed market session:", trading_date)
    print("Ending paper value: $", round(ending_value, 2))
    print("Daily simulated P/L: $", round(daily_pnl, 2))
    print("Total paper return:", round(total_return, 2), "%")
    print("Cash: $", round(float(state["cash"]), 2))
    print("Open simulated positions:", list(state["positions"].keys()))
    print("New simulated actions:", len(journal))
    print("No brokerage orders were sent.")


if __name__ == "__main__":
    main()
