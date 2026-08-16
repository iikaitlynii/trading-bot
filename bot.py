import os
import sys
import yfinance as yf

TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN"]
STARTING_MONEY = 10000
COMMISSION = 0.001
SLIPPAGE = 0.001
TRAIN_DAYS = 500
TEST_DAYS = 125
WARMUP_DAYS = 60
RESULTS_DIR = "results"
RESULTS_FILE = os.path.join(RESULTS_DIR, "latest_results.txt")

# Soft risk filter: weak training evidence gets a smaller simulated allocation.
# This is backtesting only; it does not place real trades.
MIN_TRAINING_TRADES = 3
MAX_TRAINING_DRAWDOWN = 30.0

CANDIDATES = [
    {"name": "MA 5/20", "type": "ma", "fast": 5, "slow": 20, "stop_loss": 0.02},
    {"name": "MA 10/30", "type": "ma", "fast": 10, "slow": 30, "stop_loss": 0.03},
    {"name": "MA 20/50", "type": "ma", "fast": 20, "slow": 50, "stop_loss": 0.04},
    {"name": "Momentum 10d 3%", "type": "momentum", "lookback": 10, "threshold": 0.03, "stop_loss": 0.02},
    {"name": "Momentum 20d 5%", "type": "momentum", "lookback": 20, "threshold": 0.05, "stop_loss": 0.03},
    {"name": "Momentum 30d 7%", "type": "momentum", "lookback": 30, "threshold": 0.07, "stop_loss": 0.04},
]

class Tee:
    def __init__(self, *streams): self.streams = streams
    def write(self, text):
        for stream in self.streams:
            stream.write(text); stream.flush()
    def flush(self):
        for stream in self.streams: stream.flush()

def empty_result():
    return {"return":0.0,"drawdown":0.0,"trades":0,"win_rate":0.0,"profit_factor":0.0}

def run_strategy(prices, config, score_start=0, allocation=1.0):
    prices = prices.dropna()
    if len(prices) < 60: return None
    allocation = max(0.0, min(1.0, allocation))
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
    for i in range(first_index, len(prices)):
        price = float(prices.iloc[i])
        if config["type"] == "ma":
            buy_signal = float(fast_ma.iloc[i]) > float(slow_ma.iloc[i])
            sell_signal = float(fast_ma.iloc[i]) < float(slow_ma.iloc[i])
        else:
            m = float(momentum.iloc[i])
            buy_signal = m > config["threshold"]
            sell_signal = m < 0
        if buy_signal and not in_position and allocation > 0:
            buy_price = price * (1 + SLIPPAGE)
            amount_to_invest = cash * allocation
            reserved_cash = cash - amount_to_invest
            invest_after_fee = amount_to_invest * (1 - COMMISSION)
            shares = invest_after_fee / buy_price
            cash = reserved_cash
            entry_price = buy_price
            in_position = True
        elif in_position and (price <= entry_price * (1-config["stop_loss"]) or sell_signal):
            sell_price = price * (1-SLIPPAGE)
            trades.append(((sell_price-entry_price)/entry_price)*100)
            cash += shares * sell_price * (1-COMMISSION)
            shares = 0.0; entry_price = 0.0; in_position = False
        account_values.append(cash + shares*price if in_position else cash)
    if not account_values: return None
    final_value = account_values[-1]
    total_return = ((final_value-STARTING_MONEY)/STARTING_MONEY)*100
    peak = account_values[0]; max_drawdown = 0.0
    for value in account_values:
        peak = max(peak,value)
        if peak > 0: max_drawdown=max(max_drawdown,((peak-value)/peak)*100)
    wins=[t for t in trades if t>0]; losses=[t for t in trades if t<0]
    total_wins=sum(wins); total_losses=abs(sum(losses))
    pf=total_wins/total_losses if total_losses>0 else (float("inf") if total_wins>0 else 0.0)
    return {"return":total_return,"drawdown":max_drawdown,"trades":len(trades),"win_rate":len(wins)/len(trades)*100 if trades else 0.0,"profit_factor":pf}

def training_score(result):
    if result is None: return float("-inf")
    return result["return"] - 0.50*result["drawdown"]

