import bot

SCENARIOS = [
    {
        "name": "BASELINE",
        "commission": 0.001,
        "slippage": 0.001,
        "tickers": ["AAPL", "MSFT", "NVDA", "AMZN"],
    },
    {
        "name": "2X TRADING FRICTION",
        "commission": 0.002,
        "slippage": 0.002,
        "tickers": ["AAPL", "MSFT", "NVDA", "AMZN"],
    },
    {
        "name": "3X TRADING FRICTION",
        "commission": 0.003,
        "slippage": 0.003,
        "tickers": ["AAPL", "MSFT", "NVDA", "AMZN"],
    },
    {
        "name": "DIFFERENT LARGE-CAP STOCKS",
        "commission": 0.001,
        "slippage": 0.001,
        "tickers": ["GOOGL", "META", "JPM", "XOM"],
    },
    {
        "name": "MIXED-SECTOR STOCKS",
        "commission": 0.001,
        "slippage": 0.001,
        "tickers": ["KO", "WMT", "CAT", "JNJ"],
    },
]


def run_scenario(scenario):
    bot.COMMISSION = scenario["commission"]
    bot.SLIPPAGE = scenario["slippage"]
    bot.TICKERS = scenario["tickers"]
    prices = bot.load_prices()
    result = bot.run_portfolio(prices)
    days = result["windows"] * bot.TEST_DAYS
    benchmark = bot.equal_weight_hold(prices, bot.TRAIN_DAYS, days)
    return {
        "name": scenario["name"],
        "tickers": ", ".join(scenario["tickers"]),
        "final": result["final"],
        "return": result["total"],
        "cagr": result["cagr"],
        "drawdown": result["mdd"],
        "sharpe": result["sharpe"],
        "trades": result["trades"],
        "benchmark": benchmark,
        "benchmark_return": (benchmark / bot.STARTING_MONEY - 1) * 100,
    }


def main():
    print("VERSION 9: ROBUSTNESS STRESS TESTS")
    print("No strategy parameters are optimized in this file. The Version 8 rules are challenged under changed costs and different stock groups.")
    print()
    results = []
    for scenario in SCENARIOS:
        print("Running:", scenario["name"])
        results.append(run_scenario(scenario))

    print("\n========== VERSION 9 STRESS-TEST SCOREBOARD ==========")
    for r in results:
        print("\nSCENARIO:", r["name"])
        print("Stocks:", r["tickers"])
        print("Bot ending simulated account: $", round(r["final"], 2))
        print("Bot compounded return:", round(r["return"], 2), "%")
        print("Bot estimated CAGR:", round(r["cagr"], 2), "%")
        print("Bot max drawdown:", round(r["drawdown"], 2), "%")
        print("Bot Sharpe:", round(r["sharpe"], 2))
        print("Completed trades:", r["trades"])
        print("Equal-weight Buy & Hold ending value: $", round(r["benchmark"], 2))
        print("Equal-weight Buy & Hold return:", round(r["benchmark_return"], 2), "%")

    profitable = sum(r["return"] > 0 for r in results)
    positive_sharpe = sum(r["sharpe"] > 0 for r in results)
    print("\n========== ROBUSTNESS CHECK ==========")
    print("Profitable scenarios:", profitable, "of", len(results))
    print("Positive-Sharpe scenarios:", positive_sharpe, "of", len(results))
    print("This is a robustness screen, not evidence or a guarantee of future profit.")


if __name__ == "__main__":
    main()
