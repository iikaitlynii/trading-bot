import os
import sys
import yfinance as yf

# ==========================================
# SETTINGS
# ==========================================

TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN"]
STARTING_MONEY = 10000
COMMISSION = 0.001
SLIPPAGE = 0.001

TRAIN_DAYS = 500
TEST_DAYS = 125
WARMUP_DAYS = 60

RESULTS_DIR = "results"
RESULTS_FILE = os.path.join(RESULTS_DIR, "latest_results.txt")

# Each candidate has a strategy plus parameters to test on training data.
CANDIDATES = [
    {"name": "MA 5/20", "type": "ma", "fast": 5, "slow": 20, "stop_loss": 0.02},
    {"name": "MA 10/30", "type": "ma", "fast": 10, "slow": 30, "stop_loss": 0.03},
    {"name": "MA 20/50", "type": "ma", "fast": 20, "slow": 50, "stop_loss": 0.04},
    {"name": "Momentum 10d 3%", "type": "momentum", "lookback": 10, "threshold": 0.03, "stop_loss": 0.02},
    {"name": "Momentum 20d 5%", "type": "momentum", "lookback": 20, "threshold": 0.05, "stop_loss": 0.03},
    {"name": "Momentum 30d 7%", "type": "momentum", "lookback": 30, "threshold": 0.07, "stop_loss": 0.04},
]


