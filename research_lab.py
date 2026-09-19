import csv
import math
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

OUT_DIR = "research_lab"
LATEST_FILE = os.path.join(OUT_DIR, "latest_shadow_results.csv")
HISTORY_FILE = os.path.join(OUT_DIR, "shadow_history.csv")
REPORT_FILE = os.path.join(OUT_DIR, "report.txt")
STARTING = 10000.0
COMMISSION = 0.001
SLIPPAGE = 0.001
RUN_TZ = ZoneInfo("America/Chicago")

# Research only. These are independent historical simulations, not brokerage orders.
UNIVERSES = {
    "core4": ["AAPL", "MSFT", "NVDA", "AMZN"],
    "diversified16": [
        "AAPL", "MSFT", "NVDA", "AMZN",
        "GOOGL", "META", "JPM", "XOM",
        "WMT", "KO", "JNJ", "UNH",
        "CAT", "HD", "PG", "CVX",
    ],
}

VARIANTS = [
    {"name": "current_20_50", "fast": 20, "slow": 50, "regime": 200, "stop": 0.04, "max_weight": 0.20},
    {"name": "faster_10_30", "fast": 10, "slow": 30, "regime": 150, "stop": 0.03, "max_weight": 0.15},
    {"name": "conservative_30_75", "fast": 30, "slow": 75, "regime": 200, "stop": 0.05, "max_weight": 0.15},
    {"name": "low_concentration_20_50", "fast": 20, "slow": 50, "regime": 200, "stop": 0.04, "max_weight": 0.10},
]


def download(universe):
    frames = []
    for ticker in universe:
        data = yf.download(ticker, period="10y", interval="1d", auto_adjust=False, progress=False)
        close = data["Close"]
        if hasattr(close, "columns"):
            close = close.iloc[:, 0]
        frames.append(close.rename(ticker))
    return pd.concat(frames, axis=1).dropna()


def max_drawdown(values):
    peak = values[0]
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        worst = max(worst, (peak - value) / peak if peak else 0.0)
    return worst * 100


def run_variant(prices, cfg):
    warmup = max(cfg["regime"], cfg["slow"])
    cash = STARTING
    positions = {}
    entries = {}
    equity = [STARTING]
    wins = losses = trades = 0
    gross_wins = gross_losses = 0.0
    hold_days = []

    for i in range(warmup, len(prices)):
        row = prices.iloc[i]
        account = cash + sum(positions[t] * float(row[t]) for t in positions)

        # Exits first.
        for ticker in list(positions):
            p = float(row[ticker])
            series = prices[ticker]
            fast = float(series.iloc[i-cfg["fast"]+1:i+1].mean())
            slow = float(series.iloc[i-cfg["slow"]+1:i+1].mean())
            regime = float(series.iloc[i-cfg["regime"]+1:i+1].mean())
            entry = entries[ticker]
            if fast < slow or p < regime or p <= entry["price"] * (1 - cfg["stop"]):
                proceeds = positions[ticker] * p * (1 - SLIPPAGE) * (1 - COMMISSION)
                pnl = proceeds - entry["cost"]
                cash += proceeds
                trades += 1
                hold_days.append(i - entry["index"])
                if pnl > 0:
                    wins += 1
                    gross_wins += pnl
                else:
                    losses += 1
                    gross_losses += abs(pnl)
                del positions[ticker]
                del entries[ticker]

        account = cash + sum(positions[t] * float(row[t]) for t in positions)
        slots = max(0, int(1 / cfg["max_weight"]) - len(positions))

        # Entries are equal-risk capped; no leverage.
        if slots:
            candidates = []
            for ticker in prices.columns:
                if ticker in positions:
                    continue
                series = prices[ticker]
                p = float(row[ticker])
                fast = float(series.iloc[i-cfg["fast"]+1:i+1].mean())
                slow = float(series.iloc[i-cfg["slow"]+1:i+1].mean())
                regime = float(series.iloc[i-cfg["regime"]+1:i+1].mean())
                if p > regime and fast > slow:
                    momentum = p / float(series.iloc[max(0, i-63)]) - 1
                    candidates.append((momentum, ticker))
            for _, ticker in sorted(candidates, reverse=True)[:slots]:
                target = min(cash, account * cfg["max_weight"])
                if target < 50:
                    break
                p = float(row[ticker])
                buy_price = p * (1 + SLIPPAGE)
                shares = (target * (1 - COMMISSION)) / buy_price
                cash -= target
                positions[ticker] = shares
                entries[ticker] = {"price": buy_price, "cost": target, "index": i}

        equity.append(cash + sum(positions[t] * float(row[t]) for t in positions))

    final = equity[-1]
    total_return = (final / STARTING - 1) * 100
    years = max((len(equity) - 1) / 252, 1 / 252)
    cagr = ((final / STARTING) ** (1 / years) - 1) * 100 if final > 0 else -100.0
    daily = pd.Series(equity).pct_change().dropna()
    sharpe = float(daily.mean() / daily.std() * math.sqrt(252)) if len(daily) > 1 and daily.std() else 0.0
    win_rate = wins / trades * 100 if trades else 0.0
    profit_factor = gross_wins / gross_losses if gross_losses else (999.0 if gross_wins else 0.0)
    avg_hold = sum(hold_days) / len(hold_days) if hold_days else 0.0

    # Buy-and-hold benchmark over the same post-warmup period.
    start = prices.iloc[warmup]
    end = prices.iloc[-1]
    benchmark_return = sum(float(end[t] / start[t] - 1) for t in prices.columns) / len(prices.columns) * 100

    return {
        "ending_value": round(final, 2),
        "return_pct": round(total_return, 4),
        "cagr_pct": round(cagr, 4),
        "max_drawdown_pct": round(max_drawdown(equity), 4),
        "sharpe": round(sharpe, 4),
        "completed_trades": trades,
        "win_rate_pct": round(win_rate, 4),
        "profit_factor": round(profit_factor, 4),
        "avg_hold_days": round(avg_hold, 2),
        "benchmark_return_pct": round(benchmark_return, 4),
        "excess_vs_benchmark_pct": round(total_return - benchmark_return, 4),
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    run_date = datetime.now(RUN_TZ).date().isoformat()
    rows = []

    for universe_name, tickers in UNIVERSES.items():
        print("Downloading", universe_name, "...")
        prices = download(tickers)
        for cfg in VARIANTS:
            print("Testing", universe_name, cfg["name"])
            result = run_variant(prices, cfg)
            rows.append({"run_date": run_date, "universe": universe_name, "variant": cfg["name"], **result})

    df = pd.DataFrame(rows)
    df.to_csv(LATEST_FILE, index=False)

    history_exists = os.path.exists(HISTORY_FILE)
    df.to_csv(HISTORY_FILE, mode="a", header=not history_exists, index=False)

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("PARALLEL SHADOW STRATEGY RESEARCH LAB\n")
        f.write("Simulation/research only — no brokerage orders are sent.\n\n")
        f.write("Run date: " + run_date + "\n")
        f.write("Variants tested: " + str(len(VARIANTS)) + "\n")
        f.write("Universes tested: " + str(len(UNIVERSES)) + "\n")
        f.write("This lab compares fixed strategy variants and benchmarks.\n")
        f.write("Do not select a winner from one run; use repeated out-of-sample evidence.\n\n")
        f.write(df.to_string(index=False))
        f.write("\n")

    print(df.to_string(index=False))
    print("\nSaved:", LATEST_FILE, HISTORY_FILE, REPORT_FILE)


if __name__ == "__main__":
    main()
