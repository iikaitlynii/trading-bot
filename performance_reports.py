"""Read-only simulated forward-paper reporting; no market requests or engine imports."""
import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ACCOUNTS = {"stocks": ("paper", 10000.0, "shares", ("AAPL", "MSFT", "NVDA", "AMZN")),
            "crypto": ("crypto_paper", 5000.0, "units", ("BTC-USD",))}


def numeric(value, positive=False):
    number = float(value)
    if not math.isfinite(number) or (positive and number <= 0):
        raise ValueError("invalid number")
    return number


def day(value):
    return date.fromisoformat(value).isoformat()


def read_csv(path, warnings, required=()):
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or not set(required).issubset(reader.fieldnames):
                raise ValueError("missing required columns")
            return list(reader)
    except (OSError, ValueError, csv.Error) as exc:
        warnings.append(f"Unavailable {path.name}: {type(exc).__name__}")
        return None


def valuations(records, warnings, today):
    valid = []
    for row in records or []:
        try:
            d = day(row["date_utc"])
            if d > today:
                raise ValueError("future valuation")
            valid.append({"date_utc": d, "paper_value": numeric(row["paper_value"], True),
                          "cash": numeric(row["cash"])})
        except (KeyError, TypeError, ValueError):
            warnings.append("Invalid/future valuation excluded")
    dates = [r["date_utc"] for r in valid]
    if dates != sorted(dates):
        warnings.append("Valuations were out of chronological order; sorted for reporting")
    duplicates = {d for d, count in Counter(dates).items() if count > 1}
    if duplicates:
        warnings.append("Ambiguous duplicate valuation dates excluded: " + ", ".join(sorted(duplicates)))
    return sorted((r for r in valid if r["date_utc"] not in duplicates), key=lambda r: r["date_utc"])


def trade_breakdown(journal, quantity_key, end, initial, warnings):
    lots = defaultdict(list)
    realized, cash, wins, losses = 0.0, initial, 0, 0
    if journal is None:
        return None
    previous = ""
    try:
        for row in journal:
            d = day(row["date_utc"])
            if d < previous or d > end:
                raise ValueError("journal order or as-of mismatch")
            previous = d
            ticker, action = row["ticker"], row["action"]
            price, qty = numeric(row["price"], True), numeric(row[quantity_key], True)
            if not ticker or action not in ("SIM_BUY", "SIM_SELL"):
                raise ValueError("unknown action/symbol")
            if action == "SIM_BUY":
                lots[ticker].append([qty, price])
                cash -= qty * price
            else:
                remaining, pnl = qty, 0.0
                for lot in lots[ticker]:
                    used = min(remaining, lot[0])
                    pnl += used * (price - lot[1])
                    lot[0] -= used
                    remaining -= used
                if remaining > 1e-6:
                    raise ValueError("unmatched sell")
                realized += pnl
                cash += qty * price
                wins += pnl > 1e-8
                losses += pnl < -1e-8
    except (KeyError, TypeError, ValueError):
        warnings.append("Journal invalid, out of order, ahead of valuation, or sells exceed buys; trade P/L unavailable")
        return None
    return {"realized": realized, "cash": cash, "lots": lots, "wins": wins, "losses": losses}


def benchmark(prices, symbols, start, end, warnings):
    """Exact endpoint raw closes only; no interpolation or monthly ETF substitution."""
    endpoints = defaultdict(list)
    try:
        for row in prices or []:
            if row.get("ticker") in symbols and row.get("date") in (start, end):
                endpoints[(row["ticker"], row["date"])].append(numeric(row["close"], True))
        returns = []
        for symbol in symbols:
            a, b = endpoints[(symbol, start)], endpoints[(symbol, end)]
            if len(a) != 1 or len(b) != 1:
                raise ValueError("missing/duplicate endpoints")
            returns.append(b[0] / a[0] - 1)
        return 100 * sum(returns) / len(returns)
    except (KeyError, ValueError, TypeError):
        warnings.append("Buy-and-hold unavailable: missing, invalid, or duplicate exact-date benchmark prices")
        return None


