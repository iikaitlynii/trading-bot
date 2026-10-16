import json
import os
import math
import pandas as pd

STATE_FILE = "paper/state.json"
PERFORMANCE_FILE = "paper/performance.csv"
JOURNAL_FILE = "paper/journal.csv"
SIGNALS_FILE = "paper/latest_signals.csv"
REPORT_FILE = "paper/report.txt"
STARTING_CASH = 10000.0


def safe_read_csv(path):
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def load_state():
    if not os.path.exists(STATE_FILE):
        return None
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def build_report():
    state = load_state()
    perf = safe_read_csv(PERFORMANCE_FILE)
    journal = safe_read_csv(JOURNAL_FILE)
    signals = safe_read_csv(SIGNALS_FILE)

    lines = []
    lines.append("LIVE PAPER TRADING HEALTH REPORT")
    lines.append("Simulation only — no brokerage orders are sent.")
    lines.append("")

    issues = []
    if state is None:
        issues.append("state.json is missing")
    if perf.empty:
        issues.append("performance history has not started yet")
    if signals.empty:
        issues.append("latest signal file is missing or empty")

    if state is not None:
        cash = float(state.get("cash", 0.0))
        positions = state.get("positions", {})
        if cash < -0.01:
            issues.append("paper cash is negative")
        if not isinstance(positions, dict):
            issues.append("positions field is invalid")
        lines.append(f"Last processed date: {state.get('last_run_date')}")
        lines.append(f"Cash: ${cash:,.2f}")
        lines.append(f"Open positions: {len(positions) if isinstance(positions, dict) else 0}")

    if not perf.empty:
        latest = perf.iloc[-1]
        current = float(latest["paper_value"])
        total_return = float(latest["total_return_pct"])
        peak = float(perf["paper_value"].max())
        drawdown = (peak - current) / peak * 100 if peak > 0 else 0.0
        max_dd = 0.0
        running_peak = None
        for value in perf["paper_value"].astype(float):
            running_peak = value if running_peak is None else max(running_peak, value)
            dd = (running_peak - value) / running_peak * 100 if running_peak > 0 else 0.0
            max_dd = max(max_dd, dd)
        total_profit = current - STARTING_CASH
        lines.append(f"Paper account value: ${current:,.2f}")
        lines.append(f"TOTAL SIMULATED PROFIT / LOSS: ${total_profit:+,.2f}")
        lines.append(f"Starting paper capital: ${STARTING_CASH:,.2f}")
        lines.append(f"Total return since launch: {total_return:.2f}%")
        lines.append(f"Current drawdown from paper peak: {drawdown:.2f}%")
        lines.append(f"Maximum forward-test drawdown: {max_dd:.2f}%")
        lines.append(f"Forward-test days collected: {len(perf)}")

    if not journal.empty:
        realized = 0.0
        lots = {}
        for _, trade in journal.iterrows():
            try:
                ticker = str(trade["ticker"])
                action = str(trade["action"])
                price = float(trade["price"])
                shares = float(trade["shares"])
                if not (math.isfinite(price) and math.isfinite(shares) and price > 0 and shares > 0):
                    raise ValueError("invalid journal trade")
                if action == "SIM_BUY":
                    lots.setdefault(ticker, []).append([shares, price])
                elif action == "SIM_SELL":
                    remaining = shares
                    for lot in lots.get(ticker, []):
                        used = min(remaining, lot[0])
                        realized += used * (price - lot[1])
                        lot[0] -= used
                        remaining -= used
                        if remaining < 1e-8:
                            break
                    if remaining > 1e-6:
                        issues.append(f"sell quantity exceeds recorded buys: {ticker}")
            except (KeyError, ValueError, TypeError):
                issues.append("invalid journal entry")
        lines.append(f"Realized simulated trade P/L (before fees): ${realized:+,.2f}")
        if not perf.empty:
            lines.append(f"Unrealized/other paper P/L (estimated): ${total_profit - realized:+,.2f}")
        buys = int((journal["action"] == "SIM_BUY").sum()) if "action" in journal else 0
        sells = int((journal["action"] == "SIM_SELL").sum()) if "action" in journal else 0
        lines.append(f"Journal actions: {len(journal)} ({buys} buys, {sells} sells)")
    else:
        lines.append("Journal actions: 0")

    if not signals.empty and "signal" in signals:
        bullish = int((signals["signal"] == "BULLISH").sum())
        defensive = int((signals["signal"] == "DEFENSIVE").sum())
        lines.append(f"Latest signals: {bullish} bullish, {defensive} defensive")

    lines.append("")
    lines.append("HEALTH CHECK")
    if issues:
        lines.append("STATUS: ATTENTION")
        for issue in issues:
            lines.append(f"- {issue}")
    else:
        lines.append("STATUS: OK")
        lines.append("State, performance, journal/signals structure, and paper cash checks passed.")

    lines.append("")
    lines.append("READINESS")
    days = len(perf)
    if days == 0:
        lines.append("Forward testing has not started yet.")
    elif days < 20:
        lines.append("Early forward test: not enough live paper history to judge the strategy.")
    elif days < 60:
        lines.append("Developing forward test: useful evidence is accumulating, but more market conditions are needed.")
    else:
        lines.append("Meaningful forward history is accumulating; performance still needs risk and consistency review before any next-stage decision.")

    return "\n".join(lines) + "\n"


def main():
    os.makedirs("paper", exist_ok=True)
    report = build_report()
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)


if __name__ == "__main__":
    main()
