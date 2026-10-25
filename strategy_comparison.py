"""Read-only historical signal research; no exchange or brokerage actions."""
import numbers
import numpy as np
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
    if isinstance(raw.columns, pd.MultiIndex):
        # yfinance supports both (field, ticker) and (ticker, field) layouts.
        keys = [key for key in (("Close", ticker), (ticker, "Close")) if key in raw.columns]
        if len(keys) != 1:
            raise ValueError(f"missing or ambiguous Close column for {ticker}")
        close = raw[keys[0]]
    else:
        close = raw["Close"]
    if not isinstance(close, pd.Series):
        raise ValueError("ambiguous closing-price columns")
    # Preserve invalid rows so calculate rejects incomplete history.
    return close.copy()


def validate_close(close):
    """Reject corrupt observations rather than filling/dropping them into signals."""
    if not isinstance(close, pd.Series):
        raise ValueError("closing prices must be a Series")
    if not isinstance(close.index, pd.DatetimeIndex) or close.index.hasnans:
        raise ValueError("closing prices require valid datetime labels")
    if not close.index.is_monotonic_increasing or not close.index.is_unique:
        raise ValueError("closing dates must be increasing and unique")
    if not close.index.normalize().is_unique:
        raise ValueError("closing prices require one observation per daily session")
    if len(close) < 230:
        raise ValueError(f"insufficient history: {len(close)} rows (need 230)")
    if not all(isinstance(value, numbers.Real) and not isinstance(value, (bool, np.bool_))
               for value in close):
        raise ValueError("closing prices must be real numeric values")
    close = close.astype(float)
    if not np.isfinite(close.to_numpy()).all() or (close <= 0).any():
        raise ValueError("closing prices must be finite and positive")
    return close


def calculate(ticker, close):
    """Illustrative close-to-close returns with additive turnover costs.

    Signals from close t-1 determine exposure to return t. This assumes a fill
    at that prior close; it is not a next-open executable backtest. Capital is
    initialized at the close preceding the evaluation window, entry costs apply
    once, and ending holdings are marked to market without forced liquidation.
    """
    close = validate_close(close)
    fast, slow = close.rolling(20).mean(), close.rolling(50).mean()
    regime = close.rolling(100 if ticker in MEMECOINS else 200).mean()
    signals = {
        "cash": pd.Series(0.0, index=close.index),
        "buy_hold": pd.Series(1.0, index=close.index),
        "trend": ((close > regime) & (fast > slow)).astype(float).shift(1).fillna(0),
        "momentum": (close.pct_change(20) > 0).astype(float).shift(1).fillna(0),
    }
    daily = close.pct_change(fill_method=None).fillna(0)
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
