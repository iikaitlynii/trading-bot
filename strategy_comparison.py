"""Read-only comparison of three research signals; never places trades.
Run: python strategy_comparison.py
Uses historical prices, shifted signals to avoid same-day lookahead, and
reports rough buy/hold, trend, and momentum comparisons before fees.
Not a realistic execution backtest; results are exploratory only.
"""
import pandas as pd
import yfinance as yf

STOCKS = ["AAPL", "MSFT", "NVDA", "AMZN"]
MEMECOINS = ["DOGE-USD", "SHIB-USD", "PEPE-USD", "BONK-USD"]


def close_history(ticker):
    frame = yf.download(ticker, period="2y", interval="1d", auto_adjust=True, progress=False)
    if frame.empty:
        return pd.Series(dtype=float)
    close = frame["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    return close.dropna().astype(float)


def evaluate(close, regime_days):
    if len(close) < max(200, regime_days) + 30:
        return None
    # Restrict all comparisons to the same recent window.
    close = close.iloc[-180:]
    daily = close.pct_change().fillna(0)
    fast = close.rolling(20, min_periods=20).mean()
    slow = close.rolling(50, min_periods=50).mean()
    regime = close.rolling(regime_days, min_periods=regime_days).mean()
    # Long-only research signals, held in cash otherwise.
    # Build indicators on full history below to avoid missing warmup.
    return daily


def compare(ticker, regime_days):
    close = close_history(ticker)
    if len(close) < 230:
        return None
    fast = close.rolling(20).mean()
    slow = close.rolling(50).mean()
    regime = close.rolling(regime_days).mean()
    trend = ((close > regime) & (fast > slow)).astype(float).shift(1).fillna(0)
    momentum = (close.pct_change(20) > 0).astype(float).shift(1).fillna(0)
    buyhold = pd.Series(1.0, index=close.index)
    returns = close.pct_change().fillna(0)
    window = returns.index[-120:]
    out = {"asset": ticker, "sessions": len(window)}
    for name, exposure in [("buy_hold", buyhold), ("trend", trend), ("momentum", momentum)]:
        strategy_returns = returns.loc[window] * exposure.loc[window]
        out[name + "_return_pct"] = round(((1 + strategy_returns).prod() - 1) * 100, 2)
        out[name + "_invested_days"] = int(exposure.loc[window].sum())
    return out


def main():
    results = []
    for ticker in STOCKS + MEMECOINS:
        try:
            row = compare(ticker, 100 if ticker in MEMECOINS else 200)
            if row is not None:
                results.append(row)
        except Exception as exc:
            print(f"{ticker}: data unavailable ({type(exc).__name__})")
    if not results:
        print("No comparable historical data available.")
        return
    output = pd.DataFrame(results)
    print("EXPLORATORY SIGNAL COMPARISON — NO FEES, SLIPPAGE OR EXECUTION")
    print(output.to_string(index=False))
    output.to_csv("strategy_comparison_results.csv", index=False)
    print("Saved strategy_comparison_results.csv (local research output).")


if __name__ == "__main__":
    main()