def choose_best_strategy(training_data):
    ranked=[]
    for config in CANDIDATES:
        result=run_strategy(training_data,config)
        if result is None or result["trades"] < MIN_TRAINING_TRADES or result["drawdown"] > MAX_TRAINING_DRAWDOWN:
            continue
        ranked.append((training_score(result),config,result))
    if not ranked: return None,None,0.0,0.0
    ranked.sort(key=lambda x:x[0],reverse=True)
    score,config,result=ranked[0]
    # Convert training quality into a conservative simulated allocation.
    # Bad/non-positive score = cash; modest = 25%; good = 50%; strong = 75%.
    if score <= 0 or result["return"] <= 0: allocation=0.0
    elif score < 10: allocation=0.25
    elif score < 25: allocation=0.50
    else: allocation=0.75
    return config,result,score,allocation

def walk_forward_optimize(close):
    results=[]; start=0
    while True:
        train_end=start+TRAIN_DAYS; test_start=train_end; test_end=test_start+TEST_DAYS
        if test_end>len(close): break
        config,train_result,score,allocation=choose_best_strategy(close.iloc[start:train_end])
        first=float(close.iloc[test_start]); last=float(close.iloc[test_end-1])
        buy_hold=((last-first)/first)*100
        if config is None or allocation==0:
            test_result=empty_result(); strategy="CASH"
        else:
            warmup_start=max(0,test_start-WARMUP_DAYS)
            test_result=run_strategy(close.iloc[warmup_start:test_end],config,test_start-warmup_start,allocation)
            strategy=config["name"]
        results.append({"period":len(results)+1,"strategy":strategy,"allocation":allocation,"training_return":train_result["return"] if train_result else 0.0,"training_drawdown":train_result["drawdown"] if train_result else 0.0,"training_score":score,"test_return":test_result["return"],"test_drawdown":test_result["drawdown"],"test_trades":test_result["trades"],"buy_hold":buy_hold})
        start += TEST_DAYS
    return results

def summarize(results):
    if not results:return None
    n=len(results)
    return {"periods":n,"avg_return":sum(r["test_return"] for r in results)/n,"avg_drawdown":sum(r["test_drawdown"] for r in results)/n,"avg_buy_hold":sum(r["buy_hold"] for r in results)/n,"positive":sum(r["test_return"]>0 for r in results)/n*100,"beat_hold":sum(r["test_return"]>r["buy_hold"] for r in results)/n*100,"avg_allocation":sum(r["allocation"] for r in results)/n*100,"cash":sum(r["allocation"]==0 for r in results)/n*100}

def run_all_tests():
    print("VERSION 3: SOFT RISK-BASED POSITION SIZING")
    print("Allocations: 0%, 25%, 50%, or 75% based only on training quality")
    for ticker in TICKERS:
        print("\n======================================\nPOSITION-SIZED WALK-FORWARD:",ticker,"\n======================================")
        data=yf.download(ticker,period="10y",interval="1d",auto_adjust=False,progress=False)
        close=data["Close"]
        if hasattr(close,"columns"): close=close.iloc[:,0]
        close=close.dropna(); results=walk_forward_optimize(close)
        for r in results:
            print("\nTEST PERIOD:",r["period"])
            print("Chosen:",r["strategy"],"| Simulated allocation:",round(r["allocation"]*100),"%")
            print("Training return:",round(r["training_return"],2),"% | score:",round(r["training_score"],2))
            print("UNSEEN return:",round(r["test_return"],2),"% | Buy & Hold:",round(r["buy_hold"],2),"%")
            print("UNSEEN drawdown:",round(r["test_drawdown"],2),"% | trades:",r["test_trades"])
        s=summarize(results)
        if s:
            print("\n========== VERSION 3 SUMMARY ==========")
            print("Test periods:",s["periods"])
            print("Average unseen return:",round(s["avg_return"],2),"%")
            print("Average Buy & Hold return:",round(s["avg_buy_hold"],2),"%")
            print("Average unseen drawdown:",round(s["avg_drawdown"],2),"%")
            print("Positive unseen periods:",round(s["positive"],2),"%")
            print("Beat Buy & Hold:",round(s["beat_hold"],2),"%")
            print("Average simulated allocation:",round(s["avg_allocation"],2),"%")
            print("Cash periods:",round(s["cash"],2),"%")

def main():
    os.makedirs(RESULTS_DIR,exist_ok=True)
    original=sys.stdout
    with open(RESULTS_FILE,"w",encoding="utf-8") as f:
        sys.stdout=Tee(original,f)
        try:
            print("Trading Bot Automated Research Results")
            print("Saved to:",RESULTS_FILE)
            run_all_tests()
        finally: sys.stdout=original
    print("\nResults saved successfully to:",RESULTS_FILE)

if __name__=="__main__": main()
