import yfinance as yf

# ==========================================
# SETTINGS
# ==========================================

TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN"]

STARTING_MONEY = 10000

COMMISSION = 0.001
SLIPPAGE = 0.001
STOP_LOSS = 0.03

STRATEGIES = [
    "10/30",
    "20/50",
    "Momentum"
]

# Walk-forward settings
TRAIN_DAYS = 500
TEST_DAYS = 125


# ==========================================
# STRATEGY BACKTEST
# ==========================================

def run_strategy(prices, strategy):

    cash = STARTING_MONEY
    shares = 0
    entry_price = 0
    in_position = False

    account_values = []
    trades = []

    ma10 = prices.rolling(10).mean()
    ma20 = prices.rolling(20).mean()
    ma30 = prices.rolling(30).mean()
    ma50 = prices.rolling(50).mean()

    momentum = prices.pct_change(20)

    for i in range(50, len(prices)):

        price = float(prices.iloc[i])

        # ----------------------------------
        # SIGNALS
        # ----------------------------------

        if strategy == "10/30":

            buy_signal = (
                float(ma10.iloc[i])
                > float(ma30.iloc[i])
            )

            sell_signal = (
                float(ma10.iloc[i])
                < float(ma30.iloc[i])
            )

        elif strategy == "20/50":

            buy_signal = (
                float(ma20.iloc[i])
                > float(ma50.iloc[i])
            )

            sell_signal = (
                float(ma20.iloc[i])
                < float(ma50.iloc[i])
            )

        elif strategy == "Momentum":

            current_momentum = float(
                momentum.iloc[i]
            )

            buy_signal = current_momentum > 0.05
            sell_signal = current_momentum < 0

        else:
            continue

        # ----------------------------------
        # BUY
        # ----------------------------------

        if buy_signal and not in_position:

            buy_price = price * (1 + SLIPPAGE)

            commission_cost = cash * COMMISSION
            available_cash = cash - commission_cost

            shares = available_cash / buy_price
            cash = 0

            entry_price = buy_price
            in_position = True

        # ----------------------------------
        # STOP LOSS
        # ----------------------------------

        elif (
            in_position
            and price <= entry_price * (1 - STOP_LOSS)
        ):

            sell_price = price * (1 - SLIPPAGE)

            trade_return = (
                (sell_price - entry_price)
                / entry_price
            ) * 100

            trades.append(trade_return)

            cash = shares * sell_price

            commission_cost = cash * COMMISSION
            cash = cash - commission_cost

            shares = 0
            entry_price = 0
            in_position = False

        # ----------------------------------
        # NORMAL SELL
        # ----------------------------------

        elif sell_signal and in_position:

            sell_price = price * (1 - SLIPPAGE)

            trade_return = (
                (sell_price - entry_price)
                / entry_price
            ) * 100

            trades.append(trade_return)

            cash = shares * sell_price

            commission_cost = cash * COMMISSION
            cash = cash - commission_cost

            shares = 0
            entry_price = 0
            in_position = False

        # ----------------------------------
        # ACCOUNT VALUE
        # ----------------------------------

        if in_position:
            account_value = shares * price
        else:
            account_value = cash

        account_values.append(account_value)

    if not account_values:
        return None

    final_value = account_values[-1]

    total_return = (
        (final_value - STARTING_MONEY)
        / STARTING_MONEY
    ) * 100

    # ----------------------------------
    # MAX DRAWDOWN
    # ----------------------------------

    peak = account_values[0]
    max_drawdown = 0

    for value in account_values:

        if value > peak:
            peak = value

        drawdown = (
            (peak - value)
            / peak
        ) * 100

        if drawdown > max_drawdown:
            max_drawdown = drawdown

    # ----------------------------------
    # TRADE STATS
    # ----------------------------------

    wins = [
        trade
        for trade in trades
        if trade > 0
    ]

    losses = [
        trade
        for trade in trades
        if trade < 0
    ]

    if trades:
        win_rate = (
            len(wins)
            / len(trades)
        ) * 100
    else:
        win_rate = 0

    if wins:
        average_win = (
            sum(wins)
            / len(wins)
        )
    else:
        average_win = 0

    if losses:
        average_loss = (
            sum(losses)
            / len(losses)
        )
    else:
        average_loss = 0

    total_wins = sum(wins)
    total_losses = abs(sum(losses))

    if total_losses > 0:
        profit_factor = (
            total_wins
            / total_losses
        )
    else:
        profit_factor = 0

    return {
        "return": total_return,
        "drawdown": max_drawdown,
        "trades": len(trades),
        "win_rate": win_rate,
        "average_win": average_win,
        "average_loss": average_loss,
        "profit_factor": profit_factor
    }


