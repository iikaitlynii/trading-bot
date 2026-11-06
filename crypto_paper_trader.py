import json
import os
import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

from market_data import completed_history, extract_close
from paper_risk import Limits, snapshot, buy_budget, record_risk

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
RUN_TIMEZONE = ZoneInfo("America/Chicago")

# Simulation only. This program never connects to a crypto exchange
# and never places real orders.
#
# Existing CSV files use the legacy column name "date_utc". For compatibility,
# new rows store the completed UTC source-session date. Historical labels
# remain unchanged and require independent reconciliation.


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
    if os.environ.get("MARKET_DATA_MANIFEST"):
        from data_contracts.ingestion import accepted_close
        return accepted_close(ticker, os.environ["MARKET_DATA_MANIFEST"])
    data = yf.download(ticker, period="1y", interval="1d", auto_adjust=False, progress=False)
    return extract_close(data, ticker)


def portfolio_value(state, prices):
    value = float(state["cash"])
    for ticker, pos in state["positions"].items():
        value += float(pos["units"]) * float(prices[ticker])
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
    """Forward-only v2; legacy records are read-only and require reviewed recovery."""
    from simulation_v2.runner import run
    return run('crypto')


if __name__ == "__main__":
    main()
