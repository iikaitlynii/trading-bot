"""Read-only historical signal research; no exchange or brokerage actions."""
import os
import pandas as pd
import yfinance as yf

STOCKS = ["AAPL", "MSFT", "NVDA", "AMZN"]
MEMECOINS = ["DOGE-USD", "SHIB-USD", "PEPE-USD", "BONK-USD"]
FEE_BPS = 10  # hypothetical fee per position change
SLIPPAGE_BPS = 10  # hypothetical adverse fill per position change
WINDOW = 120


def history(ticker):
    raw = yf.download(ticker, period="2y", interval="1d", auto_adjust=True, progress=False)
    if raw.empty:
        raise ValueError("empty price history")
    close = raw["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    return close.dropna().astype(float)


def calculate(ticker, close):
    if len(close) < 230:
        raise ValueError(f"insufficient history: {len(close)} rows (need 230)")
    fast, slow = close.rolling(20).mean(), close.rolling(50).mean()
    regime = close.rolling(100 if ticker in MEMECOINS else 200).mean()
    signals = {
        "buy_hold": pd.Series(1.0, index=close.index),
        "trend": ((close > regime) & (fast > slow)).astype(float).shift(1).fillna(0),
        "momentum": (close.pct_change(20) > 0).astype(float).shift(1).fillna(0),
    }
    daily = close.pct_change().fillna(0)
    idx = close.index[-WINDOW:]
    result = {"asset": ticker, "sessions": len(idx), "as_of": str(idx[-1].date())}
    for name, exposure in signals.items():
        held = exposure.loc[idx]
        # Opening position on the first session counts as one entry.
        turnover = held.diff().abs().fillna(held.iloc[0])
        costs = turnover * (FEE_BPS + SLIPPAGE_BPS) / 10000
        net_daily = daily.loc[idx] * held - costs
        equity = (1 + net_daily).cumprod()
        drawdown = equity / equity.cummax().clip(lower=1) - 1
        result[name + "_return_pct"] = round((equity.iloc[-1] - 1) * 100, 2)
        result[name + "_max_drawdown_pct"] = round(drawdown.min() * 100, 2)
        result[name + "_invested_days"] = int(held.sum())
        result[name + "_position_changes"] = int(turnover.sum())
    return result


def main():
    results, errors = [], []
    for ticker in STOCKS + MEMECOINS:
        try:
            results.append(calculate(ticker, history(ticker)))
        except Exception as exc:
            errors.append({"asset": ticker, "reason": str(exc)})
            print(f"{ticker}: {exc}")
    if not results:
        raise RuntimeError("No historical comparisons available")
    pd.DataFrame(results).to_csv("strategy_comparison_results.csv", index=False)
    pd.DataFrame(errors, columns=["asset", "reason"]).to_csv("strategy_comparison_missing.csv", index=False)
    print("Research only: hypothetical 10 bps fee + 10 bps slippage per entry/exit.")
    print(pd.DataFrame(results).to_string(index=False))


if __name__ == "__main__":
    main()
