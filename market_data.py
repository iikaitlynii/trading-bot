"""Fail-closed validation of daily closing prices for simulated trading."""
from datetime import timedelta

import numpy as np
import pandas as pd


def extract_close(data, ticker):
    """Select the requested symbol, never an arbitrary first download column."""
    if isinstance(data.columns, pd.MultiIndex):
        close = data[("Close", ticker)]
    else:
        close = data["Close"]
    if not isinstance(close, pd.Series):
        raise ValueError("ambiguous closing-price columns")
    # Do not drop bad rows: that can silently substitute an older price.
    return close


def completed_history(close, *, minimum, today, completed_through, max_age_days,
                      daily=False, weekdays_only=False):
    """Validate session labels and prices, then exclude an unfinished daily bar.

    Daily index dates are provider session labels, not instants to convert into
    another timezone. Freshness is a calendar-day bound, not an exchange calendar.
    """
    if not isinstance(close, pd.Series) or not isinstance(close.index, pd.DatetimeIndex):
        raise ValueError("expected a daily Series with a DatetimeIndex")
    dates = close.index.normalize()
    if dates.hasnans or not dates.is_unique or not dates.is_monotonic_increasing:
        raise ValueError("missing, duplicate, or unordered session labels")
    labels = pd.Index([stamp.date() for stamp in dates])
    if any(label > today for label in labels):
        raise ValueError("future market session")
    close = close.loc[labels <= completed_through]
    if len(close) < minimum:
        raise ValueError("insufficient completed history")
    session_dates = [stamp.date() for stamp in close.index]
    if weekdays_only and any(day.weekday() > 4 for day in session_dates):
        raise ValueError("stock price labeled with a weekend session")
    if daily and any(right - left != timedelta(days=1)
                     for left, right in zip(session_dates, session_dates[1:])):
        raise ValueError("missing daily crypto session")
    if not pd.api.types.is_numeric_dtype(close.dtype) or pd.api.types.is_bool_dtype(close.dtype):
        raise ValueError("nonnumeric closing prices")
    if pd.api.types.is_complex_dtype(close.dtype):
        raise ValueError("complex closing prices")
    values = close.to_numpy(dtype=float, na_value=np.nan)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("closing prices must be finite and positive")
    if close.index[-1].date() < today - timedelta(days=max_age_days):
        raise ValueError("stale closing prices")
    return close