class Tee:
    """Write output to Terminal and a file at the same time."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for stream in self.streams:
            stream.write(text)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()


def run_strategy(prices, config, score_start=0):
    """Backtest one strategy configuration.

    score_start lets us include warm-up history for indicators without counting
    that warm-up period in the reported performance.
    """
    prices = prices.dropna()
    if len(prices) < 60:
        return None

    cash = STARTING_MONEY
    shares = 0.0
    entry_price = 0.0
    in_position = False
    trades = []
    account_values = []

    if config["type"] == "ma":
        fast_ma = prices.rolling(config["fast"]).mean()
        slow_ma = prices.rolling(config["slow"]).mean()
        first_index = max(config["slow"], score_start)
    else:
        momentum = prices.pct_change(config["lookback"])
        first_index = max(config["lookback"], score_start)

    # Start trading only when the scored period begins. This prevents the bot
    # from opening a position during the warm-up data before an unseen test.
    for i in range(first_index, len(prices)):
        price = float(prices.iloc[i])

        if config["type"] == "ma":
            buy_signal = float(fast_ma.iloc[i]) > float(slow_ma.iloc[i])
            sell_signal = float(fast_ma.iloc[i]) < float(slow_ma.iloc[i])
        else:
            current_momentum = float(momentum.iloc[i])
            buy_signal = current_momentum > config["threshold"]
            sell_signal = current_momentum < 0

        if buy_signal and not in_position:
            buy_price = price * (1 + SLIPPAGE)
            available_cash = cash * (1 - COMMISSION)
            shares = available_cash / buy_price
            cash = 0.0
            entry_price = buy_price
            in_position = True

        elif in_position and price <= entry_price * (1 - config["stop_loss"]):
            sell_price = price * (1 - SLIPPAGE)
            trade_return = ((sell_price - entry_price) / entry_price) * 100
            trades.append(trade_return)
            cash = shares * sell_price * (1 - COMMISSION)
            shares = 0.0
            entry_price = 0.0
            in_position = False

        elif sell_signal and in_position:
            sell_price = price * (1 - SLIPPAGE)
            trade_return = ((sell_price - entry_price) / entry_price) * 100
            trades.append(trade_return)
            cash = shares * sell_price * (1 - COMMISSION)
            shares = 0.0
            entry_price = 0.0
            in_position = False

        account_value = shares * price if in_position else cash
        account_values.append(account_value)

    if not account_values:
        return None

    final_value = account_values[-1]
    total_return = ((final_value - STARTING_MONEY) / STARTING_MONEY) * 100

    peak = account_values[0]
    max_drawdown = 0.0
    for value in account_values:
        peak = max(peak, value)
        if peak > 0:
            max_drawdown = max(max_drawdown, ((peak - value) / peak) * 100)

    wins = [trade for trade in trades if trade > 0]
    losses = [trade for trade in trades if trade < 0]
    win_rate = (len(wins) / len(trades) * 100) if trades else 0.0
    average_win = sum(wins) / len(wins) if wins else 0.0
    average_loss = sum(losses) / len(losses) if losses else 0.0
    total_wins = sum(wins)
    total_losses = abs(sum(losses))
    profit_factor = total_wins / total_losses if total_losses > 0 else (float("inf") if total_wins > 0 else 0.0)

    return {
        "return": total_return,
        "drawdown": max_drawdown,
        "trades": len(trades),
        "win_rate": win_rate,
        "average_win": average_win,
        "average_loss": average_loss,
        "profit_factor": profit_factor,
    }


def training_score(result):
    """Rank candidates using return with a drawdown penalty."""
    if result is None:
        return float("-inf")
    return result["return"] - 0.50 * result["drawdown"]


def choose_best_strategy(training_data):
    best_config = None
    best_result = None
    best_score = float("-inf")

    for config in CANDIDATES:
        result = run_strategy(training_data, config)
        score = training_score(result)
        if score > best_score:
            best_score = score
            best_config = config
            best_result = result

    return best_config, best_result, best_score


def walk_forward_optimize(close):
    results = []
    start = 0

    while True:
        train_start = start
        train_end = train_start + TRAIN_DAYS
        test_start = train_end
        test_end = test_start + TEST_DAYS

        if test_end > len(close):
            break

        training_data = close.iloc[train_start:train_end]
        best_config, training_result, best_score = choose_best_strategy(training_data)

        if best_config is None:
            start += TEST_DAYS
            continue

        warmup_start = max(0, test_start - WARMUP_DAYS)
        testing_with_warmup = close.iloc[warmup_start:test_end]
        score_start = test_start - warmup_start
        test_result = run_strategy(testing_with_warmup, best_config, score_start=score_start)

        if test_result is not None:
            first_test_price = float(close.iloc[test_start])
            last_test_price = float(close.iloc[test_end - 1])
            buy_hold_return = ((last_test_price - first_test_price) / first_test_price) * 100

            results.append({
                "period": len(results) + 1,
                "strategy": best_config["name"],
                "training_return": training_result["return"],
                "training_drawdown": training_result["drawdown"],
                "training_score": best_score,
                "test_return": test_result["return"],
                "test_drawdown": test_result["drawdown"],
                "test_trades": test_result["trades"],
                "test_win_rate": test_result["win_rate"],
                "test_profit_factor": test_result["profit_factor"],
                "buy_hold": buy_hold_return,
            })

        start += TEST_DAYS

    return results


def summarize_results(results):
    if not results:
        return None

    returns = [r["test_return"] for r in results]
    drawdowns = [r["test_drawdown"] for r in results]
    buy_hold = [r["buy_hold"] for r in results]
    positive = sum(1 for value in returns if value > 0)
    beat_hold = sum(1 for r in results if r["test_return"] > r["buy_hold"])

    strategy_counts = {}
    for r in results:
        strategy_counts[r["strategy"]] = strategy_counts.get(r["strategy"], 0) + 1

    return {
        "periods": len(results),
        "avg_return": sum(returns) / len(returns),
        "avg_drawdown": sum(drawdowns) / len(drawdowns),
        "avg_buy_hold": sum(buy_hold) / len(buy_hold),
        "positive_rate": positive / len(results) * 100,
        "beat_buy_hold_rate": beat_hold / len(results) * 100,
        "strategy_counts": strategy_counts,
    }


def print_profit_factor(value):
    return "inf" if value == float("inf") else str(round(value, 2))


def run_all_tests():
    for ticker in TICKERS:
        print("\n======================================")
        print("TRUE WALK-FORWARD OPTIMIZATION:", ticker)
        print("======================================")

        data = yf.download(
            ticker,
            period="10y",
            interval="1d",
            auto_adjust=False,
            progress=False,
        )

        close = data["Close"]
        if hasattr(close, "columns"):
            close = close.iloc[:, 0]
        close = close.dropna()

        results = walk_forward_optimize(close)

        for result in results:
            print("\n--------------------------------------")
            print("TEST PERIOD:", result["period"])
            print("Chosen from training:", result["strategy"])
            print("Training return:", round(result["training_return"], 2), "%")
            print("Training drawdown:", round(result["training_drawdown"], 2), "%")
            print("Training score:", round(result["training_score"], 2))
            print("UNSEEN test return:", round(result["test_return"], 2), "%")
            print("Buy & Hold:", round(result["buy_hold"], 2), "%")
            print("Test drawdown:", round(result["test_drawdown"], 2), "%")
            print("Test trades:", result["test_trades"])
            print("Test win rate:", round(result["test_win_rate"], 2), "%")
            print("Test profit factor:", print_profit_factor(result["test_profit_factor"]))

        summary = summarize_results(results)
        if summary is not None:
            print("\n========== WALK-FORWARD SUMMARY ==========")
            print("Test periods:", summary["periods"])
            print("Average unseen return:", round(summary["avg_return"], 2), "%")
            print("Average Buy & Hold return:", round(summary["avg_buy_hold"], 2), "%")
            print("Average unseen drawdown:", round(summary["avg_drawdown"], 2), "%")
            print("Positive unseen periods:", round(summary["positive_rate"], 2), "%")
            print("Beat Buy & Hold:", round(summary["beat_buy_hold_rate"], 2), "%")
            print("Strategies selected:")
            for name, count in summary["strategy_counts"].items():
                print("  ", name, "->", count, "period(s)")


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    original_stdout = sys.stdout
    with open(RESULTS_FILE, "w", encoding="utf-8") as result_file:
        sys.stdout = Tee(original_stdout, result_file)
        try:
            print("Trading Bot Walk-Forward Results")
            print("Saved to:", RESULTS_FILE)
            run_all_tests()
        finally:
            sys.stdout = original_stdout

    print("\nResults saved successfully to:", RESULTS_FILE)
    print("To upload the results to GitHub, run:")
    print("git add results/latest_results.txt")
    print('git commit -m "Save latest backtest results"')
    print("git push")


if __name__ == "__main__":
    main()