def build_account(root, account, today=None):
    today = today or datetime.now(timezone.utc).date().isoformat()
    folder, initial, quantity, symbols = ACCOUNTS[account]
    base, warnings = root / folder, []
    rows = valuations(read_csv(base / "performance.csv", warnings, ("date_utc", "paper_value", "cash")), warnings, today)
    journal = read_csv(base / "journal.csv", warnings, ("date_utc", "ticker", "action", "price", quantity))
    source = "research/stock_history.csv" if account == "stocks" else "research/crypto_history.csv"
    prices = read_csv(root / source, warnings, ("date", "ticker", "close"))
    report = {"schema_version": 1, "account": account, "classification": "simulated forward paper records",
              "generated_at_utc": datetime.now(timezone.utc).isoformat(), "starting_capital": initial,
              "warnings": warnings, "metrics": {}, "monthly": [], "daily": rows,
              "benchmark": {"symbols": list(symbols), "source": source,
                            "provenance": "Yahoo public daily chart endpoint via saved repository collector" if account == "stocks" else "Optional saved daily close snapshot; verify provenance before supplying",
                            "basis": "Equal-weight initial allocation, raw close price return, no rebalancing/dividends/fees; exact recorded endpoints",
                            "return_pct": None}}
    warnings.append("Recorded equity/close prices are not independently verified marks; fees, dividends and external cash flows are not recorded")
    if not rows:
        warnings.append("No unambiguous valid valuations; performance unavailable")
        return report
    first, last = rows[0], rows[-1]
    if any(row["cash"] < -.02 or row["cash"] > row["paper_value"] + .02 for row in rows):
        warnings.append("Recorded cash is negative or exceeds portfolio equity")
    if account == "stocks" and any(date.fromisoformat(row["date_utc"]).weekday() >= 5 for row in rows):
        warnings.append("Stock valuations include weekend dates; legacy session labels need review")
    gap_limit = 1 if account == "crypto" else 4
    if any((date.fromisoformat(b["date_utc"]) - date.fromisoformat(a["date_utc"])).days > gap_limit for a, b in zip(rows, rows[1:])):
        warnings.append("Gaps between recorded valuations; monthly changes cover observations, not verified complete sessions")
    report.update(start_date=first["date_utc"], as_of=last["date_utc"])
    if (date.fromisoformat(today) - date.fromisoformat(last["date_utc"])).days > 3:
        warnings.append("Latest valuation is more than 3 calendar days old (calendar check, not an exchange-session check)")
    peak, max_dd = initial, 0.0
    for row in rows:
        peak = max(peak, row["paper_value"])
        max_dd = max(max_dd, 100 * (peak - row["paper_value"]) / peak)
    change = last["paper_value"] - initial
    metrics = {"portfolio_value": last["paper_value"], "total_portfolio_change": change,
               "total_return_pct": 100 * change / initial, "cash_return_pct": 0.0,
               "excess_vs_cash_pct": 100 * change / initial, "cash_value": initial,
               "max_drawdown_pct": max_dd, "observations": len(rows),
               "realized_pnl": None, "unrealized_pnl": None, "unreconciled_change": None,
               "winning_sells": None, "losing_sells": None}
    report["metrics"] = metrics
    trades = trade_breakdown(journal, quantity, last["date_utc"], initial, warnings)
    if trades:
        metrics.update(realized_pnl=trades["realized"], winning_sells=trades["wins"], losing_sells=trades["losses"])
        try:
            state = json.loads((base / "state.json").read_text())
            if state["last_run_date"] != last["date_utc"]:
                raise ValueError("state date differs")
            if abs(numeric(state["cash"]) - last["cash"]) > .02 or abs(trades["cash"] - last["cash"]) > .02:
                raise ValueError("cash does not reconcile")
            positions = state["positions"]
            if not isinstance(positions, dict):
                raise ValueError("invalid positions")
            for symbol in set(positions) | set(trades["lots"]):
                held = sum(lot[0] for lot in trades["lots"][symbol])
                recorded = numeric(positions[symbol][quantity], True) if symbol in positions else 0
                if not math.isclose(held, recorded, rel_tol=1e-8, abs_tol=1e-6):
                    raise ValueError("positions do not reconcile")
            cost = sum(q * price for lots in trades["lots"].values() for q, price in lots)
            unrealized = last["paper_value"] - last["cash"] - cost
            residual = change - trades["realized"] - unrealized
            if abs(residual) > .02:
                raise ValueError("P/L does not reconcile")
            metrics.update(unrealized_pnl=unrealized, unreconciled_change=residual)
        except (OSError, KeyError, ValueError, TypeError):
            warnings.append("State, cash, quantities, or P/L do not reconcile at valuation date; unrealized P/L unavailable")
    if metrics["unrealized_pnl"] is None and trades:
        metrics["unreconciled_change"] = change - trades["realized"]
    bh = benchmark(prices, symbols, first["date_utc"], last["date_utc"], warnings)
    report["benchmark"]["return_pct"] = bh
    metrics["excess_vs_buy_hold_pct"] = None if bh is None else 100 * (last["paper_value"] / first["paper_value"] - 1) - bh
    metrics["comparison_return_pct"] = 100 * (last["paper_value"] / first["paper_value"] - 1)
    report["benchmark"]["ending_value"] = None if bh is None else first["paper_value"] * (1 + bh / 100)
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["date_utc"][:7]].append(row)
    previous = None
    for month, observations in sorted(grouped.items()):
        opening = previous["paper_value"] if previous else initial
        closing = observations[-1]
        report["monthly"].append({"month": month, "opening_date": previous["date_utc"] if previous else "launch capital",
                                  "as_of": closing["date_utc"], "opening_value": opening,
                                  "closing_value": closing["paper_value"], "portfolio_change": closing["paper_value"] - opening,
                                  "return_pct": 100 * (closing["paper_value"] / opening - 1),
                                  "observations": len(observations),
                                  "coverage": "partial launch month" if previous is None else "month to date" if month == today[:7] else "recorded observations only; calendar completeness unverified"})
        previous = closing
    return report


def generate(root, today=None):
    output = root / "reports"
    output.mkdir(exist_ok=True)
    for account in ACCOUNTS:
        report = build_account(root, account, today)
        (output / f"{account}.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        for kind in ("daily", "monthly"):
            records = report[kind]
            fields = list(records[0]) if records else (["date_utc", "paper_value", "cash"] if kind == "daily" else ["month", "portfolio_change", "return_pct"])
            with (output / f"{account}_{kind}.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields + ["classification", "data_quality_warnings"], lineterminator="\n")
                writer.writeheader()
                for row in records:
                    writer.writerow(dict(row, classification=report["classification"], data_quality_warnings="; ".join(report["warnings"])))
        with (output / f"{account}_summary.csv").open("w", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(["metric", "value", "classification"])
            for key, value in report["metrics"].items():
                writer.writerow([key, "" if value is None else value, report["classification"]])
            writer.writerow(["buy_hold_return_pct", report["benchmark"]["return_pct"], report["benchmark"]["basis"]])
            for warning in report["warnings"]:
                writer.writerow(["warning", warning, report["classification"]])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    generate(parser.parse_args().root)
