import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

from market_data import completed_history, extract_close
from paper_risk import Limits, snapshot, buy_budget, record_risk

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
MAX_PRICE_AGE_DAYS = 4  # Legacy additional bound; scheduled inputs also use the session contract.

# Safety: simulation only. No brokerage connection or order submission exists.
# Legacy CSVs keep the column name "date_utc", but new rows store the actual
# latest market-session date returned by the price data. New signal snapshots
# also name this source date explicitly as price_session for monitoring.


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
    if os.environ.get("MARKET_DATA_MANIFEST"):
        from data_contracts.ingestion import accepted_close
        return accepted_close(ticker, os.environ["MARKET_DATA_MANIFEST"])
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
    """Forward-only v2; legacy records are read-only and require reviewed recovery."""
    from simulation_v2.runner import run
    return run('stock')


if __name__ == "__main__":
    main()