# ==========================================
# WALK-FORWARD TEST
# ==========================================

def walk_forward_test(close, strategy):

    results = []

    start = 0

    while True:

        train_start = start
        train_end = train_start + TRAIN_DAYS

        test_start = train_end
        test_end = test_start + TEST_DAYS

        if test_end > len(close):
            break

        training_data = close.iloc[
            train_start:train_end
        ]

        testing_data = close.iloc[
            test_start - 50:test_end
        ]

        result = run_strategy(
            testing_data,
            strategy
        )

        if result is not None:

            first_test_price = float(
                close.iloc[test_start]
            )

            last_test_price = float(
                close.iloc[test_end - 1]
            )

            buy_hold_return = (
                (last_test_price - first_test_price)
                / first_test_price
            ) * 100

            result["buy_hold"] = buy_hold_return
            result["period"] = len(results) + 1

            results.append(result)

        start += TEST_DAYS

    return results


# ==========================================
# SUMMARY FUNCTION
# ==========================================

def summarize_results(results):

    if not results:
        return None

    returns = [
        result["return"]
        for result in results
    ]

    drawdowns = [
        result["drawdown"]
        for result in results
    ]

    buy_hold_returns = [
        result["buy_hold"]
        for result in results
    ]

    winning_periods = [
        value
        for value in returns
        if value > 0
    ]

    beat_buy_hold = 0

    for result in results:

        if (
            result["return"]
            > result["buy_hold"]
        ):
            beat_buy_hold += 1

    average_return = (
        sum(returns)
        / len(returns)
    )

    average_drawdown = (
        sum(drawdowns)
        / len(drawdowns)
    )

    average_buy_hold = (
        sum(buy_hold_returns)
        / len(buy_hold_returns)
    )

    positive_rate = (
        len(winning_periods)
        / len(results)
    ) * 100

    beat_buy_hold_rate = (
        beat_buy_hold
        / len(results)
    ) * 100

    return {
        "periods": len(results),
        "avg_return": average_return,
        "avg_drawdown": average_drawdown,
        "avg_buy_hold": average_buy_hold,
        "positive_rate": positive_rate,
        "beat_buy_hold_rate": beat_buy_hold_rate
    }


# ==========================================
# RUN TESTS
# ==========================================

for ticker in TICKERS:

    print()
    print("======================================")
    print("STOCK:", ticker)
    print("======================================")

    data = yf.download(
        ticker,
        period="10y",
        interval="1d",
        auto_adjust=False,
        progress=False
    )

    close = data["Close"]

    if hasattr(close, "columns"):
        close = close.iloc[:, 0]

    close = close.dropna()

    for strategy in STRATEGIES:

        print()
        print("--------------------------------------")
        print("STRATEGY:", strategy)
        print("--------------------------------------")

        results = walk_forward_test(
            close,
            strategy
        )

        # Show every test window
        for result in results:

            print()
            print(
                "Test Period",
                result["period"]
            )

            print(
                "Strategy Return:",
                round(result["return"], 2),
                "%"
            )

            print(
                "Buy & Hold:",
                round(result["buy_hold"], 2),
                "%"
            )

            print(
                "Drawdown:",
                round(result["drawdown"], 2),
                "%"
            )

            print(
                "Trades:",
                result["trades"]
            )

            print(
                "Win Rate:",
                round(result["win_rate"], 2),
                "%"
            )

            print(
                "Profit Factor:",
                round(result["profit_factor"], 2)
            )

        summary = summarize_results(
            results
        )

        if summary is not None:

            print()
            print("========== SUMMARY ==========")

            print(
                "Test periods:",
                summary["periods"]
            )

            print(
                "Average strategy return:",
                round(summary["avg_return"], 2),
                "%"
            )

            print(
                "Average Buy & Hold return:",
                round(summary["avg_buy_hold"], 2),
                "%"
            )

            print(
                "Average drawdown:",
                round(summary["avg_drawdown"], 2),
                "%"
            )

            print(
                "Positive test periods:",
                round(summary["positive_rate"], 2),
                "%"
            )

            print(
                "Beat Buy & Hold:",
                round(
                    summary["beat_buy_hold_rate"],
                    2
                ),
                "%"
            )