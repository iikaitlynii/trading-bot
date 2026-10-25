"""Shared long-only simulated-account controls. No execution integrations."""
import math
import os
from dataclasses import dataclass


def number(value, name):
    if isinstance(value, (bool, str)):
        raise ValueError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return result


@dataclass(frozen=True)
class Limits:
    position: float
    exposure: float
    drawdown_warning: float

    def __post_init__(self):
        for name in ("position", "exposure", "drawdown_warning"):
            if number(getattr(self, name), name) > 1:
                raise ValueError(f"{name} must be between zero and one")

    @classmethod
    def from_env(cls, prefix, position, exposure):
        values = []
        for suffix, default in (("MAX_POSITION_WEIGHT", position),
                                ("MAX_EXPOSURE", exposure),
                                ("DRAWDOWN_WARNING", 0.10)):
            raw = os.environ.get(f"{prefix}_{suffix}")
            values.append(default if raw is None else float(raw))
        return cls(*values)


def snapshot(state, prices, quantity):
    cash = number(state["cash"], "cash")
    holdings = {}
    for ticker, position in state["positions"].items():
        price = number(prices[ticker], "price")
        if price == 0:
            raise ValueError("price must be positive")
        holdings[ticker] = number(position[quantity], quantity) * price
    invested = number(sum(holdings.values()), "invested value")
    equity = number(cash + invested, "equity")
    return equity, invested, {t: v / equity if equity else 0.0 for t, v in holdings.items()}


def buy_budget(equity, cash, invested, limits):
    for value in (equity, cash, invested):
        number(value, "budget input")
    return max(0.0, min(cash, equity * limits.position,
                        equity * limits.exposure - invested))


def record_risk(state, prices, quantity, limits, starting_cash):
    equity, invested, weights = snapshot(state, prices, quantity)
    peak = max(number(state.get("peak_equity", starting_cash), "peak equity"), equity)
    drawdown = (peak - equity) / peak if peak else 0.0
    state["peak_equity"] = peak
    state["risk"] = {"equity": equity, "invested": invested,
                     "exposure": invested / equity if equity else 0.0,
                     "weights": weights, "drawdown": drawdown,
                     "drawdown_warning": drawdown >= limits.drawdown_warning,
                     "limit_breach": any(w > limits.position for w in weights.values())
                                     or invested > equity * limits.exposure}
    if state["risk"]["drawdown_warning"]:
        print(f"SIMULATED DRAWDOWN WARNING: {drawdown:.2%} from peak {peak:.2f}")
    if state["risk"]["limit_breach"]:
        print("SIMULATED EXPOSURE WARNING: existing holdings exceed configured entry limits")
